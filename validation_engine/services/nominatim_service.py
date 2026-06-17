import json
import time
from threading import Lock
from urllib import parse, request

from config import (
    CACHE_ENABLED,
    CACHE_NOMINATIM,
    NOMINATIM_BASE_URL,
    NOMINATIM_EMAIL,
    NOMINATIM_ENABLED,
    NOMINATIM_TIMEOUT_SECONDS,
    NOMINATIM_USER_AGENT
)
from services.cache_service import get_cache
from utils.helpers import coerce_float, normalize_text
from utils.logger import logger


_REQUEST_LOCK = Lock()
_LAST_REQUEST_AT = 0.0


def enrich_with_nominatim(record):

    default = {
        "nominatim_checked": False,
        "nominatim_reverse_match": None,
        "nominatim_search_match": None,
        "nominatim_confidence": 0.0,
        "nominatim_summary": "",
        "nearby_locality": None,
        "osm_match": record.get("osm_match", False)
    }

    if not NOMINATIM_ENABLED:
        default["nominatim_summary"] = "Nominatim disabled by configuration."
        return default

    lat = coerce_float(record.get("latitude"))
    lon = coerce_float(record.get("longitude"))
    if lat is None or lon is None:
        default["nominatim_summary"] = "Nominatim skipped because coordinates are missing."
        return default

    # Check cache first
    if CACHE_ENABLED and CACHE_NOMINATIM:
        cache = get_cache()
        cached_result = cache.get_nominatim(record)
        if cached_result is not None:
            return cached_result

    reverse_result = _reverse_lookup(lat, lon)
    search_result = _search_cemetery(record)

    reverse_match = _is_reverse_match(record, reverse_result)
    search_match = _is_search_match(record, search_result)
    confidence = _calculate_confidence(reverse_match, search_match)
    nearby_locality = _extract_locality(reverse_result)

    reasons = []
    if reverse_match:
        reasons.append("Reverse geocoding location matches record locality.")
    elif reverse_result:
        reasons.append("Reverse geocoding returned a nearby locality but it did not fully match the record.")

    if search_match:
        reasons.append("Nominatim search found a likely cemetery match.")
    elif search_result:
        reasons.append("Nominatim search returned a place but not a confident cemetery match.")

    if not reasons:
        reasons.append("No Nominatim match was confirmed.")

    result = {
        "nominatim_checked": True,
        "nominatim_reverse_match": reverse_match,
        "nominatim_search_match": search_match,
        "nominatim_confidence": confidence,
        "nominatim_summary": " ".join(reasons),
        "nearby_locality": nearby_locality,
        "osm_match": bool(record.get("osm_match")) or search_match
    }

    # Cache the result
    if CACHE_ENABLED and CACHE_NOMINATIM:
        cache = get_cache()
        cache.set_nominatim(record, result)

    return result


def _reverse_lookup(lat, lon):

    params = {
        "lat": lat,
        "lon": lon,
        "format": "jsonv2",
        "addressdetails": 1,
        "zoom": 14
    }
    return _get_json("/reverse", params)


def _search_cemetery(record):

    query_parts = [
        record.get("name"),
        record.get("city"),
        record.get("county"),
        record.get("state"),
        record.get("country") or "United States"
    ]
    query = ", ".join(str(part).strip() for part in query_parts if part not in (None, ""))
    if not query:
        return None

    params = {
        "q": query,
        "format": "jsonv2",
        "limit": 3,
        "addressdetails": 1,
        "countrycodes": "us"
    }
    results = _get_json("/search", params)
    if isinstance(results, list) and results:
        return results[0]
    return None


def _get_json(path, params):

    url = f"{NOMINATIM_BASE_URL}{path}?{parse.urlencode(_with_optional_email(params))}"
    req = request.Request(url, headers={"User-Agent": NOMINATIM_USER_AGENT})

    _rate_limit()
    try:
        with request.urlopen(req, timeout=NOMINATIM_TIMEOUT_SECONDS) as response:  # pragma: no cover - network path
            return json.loads(response.read().decode("utf-8"))
    except Exception as exc:  # pragma: no cover - network path
        logger.warning("Nominatim request failed for %s: %s", path, exc)
        return None


def _rate_limit():

    global _LAST_REQUEST_AT

    with _REQUEST_LOCK:
        elapsed = time.monotonic() - _LAST_REQUEST_AT
        if elapsed < 1.0:
            time.sleep(1.0 - elapsed)
        _LAST_REQUEST_AT = time.monotonic()


def _with_optional_email(params):

    payload = dict(params)
    if NOMINATIM_EMAIL:
        payload["email"] = NOMINATIM_EMAIL
    return payload


def _is_reverse_match(record, reverse_result):

    if not isinstance(reverse_result, dict):
        return False

    address = reverse_result.get("address", {})
    record_city = normalize_text(record.get("city", ""))
    record_county = normalize_text(record.get("county", ""))
    record_state = normalize_text(record.get("state", ""))

    reverse_city = normalize_text(
        address.get("city")
        or address.get("town")
        or address.get("village")
        or address.get("hamlet")
        or address.get("municipality")
        or ""
    )
    reverse_county = normalize_text(address.get("county", ""))
    reverse_state = normalize_text(address.get("state", ""))

    city_match = bool(record_city and reverse_city and record_city == reverse_city)
    county_match = bool(record_county and reverse_county and record_county == reverse_county)
    state_match = bool(record_state and reverse_state and record_state == reverse_state)

    return state_match and (city_match or county_match or not (record_city or record_county))


def _is_search_match(record, search_result):

    if not isinstance(search_result, dict):
        return False

    result_name = normalize_text(search_result.get("name") or search_result.get("display_name") or "")
    record_name = normalize_text(record.get("name", ""))
    if not record_name or not result_name:
        return False

    type_text = normalize_text(search_result.get("type", ""))
    category_text = normalize_text(search_result.get("category", ""))
    display_text = normalize_text(search_result.get("display_name", ""))

    cemetery_hint = any(
        keyword in " ".join([type_text, category_text, display_text])
        for keyword in ("cemetery", "grave_yard", "graveyard", "burial")
    )

    name_match = record_name in result_name or result_name in record_name
    return bool(cemetery_hint and name_match)


def _calculate_confidence(reverse_match, search_match):

    score = 0.0
    if reverse_match:
        score += 0.4
    if search_match:
        score += 0.6
    return round(score, 2)


def _extract_locality(reverse_result):

    if not isinstance(reverse_result, dict):
        return None

    address = reverse_result.get("address", {})
    locality = {
        "city": address.get("city") or address.get("town") or address.get("village") or address.get("hamlet"),
        "county": address.get("county"),
        "state": address.get("state"),
        "postcode": address.get("postcode"),
        "display_name": reverse_result.get("display_name")
    }

    cleaned = {key: value for key, value in locality.items() if value not in (None, "")}
    return cleaned or None
