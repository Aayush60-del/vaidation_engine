from db.mongo import audit_collection
from db.schemas import missing_required_fields
from services.decision_reason_service import audit_payload
from services.duplicate_service import find_duplicate_cluster
from services.trust_service import calculate_trust_score
from utils.constants import (
    QUARANTINE_STATUS,
    REVIEW_STATUS,
    VALID_STATUS,
    is_valid_us_location
)
from utils.helpers import coerce_float, utc_now
from utils.logger import logger


class IngestionGate:
    """Real-time validation checks reused by batch ingestion."""

    def validate(self, record):

        missing_fields = missing_required_fields(record)
        if missing_fields:
            return self._reject(record, "MISSING_REQUIRED_FIELD", ",".join(missing_fields))

        lat = coerce_float(record["latitude"])
        lon = coerce_float(record["longitude"])
        if lat is None or lon is None or not is_valid_us_location(lat, lon):
            return self._quarantine(record, "OUT_OF_US_BOUNDS")

        name = str(record["name"]).strip()
        if len(name) < 3 or name.lower() in ["cemetery", "unknown", "n/a"]:
            return self._quarantine(record, "INVALID_NAME")

        duplicate_cluster = find_duplicate_cluster(record)
        if duplicate_cluster["is_duplicate"]:
            return self._flag(record, "POSSIBLE_DUPLICATE")

        score = calculate_trust_score(record)
        record["trust_score"] = score
        record["validation_status"] = (
            VALID_STATUS if score >= 75
            else REVIEW_STATUS if score >= 40
            else QUARANTINE_STATUS
        )

        return record

    def _reject(self, record, code, detail=None):

        log_audit(record, "REJECTED", code, detail)
        logger.warning("Record rejected at ingestion gate: %s", code)
        return None

    def _quarantine(self, record, code):

        record["validation_status"] = QUARANTINE_STATUS
        record["dq_flags"] = record.get("dq_flags", []) + [code]
        return record

    def _flag(self, record, code):

        record["review_required"] = True
        record["validation_status"] = REVIEW_STATUS
        record["dq_flags"] = record.get("dq_flags", []) + [code]
        return record


def log_audit(record, status, code, detail=None):

    audit_collection.insert_one({
        **audit_payload(record, status, code, detail),
        "audit_timestamp": utc_now(),
        "target_collection": "validation_audit"
    })
