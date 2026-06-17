import argparse

from db.mongo import good_collection, reject_collection, review_collection
from services.persistence_service import build_persisted_record


TARGET_COLLECTIONS = (
    ("good_data", good_collection),
    ("human_review", review_collection),
    ("rejected_flagged", reject_collection)
)


def compact_validation_db(dry_run=False, limit=None):

    summary = []

    for label, collection in TARGET_COLLECTIONS:
        cursor = collection.find({}, limit=limit or 0)
        scanned = 0
        updated = 0

        for record in cursor:
            scanned += 1
            compacted = build_persisted_record(record)
            if _documents_equal(record, compacted):
                continue

            updated += 1
            if not dry_run:
                collection.replace_one({"_id": record["_id"]}, compacted, upsert=False)

        summary.append({
            "collection": label,
            "scanned": scanned,
            "updated": updated
        })

    return summary


def _documents_equal(original, compacted):

    relevant_original = {
        key: value
        for key, value in original.items()
        if key in compacted
    }
    return relevant_original == compacted and set(original.keys()) == set(compacted.keys())


def main():

    parser = argparse.ArgumentParser(description="Compact existing Validation_DB documents to the current minimal schema.")
    parser.add_argument("--dry-run", action="store_true", help="Show what would change without writing updates.")
    parser.add_argument("--limit", type=int, default=None, help="Only inspect the first N records per collection.")
    args = parser.parse_args()

    results = compact_validation_db(dry_run=args.dry_run, limit=args.limit)
    for row in results:
        print(
            f"{row['collection']}: scanned={row['scanned']} updated={row['updated']}"
        )


if __name__ == "__main__":
    main()
