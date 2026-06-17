import time
from threading import Lock
from typing import Any, Dict, List, Optional

import requests
from rapidfuzz.fuzz import token_sort_ratio

from config import (
    CACHE_ENABLED,
    CACHE_OVERPASS,
    OVERPASS_API_URL,
    OVERPASS_MAX_RETRIES,
    OVERPASS_RADIUS_METERS,
    OVERPASS_RATE_LIMIT_SECONDS,
    OVERPASS_TIMEOUT_SECONDS,
)
from services.cache_service import get_cache
from utils.helpers import coerce_float, haversine_km
from utils.logger import logger


TYPE_MAPPING = {
    "human": ["cemetery", "grave_yard"],
    "cemetery": ["cemetery", "grave_yard"],
    "burial_ground": ["cemetery", "grave_yard"],
}

OSM_CEMETERY_TYPES = {"cemetery", "grave_yard", "yes"}
NAME_MATCH_THRESHOLD = 70

_REQUEST_LOCK = Lock()
_LAST_REQUEST_AT = 0.0


def verify_with_overpass(record: Dict[str, Any], radius_meters: Optional[int] = None) -> Dict[str, Any]:
    """Verify a cemetery record against nearby OSM cemetery objects."""

    radius = radius_meters or OVERPASS_RADIUS_METERS
    lat = coerce_float(record.get("latitude"))
    lon = coerce_float(record.get("longitude"))
    if lat is None or lon is None:
        return _default_result(
            checked=False,
            reason="Overpass skipped because coordinates are missing or invalid.",
        )

    # Check cache first
    if CACHE_ENABLED and CACHE_OVERPASS:
        cache = get_cache()
        cached_result = cache.get_overpass(record)
        if cached_result is not None:
            return cached_result

    response = _fetch_overpass(lat, lon, radius)
    elements = response.get("elements", []) if isinstance(response, dict) else []
    if not elements:
        result = _default_result(
            checked=True,
            reason=f"No OSM cemetery object found within {radius} meters.",
        )
    else:
        candidates = [
            _build_candidate(record, element, lat, lon, radius)
            for element in elements
        ]
        candidates = [candidate for candidate in candidates if candidate["osm_type"] in OSM_CEMETERY_TYPES]
        if not candidates:
            result = _default_result(
                checked=True,
                reason="OSM objects were found, but none used a supported cemetery tag.",
            )
        else:
            best = _choose_best_candidate(candidates)
            best["candidate_count"] = len(candidates)
            best["multiple_nearby_candidates"] = len(candidates) > 1
            result = _build_verification_result(best, radius)

    # Cache the result
    if CACHE_ENABLED and CACHE_OVERPASS:
        cache = get_cache()
        cache.set_overpass(record, result)

    return result


def build_overpass_query(lat: float, lon: float, radius_meters: int) -> str:

    return f"""[out:json][timeout:25];
(
  nwr["amenity"="grave_yard"](around:{radius_meters},{lat},{lon});
  nwr["landuse"="cemetery"](around:{radius_meters},{lat},{lon});
  nwr["historic"="cemetery"](around:{radius_meters},{lat},{lon});
  nwr["cemetery"="yes"](around:{radius_meters},{lat},{lon});
);
out center;"""


def _fetch_overpass(lat: float, lon: float, radius_meters: int) -> Dict[str, Any]:

    query = build_overpass_query(lat, lon, radius_meters)
    session = requests.Session()

    for attempt in range(OVERPASS_MAX_RETRIES + 1):
        _respect_rate_limit()
        try:
            response = session.post(
                OVERPASS_API_URL,
                data={"data": query},
                timeout=OVERPASS_TIMEOUT_SECONDS,
                headers={"User-Agent": "validation-engine/1.0"},
            )
            if response.status_code == 429:
                _sleep_before_retry(attempt)
                continue
            response.raise_for_status()
            payload = response.json()
            return payload if isinstance(payload, dict) else {"elements": []}
        except (requests.Timeout, requests.ConnectionError) as exc:
            logger.warning("Overpass transient request failed: %s", exc)
            _sleep_before_retry(attempt)
        except (ValueError, requests.HTTPError) as exc:
            logger.warning("Overpass request returned unusable response: %s", exc)
            return {"elements": []}
        except Exception as exc:  # pragma: no cover - defensive pipeline safety
            logger.exception("Unexpected Overpass verification failure: %s", exc)
            return {"elements": []}

    return {"elements": []}


