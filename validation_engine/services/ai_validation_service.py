import json
from urllib import request

from config import (
    AI_VALIDATION_API_KEY,
    AI_VALIDATION_ENABLED,
    AI_VALIDATION_LLM_ENABLED,
    AI_VALIDATION_LLM_MODEL,
    AI_VALIDATION_LLM_PROVIDER,
    AI_VALIDATION_MIN_TRUST_SCORE_FOR_LLM,
    AI_VALIDATION_SKIP_HIGH_CONFIDENCE,
    CACHE_AI_VALIDATION,
    CACHE_ENABLED
)
from models.inference import predict_ai_validation
from services.cache_service import get_cache
from utils.logger import logger


def _safe_float(value, default=0.0):

    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _resolved_llm_api_key():

    return AI_VALIDATION_API_KEY


def run_ai_validation(record):

    if not AI_VALIDATION_ENABLED:
        return _default_result("disabled")

    # Check cache first
    if CACHE_ENABLED and CACHE_AI_VALIDATION:
        cache = get_cache()
        cached_result = cache.get_ai_validation(record)
        if cached_result is not None:
            return cached_result

    gnis_match = _bool_flag(record.get("gnis_match"))
    findagrave_match = _bool_flag(record.get("findagrave_match"))
    osm_match = _bool_flag(record.get("osm_match"))

    # Skip AI validation for high-confidence records
    if AI_VALIDATION_SKIP_HIGH_CONFIDENCE and _is_high_confidence_record(record, osm_match):
        result = _build_skip_ai_result(
            gnis_match=gnis_match,
            findagrave_match=findagrave_match,
            osm_match=osm_match,
            reason="Skipped: High-confidence record"
        )
        # Cache the result
        if CACHE_ENABLED and CACHE_AI_VALIDATION:
            cache = get_cache()
            cache.set_ai_validation(record, result)
        return result

    model_result = predict_ai_validation(record)
    model_label = model_result.get("ai_validation_label") if model_result else None

    llm_result = None
    if _should_invoke_llm(record, gnis_match, findagrave_match, osm_match, model_label):
        llm_result = _invoke_llm(record)

    total_score, confidence_level, action_required = _calculate_score(
        gnis_match=gnis_match,
        findagrave_match=findagrave_match,
        osm_match=osm_match,
        model_label=model_label,
        llm_result=llm_result
    )

    external_positive_count = gnis_match + findagrave_match + osm_match

    issues = []
    # Sparse metadata is normal for remote, rural, and historical cemeteries.
    # Missing contact fields are intentionally not treated as validation issues;
    # direct external matches, especially OSM verification, carry the trust.
    if not record.get("county"):
        issues.append("missing_county")
    if llm_result:
        issues.extend(llm_result.get("issues", []))

    issues = list(dict.fromkeys(str(issue) for issue in issues if issue))

    result = {
        "ai_validation_enabled": True,
        "ai_validation_external_matches": {
            "gnis_match": bool(gnis_match),
            "findagrave_match": bool(findagrave_match),
            "osm_match": bool(osm_match),
            "positive_count": external_positive_count
        },
        "ai_validation_model_label": model_label,
        "ai_validation_model_confidence": model_result.get("ai_validation_model_confidence") if model_result else None,
        "ai_validation_model_scores": model_result.get("ai_validation_model_scores") if model_result else {},
        "ai_validation_model_source": model_result.get("ai_validation_model_source") if model_result else None,
        "ai_validation_llm_used": bool(llm_result),
        "ai_validation_llm_confidence": llm_result.get("confidence") if llm_result else None,
        "ai_validation_llm_valid": llm_result.get("valid") if llm_result else None,
        "ai_validation_llm_reasoning": llm_result.get("reasoning") if llm_result else "",
        "ai_validation_score": total_score,
        "ai_validation_confidence_level": confidence_level,
        "ai_validation_action": action_required,
        "ai_validation_issues": issues,
        "ai_validation_summary": _build_summary(
            confidence_level=confidence_level,
            total_score=total_score,
            external_positive_count=external_positive_count,
            model_label=model_label,
            llm_result=llm_result,
            issues=issues
        )
    }

    # Cache the result
    if CACHE_ENABLED and CACHE_AI_VALIDATION:
        cache = get_cache()
        cache.set_ai_validation(record, result)

    return result


