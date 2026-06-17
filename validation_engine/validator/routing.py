from db.mongo import (
    audit_collection,
    good_collection,
    review_collection,
    reject_collection
)
from services.decision_reason_service import audit_payload
from services.persistence_service import build_persisted_record
from utils.helpers import utc_now
from utils.logger import logger

from utils.constants import (
    QUARANTINE_STATUS,
    REVIEW_STATUS,
    VALID_STATUS
)

def route_record(record):

    status = record.get("validation_status")
    persisted_record = build_persisted_record(record)

    if status == VALID_STATUS:
        _safe_insert(good_collection, persisted_record, record)
        return "good"

    if status == REVIEW_STATUS:
        _safe_insert(review_collection, persisted_record, record)
        _safe_insert(audit_collection, {
            **audit_payload(
                record,
                "REVIEW",
                "ROUTED_TO_HUMAN_REVIEW",
                record.get("decision_summary")
            ),
            "audit_timestamp": utc_now(),
            "target_collection": "review"
        }, record)
        return "review"

    if status == QUARANTINE_STATUS:
        _safe_insert(reject_collection, persisted_record, record)
        _safe_insert(audit_collection, {
            **audit_payload(
                record,
                "REJECTED",
                "ROUTED_TO_REJECT",
                record.get("decision_summary")
            ),
            "audit_timestamp": utc_now(),
            "target_collection": "reject"
        }, record)
        return "reject"

    _safe_insert(reject_collection, persisted_record, record)
    _safe_insert(audit_collection, {
        **audit_payload(
            record,
            "REJECTED",
            "ROUTED_TO_REJECT_FALLBACK",
            "Record had an unknown validation status and was sent to reject."
        ),
        "audit_timestamp": utc_now(),
        "target_collection": "reject"
    }, record)
    return "reject"


def _safe_insert(collection, payload, record):

    try:
        collection.insert_one(payload)
    except Exception:
        logger.exception("DB insert failed for record %s", record.get("_id"))
