from copy import deepcopy
from pathlib import Path
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from db.mongo import good_collection, reject_collection, review_collection
from services.persistence_service import build_persisted_record
from services.geo_service import validate_geo
from validator.validate_record import validate_record
from utils.constants import QUARANTINE_STATUS, REVIEW_STATUS, VALID_STATUS


TARGET_COLLECTIONS = (
    ("good", good_collection),
    ("review", review_collection),
    ("reject", reject_collection),
)

OLD_GEO_FLAGS = {
    "OUT_OF_US_BOUNDS",
    "GEO_OUT_OF_US",
    "coordinates_out_of_us",
    "INVALID_GEO",
}


def reprocess_alaska():

    candidates = list(_find_alaska_quarantine_records())
    results = {
        "scanned": len(candidates),
        "geo_fixed": 0,
        "moved_to_good": 0,
        "moved_to_review": 0,
        "kept_quarantine": 0,
    }

    for record in candidates:
        working = _prepare_record(record)
        if not validate_geo(working):
            results["kept_quarantine"] += 1
            continue

        results["geo_fixed"] += 1
        validated = validate_record(working)
        destination = _destination_for_status(validated.get("validation_status"))
        _replace_in_destination(destination, validated)
        _delete_from_other_collections(validated["_id"], destination)

        if destination == "good":
            results["moved_to_good"] += 1
        elif destination == "review":
            results["moved_to_review"] += 1
        else:
            results["kept_quarantine"] += 1

        print(
            f"{validated.get('name')}: geo_valid={validated.get('geo_valid')} "
            f"trust_score={validated.get('trust_score')} "
            f"ai={validated.get('ai_validation_confidence_level')} "
            f"status={validated.get('validation_status')} "
            f"destination={destination}"
        )

    return results


def _find_alaska_quarantine_records():

    query = {
        "state": "Alaska",
        "geo_valid": False,
        "validation_status": QUARANTINE_STATUS,
    }
    yield from reject_collection.find(query)


def _prepare_record(record):

    working = deepcopy(record)
    for field in (
        "decision_reasons",
        "decision_reason_codes",
        "decision_summary",
        "flags",
        "city_coordinate_check",
    ):
        working.pop(field, None)

    working["dq_flags"] = [
        flag for flag in working.get("dq_flags", [])
        if flag not in OLD_GEO_FLAGS
    ]
    return working


def _destination_for_status(status):

    if status == VALID_STATUS:
        return "good"
    if status == REVIEW_STATUS:
        return "review"
    return "reject"


def _collection_for_destination(destination):

    if destination == "good":
        return good_collection
    if destination == "review":
        return review_collection
    return reject_collection


def _replace_in_destination(destination, record):

    collection = _collection_for_destination(destination)
    collection.replace_one(
        {"_id": record["_id"]},
        build_persisted_record(record),
        upsert=True,
    )


def _delete_from_other_collections(record_id, destination):

    for label, collection in TARGET_COLLECTIONS:
        if label != destination:
            collection.delete_one({"_id": record_id})


def main():

    results = reprocess_alaska()
    print("\nAlaska reprocess summary")
    for key, value in results.items():
        print(f"{key}: {value}")


if __name__ == "__main__":
    main()
