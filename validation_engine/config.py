import os

from dotenv import find_dotenv, load_dotenv

ENV_PATH = find_dotenv()
load_dotenv(dotenv_path=ENV_PATH, override=True)

def _env(name, default=None, required=False):
    value = os.getenv(name, default)
    if required and value in (None, ""):
        raise RuntimeError(f"{name} is not set. Define it in a .env file.")
    return value


def _env_bool(name, default=False):
    value = os.getenv(name)
    if value in (None, ""):
        return default
    return str(value).strip().lower() in {"1", "true", "yes", "y", "on"}


def _env_int(name, default):
    try:
        return int(os.getenv(name, default))
    except (TypeError, ValueError):
        return default


def _env_float(name, default):
    try:
        return float(os.getenv(name, default))
    except (TypeError, ValueError):
        return default


MONGO_URI = _env("MONGO_URI", required=True)
if not MONGO_URI:
    raise RuntimeError("MONGO_URI is not set. Define it in a .env file.")

RAW_DB = _env("RAW_DB")
RAW_COLLECTION = _env("RAW_COLLECTION")

VALIDATION_DB = _env("VALIDATION_DB", required=True)

GOOD_COLLECTION = _env("GOOD_COLLECTION", required=True)
REVIEW_COLLECTION = _env("REVIEW_COLLECTION", required=True)
REJECT_COLLECTION = _env("REJECT_COLLECTION", required=True)
AUDIT_COLLECTION = _env("AUDIT_COLLECTION", required=True)

CRON_JOBS = [
    {"func": "run_dedup_sweep", "trigger": "cron", "hour": 2},
    {"func": "run_nlp_reclassify", "trigger": "cron", "day_of_week": "sun", "hour": 3},
    {"func": "run_geo_anomaly", "trigger": "cron", "day": 1, "hour": 4},
    {"func": "run_google_reenrich", "trigger": "cron", "month": "1,4,7,10", "day": 1},
    {"func": "generate_and_email_report", "trigger": "cron", "hour": 7}
]

MODEL_DIR = "models/artifacts"
CLASSIFIER_MODEL_PATH = os.path.join(MODEL_DIR, "cemetery_classifier.joblib")
DUPLICATE_MODEL_PATH = os.path.join(MODEL_DIR, "duplicate_matcher.joblib")
AI_VALIDATION_MODEL_PATH = os.path.join(MODEL_DIR, "ai_confidence_validator.joblib")

AI_VALIDATION_ENABLED = _env_bool("AI_VALIDATION_ENABLED", True)
AI_VALIDATION_LLM_ENABLED = _env_bool("AI_VALIDATION_LLM_ENABLED", False)
AI_VALIDATION_LLM_PROVIDER = _env("AI_VALIDATION_LLM_PROVIDER", "openai")
AI_VALIDATION_LLM_MODEL = _env("AI_VALIDATION_LLM_MODEL", "gpt-4.1-mini")
AI_VALIDATION_API_KEY = (
    _env("AI_VALIDATION_API_KEY")
    or _env("GEMINI_API_KEY")
    or _env("GOOGLE_API_KEY")
)

NOMINATIM_ENABLED = _env_bool("NOMINATIM_ENABLED", True)
NOMINATIM_BASE_URL = _env("NOMINATIM_BASE_URL", "https://nominatim.openstreetmap.org")
NOMINATIM_USER_AGENT = _env("NOMINATIM_USER_AGENT", "validation-engine/1.0")
NOMINATIM_EMAIL = _env("NOMINATIM_EMAIL", "")
NOMINATIM_TIMEOUT_SECONDS = _env_int("NOMINATIM_TIMEOUT_SECONDS", 20)

OVERPASS_API_URL = _env("OVERPASS_API_URL", "https://overpass-api.de/api/interpreter")
OVERPASS_RADIUS_METERS = _env_int("OVERPASS_RADIUS_METERS", 500)
OVERPASS_TIMEOUT_SECONDS = _env_int("OVERPASS_TIMEOUT_SECONDS", 30)
OVERPASS_MAX_RETRIES = _env_int("OVERPASS_MAX_RETRIES", 2)
OVERPASS_RATE_LIMIT_SECONDS = _env_float("OVERPASS_RATE_LIMIT_SECONDS", 1.0)

# Threading Configuration
THREADING_ENABLED = _env_bool("THREADING_ENABLED", True)
MAX_WORKER_THREADS = _env_int("MAX_WORKER_THREADS", 8)
BATCH_SIZE = _env_int("BATCH_SIZE", 100)
QUEUE_TIMEOUT_SECONDS = _env_float("QUEUE_TIMEOUT_SECONDS", 30.0)

# Cache Configuration
CACHE_ENABLED = _env_bool("CACHE_ENABLED", True)
CACHE_TTL_SECONDS = _env_int("CACHE_TTL_SECONDS", 86400)  # 24 hours default
CACHE_NOMINATIM = _env_bool("CACHE_NOMINATIM", True)
CACHE_OVERPASS = _env_bool("CACHE_OVERPASS", True)
CACHE_AI_VALIDATION = _env_bool("CACHE_AI_VALIDATION", True)

# AI Validation Optimization
AI_VALIDATION_SKIP_HIGH_CONFIDENCE = _env_bool("AI_VALIDATION_SKIP_HIGH_CONFIDENCE", True)
AI_VALIDATION_MIN_TRUST_SCORE_FOR_LLM = _env_float("AI_VALIDATION_MIN_TRUST_SCORE_FOR_LLM", 0.90)

# Duplicate Prevention at Insert
DUPLICATE_CHECK_ON_INSERT = _env_bool("DUPLICATE_CHECK_ON_INSERT", True)
DUPLICATE_CHECK_DISTANCE_METERS = _env_int("DUPLICATE_CHECK_DISTANCE_METERS", 500)  # 500m = 0.5km
