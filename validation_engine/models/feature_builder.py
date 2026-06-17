from rapidfuzz import fuzz

from services.trust_service import calculate_trust_score
from utils.constants import is_valid_us_location
from utils.helpers import (
    build_address_text,
    build_text_blob,
    coerce_float,
    haversine_km,
    normalize_text
)


CLASSIFIER_NUMERIC_FIELDS = [
    "latitude",
    "longitude",
    "trust_score",
    "has_phone",
    "has_website",
    "has_opening_hours",
    "has_city",
    "has_state",
    "has_zip_code",
    "geo_valid"
]


AI_VALIDATION_NUMERIC_FIELDS = [
    "name_word_count",
    "has_cemetery_keyword",
    "geo_valid",
    "latitude",
    "longitude",
    "trust_score",
    "has_city",
    "has_state",
    "has_county",
    "has_zip_code",
    "has_phone",
    "has_website",
    "has_email",
    "gnis_match",
    "findagrave_match",
    "osm_match",
    "external_positive_count",
    "external_weighted_score"
]


DUPLICATE_NUMERIC_FIELDS = [
    "name_token_sort_ratio",
    "name_token_set_ratio",
    "address_partial_ratio",
    "distance_km",
    "geo_score",
    "same_state",
    "same_zip_code",
    "same_type",
    "trust_score_gap",
    "both_geo_valid"
]


def build_classifier_training_row(record):

    lat = coerce_float(record.get("latitude"))
    lon = coerce_float(record.get("longitude"))
    geo_valid = int(
        lat is not None
        and lon is not None
        and is_valid_us_location(lat, lon)
    )

    return {
        "combined_text": build_text_blob(record, ("name", "notes", "labels")),
        "address_text": build_address_text(record),
        "data_source": normalize_text(record.get("data_source", "")) or "unknown",
        "state": normalize_text(record.get("state", "")) or "unknown",
        "osm_signature": _build_osm_signature(record.get("osm_tags", {})),
        "latitude": lat or 0.0,
        "longitude": lon or 0.0,
        "trust_score": record.get("trust_score", calculate_trust_score(record)),
        "has_phone": int(bool(record.get("phone"))),
        "has_website": int(bool(record.get("website"))),
        "has_opening_hours": int(bool(record.get("opening_hours"))),
        "has_city": int(bool(record.get("city"))),
        "has_state": int(bool(record.get("state"))),
        "has_zip_code": int(bool(record.get("zip_code"))),
        "geo_valid": geo_valid
    }


def build_duplicate_training_row(left_record, right_record):

    left_name = normalize_text(left_record.get("name", ""))
    right_name = normalize_text(right_record.get("name", ""))
    left_address = build_address_text(left_record)
    right_address = build_address_text(right_record)

    distance_km = _pair_distance_km(left_record, right_record)
    geo_score = max(0, 100 - (distance_km * 200)) if distance_km is not None else 0

    return {
        "name_text_left": left_name,
        "name_text_right": right_name,
        "address_text_left": left_address,
        "address_text_right": right_address,
        "name_token_sort_ratio": fuzz.token_sort_ratio(left_name, right_name),
        "name_token_set_ratio": fuzz.token_set_ratio(left_name, right_name),
        "address_partial_ratio": fuzz.partial_ratio(left_address, right_address),
        "distance_km": distance_km if distance_km is not None else 9999.0,
        "geo_score": geo_score,
        "same_state": int(normalize_text(left_record.get("state", "")) == normalize_text(right_record.get("state", ""))),
        "same_zip_code": int(normalize_text(left_record.get("zip_code", "")) == normalize_text(right_record.get("zip_code", ""))),
        "same_type": int(normalize_text(left_record.get("type", "")) == normalize_text(right_record.get("type", ""))),
        "trust_score_gap": abs(
            (left_record.get("trust_score") or calculate_trust_score(left_record))
            - (right_record.get("trust_score") or calculate_trust_score(right_record))
        ),
        "both_geo_valid": int(distance_km is not None)
    }


def build_ai_validation_training_row(record):

    name = normalize_text(record.get("name", ""))
    lat = coerce_float(record.get("latitude"))
    lon = coerce_float(record.get("longitude"))
    geo_valid = int(
        lat is not None
        and lon is not None
        and is_valid_us_location(lat, lon)
    )

    gnis_match = _bool_flag(record.get("gnis_match"))
    findagrave_match = _bool_flag(record.get("findagrave_match"))
    osm_match = _bool_flag(record.get("osm_match"))
    external_positive_count = gnis_match + findagrave_match + osm_match
    external_weighted_score = (gnis_match * 3) + (findagrave_match * 2) + osm_match

    return {
        "state": normalize_text(record.get("state", "")) or "unknown",
        "type": normalize_text(record.get("type", "")) or "unknown",
        "combined_text": build_text_blob(record, ("name", "notes", "labels", "description")),
        "address_text": build_address_text(record),
        "name_word_count": len(name.split()) if name else 0,
        "has_cemetery_keyword": int(any(
            keyword in name for keyword in ("cemetery", "graveyard", "burial", "mausoleum", "memorial")
        )),
        "geo_valid": geo_valid,
        "latitude": lat or 0.0,
        "longitude": lon or 0.0,
        "trust_score": record.get("trust_score", calculate_trust_score(record)),
        "has_city": int(bool(record.get("city"))),
        "has_state": int(bool(record.get("state"))),
        "has_county": int(bool(record.get("county"))),
        "has_zip_code": int(bool(record.get("zip_code"))),
        "has_phone": int(bool(record.get("phone") or record.get("phone_number"))),
        "has_website": int(bool(record.get("website"))),
        "has_email": int(bool(record.get("email"))),
        "gnis_match": gnis_match,
        "findagrave_match": findagrave_match,
        "osm_match": osm_match,
        "external_positive_count": external_positive_count,
        "external_weighted_score": external_weighted_score
    }


def _build_osm_signature(osm_tags):

    if not isinstance(osm_tags, dict) or not osm_tags:
        return "none"

    pairs = [f"{key}={value}" for key, value in sorted(osm_tags.items())]
    return "|".join(pairs)


def _pair_distance_km(left_record, right_record):

    left_lat = coerce_float(left_record.get("latitude"))
    left_lon = coerce_float(left_record.get("longitude"))
    right_lat = coerce_float(right_record.get("latitude"))
    right_lon = coerce_float(right_record.get("longitude"))

    if None in (left_lat, left_lon, right_lat, right_lon):
        return None

    return haversine_km(left_lat, left_lon, right_lat, right_lon)


def _bool_flag(value):

    if isinstance(value, bool):
        return int(value)
    if value is None:
        return 0
    return int(str(value).strip().lower() in {"1", "true", "yes", "y", "matched"})