def _build_candidate(
    record: Dict[str, Any],
    element: Dict[str, Any],
    csv_lat: float,
    csv_lon: float,
    radius_meters: int,
) -> Dict[str, Any]:

    tags = element.get("tags") if isinstance(element.get("tags"), dict) else {}
    osm_lat, osm_lon = _extract_coordinates(element)
    osm_name = tags.get("name")
    osm_type = _extract_osm_type(tags)
    fuzzy_score = token_sort_ratio(str(record.get("name") or ""), osm_name or "") if osm_name else 0.0
    distance_meters = _distance_meters(csv_lat, csv_lon, osm_lat, osm_lon)
    location_match = distance_meters is not None and distance_meters <= radius_meters
    name_match = bool(osm_name and fuzzy_score >= NAME_MATCH_THRESHOLD)
    type_match = _type_matches(record.get("type"), osm_type)

    return {
        "osm_found": True,
        "osm_id": element.get("id"),
        "osm_element_type": element.get("type"),
        "osm_name": osm_name,
        "osm_type": osm_type,
        "osm_lat": osm_lat,
        "osm_lon": osm_lon,
        "osm_tags": tags,
        "distance_meters": None if distance_meters is None else round(distance_meters, 2),
        "location_match": location_match,
        "fuzzy_match_score": round(float(fuzzy_score), 2),
        "name_match_passed": name_match,
        "type_match": type_match,
    }


def _build_verification_result(candidate: Dict[str, Any], radius_meters: int) -> Dict[str, Any]:

    confidence_score, status, reasons = _score_candidate(candidate, radius_meters)
    osm_data = {
        "osm_id": candidate["osm_id"],
        "osm_element_type": candidate["osm_element_type"],
        "osm_name": candidate["osm_name"],
        "osm_type": candidate["osm_type"],
        "osm_lat": candidate["osm_lat"],
        "osm_lon": candidate["osm_lon"],
        "osm_tags": candidate["osm_tags"],
    }

    return {
        "overpass_checked": True,
        "osm_found": True,
        "osm_match": status in {"VERIFIED", "STRONG_MATCH", "PARTIAL_MATCH"},
        "osm_name": candidate["osm_name"],
        "osm_id": candidate["osm_id"],
        "osm_type": candidate["osm_type"],
        "osm_lat": candidate["osm_lat"],
        "osm_lon": candidate["osm_lon"],
        "osm_distance_m": candidate["distance_meters"],
        "osm_name_score": candidate["fuzzy_match_score"],
        "osm_tags": candidate["osm_tags"],
        "osm_summary": " ".join(reasons),
        "distance_meters": candidate["distance_meters"],
        "location_match": candidate["location_match"],
        "fuzzy_match_score": candidate["fuzzy_match_score"],
        "name_match_passed": candidate["name_match_passed"],
        "type_match": candidate["type_match"],
        "candidate_count": candidate.get("candidate_count", 1),
        "multiple_nearby_candidates": candidate.get("multiple_nearby_candidates", False),
        "confidence_score": confidence_score,
        "verification_status": status,
        "verification_reasons": reasons,
        "osm_data": osm_data,
    }


