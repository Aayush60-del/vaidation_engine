REQUIRED_FIELDS = [
    "name",
    "latitude",
    "longitude"
]


VALIDATED_RECORD_SCHEMA = {
    "name": str,
    "trust_score": int,
    "predicted_type": str,
    "validation_status": str
}


def missing_required_fields(record):

    missing = []
    for field in REQUIRED_FIELDS:
        value = record.get(field)
        if not value or not str(value).strip():
            missing.append(field)

    return missing
