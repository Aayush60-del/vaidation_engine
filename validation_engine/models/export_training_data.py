import argparse
import csv
import json
from itertools import combinations
from pathlib import Path

from rapidfuzz import fuzz

from db.mongo import good_collection, raw_collection, reject_collection, review_collection
from utils.helpers import build_address_text, coerce_float, ensure_directory, haversine_km, normalize_text


CLASSIFIER_HEADERS = [
    "label",
    "record_id",
    "source_collection",
    "name",
    "notes",
    "labels",
    "address",
    "city",
    "state",
    "zip_code",
    "latitude",
    "longitude",
    "data_source",
    "type",
    "phone",
    "website",
    "opening_hours",
    "osm_tags",
    "predicted_type",
    "validation_status",
    "review_required",
    "is_duplicate",
    "auto_label_hint"
]

PAIR_HEADERS = [
    "label",
    "left_record_id",
    "right_record_id",
    "left_name",
    "right_name",
    "left_address",
    "right_address",
    "left_city",
    "right_city",
    "left_state",
    "right_state",
    "left_zip_code",
    "right_zip_code",
    "left_type",
    "right_type",
    "left_latitude",
    "left_longitude",
    "right_latitude",
    "right_longitude",
    "left_trust_score",
    "right_trust_score",
    "existing_duplicate_flag",
    "name_similarity_hint",
    "address_similarity_hint",
    "distance_km_hint"
]


def export_training_data(outdir, limit_per_collection, duplicate_limit):

    output_dir = Path(outdir)
    ensure_directory(str(output_dir))

    classifier_path = output_dir / "cemetery_training_export.csv"
    duplicate_path = output_dir / "duplicate_pairs_export.csv"

    records = fetch_labeling_records(limit_per_collection)
    write_classifier_export(classifier_path, records)
    write_duplicate_export(duplicate_path, records, duplicate_limit)

    return classifier_path, duplicate_path


def fetch_labeling_records(limit_per_collection):

    collections = [
        ("raw", raw_collection),
        ("good", good_collection),
        ("review", review_collection),
        ("reject", reject_collection)
    ]

    records = []
    for source_name, collection in collections:
        if collection is None:
            continue
        for record in collection.find({}).limit(limit_per_collection):
            normalized = dict(record)
            normalized["_source_collection"] = source_name
            records.append(normalized)

    return records


def write_classifier_export(path, records):

    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=CLASSIFIER_HEADERS)
        writer.writeheader()

        for record in records:
            writer.writerow({
                "label": record.get("true_type", ""),
                "record_id": str(record.get("_id", "")),
                "source_collection": record.get("_source_collection", ""),
                "name": record.get("name", ""),
                "notes": record.get("notes", ""),
                "labels": _json_cell(record.get("labels", [])),
                "address": record.get("address", ""),
                "city": record.get("city", ""),
                "state": record.get("state", ""),
                "zip_code": record.get("zip_code", ""),
                "latitude": record.get("latitude", ""),
                "longitude": record.get("longitude", ""),
                "data_source": record.get("data_source", ""),
                "type": record.get("type", ""),
                "phone": record.get("phone", ""),
                "website": record.get("website", ""),
                "opening_hours": record.get("opening_hours", ""),
                "osm_tags": _json_cell(record.get("osm_tags", {})),
                "predicted_type": record.get("predicted_type", ""),
                "validation_status": record.get("validation_status", ""),
                "review_required": record.get("review_required", ""),
                "is_duplicate": record.get("is_duplicate", ""),
                "auto_label_hint": record.get("predicted_type", "")
            })


