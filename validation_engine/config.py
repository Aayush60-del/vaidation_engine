from dotenv import load_dotenv
import os

load_dotenv()

MONGO_URI = os.getenv("MONGO_URI")

RAW_DB = os.getenv("RAW_DB")
RAW_COLLECTION = os.getenv("RAW_COLLECTION")

VALIDATION_DB = os.getenv("VALIDATION_DB")

GOOD_COLLECTION = os.getenv("GOOD_COLLECTION")
REVIEW_COLLECTION = os.getenv("REVIEW_COLLECTION")
REJECT_COLLECTION = os.getenv("REJECT_COLLECTION")
AUDIT_COLLECTION = os.getenv("AUDIT_COLLECTION", "validation_audit")

CRON_JOBS = [
    {"func": "run_dedup_sweep", "trigger": "cron", "hour": 2},
    {"func": "run_nlp_reclassify", "trigger": "cron", "day_of_week": "sun", "hour": 3},
    {"func": "run_geo_anomaly", "trigger": "cron", "day": 1, "hour": 4},
    {"func": "run_google_reenrich", "trigger": "cron", "month": "1,4,7,10", "day": 1},
    {"func": "generate_and_email_report", "trigger": "cron", "hour": 7}
]

MODEL_DIR = os.getenv("MODEL_DIR", "models/artifacts")
CLASSIFIER_MODEL_PATH = os.getenv(
    "CLASSIFIER_MODEL_PATH",
    os.path.join(MODEL_DIR, "cemetery_classifier.joblib")
)
DUPLICATE_MODEL_PATH = os.getenv(
    "DUPLICATE_MODEL_PATH",
    os.path.join(MODEL_DIR, "duplicate_matcher.joblib")
)
AI_VALIDATION_MODEL_PATH = os.getenv(
    "AI_VALIDATION_MODEL_PATH",
    os.path.join(MODEL_DIR, "ai_confidence_validator.joblib")
)
AI_VALIDATION_ENABLED = os.getenv("AI_VALIDATION_ENABLED", "true").lower() == "true"
AI_VALIDATION_LLM_ENABLED = os.getenv("AI_VALIDATION_LLM_ENABLED", "false").lower() == "true"
AI_VALIDATION_LLM_PROVIDER = os.getenv("AI_VALIDATION_LLM_PROVIDER", "openai").strip().lower()
AI_VALIDATION_LLM_MODEL = os.getenv("AI_VALIDATION_LLM_MODEL", "gpt-4.1-mini")
AI_VALIDATION_API_KEY = (
    os.getenv("AI_VALIDATION_API_KEY")
    or os.getenv("GEMINI_API_KEY")
    or ""
).strip()

NOMINATIM_ENABLED = os.getenv("NOMINATIM_ENABLED", "true").lower() == "true"
NOMINATIM_BASE_URL = os.getenv("NOMINATIM_BASE_URL", "https://nominatim.openstreetmap.org").strip().rstrip("/")
NOMINATIM_USER_AGENT = os.getenv("NOMINATIM_USER_AGENT", "validation-engine/1.0").strip()
NOMINATIM_EMAIL = os.getenv("NOMINATIM_EMAIL", "").strip()
NOMINATIM_TIMEOUT_SECONDS = int(os.getenv("NOMINATIM_TIMEOUT_SECONDS", "20"))

OVERPASS_API_URL = os.getenv("OVERPASS_API_URL", "https://overpass-api.de/api/interpreter").strip()
OVERPASS_RADIUS_METERS = int(os.getenv("OVERPASS_RADIUS_METERS", "500"))
OVERPASS_TIMEOUT_SECONDS = int(os.getenv("OVERPASS_TIMEOUT_SECONDS", "30"))
OVERPASS_MAX_RETRIES = int(os.getenv("OVERPASS_MAX_RETRIES", "2"))
OVERPASS_RATE_LIMIT_SECONDS = float(os.getenv("OVERPASS_RATE_LIMIT_SECONDS", "1.0"))