def _calculate_score(gnis_match, findagrave_match, osm_match, model_label, llm_result):

    score = (gnis_match * 3) + (findagrave_match * 2) + (osm_match * 5)

    if model_label == "HIGH":
        score += 2
    elif model_label == "MEDIUM":
        score += 1

    llm_confidence = llm_result.get("confidence", 0) if llm_result else 0
    if llm_confidence > 0.8:
        score += 2
    elif llm_confidence > 0.5:
        score += 1

    if score >= 5:
        return score, "HIGH", "auto_approve"
    if score >= 3:
        return score, "MEDIUM", "spot_check"
    return score, "LOW", "manual_review"


def _should_invoke_llm(record, gnis_match, findagrave_match, osm_match, model_label):

    if not AI_VALIDATION_LLM_ENABLED or not _resolved_llm_api_key():
        return False

    external_positive_count = gnis_match + findagrave_match + osm_match
    classification_confidence = _safe_float(record.get("classification_confidence"), 0.0)
    trust_score = _safe_float(record.get("trust_score"), 0.0)
    classification_confidence = max(0.0, min(1.0, classification_confidence))
    trust_score = max(0.0, min(100.0, trust_score))

    # Skip LLM for high-confidence records (trust_score >= threshold)
    if AI_VALIDATION_SKIP_HIGH_CONFIDENCE:
        if trust_score >= AI_VALIDATION_MIN_TRUST_SCORE_FOR_LLM * 100:
            return False

    return any([
        external_positive_count in {1, 2},
        model_label == "MEDIUM",
        classification_confidence < 0.75,
        record.get("ambiguity_needs_human_review", False),
        40 <= trust_score < 75
    ])


def _invoke_llm(record):

    payload = _build_llm_payload(record)
    try:
        if AI_VALIDATION_LLM_PROVIDER == "anthropic":
            response_text = _call_anthropic(payload)
        elif AI_VALIDATION_LLM_PROVIDER == "gemini":
            response_text = _call_gemini(payload)
        else:
            response_text = _call_openai(payload)
        parsed = json.loads(response_text)
        return {
            "valid": parsed.get("valid"),
            "confidence": float(parsed.get("confidence", 0.5)),
            "issues": parsed.get("issues", []),
            "reasoning": str(parsed.get("reasoning", "")).strip()
        }
    except (ValueError, TypeError, json.JSONDecodeError) as exc:
        logger.warning("AI validation LLM parsing failed for %s: %s", record.get("name"), exc)
    except Exception as exc:  # pragma: no cover - network-only runtime path
        logger.warning("AI validation LLM request failed for %s: %s", record.get("name"), exc)

    return None


def _build_llm_payload(record):

    llm_record = {
        "name": record.get("name"),
        "state": record.get("state"),
        "county": record.get("county"),
        "city": record.get("city"),
        "address": record.get("address") or record.get("street_address"),
        "zip_code": record.get("zip_code"),
        "latitude": record.get("latitude"),
        "longitude": record.get("longitude"),
        "phone": record.get("phone") or record.get("phone_number"),
        "website": record.get("website"),
        "email": record.get("email"),
        "type": record.get("type"),
        "description": record.get("description") or record.get("notes"),
        "gnis_match": record.get("gnis_match"),
        "findagrave_match": record.get("findagrave_match"),
        "osm_match": record.get("osm_match")
    }

    prompt = f"""
You are validating whether a US cemetery record looks legitimate.
Return only a JSON object.

Record:
{json.dumps(llm_record, indent=2)}

Check:
1. Do the coordinates look consistent with the stated location?
2. Does the name look like a legitimate cemetery or burial site?
3. Are missing fields normal or suspicious?
4. Considering all signals, should this record be treated as valid?

Return only:
{{
  "valid": true,
  "confidence": 0.0,
  "issues": ["issue"],
  "reasoning": "short explanation"
}}
""".strip()

    return prompt


def _call_openai(prompt):

    body = {
        "model": AI_VALIDATION_LLM_MODEL,
        "input": prompt
    }
    req = request.Request(
        "https://api.openai.com/v1/responses",
        data=json.dumps(body).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {_resolved_llm_api_key()}",
            "Content-Type": "application/json"
        },
        method="POST"
    )
    with request.urlopen(req, timeout=30) as response:  # pragma: no cover - network-only runtime path
        payload = json.loads(response.read().decode("utf-8"))

    output = payload.get("output", [])
    for item in output:
        for content in item.get("content", []):
            if content.get("type") in {"output_text", "text"} and content.get("text"):
                return content["text"]
    raise ValueError("No text returned from OpenAI response")


