from rapidfuzz import fuzz

from utils.constants import CLEAR_TYPES, is_valid_us_location
from utils.helpers import coerce_float, normalize_text


CITY_COORD_MISMATCH_FLAG = "city_coord_mismatch"
CITY_MATCH_THRESHOLD = 70


def determine_sparse_dataset_mode(record):
    """Identify sparse-but-verifiable cemetery records.

    Rural and historical datasets often contain only name, admin locality, and
    coordinates. When OSM confirms the cemetery object, the record is
    structurally complete even without contact/profile metadata.
    """

    lat = coerce_float(record.get("latitude"))
    lon = coerce_float(record.get("longitude"))
    name = str(record.get("name") or "").strip()
    enabled = all([
        bool(name),
        lat is not None,
        lon is not None,
        is_valid_us_location(lat, lon),
        record.get("osm_found"),
        record.get("name_match_passed"),
        record.get("location_match"),
        record.get("type_match"),
    ])

    return {
        "sparse_dataset_mode": bool(enabled),
        "structurally_complete": bool(enabled),
        "metadata_penalty_applied": False,
    }


def calculate_trust_score(record):

    score = 0

    name = str(record.get("name") or "").strip()
    if name and len(name) >= 3 and not name.isdigit():
        score += 20

    lat = coerce_float(record.get("latitude"))
    lon = coerce_float(record.get("longitude"))
    if lat is not None and lon is not None and is_valid_us_location(lat, lon):
        score += 25

    if record.get("city") and record.get("state"):
        score += 10
    if record.get("zip_code"):
        score += 2

    if record.get("city") and record.get("state") and CITY_COORD_MISMATCH_FLAG not in record.get("dq_flags", []):
        score += 5

    data_source = str(record.get("data_source", ""))
    if "google" in data_source.lower():
        score += 10
    else:
        score += 5

    labels = str(record.get("labels", [])).lower()
    if record.get("type") in CLEAR_TYPES or any(value in labels for value in CLEAR_TYPES):
        score += 10

    # Contact fields are optional for rural, historical, and remote cemeteries.
    # They can add a little support, but missing metadata should not outweigh
    # direct OSM, name, and coordinate evidence.
    enrichment = sum([
        bool(record.get("phone")),
        bool(record.get("website")),
        bool(record.get("opening_hours"))
    ])
    score += min(enrichment, 3)

    osm_tags = record.get("osm_tags", {})
    osm_verified = (
        record.get("osm_found")
        and record.get("name_match_passed")
        and record.get("location_match")
        and record.get("type_match")
        and record.get("confidence_score", 0) >= 70
    )
    if osm_verified:
        score += 35
    elif (
        osm_tags.get("amenity") == "grave_yard"
        or osm_tags.get("landuse") == "cemetery"
        or osm_tags.get("historic") == "cemetery"
        or osm_tags.get("cemetery") == "yes"
    ):
        score += 15
    elif record.get("osm_match") or record.get("nominatim_search_match"):
        score += 10

    if CITY_COORD_MISMATCH_FLAG in record.get("dq_flags", []):
        score -= 10

    return max(0, min(score, 100))


def apply_city_coordinate_consistency(record):

    locality = record.get("nearby_locality")
    if not isinstance(locality, dict):
        return record

    csv_city = normalize_text(record.get("city"))
    csv_county = normalize_text(record.get("county"))
    actual_city = normalize_text(locality.get("city"))
    actual_county = normalize_text(locality.get("county"))

    if not csv_city:
        return record

    city_score = None
    county_score = None
    mismatch = False

    if actual_city:
        city_score = fuzz.token_sort_ratio(csv_city, actual_city)
        mismatch = city_score < CITY_MATCH_THRESHOLD
    elif csv_county and actual_county:
        county_score = fuzz.token_sort_ratio(csv_county, actual_county)
        mismatch = county_score < CITY_MATCH_THRESHOLD

    if not mismatch:
        return record

    dq_flags = list(record.get("dq_flags", []))
    if CITY_COORD_MISMATCH_FLAG not in dq_flags:
        dq_flags.append(CITY_COORD_MISMATCH_FLAG)
    record["dq_flags"] = dq_flags
    record["city_coordinate_check"] = {
        "csv_city": record.get("city"),
        "osm_city": locality.get("city"),
        "csv_county": record.get("county"),
        "osm_county": locality.get("county"),
        "city_match_score": city_score,
        "county_match_score": county_score,
        "match_threshold": CITY_MATCH_THRESHOLD,
        "matched": False
    }
    return record
