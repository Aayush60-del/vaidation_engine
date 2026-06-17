from datetime import datetime, timezone
import re

from utils.constants import (
    ACTIVE_CEMETERY_STATUS,
    ACTIVITY_STATUS_HIGH_THRESHOLD,
    ACTIVITY_STATUS_UNKNOWN_THRESHOLD,
    CLOSED_CEMETERY_STATUS,
    INACTIVE_CEMETERY_STATUS,
    UNKNOWN_CEMETERY_STATUS
)


RECENT_BURIAL_WEIGHT = 40
STALE_BURIAL_WEIGHT = -40
ACTIVE_FLAG_WEIGHT = 30
CLOSED_FLAG_WEIGHT = -45
INACTIVE_FLAG_WEIGHT = -30
RECENT_UPDATE_WEIGHT = 15
STALE_UPDATE_WEIGHT = -10
CONTACT_WEIGHT = 10
LIMITED_PLOTS_WEIGHT = -10
NO_PLOTS_WEIGHT = -20

YEAR_FIELDS = (
    "latest_burial_year",
    "last_burial_year",
    "latest_interment_year",
    "last_interment_year",
    "burial_year",
    "interment_year",
    "most_recent_burial_year"
)

DATE_FIELDS = (
    "updated_at",
    "last_updated",
    "source_updated_at",
    "modified_at",
    "last_modified",
    "last_verified_at",
    "record_updated_at",
    "validated_at"
)

STATUS_FIELDS = (
    "status",
    "official_status",
    "operational_status",
    "description",
    "notes",
    "labels"
)


def detect_activity_status(record, now=None):
    """Return scoring-based cemetery activity assessment for a record.

    Schema assumptions:
    - burial timing may exist as direct year fields or inside lists such as `burials` / `interments`
    - freshness may exist in common timestamp fields like `updated_at` or `last_updated`
    - operational hints may exist as booleans or free-text fields such as `status`, `description`, `labels`
    - plot availability may exist as `available_plots`, `plot_availability`, `is_full`, or `full`
    """

    now = now or datetime.now(timezone.utc)
    reasons = []
    score = 0

    latest_burial_year = _find_latest_burial_year(record)
    burial_score, burial_reasons = _score_burial_activity(latest_burial_year, now.year)
    score += burial_score
    reasons.extend(burial_reasons)

    status_signal = _score_official_status(record)
    score += status_signal["score"]
    reasons.extend(status_signal["reasons"])

    freshness_score, freshness_reasons = _score_data_freshness(record, now)
    score += freshness_score
    reasons.extend(freshness_reasons)

    plot_score, plot_reasons = _score_plot_availability(record)
    score += plot_score
    reasons.extend(plot_reasons)

    contact_score, contact_reasons = _score_contact_metadata(record)
    score += contact_score
    reasons.extend(contact_reasons)

    has_evidence = bool(reasons)
    status = _resolve_activity_status(score, status_signal["closed"], has_evidence)
    confidence = max(0, min(100, score))

    if not reasons:
        reasons.append("Insufficient activity evidence found in available fields.")

    return {
        "cemeteryId": record.get("_id"),
        "activity_status": status,
        "activity_confidence_score": confidence,
        "activity_reasons": reasons,
        "latest_burial_year": latest_burial_year,
        "activity_status_needs_review": status == UNKNOWN_CEMETERY_STATUS
    }


def _score_burial_activity(latest_burial_year, current_year):

    if latest_burial_year is None:
        return 0, []

    age = current_year - latest_burial_year
    if age <= 5:
        return RECENT_BURIAL_WEIGHT, [f"Recent burial activity found in {latest_burial_year}."]
    if age >= 20:
        return STALE_BURIAL_WEIGHT, [f"No recent burial activity; latest burial year is {latest_burial_year}."]
    return 10, [f"Burial activity exists but is not recent; latest burial year is {latest_burial_year}."]


def _score_official_status(record):

    signals = []
    score = 0
    closed = False

    for field in STATUS_FIELDS:
        value = record.get(field)
        text = _normalize_status_value(value)
        if not text:
            continue

        if any(keyword in text for keyword in ("closed", "permanently closed")):
            score += CLOSED_FLAG_WEIGHT
            closed = True
            signals.append(f"Official status field '{field}' indicates closed.")
        elif any(keyword in text for keyword in ("abandoned", "historic only", "inactive")):
            score += INACTIVE_FLAG_WEIGHT
            signals.append(f"Official status field '{field}' suggests inactive cemetery.")
        elif any(keyword in text for keyword in ("active", "operational", "open")):
            score += ACTIVE_FLAG_WEIGHT
            signals.append(f"Official status field '{field}' suggests active cemetery.")

    bool_active = _coerce_bool(record.get("active"))
    bool_operational = _coerce_bool(record.get("operational")) or _coerce_bool(record.get("is_operational"))
    bool_open = _coerce_bool(record.get("open"))
    bool_closed = _coerce_bool(record.get("closed"))
    bool_abandoned = _coerce_bool(record.get("abandoned"))
    bool_historic = _coerce_bool(record.get("historic"))
    bool_inactive = _coerce_bool(record.get("inactive"))

    if any(flag is True for flag in (bool_active, bool_operational, bool_open)):
        score += ACTIVE_FLAG_WEIGHT
        signals.append("Boolean status fields indicate cemetery is active or operational.")
    if bool_closed is True:
        score += CLOSED_FLAG_WEIGHT
        closed = True
        signals.append("Boolean closed flag indicates cemetery is closed.")
    if any(flag is True for flag in (bool_abandoned, bool_historic, bool_inactive)):
        score += INACTIVE_FLAG_WEIGHT
        signals.append("Boolean status fields indicate cemetery is inactive, historic, or abandoned.")

    return {"score": score, "reasons": signals, "closed": closed}


