from rapidfuzz import fuzz
import re
import os
from concurrent.futures import ThreadPoolExecutor, as_completed

from db.mongo import good_collection, review_collection, reject_collection
from models.inference import predict_duplicate_probability
from utils.constants import (
    DUPLICATE_DISTANCE_KM,
    DUPLICATE_NAME_THRESHOLD,
    SOFT_DUPLICATE_ADDRESS_THRESHOLD,
    SOFT_DUPLICATE_NAME_THRESHOLD
)
from utils.helpers import build_address_text, coerce_float, haversine_km, normalize_text



VALIDATION_COLLECTIONS = (
    good_collection,
    review_collection,
    reject_collection
)


def near_duplicate_score(rec1, rec2):

    if not _has_geo(rec1) or not _has_geo(rec2):
        return 0
    if not _same_admin_area(rec1, rec2):
        return 0

    ml_result = predict_duplicate_probability(rec1, rec2)
    if ml_result is not None:
        distance_km = _distance_km(rec1, rec2)
        if distance_km is None or distance_km > DUPLICATE_DISTANCE_KM:
            return 0
        return ml_result["duplicate_probability"] * 100

    name_score = fuzz.token_sort_ratio(
        normalize_text(rec1.get("name", "")),
        normalize_text(rec2.get("name", ""))
    )

    dist_km = _distance_km(rec1, rec2)
    if dist_km is None or dist_km > DUPLICATE_DISTANCE_KM:
        return 0

    geo_score = max(0, 100 - (dist_km * 200))
    return (name_score * 0.6) + (geo_score * 0.4)


def soft_match(rec1, rec2):

    if not _same_admin_area(rec1, rec2):
        return False

    distance_km = _distance_km(rec1, rec2)
    if distance_km is None or distance_km > DUPLICATE_DISTANCE_KM:
        return False

    left_address = build_address_text(rec1)
    right_address = build_address_text(rec2)
    if not left_address or not right_address:
        return False

    addr_score = fuzz.partial_ratio(
        left_address,
        right_address
    )
    name_score = fuzz.token_set_ratio(
        normalize_text(rec1.get("name", "")),
        normalize_text(rec2.get("name", ""))
    )

    return (
        addr_score >= SOFT_DUPLICATE_ADDRESS_THRESHOLD
        and name_score >= SOFT_DUPLICATE_NAME_THRESHOLD
    )


def is_duplicate(record):

    result = find_duplicate_cluster(record)
    return result["is_duplicate"]


def find_duplicate_cluster(record):

    candidates = _fetch_duplicate_candidates(record)
    exact_matches = []
    near_matches = []
    soft_matches = []

    for existing in candidates:
        if _is_exact_duplicate(record, existing):
            exact_matches.append(existing)
            continue

        if near_duplicate_score(record, existing) >= DUPLICATE_NAME_THRESHOLD:
            near_matches.append(existing)
            continue

        if soft_match(record, existing):
            soft_matches.append(existing)

    matches = exact_matches or near_matches or soft_matches
    if not matches:
        return {
            "is_duplicate": False,
            "duplicate_type": None,
            "duplicate_candidates": []
        }

    duplicate_type = (
        "exact"
        if exact_matches
        else "near"
        if near_matches
        else "soft"
    )

    return {
        "is_duplicate": True,
        "duplicate_type": duplicate_type,
        "duplicate_candidates": matches
    }


def apply_canonical_decision(record):

    cluster = find_duplicate_cluster(record)
    if not cluster["is_duplicate"]:
        record["is_duplicate"] = False
        record["duplicate_type"] = None
        record["is_canonical"] = True
        record["canonical_id"] = record.get("_id")
        record["merged_into"] = None
        return record

    candidates = cluster["duplicate_candidates"]
    canonical = max(
        candidates + [record],
        key=lambda item: item.get("trust_score", 0)
    )
    canonical_id = canonical.get("_id")

    record["is_duplicate"] = True
    record["duplicate_type"] = cluster["duplicate_type"]
    record["canonical_id"] = canonical_id
    record["is_canonical"] = canonical_id == record.get("_id")
    record["merged_into"] = None if record["is_canonical"] else canonical_id

    for candidate in candidates:
        updates = {
            "canonical_id": canonical_id,
            "is_canonical": candidate.get("_id") == canonical_id,
            "merged_into": None if candidate.get("_id") == canonical_id else canonical_id,
            "is_duplicate": True,
            "duplicate_type": cluster["duplicate_type"]
        }
        _update_existing_candidate(candidate["_id"], updates)

    return record


