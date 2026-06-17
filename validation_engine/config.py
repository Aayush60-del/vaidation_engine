import os

MONGO_URI = os.getenv("MONGO_URI")

RAW_DB = os.getenv("RAW_DB")
RAW_COLLECTION = os.getenv("RAW_COLLECTION")

VALIDATION_DB = os.getenv("VALIDATION_DB")

GOOD_COLLECTION = os.getenv("GOOD_COLLECTION")
REVIEW_COLLECTION = os.getenv("REVIEW_COLLECTION")
REJECT_COLLECTION = os.getenv("REJECT_COLLECTION")
AUDIT_COLLECTION = os.getenv("AUDIT_COLLECTION")

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

AI_VALIDATION_ENABLED = True
AI_VALIDATION_LLM_ENABLED = False
AI_VALIDATION_LLM_PROVIDER = "openai"
AI_VALIDATION_LLM_MODEL = "gpt-4.1-mini"
AI_VALIDATION_API_KEY = ""

NOMINATIM_ENABLED = True
NOMINATIM_BASE_URL = "https://nominatim.openstreetmap.org"
NOMINATIM_USER_AGENT = "validation-engine/1.0"
NOMINATIM_EMAIL = ""
NOMINATIM_TIMEOUT_SECONDS = 20

OVERPASS_API_URL = "https://overpass-api.de/api/interpreter"
OVERPASS_RADIUS_METERS = 500
OVERPASS_TIMEOUT_SECONDS = 30
OVERPASS_MAX_RETRIES = 2
OVERPASS_RATE_LIMIT_SECONDS = 1.0

# Threading Configuration
THREADING_ENABLED = True
MAX_WORKER_THREADS = 8
BATCH_SIZE = 100
QUEUE_TIMEOUT_SECONDS = 30.0
