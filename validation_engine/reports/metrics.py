from db.mongo import (
    audit_collection,
    good_collection,
    review_collection,
    reject_collection
)
from utils.constants import VALID_STATUS


def _all_collections():

    return (
        good_collection,
        review_collection,
        reject_collection
    )


def _count_documents(query):

    return sum(collection.count_documents(query) for collection in _all_collections())


def _aggregate_type_counts():

    counts = {}
    for collection in _all_collections():
        for row in collection.aggregate([
            {"$group": {"_id": "$predicted_type", "count": {"$sum": 1}}}
        ]):
            counts[row["_id"]] = counts.get(row["_id"], 0) + row["count"]

    return [
        {"_id": key, "count": value}
        for key, value in sorted(counts.items(), key=lambda item: item[0] or "")
    ]


def _aggregate_state_quality():

    states = {}
    for collection in _all_collections():
        for row in collection.aggregate([
            {
                "$group": {
                    "_id": "$state",
                    "avg_score": {"$avg": "$trust_score"},
                    "count": {"$sum": 1},
                    "valid_count": {
                        "$sum": {
                            "$cond": [{"$gte": ["$trust_score", 75]}, 1, 0]
                        }
                    }
                }
            }
        ]):
            state = row["_id"] or "UNKNOWN"
            current = states.setdefault(state, {
                "_id": state,
                "score_total": 0,
                "count": 0,
                "valid_count": 0
            })
            avg_score = row.get("avg_score") or 0.0
            current["score_total"] += avg_score * row["count"]
            current["count"] += row["count"]
            current["valid_count"] += row["valid_count"]

    output = []
    for state, row in states.items():
        avg_score = row["score_total"] / row["count"] if row["count"] else 0
        output.append({
            "_id": state,
            "avg_score": round(avg_score, 2),
            "count": row["count"],
            "valid_count": row["valid_count"]
        })

    return sorted(output, key=lambda row: row["avg_score"])


def _aggregate_reason_counts(collection, limit=10):

    return list(collection.aggregate([
        {"$unwind": "$decision_reason_codes"},
        {"$group": {"_id": "$decision_reason_codes", "count": {"$sum": 1}}},
        {"$sort": {"count": -1, "_id": 1}},
        {"$limit": limit}
    ]))


def _aggregate_verification_status_counts():

    counts = {}
    for collection in _all_collections():
        for row in collection.aggregate([
            {"$group": {"_id": "$verification_status", "count": {"$sum": 1}}}
        ]):
            status = row["_id"] or "UNKNOWN"
            counts[status] = counts.get(status, 0) + row["count"]

    return [
        {"_id": key, "count": value}
        for key, value in sorted(counts.items(), key=lambda item: item[0])
    ]


def generate_metrics():

    total_records = _count_documents({})
    valid_count = _count_documents({"validation_status": VALID_STATUS})
    sparse_filter = {
        "validation_status": VALID_STATUS,
        "osm_found": True,
        "name_match_passed": True,
        "location_match": True,
        "$or": [
            {"phone": {"$exists": False}},
            {"website": {"$exists": False}},
            {"email": {"$exists": False}},
            {"zip_code": {"$exists": False}}
        ]
    }

    metrics_dict = {
        "good_data": good_collection.count_documents({}),
        "good_osm_verified": good_collection.count_documents({
            "osm_found": True,
            "name_match_passed": True,
            "location_match": True,
            "confidence_score": {"$gte": 70}
        }),
        "good_sparse_osm_verified": good_collection.count_documents(sparse_filter),
        "sparse_dataset_mode_good": good_collection.count_documents({"sparse_dataset_mode": True}),
        "sparse_dataset_mode_review": review_collection.count_documents({"sparse_dataset_mode": True}),
        "human_review": review_collection.count_documents({}),
        "rejected": reject_collection.count_documents({}),
        "total_records": total_records,
        "valid_pct": round((valid_count / total_records) * 100, 2) if total_records else 0,
        "review_queue": _count_documents({"review_required": True}),
        "quarantined": _count_documents({"validation_status": "quarantine"}),
        "duplicate_clusters": _count_documents({"is_canonical": False}),
        "canonical_records": _count_documents({"is_canonical": True}),
        "ambiguous_count": _count_documents({"classification_confidence": {"$lt": 0.6}}),
        "by_type": _aggregate_type_counts(),
        "by_verification_status": _aggregate_verification_status_counts(),
        "state_quality": _aggregate_state_quality(),
        "review_reasons": _aggregate_reason_counts(review_collection),
        "reject_reasons": _aggregate_reason_counts(reject_collection),
        "audit_reasons": _aggregate_reason_counts(audit_collection)
    }

    # Inject threading performance metrics if available
    from validator.pipeline import get_last_run_metrics
    last_run = get_last_run_metrics()
    if last_run:
        metrics_dict["execution_performance"] = last_run

    return metrics_dict
