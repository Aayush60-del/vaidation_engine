from db.mongo import (
    raw_collection,
    good_collection,
    review_collection,
    reject_collection,
    audit_collection
)

def create_indexes():

    if raw_collection is not None:
        raw_collection.create_index("validation_processed")

    for collection in (
        good_collection,
        review_collection,
        reject_collection
    ):
        collection.create_index([("name", 1), ("latitude", 1), ("longitude", 1)])
        collection.create_index([("location", "2dsphere")])
        collection.create_index([("name", "text"), ("city", "text")])
        collection.create_index([("state", 1), ("trust_score", -1)])
        collection.create_index("predicted_type")
        collection.create_index("canonical_id")
        collection.create_index("is_canonical")
        collection.create_index("validation_status")
        collection.create_index("review_required")

    audit_collection.create_index("audit_timestamp")

    print("Indexes created")
