from services.ingestion_service import fetch_records
from services.ingestion_gate import IngestionGate
from validator.validate_record import validate_record
from validator.routing import route_record

from utils.logger import logger

def run_pipeline():

    gate = IngestionGate()
    records = fetch_records()

    processed_count = 0

    for record in records:

        gated_record = gate.validate(record)
        if gated_record is None:
            continue

        try:
            validated_record = validate_record(gated_record)
            destination = route_record(validated_record)
        except Exception:
            logger.exception("Failed to process record %s", record.get("_id"))
            continue

        processed_count += 1

        logger.info(
            "Processed record %s with status=%s route=%s trust_score=%s",
            record.get("_id"),
            validated_record.get("validation_status"),
            destination,
            validated_record.get("trust_score")
        )
        print(f"Processed: {record.get('name')}")

    print(f"\nValidation run completed. Stored {processed_count} processed records in Validation_DB.")
