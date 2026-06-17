import argparse
from pathlib import Path

import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.feature_extraction import DictVectorizer
from sklearn.metrics import classification_report
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline

from models.artifacts import AI_VALIDATION_ARTIFACT, save_artifact
from models.feature_builder import build_ai_validation_training_row


def train_ai_validator(dataset_path):

    df = pd.read_csv(dataset_path)
    required = {"label"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"AI validation dataset missing columns: {sorted(missing)}")
    if len(df) < 10:
        raise ValueError(f"Not enough training data: {len(df)} rows. Need at least 10.")

    unique_labels = df["label"].nunique()
    if unique_labels < 2:
        raise ValueError(f"Need at least 2 label classes, found: {unique_labels}")

    records = df.fillna("").to_dict(orient="records")
    labels = [str(row["label"]).strip().upper() for row in records]
    features = [build_ai_validation_training_row(row) for row in records]

    x_train, x_test, y_train, y_test = train_test_split(
        features,
        labels,
        test_size=0.2,
        random_state=42,
        stratify=labels if len(set(labels)) > 1 else None
    )

    model = Pipeline([
        ("vectorize", DictVectorizer(sparse=False)),
        ("classifier", RandomForestClassifier(
            n_estimators=250,
            max_depth=10,
            random_state=42,
            class_weight="balanced_subsample"
        ))
    ])
    model.fit(x_train, y_train)

    predictions = model.predict(x_test)
    report = classification_report(y_test, predictions, zero_division=0)

    artifact = {
        "model": model,
        "labels": sorted(set(labels)),
        "metadata": {
            "task": "cemetery_confidence_validation",
            "training_rows": len(records),
            "dataset_path": str(Path(dataset_path).resolve())
        }
    }
    path = save_artifact(AI_VALIDATION_ARTIFACT, artifact)
    return path, report


def main():

    parser = argparse.ArgumentParser(description="Train HIGH/MEDIUM/LOW AI confidence validator.")
    parser.add_argument("--dataset", required=True, help="CSV path with confidence labels.")
    args = parser.parse_args()

    path, report = train_ai_validator(args.dataset)
    print(f"Saved AI validator artifact to {path}")
    print(report)


if __name__ == "__main__":
    main()
