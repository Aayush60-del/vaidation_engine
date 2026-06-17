from pathlib import Path

import config


def _redact(value):
    if not value:
        return value
    text = str(value)
    if "://" in text and "@" in text:
        prefix, rest = text.split("://", 1)
        return f"{prefix}://<redacted>@{rest.split('@', 1)[1]}"
    if len(text) > 12:
        return f"{text[:4]}...<redacted>"
    return "<redacted>"


print("=== DIAGNOSTIC: Config Values Loaded From .env ===")
print(f"ENV_PATH = {Path(config.ENV_PATH).resolve() if config.ENV_PATH else '<not found>'}")
print(f"MONGO_URI = {_redact(config.MONGO_URI)}")
print(f"RAW_DB = {config.RAW_DB}")
print(f"RAW_COLLECTION = {config.RAW_COLLECTION}")
print(f"VALIDATION_DB = {config.VALIDATION_DB}")
print(f"GOOD_COLLECTION = {config.GOOD_COLLECTION}")
print(f"REVIEW_COLLECTION = {config.REVIEW_COLLECTION}")
print(f"REJECT_COLLECTION = {config.REJECT_COLLECTION}")
print(f"AUDIT_COLLECTION = {config.AUDIT_COLLECTION}")
print(f"AI_VALIDATION_ENABLED = {config.AI_VALIDATION_ENABLED}")
print(f"AI_VALIDATION_LLM_ENABLED = {config.AI_VALIDATION_LLM_ENABLED}")
print(f"AI_VALIDATION_LLM_PROVIDER = {config.AI_VALIDATION_LLM_PROVIDER}")
print(f"AI_VALIDATION_LLM_MODEL = {config.AI_VALIDATION_LLM_MODEL}")
print(f"AI_VALIDATION_API_KEY set = {bool(config.AI_VALIDATION_API_KEY)}")
print(f"NOMINATIM_ENABLED = {config.NOMINATIM_ENABLED}")
print(f"NOMINATIM_USER_AGENT = {config.NOMINATIM_USER_AGENT}")
print(f"NOMINATIM_EMAIL = {config.NOMINATIM_EMAIL}")
print(f"OVERPASS_API_URL = {config.OVERPASS_API_URL}")
print(f"OVERPASS_RADIUS_METERS = {config.OVERPASS_RADIUS_METERS}")
print(f"OVERPASS_TIMEOUT_SECONDS = {config.OVERPASS_TIMEOUT_SECONDS}")
print(f"OVERPASS_MAX_RETRIES = {config.OVERPASS_MAX_RETRIES}")
print(f"OVERPASS_RATE_LIMIT_SECONDS = {config.OVERPASS_RATE_LIMIT_SECONDS}")
