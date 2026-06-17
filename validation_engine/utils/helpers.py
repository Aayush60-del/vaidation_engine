from datetime import datetime, timezone
from math import asin, cos, radians, sin, sqrt
import os
import re


def haversine_km(lat1, lon1, lat2, lon2):

    R = 6371

    dlat = radians(lat2 - lat1)
    dlon = radians(lon2 - lon1)

    a = (
        sin(dlat / 2) ** 2
        + cos(radians(lat1))
        * cos(radians(lat2))
        * sin(dlon / 2) ** 2
    )

    return R * 2 * asin(sqrt(a))


def coerce_float(value):

    try:
        if value is None or value == "":
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def normalize_text(value):

    text = str(value or "").strip().lower()
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def build_text_blob(record, fields):

    parts = []
    for field in fields:
        value = record.get(field)
        if isinstance(value, list):
            parts.append(" ".join(str(item) for item in value))
        elif isinstance(value, dict):
            parts.append(" ".join(f"{key} {val}" for key, val in value.items()))
        else:
            parts.append(str(value or ""))

    return normalize_text(" ".join(parts))


def build_address_text(record):

    parts = [
        record.get("address", ""),
        record.get("city", ""),
        record.get("state", ""),
        record.get("zip_code", "")
    ]
    return normalize_text(" ".join(str(part) for part in parts if part))


def utc_now():

    return datetime.now(timezone.utc)


def ensure_directory(path):

    os.makedirs(path, exist_ok=True)