def write_duplicate_export(path, records, duplicate_limit):

    candidate_pairs = generate_duplicate_candidates(records, duplicate_limit)

    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=PAIR_HEADERS)
        writer.writeheader()

        for left_record, right_record, hints in candidate_pairs:
            writer.writerow({
                "label": "",
                "left_record_id": str(left_record.get("_id", "")),
                "right_record_id": str(right_record.get("_id", "")),
                "left_name": left_record.get("name", ""),
                "right_name": right_record.get("name", ""),
                "left_address": left_record.get("address", ""),
                "right_address": right_record.get("address", ""),
                "left_city": left_record.get("city", ""),
                "right_city": right_record.get("city", ""),
                "left_state": left_record.get("state", ""),
                "right_state": right_record.get("state", ""),
                "left_zip_code": left_record.get("zip_code", ""),
                "right_zip_code": right_record.get("zip_code", ""),
                "left_type": left_record.get("type", ""),
                "right_type": right_record.get("type", ""),
                "left_latitude": left_record.get("latitude", ""),
                "left_longitude": left_record.get("longitude", ""),
                "right_latitude": right_record.get("latitude", ""),
                "right_longitude": right_record.get("longitude", ""),
                "left_trust_score": left_record.get("trust_score", ""),
                "right_trust_score": right_record.get("trust_score", ""),
                "existing_duplicate_flag": int(bool(left_record.get("is_duplicate")) or bool(right_record.get("is_duplicate"))),
                "name_similarity_hint": round(hints["name_similarity"], 2),
                "address_similarity_hint": round(hints["address_similarity"], 2),
                "distance_km_hint": "" if hints["distance_km"] is None else round(hints["distance_km"], 4)
            })


def generate_duplicate_candidates(records, duplicate_limit):

    grouped = {}
    for record in records:
        state = normalize_text(record.get("state", "")) or "unknown"
        grouped.setdefault(state, []).append(record)

    pairs = []
    for state_records in grouped.values():
        for left_record, right_record in combinations(state_records, 2):
            hints = similarity_hints(left_record, right_record)
            if not _looks_like_candidate(hints):
                continue

            pairs.append((left_record, right_record, hints))
            if len(pairs) >= duplicate_limit:
                return pairs

    return pairs


def similarity_hints(left_record, right_record):

    left_name = normalize_text(left_record.get("name", ""))
    right_name = normalize_text(right_record.get("name", ""))
    left_address = build_address_text(left_record)
    right_address = build_address_text(right_record)

    distance_km = _distance_km(left_record, right_record)

    return {
        "name_similarity": fuzz.token_sort_ratio(left_name, right_name),
        "address_similarity": fuzz.partial_ratio(left_address, right_address),
        "distance_km": distance_km
    }


def _looks_like_candidate(hints):

    if hints["name_similarity"] >= 70:
        return True
    if hints["address_similarity"] >= 80:
        return True
    if hints["distance_km"] is not None and hints["distance_km"] <= 0.5:
        return True
    return False


def _distance_km(left_record, right_record):

    left_lat = coerce_float(left_record.get("latitude"))
    left_lon = coerce_float(left_record.get("longitude"))
    right_lat = coerce_float(right_record.get("latitude"))
    right_lon = coerce_float(right_record.get("longitude"))

    if None in (left_lat, left_lon, right_lat, right_lon):
        return None

    return haversine_km(left_lat, left_lon, right_lat, right_lon)


def _json_cell(value):

    return json.dumps(value, ensure_ascii=True)


def main():

    parser = argparse.ArgumentParser(description="Export Mongo records into labeling CSVs.")
    parser.add_argument("--outdir", default="models/exports", help="Directory for generated CSV files.")
    parser.add_argument("--limit-per-collection", type=int, default=250, help="Max records exported from each collection.")
    parser.add_argument("--duplicate-limit", type=int, default=500, help="Max duplicate candidate pairs to export.")
    args = parser.parse_args()

    classifier_path, duplicate_path = export_training_data(
        outdir=args.outdir,
        limit_per_collection=args.limit_per_collection,
        duplicate_limit=args.duplicate_limit
    )
    print(f"Classifier export written to {classifier_path}")
    print(f"Duplicate export written to {duplicate_path}")


if __name__ == "__main__":
    main()
