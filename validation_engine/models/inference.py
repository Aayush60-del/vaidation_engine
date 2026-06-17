from models.artifacts import (
    AI_VALIDATION_ARTIFACT,
    CLASSIFIER_ARTIFACT,
    DUPLICATE_ARTIFACT,
    load_artifact
)
from models.feature_builder import (
    build_ai_validation_training_row,
    build_classifier_training_row,
    build_duplicate_training_row
)


def predict_cemetery_type(record):

    artifact = load_artifact(CLASSIFIER_ARTIFACT)
    if artifact is None:
        return None

    model = artifact["model"]
    features = build_classifier_training_row(record)
    predicted_label = model.predict([features])[0]
    probabilities = _predict_proba(model, [features])

    if probabilities is None:
        confidence = 1.0
        scores = {predicted_label: 1.0}
    else:
        labels = artifact.get("labels", [])
        confidence = max(probabilities[0])
        scores = {
            label: round(probability, 4)
            for label, probability in zip(labels, probabilities[0])
        }

    return {
        "predicted_type": predicted_label,
        "classification_confidence": round(confidence, 2),
        "classification_scores": scores,
        "classification_needs_human_review": confidence < 0.6,
        "classification_source": "ml_model"
    }


def predict_duplicate_probability(left_record, right_record):

    artifact = load_artifact(DUPLICATE_ARTIFACT)
    if artifact is None:
        return None

    model = artifact["model"]
    features = build_duplicate_training_row(left_record, right_record)
    probabilities = _predict_proba(model, [features])
    if probabilities is None:
        predicted = int(model.predict([features])[0])
        probability = float(predicted)
    else:
        probability = float(probabilities[0][1])

    return {
        "duplicate_probability": round(probability, 4),
        "duplicate_source": "ml_model"
    }


def predict_ai_validation(record):

    artifact = load_artifact(AI_VALIDATION_ARTIFACT)
    if artifact is None:
        return None

    model = artifact["model"]
    features = build_ai_validation_training_row(record)
    predicted_label = model.predict([features])[0]
    probabilities = _predict_proba(model, [features])

    if probabilities is None:
        confidence = 1.0
        scores = {predicted_label: 1.0}
    else:
        labels = artifact.get("labels", [])
        confidence = max(probabilities[0])
        scores = {
            label: round(probability, 4)
            for label, probability in zip(labels, probabilities[0])
        }

    return {
        "ai_validation_label": predicted_label,
        "ai_validation_model_confidence": round(confidence, 2),
        "ai_validation_model_scores": scores,
        "ai_validation_model_source": "ml_model"
    }


def _predict_proba(model, rows):

    if not hasattr(model, "predict_proba"):
        return None
    return model.predict_proba(rows)