def _call_anthropic(prompt):

    body = {
        "model": AI_VALIDATION_LLM_MODEL,
        "max_tokens": 500,
        "messages": [{"role": "user", "content": prompt}]
    }
    req = request.Request(
        "https://api.anthropic.com/v1/messages",
        data=json.dumps(body).encode("utf-8"),
        headers={
            "x-api-key": _resolved_llm_api_key(),
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json"
        },
        method="POST"
    )
    with request.urlopen(req, timeout=30) as response:  # pragma: no cover - network-only runtime path
        payload = json.loads(response.read().decode("utf-8"))

    for item in payload.get("content", []):
        if item.get("type") == "text" and item.get("text"):
            return item["text"]
    raise ValueError("No text returned from Anthropic response")


def _call_gemini(prompt):

    try:
        from google import genai
        from google.genai import types
    except ImportError as exc:
        raise RuntimeError(
            "Gemini provider requires the google-genai package. Install requirements.txt dependencies first."
        ) from exc

    api_key = _resolved_llm_api_key()
    client = genai.Client(api_key=api_key) if api_key else genai.Client()
    response = client.models.generate_content(
        model=AI_VALIDATION_LLM_MODEL,
        contents=prompt,
        config=types.GenerateContentConfig(
            response_mime_type="application/json"
        )
    )

    if not getattr(response, "text", None):
        raise ValueError("No text returned from Gemini response")
    return response.text


def _is_high_confidence_record(record, osm_match):
    """
    Check if a record is high-confidence and should skip LLM validation.
    
    Returns True if:
    - OSM match confirmed, OR
    - Trust score >= 90, OR
    - Validation status already GOOD/VALID
    """
    trust_score = _safe_float(record.get("trust_score"), 0.0)
    validation_status = record.get("validation_status", "")
    
    high_confidence_threshold = AI_VALIDATION_MIN_TRUST_SCORE_FOR_LLM * 100
    
    return any([
        bool(osm_match),
        trust_score >= high_confidence_threshold,
        validation_status in {"GOOD", "VALID"}
    ])


def _build_skip_ai_result(gnis_match, findagrave_match, osm_match, reason):
    """
    Build a result object for skipped AI validation (high-confidence record).
    """
    external_positive_count = gnis_match + findagrave_match + osm_match
    
    return {
        "ai_validation_enabled": True,
        "ai_validation_external_matches": {
            "gnis_match": bool(gnis_match),
            "findagrave_match": bool(findagrave_match),
            "osm_match": bool(osm_match),
            "positive_count": external_positive_count
        },
        "ai_validation_model_label": None,
        "ai_validation_model_confidence": None,
        "ai_validation_model_scores": {},
        "ai_validation_model_source": None,
        "ai_validation_llm_used": False,
        "ai_validation_llm_confidence": None,
        "ai_validation_llm_valid": None,
        "ai_validation_llm_reasoning": "",
        "ai_validation_score": 10 if external_positive_count >= 1 else 5,
        "ai_validation_confidence_level": "HIGH" if external_positive_count >= 1 else "MEDIUM",
        "ai_validation_action": "auto_approve" if external_positive_count >= 1 else "spot_check",
        "ai_validation_issues": [],
        "ai_validation_summary": reason
    }


def _build_summary(confidence_level, total_score, external_positive_count, model_label, llm_result, issues):

    parts = [
        f"AI validation confidence is {confidence_level} with score {total_score}/10.",
        f"External source matches: {external_positive_count}/3."
    ]

    if model_label:
        parts.append(f"Model predicted {model_label}.")
    if llm_result and llm_result.get("reasoning"):
        parts.append(llm_result["reasoning"])
    if issues:
        parts.append(f"Issues: {', '.join(issues[:5])}.")

    return " ".join(parts)


def _default_result(reason):

    return {
        "ai_validation_enabled": False,
        "ai_validation_external_matches": {
            "gnis_match": False,
            "findagrave_match": False,
            "osm_match": False,
            "positive_count": 0
        },
        "ai_validation_model_label": None,
        "ai_validation_model_confidence": None,
        "ai_validation_model_scores": {},
        "ai_validation_model_source": None,
        "ai_validation_llm_used": False,
        "ai_validation_llm_confidence": None,
        "ai_validation_llm_valid": None,
        "ai_validation_llm_reasoning": "",
        "ai_validation_score": 0,
        "ai_validation_confidence_level": "UNAVAILABLE",
        "ai_validation_action": "not_run",
        "ai_validation_issues": [],
        "ai_validation_summary": f"AI validation not run: {reason}."
    }


def _bool_flag(value):

    if isinstance(value, bool):
        return int(value)
    return int(str(value).strip().lower() in {"1", "true", "yes", "y", "matched"})
