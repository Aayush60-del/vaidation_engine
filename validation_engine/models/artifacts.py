from pathlib import Path

from config import (
    AI_VALIDATION_MODEL_PATH,
    CLASSIFIER_MODEL_PATH,
    DUPLICATE_MODEL_PATH,
    MODEL_DIR
)
from utils.helpers import ensure_directory

try:
    import joblib
except ImportError:  # pragma: no cover - runtime fallback when ML deps are absent
    joblib = None


CLASSIFIER_ARTIFACT = "classifier"
DUPLICATE_ARTIFACT = "duplicate"
AI_VALIDATION_ARTIFACT = "ai_validation"


def artifact_path(kind):

    if kind == CLASSIFIER_ARTIFACT:
        return Path(CLASSIFIER_MODEL_PATH)
    if kind == DUPLICATE_ARTIFACT:
        return Path(DUPLICATE_MODEL_PATH)
    if kind == AI_VALIDATION_ARTIFACT:
        return Path(AI_VALIDATION_MODEL_PATH)
    raise ValueError(f"Unknown artifact kind: {kind}")


def save_artifact(kind, artifact):

    if joblib is None:
        raise RuntimeError(
            "joblib is not installed. Install ML dependencies from requirements.txt before training models."
        )

    ensure_directory(MODEL_DIR)
    path = artifact_path(kind)
    joblib.dump(artifact, path)
    return path


def load_artifact(kind):

    if joblib is None:
        return None

    path = artifact_path(kind)
    if not path.exists():
        return None

    return joblib.load(path)
