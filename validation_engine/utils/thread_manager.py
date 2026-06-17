from threading import current_thread
from validator.validate_record import validate_record
from validator.routing import route_record
from utils.logger import logger

def process_record_worker(gated_record, original_record):
    """
    Worker function for thread pool.
    Handles single record validation and routing.
    """
    thread_id = current_thread().name
    record_id = original_record.get("_id")
    
    try:
        # Validate record
        validated_record = validate_record(gated_record)
        
        # Route record
        destination = route_record(validated_record)
        
        logger.info(
            "[%s] Processed %s: status=%s, route=%s, trust_score=%s",
            thread_id,
            record_id,
            validated_record.get("validation_status"),
            destination,
            validated_record.get("trust_score")
        )
        
        return {
            "record_id": record_id,
            "status": "success",
            "validation_status": validated_record.get("validation_status"),
            "route": destination,
            "error": None
        }
        
    except Exception as e:
        logger.exception(
            "[%s] Error processing %s: %s",
            thread_id,
            record_id,
            e
        )
        return {
            "record_id": record_id,
            "status": "error",
            "validation_status": "error",
            "route": "error",
            "error": str(e)
        }
