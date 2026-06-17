from utils.constants import QUARANTINE_STATUS, REVIEW_STATUS, VALID_STATUS


def attach_decision_reasons(record):

    reasons = []
    summary = []

    trust_score = record.get("trust_score")
    if trust_score is not None:
        if trust_score < 40:
            reasons.append(_reason("LOW_TRUST_SCORE", f"Trust score is {trust_score}, below quarantine threshold 40."))
        elif trust_score < 75:
            reasons.append(_reason("MEDIUM_TRUST_SCORE", f"Trust score is {trust_score}, in human review range 40-74."))
        else:
            summary.append(f"Trust score {trust_score} meets auto-valid threshold.")

    if not record.get("geo_valid", True):
        reasons.append(_reason("INVALID_GEO", "Coordinates are missing or outside supported US bounds."))
    elif record.get("nominatim_search_match"):
        summary.append("Nominatim confirmed a likely cemetery location match.")
    elif record.get("nominatim_checked") and not record.get("nominatim_reverse_match") and not record.get("nominatim_search_match"):
        reasons.append(_reason(
            "NOMINATIM_NO_MATCH",
            "Nominatim did not confirm the cemetery name/location with high confidence."
        ))

    predicted_type = record.get("predicted_type")
    if predicted_type == "invalid":
        reasons.append(_reason("INVALID_TYPE_CLASSIFICATION", "Classifier marked this record as invalid/non-cemetery."))
    elif predicted_type:
        summary.append(f"Predicted type is {predicted_type}.")

    if record.get("classification_needs_human_review"):
        reasons.append(_reason(
            "LOW_CLASSIFICATION_CONFIDENCE",
            f"Classification confidence is {record.get('classification_confidence')}, below 0.60."
        ))

    if record.get("ambiguity_needs_human_review") or record.get("is_ambiguous"):
        reasons.append(_reason(
            "AMBIGUOUS_CEMETERY_SIGNAL",
            f"Ambiguity category is {record.get('ambiguity_category')}."
        ))

    if record.get("action") == "reject":
        reasons.append(_reason(
            "AMBIGUITY_RULE_REJECT",
            f"Ambiguity hierarchy action is reject for category {record.get('ambiguity_category')}."
        ))

    for flag in record.get("flags", []):
        reasons.append(_reason("SUSPICIOUS_FLAG", f"Suspicious flag detected: {flag}.", {"flag": flag}))

    for dq_flag in record.get("dq_flags", []):
        if dq_flag == "POSSIBLE_DUPLICATE":
            reasons.append(_reason("POSSIBLE_DUPLICATE", "Record matched an existing cemetery and needs duplicate review."))
        elif dq_flag not in record.get("flags", []):
            reasons.append(_reason("DATA_QUALITY_FLAG", f"Data quality flag present: {dq_flag}.", {"flag": dq_flag}))

    ai_confidence = record.get("ai_validation_confidence_level")
    if ai_confidence == "LOW":
        reasons.append(_reason(
            "LOW_AI_VALIDATION_CONFIDENCE",
            f"AI validation confidence is LOW with score {record.get('ai_validation_score')}."
        ))
    elif ai_confidence == "MEDIUM":
        reasons.append(_reason(
            "MEDIUM_AI_VALIDATION_CONFIDENCE",
            f"AI validation confidence is MEDIUM with score {record.get('ai_validation_score')}."
        ))
    elif ai_confidence == "HIGH":
        summary.append(f"AI validation confidence is HIGH with score {record.get('ai_validation_score')}.")

    if record.get("ai_validation_llm_used"):
        summary.append("LLM review was used for this record.")
        if record.get("ai_validation_llm_reasoning"):
            summary.append(record.get("ai_validation_llm_reasoning"))

    for issue in record.get("ai_validation_issues", []):
        reasons.append(_reason(
            "AI_VALIDATION_ISSUE",
            f"AI validation flagged issue: {issue}.",
            {"issue": issue}
        ))

    activity_status = record.get("activity_status")
    if activity_status == "CLOSED":
        reasons.append(_reason(
            "CEMETERY_ACTIVITY_CLOSED",
            f"Cemetery activity status was detected as CLOSED with score {record.get('activity_confidence_score')}."
        ))
    elif activity_status == "INACTIVE":
        reasons.append(_reason(
            "CEMETERY_ACTIVITY_INACTIVE",
            f"Cemetery activity status was detected as INACTIVE with score {record.get('activity_confidence_score')}."
        ))
    elif activity_status == "UNKNOWN":
        reasons.append(_reason(
            "CEMETERY_ACTIVITY_UNKNOWN",
            f"Cemetery activity status is UNKNOWN with score {record.get('activity_confidence_score')}."
        ))
    elif activity_status == "ACTIVE":
        summary.append(
            f"Cemetery activity status is ACTIVE with score {record.get('activity_confidence_score')}."
        )

    if record.get("is_duplicate"):
        duplicate_type = record.get("duplicate_type") or "unknown"
        if record.get("merged_into"):
            reasons.append(_reason(
                "DUPLICATE_MERGED",
                f"Record is a {duplicate_type} duplicate merged into canonical record {record.get('merged_into')}.",
                {"duplicate_type": duplicate_type, "canonical_id": record.get("merged_into")}
            ))
        else:
            reasons.append(_reason(
                "DUPLICATE_CLUSTER",
                f"Record is part of a {duplicate_type} duplicate cluster and marked canonical.",
                {"duplicate_type": duplicate_type, "canonical_id": record.get("canonical_id")}
            ))

    status = record.get("validation_status")
    if status == VALID_STATUS and not reasons:
        reasons.append(_reason("AUTO_VALIDATED", "Record passed automated cemetery validation checks."))
    elif status == REVIEW_STATUS and not reasons:
        reasons.append(_reason("REQUIRES_HUMAN_REVIEW", "Record requires manual review based on validation policy."))
    elif status == QUARANTINE_STATUS and not reasons:
        reasons.append(_reason("QUARANTINED", "Record failed automated validation checks."))

    record["decision_reasons"] = reasons
    record["decision_reason_codes"] = [reason["code"] for reason in reasons]
    record["decision_summary"] = " ".join(
        [reason["message"] for reason in reasons] + summary
    ).strip()

    return record


def audit_payload(record, status, code, detail=None):

    reasons = []
    if code:
        reasons.append(_reason(code, detail or f"Audit event recorded with code {code}."))

    return {
        "record_id": record.get("_id"),
        "status": status,
        "code": code,
        "detail": detail,
        "decision_reasons": reasons,
        "decision_reason_codes": [reason["code"] for reason in reasons],
        "decision_summary": detail or f"{status}: {code}"
    }


def _reason(code, message, metadata=None):

    payload = {
        "code": code,
        "message": message
    }
    if metadata:
        payload["metadata"] = metadata
    return payload