def _score_candidate(candidate: Dict[str, Any], radius_meters: int):

    score = 30
    reasons = ["OSM cemetery object found."]

    if candidate["name_match_passed"]:
        score += 30
        reasons.append(f"Name fuzzy match passed with score {candidate['fuzzy_match_score']}.")
    elif not candidate["osm_name"]:
        reasons.append("OSM cemetery object has no name tag.")
    else:
        reasons.append(f"Name fuzzy match failed with score {candidate['fuzzy_match_score']}.")

    if candidate["location_match"]:
        score += 30
        reasons.append(f"OSM object is within {radius_meters} meters.")
    else:
        reasons.append("OSM object is outside radius or lacks coordinates.")

    if candidate["type_match"]:
        score += 10
        reasons.append("CSV type maps to OSM cemetery type.")
    else:
        reasons.append("CSV type does not map to the OSM cemetery type.")

    return score, _status_for_score(score), reasons


def _status_for_score(score: int) -> str:

    if score >= 90:
        return "VERIFIED"
    if score >= 70:
        return "STRONG_MATCH"
    if score >= 50:
        return "PARTIAL_MATCH"
    return "WEAK_MATCH"


def _choose_best_candidate(candidates: List[Dict[str, Any]]) -> Dict[str, Any]:

    def sort_key(candidate):
        distance = candidate["distance_meters"]
        distance_score = 0 if distance is None else max(0, 1000 - distance)
        return (
            candidate["name_match_passed"],
            candidate["location_match"],
            candidate["type_match"],
            candidate["fuzzy_match_score"],
            distance_score,
        )

    return sorted(candidates, key=sort_key, reverse=True)[0]


def _extract_coordinates(element: Dict[str, Any]):

    center = element.get("center") if isinstance(element.get("center"), dict) else {}
    lat = element.get("lat") if element.get("lat") is not None else center.get("lat")
    lon = element.get("lon") if element.get("lon") is not None else center.get("lon")
    return coerce_float(lat), coerce_float(lon)


def _extract_osm_type(tags: Dict[str, Any]) -> Optional[str]:

    for key in ("amenity", "landuse", "historic", "cemetery"):
        value = tags.get(key)
        if value:
            return _normalize_type(value)
    return None


def _type_matches(csv_type, osm_type) -> bool:

    normalized_csv_type = _normalize_type(csv_type)
    normalized_osm_type = _normalize_type(osm_type)
    if not normalized_csv_type:
        return normalized_osm_type in OSM_CEMETERY_TYPES
    allowed = TYPE_MAPPING.get(normalized_csv_type, [])
    return bool(allowed and (normalized_osm_type in allowed or normalized_osm_type in OSM_CEMETERY_TYPES))


def _normalize_type(value) -> str:

    return str(value or "").strip().lower().replace(" ", "_")


def _distance_meters(csv_lat, csv_lon, osm_lat, osm_lon):

    if None in (csv_lat, csv_lon, osm_lat, osm_lon):
        return None
    return haversine_km(csv_lat, csv_lon, osm_lat, osm_lon) * 1000


def _respect_rate_limit():

    global _LAST_REQUEST_AT
    with _REQUEST_LOCK:
        elapsed = time.monotonic() - _LAST_REQUEST_AT
        if elapsed < OVERPASS_RATE_LIMIT_SECONDS:
            time.sleep(OVERPASS_RATE_LIMIT_SECONDS - elapsed)
        _LAST_REQUEST_AT = time.monotonic()


def _sleep_before_retry(attempt: int):

    if attempt >= OVERPASS_MAX_RETRIES:
        return
    time.sleep(2 ** attempt)


def _default_result(checked: bool, reason: str) -> Dict[str, Any]:

    return {
        "overpass_checked": checked,
        "osm_found": False,
        "osm_match": False,
        "osm_name": None,
        "osm_id": None,
        "osm_type": None,
        "osm_lat": None,
        "osm_lon": None,
        "osm_distance_m": None,
        "osm_name_score": None,
        "osm_tags": {},
        "osm_summary": reason,
        "distance_meters": None,
        "location_match": False,
        "fuzzy_match_score": None,
        "name_match_passed": False,
        "type_match": False,
        "candidate_count": 0,
        "multiple_nearby_candidates": False,
        "confidence_score": 0,
        "verification_status": "WEAK_MATCH",
        "verification_reasons": [reason],
        "osm_data": {},
    }
