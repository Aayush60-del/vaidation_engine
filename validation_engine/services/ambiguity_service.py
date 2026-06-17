from utils.constants import AMBIGUITY_HIERARCHY
from utils.helpers import build_text_blob


def assess_ambiguity(record):

    text = build_text_blob(record, ("name", "notes", "labels"))
    osm_tags = record.get("osm_tags", {})
    osm_pairs = {
        f"{key}={value}" for key, value in osm_tags.items()
    }
    geo_valid = bool(record.get("geo_valid"))

    for category, rules in AMBIGUITY_HIERARCHY.items():
        osm_rule_matches = any(pair in osm_pairs for pair in rules.get("osm_tags", []))
        name_rule_matches = any(pattern in text for pattern in rules.get("name_patterns", []))

        if not (osm_rule_matches or name_rule_matches):
            continue

        if rules.get("requires_geo_confirm") and not geo_valid:
            continue

        return {
            "ambiguity_category": category,
            "ambiguity_confidence": rules["confidence"],
            "is_ambiguous": category == "ambiguous",
            "ambiguity_needs_human_review": bool(rules.get("escalate_to_human")),
            "action": rules.get("action", "review" if category == "ambiguous" else "allow")
        }

    return {
        "ambiguity_category": "unclassified",
        "ambiguity_confidence": 0.5,
        "is_ambiguous": False,
        "ambiguity_needs_human_review": False,
        "action": "allow"
    }


def check_ambiguity(record):

    return assess_ambiguity(record)["is_ambiguous"]
