from reports.metrics import generate_metrics
import json
from datetime import datetime, timezone
from db.mongo import raw_collection
from utils.helpers import ensure_directory

def generate_daily_report():

    ensure_directory("output/reports")
    metrics = generate_metrics()
    today = datetime.now(timezone.utc).date()
    start_of_day = datetime.combine(today, datetime.min.time(), tzinfo=timezone.utc)

    report = {
        "date": str(today),
        "executive_summary": {
            "total_records": metrics["total_records"],
            "valid_pct": metrics["valid_pct"],
            "review_queue": metrics["review_queue"],
            "quarantined": metrics["quarantined"],
            "new_today": raw_collection.count_documents({
                "created_at": {"$gte": start_of_day}
            }) if raw_collection is not None else 0
        },
        "dedup_report": {
            "duplicate_clusters": metrics["duplicate_clusters"],
            "canonical_records": metrics["canonical_records"]
        },
        "ambiguity_report": {
            "ambiguous_count": metrics["ambiguous_count"],
            "by_type": metrics["by_type"]
        },
        "state_quality": metrics["state_quality"]
    }

    filename = f"output/reports/report_{today}.json"

    with open(filename, "w") as f:
        json.dump(report, f, indent=4)

    print("Daily report generated")