def run_dedup_sweep(workers: int | None = None, batch_size: int = 200):

    sweep_results = []

    if workers is None:
        from config import MAX_WORKER_THREADS
        workers = MAX_WORKER_THREADS

    for collection in VALIDATION_COLLECTIONS:
        cursor = collection.find({"validation_status": {"$in": ["valid", "review"]}})

        # Process in chunks to avoid unbounded memory growth.
        while True:
            batch = list(cursor.limit(batch_size))
            if not batch:
                break

            futures = []
            with ThreadPoolExecutor(max_workers=workers) as executor:
                for record in batch:
                    futures.append(
                        executor.submit(_compute_canonical_updates, record)
                    )

                for fut in as_completed(futures):
                    updated_id, updates = fut.result()
                    collection.update_one({"_id": updated_id}, {"$set": updates})
                    sweep_results.append(updated_id)

    return sweep_results


def _compute_canonical_updates(record):

    # Compute all dedup fields for the record. To keep Mongo writes safe and
    # deterministic, we do NOT update other candidates here.
    cluster = find_duplicate_cluster(record)
    if not cluster["is_duplicate"]:
        updated = {
            "is_duplicate": False,
            "duplicate_type": None,
            "canonical_id": record.get("_id"),
            "is_canonical": True,
            "merged_into": None,
        }
        return record.get("_id"), updated

    candidates = cluster["duplicate_candidates"]
    canonical = max(
        candidates + [record],
        key=lambda item: item.get("trust_score", 0)
    )
    canonical_id = canonical.get("_id")

    updates = {
        "is_duplicate": True,
        "duplicate_type": cluster["duplicate_type"],
        "canonical_id": canonical_id,
        "is_canonical": canonical_id == record.get("_id"),
        "merged_into": None if canonical_id == record.get("_id") else canonical_id,
    }

    return record.get("_id"), updates



def _fetch_duplicate_candidates(record):

    state = record.get("state")
    name = record.get("name")
    lat = coerce_float(record.get("latitude"))
    lon = coerce_float(record.get("longitude"))

    query = {"_id": {"$ne": record.get("_id")}}
    filters = []
    if state and lat is not None and lon is not None:
        filters.append({
            "state": state,
            "latitude": {
                "$gte": lat - 0.02,
                "$lte": lat + 0.02
            },
            "longitude": {
                "$gte": lon - 0.02,
                "$lte": lon + 0.02
            }
        })
    if name:
        filters.append({"name": {"$regex": re.escape(str(name)[:20]), "$options": "i"}})
    if lat is not None and lon is not None:
        filters.append({
            "latitude": {
                "$gte": lat - 0.02,
                "$lte": lat + 0.02
            },
            "longitude": {
                "$gte": lon - 0.02,
                "$lte": lon + 0.02
            }
        })

    if not filters:
        return []

    query["$or"] = filters

    candidates = []
    for collection in VALIDATION_COLLECTIONS:
        candidates.extend(collection.find(query))

    return candidates


def _is_exact_duplicate(rec1, rec2):

    left_name = normalize_text(rec1.get("name", ""))
    right_name = normalize_text(rec2.get("name", ""))
    return (
        left_name
        and left_name == right_name
        and coerce_float(rec1.get("latitude")) == coerce_float(rec2.get("latitude"))
        and coerce_float(rec1.get("longitude")) == coerce_float(rec2.get("longitude"))
    )


def _has_geo(record):

    lat = coerce_float(record.get("latitude"))
    lon = coerce_float(record.get("longitude"))
    return lat is not None and lon is not None


def _same_admin_area(rec1, rec2):

    left_state = normalize_text(rec1.get("state", ""))
    right_state = normalize_text(rec2.get("state", ""))
    if left_state and right_state and left_state != right_state:
        return False

    left_county = normalize_text(rec1.get("county", ""))
    right_county = normalize_text(rec2.get("county", ""))
    if left_county and right_county and left_county != right_county:
        return False

    return True


def _distance_km(rec1, rec2):

    if not _has_geo(rec1) or not _has_geo(rec2):
        return None

    return haversine_km(
        coerce_float(rec1["latitude"]),
        coerce_float(rec1["longitude"]),
        coerce_float(rec2["latitude"]),
        coerce_float(rec2["longitude"])
    )


def _update_existing_candidate(candidate_id, updates):

    for collection in VALIDATION_COLLECTIONS:
        result = collection.update_one({"_id": candidate_id}, {"$set": updates})
        if result.matched_count:
            return
