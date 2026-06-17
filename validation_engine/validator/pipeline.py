from services.ingestion_service import fetch_records
from services.ingestion_gate import IngestionGate
from validator.validate_record import validate_record
from validator.routing import route_record

from utils.logger import logger
from utils.thread_manager import process_record_worker
from config import THREADING_ENABLED, MAX_WORKER_THREADS, BATCH_SIZE, CACHE_ENABLED
from services.cache_service import get_cache
from concurrent.futures import ThreadPoolExecutor, as_completed
import time

def run_pipeline():
    """Main entry point. Dispatches to threaded or sequential implementation."""
    if THREADING_ENABLED:
        logger.info("Starting multithreaded pipeline with %s workers", MAX_WORKER_THREADS)
        return run_pipeline_threaded(MAX_WORKER_THREADS, BATCH_SIZE)
    else:
        logger.info("Starting sequential pipeline")
        return run_pipeline_sequential()

def run_pipeline_threaded(max_workers=8, batch_size=100):
    gate = IngestionGate()
    records = fetch_records()
    
    processed_count = 0
    failed_count = 0
    errors = []
    
    start_time = time.time()
    
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {}
        
        for record in records:
            gated_record = gate.validate(record)
            if gated_record is None:
                continue
            
            future = executor.submit(process_record_worker, gated_record, record)
            futures[future] = record.get("_id")
            
        for future in as_completed(futures):
            record_id = futures[future]
            try:
                result = future.result()
                if result and result.get("status") == "success":
                    processed_count += 1
                    print(f"Processed: {record_id}")
                else:
                    failed_count += 1
                    errors.append({"record_id": record_id, "error": result.get("error")})
            except Exception as e:
                failed_count += 1
                errors.append({"record_id": record_id, "error": str(e)})
                logger.exception("Failed to process: %s", record_id)
                
    elapsed = time.time() - start_time
    
    # Store metrics globally for generating metrics report if needed
    global _last_run_metrics
    _last_run_metrics = {
        "total_time_seconds": round(elapsed, 2),
        "processed_records": processed_count,
        "failed_records": failed_count,
        "avg_time_per_record": round(elapsed / (processed_count or 1), 3),
        "max_worker_threads_used": max_workers,
    }
    
    # Log cache statistics if caching is enabled
    if CACHE_ENABLED:
        cache = get_cache()
        cache.log_stats(logger.info)
                
    print(f"\nValidation run completed in {elapsed:.2f}s. Stored {processed_count} processed records, {failed_count} failures.")
    return processed_count, failed_count, errors

def run_pipeline_sequential():
    gate = IngestionGate()
    records = fetch_records()

    processed_count = 0
    start_time = time.time()

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

    elapsed = time.time() - start_time
    
    # Log cache statistics if caching is enabled
    if CACHE_ENABLED:
        cache = get_cache()
        cache.log_stats(logger.info)

    print(f"\nValidation run completed in {elapsed:.2f}s. Stored {processed_count} processed records in Validation_DB.")

_last_run_metrics = {}
def get_last_run_metrics():
    return _last_run_metrics
