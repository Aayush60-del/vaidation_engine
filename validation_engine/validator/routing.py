from db.mongo import (
    audit_collection,
    good_collection,
    review_collection,
    reject_collection
)
from services.decision_reason_service import audit_payload
from services.persistence_service import build_persisted_record
from utils.helpers import utc_now, normalize_text, coerce_float, haversine_km
from utils.logger import logger

from utils.constants import (
    QUARANTINE_STATUS,
    REVIEW_STATUS,
    VALID_STATUS,
    DUPLICATE_DISTANCE_KM
)

from config import (
    REVIEW_COLLECTION,
    REJECT_COLLECTION,
    AUDIT_COLLECTION,
    DUPLICATE_CHECK_ON_INSERT,
    DUPLICATE_CHECK_DISTANCE_METERS
)

# Convert meters to km for haversine calculation
DUPLICATE_CHECK_DISTANCE_KM = DUPLICATE_CHECK_DISTANCE_METERS / 1000.0

def route_record(record):

    status = record.get("validation_status")
    persisted_record = build_persisted_record(record)

    if status == VALID_STATUS:
        route_result = _safe_route(good_collection, (review_collection, reject_collection), persisted_record, record)
        return route_result if route_result else "good"

    if status == REVIEW_STATUS:
        route_result = _safe_route(review_collection, (good_collection, reject_collection), persisted_record, record)
        if not route_result or route_result != "skipped_duplicate":
            _safe_insert(audit_collection, {
                **audit_payload(
                    record,
                    "REVIEW",
                    "ROUTED_TO_HUMAN_REVIEW",
                    record.get("decision_summary")
                ),
                "audit_timestamp": utc_now(),
                "target_collection": REVIEW_COLLECTION
            }, record)
        return route_result if route_result else "review"

    if status == QUARANTINE_STATUS:
        route_result = _safe_route(reject_collection, (good_collection, review_collection), persisted_record, record)
        if not route_result or route_result != "skipped_duplicate":
            _safe_insert(audit_collection, {
                **audit_payload(
                    record,
                    "REJECTED",
                    "ROUTED_TO_REJECT",
                    record.get("decision_summary")
                ),
                "audit_timestamp": utc_now(),
                "target_collection": REJECT_COLLECTION
            }, record)
        return route_result if route_result else "reject"

    route_result = _safe_route(reject_collection, (good_collection, review_collection), persisted_record, record)
    if not route_result or route_result != "skipped_duplicate":
        _safe_insert(audit_collection, {
            **audit_payload(
                record,
                "REJECTED",
                "ROUTED_TO_REJECT_FALLBACK",
                "Record had an unknown validation status and was sent to reject."
            ),
            "audit_timestamp": utc_now(),
            "target_collection": REJECT_COLLECTION
        }, record)
    return route_result if route_result else "reject"


def _safe_route(target_collection, other_collections, payload, record):

    try:
        # Check if record already exists in database (if enabled)
        if DUPLICATE_CHECK_ON_INSERT and _record_already_exists_in_db(payload, target_collection):
            logger.warning(
                "Record %s skipped - duplicate already exists in %s collection",
                payload.get("_id"),
                target_collection.name
            )
            return "skipped_duplicate"
        
        target_collection.replace_one({"_id": payload["_id"]}, payload, upsert=True)
        for collection in other_collections:
            collection.delete_one({"_id": payload["_id"]})
        
        return None  # Success
    except Exception:
        logger.exception("DB route failed for record %s", record.get("_id"))
        return None


def _safe_insert(collection, payload, record):

    try:
        collection.insert_one(payload)
    except Exception:
        logger.exception("DB insert failed for record %s", record.get("_id"))


def _record_already_exists_in_db(payload, target_collection):
    """
    Check if a record already exists in the database.
    
    Returns True if:
    1. Record with same _id exists, OR
    2. Record with same normalized name AND very close coordinates exists
    
    Args:
        payload: Record to insert
        target_collection: MongoDB collection to check against
        
    Returns:
        bool: True if duplicate found, False otherwise
    """
    record_id = payload.get("_id")
    name = payload.get("name")
    lat = coerce_float(payload.get("latitude"))
    lon = coerce_float(payload.get("longitude"))
    
    # Check 1: Exact ID match (fastest)
    if record_id and target_collection.find_one({"_id": record_id}):
        logger.debug("Duplicate found by ID: %s", record_id)
        return True
    
    # Check 2: Name + location similarity
    if not name or lat is None or lon is None:
        return False
    
    normalized_name = normalize_text(name)
    
    # Find all records with similar name
    similar_records = list(target_collection.find(
        {
            "name": {"$exists": True},
            "latitude": {"$exists": True},
            "longitude": {"$exists": True}
        }
    ).limit(100))  # Limit to avoid performance issues
    
    for existing in similar_records:
        existing_name = existing.get("name", "")
        existing_lat = coerce_float(existing.get("latitude"))
        existing_lon = coerce_float(existing.get("longitude"))
        
        if existing_lat is None or existing_lon is None:
            continue
        
        # Check name similarity
        normalized_existing = normalize_text(existing_name)
        if normalized_name != normalized_existing:
            continue
        
        # Check location similarity (within 500 meters)
        distance_km = haversine_km(lat, lon, existing_lat, existing_lon)
        if distance_km <= DUPLICATE_CHECK_DISTANCE_KM:
            logger.debug(
                "Duplicate found: %s (existing: %s, distance: %.3f km)",
                record_id,
                existing.get("_id"),
                distance_km
            )
            return True
    
    return False
