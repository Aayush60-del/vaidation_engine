import argparse
from pathlib import Path

import pandas as pd
from sklearn.feature_extraction import DictVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import classification_report
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline

from models.artifacts import DUPLICATE_ARTIFACT, save_artifact
from models.feature_builder import build_duplicate_training_row


def train_duplicate_model(dataset_path):

    df = pd.read_csv(dataset_path)
    required = {"left_name", "right_name", "label"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"Duplicate dataset missing columns: {sorted(missing)}")
    if len(df) < 10:
        raise ValueError(f"Not enough training data: {len(df)} rows. Need at least 10.")

    unique_labels = df["label"].nunique()
    if unique_labels < 2:
        raise ValueError(f"Need at least 2 label classes, found: {unique_labels}")

    rows = df.fillna("").to_dict(orient="records")
    features = []
    labels = []
    for row in rows:
        left_record = _pair_side_to_record(row, "left")
        right_record = _pair_side_to_record(row, "right")
        features.append(build_duplicate_training_row(left_record, right_record))
        labels.append(int(row["label"]))

    x_train, x_test, y_train, y_test = train_test_split(
        features,
        labels,
        test_size=0.2,
        random_state=42,
        stratify=labels if len(set(labels)) > 1 else None
    )

    model = Pipeline([
        ("vectorize", DictVectorizer(sparse=True)),
        ("classifier", LogisticRegression(max_iter=2000, class_weight="balanced"))
    ])
    model.fit(x_train, y_train)

    predictions = model.predict(x_test)
    report = classification_report(y_test, predictions, zero_division=0)

    artifact = {
        "model": model,
        "labels": [0, 1],
        "metadata": {
            "task": "duplicate_match_classification",
            "training_rows": len(rows),
            "dataset_path": str(Path(dataset_path).resolve())
        }
    }
    path = save_artifact(DUPLICATE_ARTIFACT, artifact)
    return path, report


def _pair_side_to_record(row, prefix):

    return {
        "name": row.get(f"{prefix}_name"),
        "address": row.get(f"{prefix}_address"),
        "city": row.get(f"{prefix}_city"),
        "state": row.get(f"{prefix}_state"),
        "zip_code": row.get(f"{prefix}_zip_code"),
        "type": row.get(f"{prefix}_type"),
        "latitude": row.get(f"{prefix}_latitude"),
        "longitude": row.get(f"{prefix}_longitude"),
        "trust_score": row.get(f"{prefix}_trust_score")
    }


def main():

    parser = argparse.ArgumentParser(description="Train cemetery duplicate matcher.")
    parser.add_argument("--dataset", required=True, help="CSV path with labeled record pairs.")
    args = parser.parse_args()

    path, report = train_duplicate_model(args.dataset)
    print(f"Saved duplicate artifact to {path}")
    print(report)


if __name__ == "__main__":
    main()
