from utils.constants import (
    AMBIGUOUS_KEYWORDS,
    HUMAN_CEMETERY_KEYWORDS,
    INVALID_KEYWORDS,
    PET_KEYWORDS
)
from models.inference import predict_cemetery_type
from utils.helpers import build_text_blob


def classify_cemetery_type(record):

    ml_result = predict_cemetery_type(record)
    if ml_result is not None:
        return ml_result

    text = build_text_blob(record, ("name", "notes", "labels"))

    scores = {
        "human_cemetery": sum(1 for keyword in HUMAN_CEMETERY_KEYWORDS if keyword in text),
        "pet_cemetery": sum(1 for keyword in PET_KEYWORDS if keyword in text),
        "ambiguous": sum(1 for keyword in AMBIGUOUS_KEYWORDS if keyword in text),
        "invalid": sum(1 for keyword in INVALID_KEYWORDS if keyword in text)
    }

    osm_tags = record.get("osm_tags", {})
    if osm_tags.get("amenity") == "grave_yard":
        scores["human_cemetery"] += 3
    if osm_tags.get("landuse") == "cemetery":
        scores["human_cemetery"] += 2
    if osm_tags.get("historic") == "cemetery" or osm_tags.get("cemetery") == "yes":
        scores["human_cemetery"] += 2
    if record.get("osm_found") and record.get("type_match"):
        scores["human_cemetery"] += 4

    best = max(scores, key=scores.get)
    confidence = scores[best] / (sum(scores.values()) + 0.001)

    return {
        "predicted_type": best,
        "classification_confidence": round(confidence, 2),
        "classification_scores": scores,
        "classification_needs_human_review": confidence < 0.6,
        "classification_source": "rules"
    }


def classify_record(record):

    return classify_cemetery_type(record)["predicted_type"]