def _score_data_freshness(record, now):

    last_updated = _find_latest_update_datetime(record)
    if last_updated is None:
        return 0, []

    age_days = (now - last_updated).days
    if age_days <= 365 * 2:
        return RECENT_UPDATE_WEIGHT, [f"Record was updated recently on {last_updated.date().isoformat()}."]
    if age_days >= 365 * 10:
        return STALE_UPDATE_WEIGHT, [f"Record has not been updated for many years since {last_updated.date().isoformat()}."]
    return 5, [f"Record has a moderate update age from {last_updated.date().isoformat()}."]


def _score_plot_availability(record):

    reasons = []
    score = 0

    available_plots = _coerce_int(
        record.get("available_plots")
        or record.get("plots_available")
        or record.get("plot_availability")
    )
    is_full = _coerce_bool(record.get("is_full"))
    full = _coerce_bool(record.get("full"))

    if available_plots == 0 or is_full is True or full is True:
        score += NO_PLOTS_WEIGHT
        reasons.append("No plots available or cemetery is marked full.")
    elif available_plots is not None and available_plots <= 10:
        score += LIMITED_PLOTS_WEIGHT
        reasons.append(f"Only limited plots appear available ({available_plots}).")

    return score, reasons


def _score_contact_metadata(record):

    signals = 0
    if record.get("website"):
        signals += 1
    if record.get("phone") or record.get("phone_number") or record.get("office_phone"):
        signals += 1
    if record.get("opening_hours") or record.get("office_hours"):
        signals += 1
    if record.get("caretaker") or record.get("manager") or record.get("operator"):
        signals += 1

    if signals == 0:
        return 0, []

    return CONTACT_WEIGHT, [f"Contact and metadata signals present ({signals} matched fields)."]


def _resolve_activity_status(score, explicit_closed, has_evidence):

    if explicit_closed:
        return CLOSED_CEMETERY_STATUS
    if not has_evidence:
        return UNKNOWN_CEMETERY_STATUS
    if score >= ACTIVITY_STATUS_HIGH_THRESHOLD:
        return ACTIVE_CEMETERY_STATUS
    if score >= ACTIVITY_STATUS_UNKNOWN_THRESHOLD:
        return UNKNOWN_CEMETERY_STATUS
    return INACTIVE_CEMETERY_STATUS


def _find_latest_burial_year(record):

    years = []
    for field in YEAR_FIELDS:
        year = _coerce_year(record.get(field))
        if year is not None:
            years.append(year)

    for list_field in ("burials", "interments", "burial_records", "interment_records"):
        value = record.get(list_field)
        if isinstance(value, list):
            for item in value:
                years.extend(_extract_years_from_nested(item))

    text_blob = " ".join(str(record.get(field, "")) for field in ("description", "notes"))
    years.extend(_extract_years_from_text(text_blob))

    valid_years = [year for year in years if 1600 <= year <= 3000]
    return max(valid_years) if valid_years else None


def _find_latest_update_datetime(record):

    dates = []
    for field in DATE_FIELDS:
        parsed = _coerce_datetime(record.get(field))
        if parsed is not None:
            dates.append(parsed)
    return max(dates) if dates else None


def _extract_years_from_nested(value):

    years = []
    if isinstance(value, dict):
        for nested_value in value.values():
            years.extend(_extract_years_from_nested(nested_value))
    elif isinstance(value, list):
        for nested_value in value:
            years.extend(_extract_years_from_nested(nested_value))
    else:
        year = _coerce_year(value)
        if year is not None:
            years.append(year)
    return years


def _extract_years_from_text(text):

    years = []
    for match in re.findall(r"\b(16\d{2}|17\d{2}|18\d{2}|19\d{2}|20\d{2}|21\d{2}|22\d{2}|23\d{2}|24\d{2}|25\d{2}|26\d{2}|27\d{2}|28\d{2}|29\d{2}|3000)\b", str(text or "")):
        year = _coerce_year(match)
        if year is not None:
            years.append(year)
    return years


def _coerce_year(value):

    if value is None or value == "":
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    match = re.search(r"\b(16\d{2}|17\d{2}|18\d{2}|19\d{2}|20\d{2}|21\d{2}|22\d{2}|23\d{2}|24\d{2}|25\d{2}|26\d{2}|27\d{2}|28\d{2}|29\d{2}|3000)\b", str(value))
    return int(match.group(1)) if match else None


def _coerce_datetime(value):

    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)

    text = str(value).strip()
    for candidate in (text, text.replace("Z", "+00:00")):
        try:
            parsed = datetime.fromisoformat(candidate)
            return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
        except ValueError:
            continue

    year = _coerce_year(text)
    if year is not None:
        return datetime(year, 1, 1, tzinfo=timezone.utc)

    return None


def _coerce_bool(value):

    if isinstance(value, bool):
        return value
    if value is None or value == "":
        return None
    text = str(value).strip().lower()
    if text in {"1", "true", "yes", "y", "open", "active", "operational"}:
        return True
    if text in {"0", "false", "no", "n", "closed", "inactive", "abandoned"}:
        return False
    return None


def _coerce_int(value):

    try:
        if value is None or value == "":
            return None
        return int(float(value))
    except (TypeError, ValueError):
        return None


def _normalize_status_value(value):

    if isinstance(value, list):
        return " ".join(str(item).strip().lower() for item in value if item not in (None, ""))
    return str(value or "").strip().lower()
