import argparse
from pathlib import Path

import pandas as pd
from sklearn.feature_extraction import DictVectorizer
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import classification_report
from sklearn.model_selection import train_test_split
from sklearn.pipeline import FeatureUnion, Pipeline

from models.artifacts import CLASSIFIER_ARTIFACT, save_artifact
from models.feature_builder import build_classifier_training_row


def train_classifier(dataset_path):

    df = pd.read_csv(dataset_path)
    required = {"label"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"Classifier dataset missing columns: {sorted(missing)}")
    if len(df) < 10:
        raise ValueError(f"Not enough training data: {len(df)} rows. Need at least 10.")

    unique_labels = df["label"].nunique()
    if unique_labels < 2:
        raise ValueError(f"Need at least 2 label classes, found: {unique_labels}")

    records = df.fillna("").to_dict(orient="records")
    labels = [row["label"] for row in records]
    features = [build_classifier_training_row(row) for row in records]

    x_train, x_test, y_train, y_test = train_test_split(
        features,
        labels,
        test_size=0.2,
        random_state=42,
        stratify=labels if len(set(labels)) > 1 else None
    )

    model = build_classifier_pipeline()
    model.fit(x_train, y_train)

    predictions = model.predict(x_test)
    report = classification_report(y_test, predictions, zero_division=0)

    artifact = {
        "model": model,
        "labels": sorted(set(labels)),
        "metadata": {
            "task": "cemetery_type_classification",
            "training_rows": len(records),
            "dataset_path": str(Path(dataset_path).resolve())
        }
    }
    path = save_artifact(CLASSIFIER_ARTIFACT, artifact)
    return path, report


def build_classifier_pipeline():

    return Pipeline([
        ("features", FeatureUnion([
            ("combined_text", Pipeline([
                ("select", TextColumnSelector("combined_text")),
                ("vectorize", TfidfVectorizer(ngram_range=(1, 2), min_df=1))
            ])),
            ("address_text", Pipeline([
                ("select", TextColumnSelector("address_text")),
                ("vectorize", TfidfVectorizer(ngram_range=(1, 2), min_df=1))
            ])),
            ("metadata", Pipeline([
                ("select", DictColumnSelector([
                    "data_source",
                    "state",
                    "osm_signature",
                    "latitude",
                    "longitude",
                    "trust_score",
                    "has_phone",
                    "has_website",
                    "has_opening_hours",
                    "has_city",
                    "has_state",
                    "has_zip_code",
                    "geo_valid"
                ])),
                ("vectorize", DictVectorizer(sparse=True))
            ]))
        ])),
        ("classifier", LogisticRegression(max_iter=2000, class_weight="balanced"))
    ])


class DictColumnSelector:
    def __init__(self, columns):
        self.columns = columns

    def fit(self, x, y=None):
        return self

    def transform(self, x):
        return [
            {column: row.get(column) for column in self.columns}
            for row in x
        ]


class TextColumnSelector:
    def __init__(self, column):
        self.column = column

    def fit(self, x, y=None):
        return self

    def transform(self, x):
        return [str(row.get(self.column, "")) for row in x]


def main():

    parser = argparse.ArgumentParser(description="Train cemetery type classifier.")
    parser.add_argument("--dataset", required=True, help="CSV path with labeled cemetery records.")
    args = parser.parse_args()

    path, report = train_classifier(args.dataset)
    print(f"Saved classifier artifact to {path}")
    print(report)


if __name__ == "__main__":
    main()
