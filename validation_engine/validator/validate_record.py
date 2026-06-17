from services.trust_service import (
    apply_city_coordinate_consistency,
    calculate_trust_score,
    determine_sparse_dataset_mode,
)
from services.ai_validation_service import run_ai_validation
from services.activity_status_service import detect_activity_status
from services.nominatim_service import enrich_with_nominatim
from services.overpass_service import verify_with_overpass
from services.classifier_service import classify_cemetery_type
from services.ambiguity_service import assess_ambiguity
from services.decision_reason_service import attach_decision_reasons
from services.suspicious_service import detect_suspicious
from services.geo_service import validate_geo
from services.duplicate_service import apply_canonical_decision
from utils.constants import QUARANTINE_STATUS, REVIEW_STATUS, VALID_STATUS
from utils.helpers import coerce_float, utc_now


HARD_LOCATION_FLAGS = {"missing_coordinates", "coordinates_out_of_us", "city_coord_mismatch"}


def validate_record(record):

    record["validated_at"] = utc_now()
    record["geo_valid"] = validate_geo(record)
    record["location"] = _build_location(record)
    record.update(enrich_with_nominatim(record))
    record.update(verify_with_overpass(record))
    record = apply_city_coordinate_consistency(record)
    record.update(determine_sparse_dataset_mode(record))
    record["trust_score"] = calculate_trust_score(record)

    classification = classify_cemetery_type(record)
    record.update(classification)

    ambiguity = assess_ambiguity(record)
    record.update(ambiguity)

    ai_validation = run_ai_validation(record)
    record.update(ai_validation)

    activity_status = detect_activity_status(record)
    record.update(activity_status)

    record["flags"] = detect_suspicious(record)
    record["review_required"] = any([
        record.get("classification_needs_human_review", False),
        ambiguity.get("ambiguity_needs_human_review", False),
        bool(record["flags"]),
        record.get("ai_validation_action") in {"spot_check", "manual_review"},
        record.get("activity_status_needs_review", False)
    ])
    if record.get("sparse_dataset_mode") and _has_strong_osm_confirmation(record):
        # Sparse dataset mode intentionally lets OSM/name/coordinate evidence
        # override missing optional profile metadata and unknown activity.
        record["review_required"] = False
    record["dq_flags"] = list(dict.fromkeys(record.get("dq_flags", []) + record["flags"]))

    record = apply_canonical_decision(record)
    if record.get("is_duplicate"):
        record["review_required"] = True
        if record.get("merged_into"):
            record["dq_flags"] = list(dict.fromkeys(record["dq_flags"] + ["POSSIBLE_DUPLICATE"]))

    record["validation_status"] = _resolve_validation_status(record)
    record = attach_decision_reasons(record)

    return record


def _resolve_validation_status(record):

    if _has_hard_reject_signal(record):
        return QUARANTINE_STATUS

    if _has_strong_osm_confirmation(record):
        if _has_human_verify_signal(record):
            return REVIEW_STATUS
        return VALID_STATUS

    if not record.get("osm_found") and record["trust_score"] < 40:
        return QUARANTINE_STATUS

    if record.get("ai_validation_confidence_level") == "LOW":
        return REVIEW_STATUS

    if (
        record["trust_score"] >= 75
        and not record.get("review_required")
        and record.get("ai_validation_confidence_level") in {None, "UNAVAILABLE", "HIGH"}
    ):
        return VALID_STATUS

    return REVIEW_STATUS


def _has_strong_osm_confirmation(record):

    return all([
        record.get("osm_found") is True,
        record.get("name_match_passed") is True,
        record.get("location_match") is True,
        record.get("type_match") is True,
        _safe_score(record.get("confidence_score")) >= 70
    ])


def _has_human_verify_signal(record):

    dq_flags = set(record.get("dq_flags", []))
    return any([
        "city_coord_mismatch" in dq_flags,
        record.get("multiple_nearby_candidates"),
        record.get("is_duplicate"),
        record.get("ambiguity_needs_human_review") and record.get("ambiguity_category") != "definite_cemetery",
        record.get("verification_status") == "PARTIAL_MATCH",
    ])


def _has_hard_reject_signal(record):

    flags = set(record.get("flags", []))
    dq_flags = set(record.get("dq_flags", []))
    return any([
        not record.get("geo_valid", True),
        bool(flags & HARD_LOCATION_FLAGS),
        bool(dq_flags & {"OUT_OF_US_BOUNDS", "INVALID_NAME"}),
        record.get("predicted_type") == "invalid" and not _has_strong_osm_confirmation(record),
        record.get("action") == "reject",
        record.get("osm_found") and not record.get("location_match") and _safe_score(record.get("confidence_score")) < 70,
    ])


def _safe_score(value):

    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def _build_location(record):

    lat = coerce_float(record.get("latitude"))
    lon = coerce_float(record.get("longitude"))
    if lat is None or lon is None:
        return None

    return {
        "type": "Point",
        "coordinates": [lon, lat]
    }
