# Cemetery Validation Engine

A MongoDB-backed cemetery validation pipeline that ingests raw cemetery candidates, evaluates data quality, classifies whether they are likely real cemeteries, detects ambiguity and duplicates, routes records into validation buckets, and generates reporting output.

This project is designed to work in two modes:

- rule-based validation out of the box
- ML-assisted validation when trained model artifacts are available
- AI-assisted confidence validation when external source matches or LLM access are available
- interactive CSV-driven intake from the local `Final_states_data 1 (1)/Final_states_data` folder
- optional OpenStreetMap Nominatim verification for reverse geocoding and cemetery locality checks

## What This Engine Does

The engine processes raw cemetery records and decides whether each one should be:

- `valid` and auto-accepted
- `review` and sent to a human review queue
- `quarantine` and rejected from trusted output

It also stores the reason behind those decisions so rejected and review records are easier to analyze later.

## Core Workflow

When you run:

```bash
python main.py
```

the engine executes this flow:

1. Create MongoDB indexes.
2. Ask which CSV file to load from the local state-data folder.
3. Ask how many records to verify.
3. Run ingestion gate checks.
4. Run full validation and enrichment.
5. Detect duplicate relationships and canonical records.
6. Route the record into `good`, `review`, or `reject`.
7. Store the result in `Validation_DB`.
8. Generate a daily JSON report.

The entrypoint is [main.py](D:/WEB/Projects/AlgoSon's%20Intern/Data_Validation/validation_engine/main.py).

## High-Level Architecture

### Entrypoint

- [main.py](D:/WEB/Projects/AlgoSon's%20Intern/Data_Validation/validation_engine/main.py)
  Initializes indexes, runs the pipeline, and generates the daily report.

### Pipeline

- [validator/pipeline.py](D:/WEB/Projects/AlgoSon's%20Intern/Data_Validation/validation_engine/validator/pipeline.py)
  Orchestrates the batch process from raw ingestion to routing.

- [validator/validate_record.py](D:/WEB/Projects/AlgoSon's%20Intern/Data_Validation/validation_engine/validator/validate_record.py)
  Applies full validation logic to a single record and attaches final decision reasons.

- [validator/routing.py](D:/WEB/Projects/AlgoSon's%20Intern/Data_Validation/validation_engine/validator/routing.py)
  Sends validated records to the correct Mongo collection and writes audit events for review and reject flows.

### Database Layer

- [db/mongo.py](D:/WEB/Projects/AlgoSon's%20Intern/Data_Validation/validation_engine/db/mongo.py)
  Central MongoDB connection and collection mapping.

- [db/indexes.py](D:/WEB/Projects/AlgoSon's%20Intern/Data_Validation/validation_engine/db/indexes.py)
  Creates validation, duplicate, text, geospatial, and audit indexes.

- [db/schemas.py](D:/WEB/Projects/AlgoSon's%20Intern/Data_Validation/validation_engine/db/schemas.py)
  Defines required fields and simple schema helpers.

### Services

- [services/ingestion_service.py](D:/WEB/Projects/AlgoSon's%20Intern/Data_Validation/validation_engine/services/ingestion_service.py)
  Prompts for a local CSV file, prompts for a record limit, and normalizes rows into validation-ready records.

- [services/ingestion_gate.py](D:/WEB/Projects/AlgoSon's%20Intern/Data_Validation/validation_engine/services/ingestion_gate.py)
  Runs fast pre-checks before full validation, including required fields, geo bounds, name sanity, duplicate pre-flagging, and initial trust scoring.

- [services/trust_service.py](D:/WEB/Projects/AlgoSon's%20Intern/Data_Validation/validation_engine/services/trust_service.py)
  Computes a data quality trust score.

- [services/classifier_service.py](D:/WEB/Projects/AlgoSon's%20Intern/Data_Validation/validation_engine/services/classifier_service.py)
  Predicts cemetery type using ML if a trained model exists, otherwise falls back to rules.

- [services/ambiguity_service.py](D:/WEB/Projects/AlgoSon's%20Intern/Data_Validation/validation_engine/services/ambiguity_service.py)
  Determines whether the record is clearly a cemetery, probably one, ambiguous, or likely not a cemetery.

- [services/suspicious_service.py](D:/WEB/Projects/AlgoSon's%20Intern/Data_Validation/validation_engine/services/suspicious_service.py)
  Flags suspicious cases such as bad geo, generic names, or likely funeral homes.

- [services/geo_service.py](D:/WEB/Projects/AlgoSon's%20Intern/Data_Validation/validation_engine/services/geo_service.py)
  Validates geographic coordinates against the supported US bounds.

- [services/duplicate_service.py](D:/WEB/Projects/AlgoSon's%20Intern/Data_Validation/validation_engine/services/duplicate_service.py)
  Detects exact, near, and soft duplicates, and manages canonical record selection.

- [services/decision_reason_service.py](D:/WEB/Projects/AlgoSon's%20Intern/Data_Validation/validation_engine/services/decision_reason_service.py)
  Builds structured reason codes and summaries explaining why a record was validated, reviewed, quarantined, or rejected.

- [services/ai_validation_service.py](D:/WEB/Projects/AlgoSon's%20Intern/Data_Validation/validation_engine/services/ai_validation_service.py)
  Runs the optional 4th-layer confidence validator using GNIS/FindAGrave/OSM match fields when present, a local HIGH/MEDIUM/LOW ML model, and optional LLM escalation for uncertain records.

- [services/nominatim_service.py](D:/WEB/Projects/AlgoSon's%20Intern/Data_Validation/validation_engine/services/nominatim_service.py)
  Uses the free Nominatim API to reverse-geocode coordinates, compare nearby locality details, and attempt a lightweight cemetery search match.

### Reporting

- [reports/metrics.py](D:/WEB/Projects/AlgoSon's%20Intern/Data_Validation/validation_engine/reports/metrics.py)
  Builds validation, ambiguity, duplicate, state-quality, and reason-code metrics.

- [reports/daily_report.py](D:/WEB/Projects/AlgoSon's%20Intern/Data_Validation/validation_engine/reports/daily_report.py)
  Writes a daily JSON report to `output/reports/`.

### ML Layer

- [models/inference.py](D:/WEB/Projects/AlgoSon's%20Intern/Data_Validation/validation_engine/models/inference.py)
  Loads trained artifacts and runs classifier or duplicate predictions when available.

- [models/train_classifier.py](D:/WEB/Projects/AlgoSon's%20Intern/Data_Validation/validation_engine/models/train_classifier.py)
  Trains a cemetery type classifier from labeled CSV data.

- [models/train_duplicate_model.py](D:/WEB/Projects/AlgoSon's%20Intern/Data_Validation/validation_engine/models/train_duplicate_model.py)
  Trains a duplicate matcher from labeled record pairs.

- [models/train_ai_validator.py](D:/WEB/Projects/AlgoSon's%20Intern/Data_Validation/validation_engine/models/train_ai_validator.py)
  Trains a HIGH/MEDIUM/LOW confidence model for the AI validation layer.

- [models/export_training_data.py](D:/WEB/Projects/AlgoSon's%20Intern/Data_Validation/validation_engine/models/export_training_data.py)
  Exports records from Mongo into CSV files for human labeling.

## Validation Workflow in Detail

### Step 1: Ingestion Gate

The ingestion gate stops obvious bad data early.

Checks include:

- required fields present: `name`, `latitude`, `longitude`
- US bounding box validation
- invalid or too-generic names
- fast duplicate pre-check
- initial trust score assignment

Possible outcomes:

- reject immediately and log to `validation_audit`
- quarantine for later rejection
- mark for review
- pass through to full validation

### Step 2: Trust Score

The trust score estimates record quality using signals such as:

- name quality
- geo validity
- address completeness
- data source quality
- cemetery type clarity
- enrichment fields like phone, website, and opening hours
- OSM tag confidence

Thresholds:

- `>= 75` -> candidate for auto-validation
- `40-74` -> review range
- `< 40` -> quarantine range

### Step 3: Cemetery Type Classification

The engine predicts:

- `human_cemetery`
- `pet_cemetery`
- `ambiguous`
- `invalid`

Runtime behavior:

- if a trained model artifact exists, use ML inference
- if not, use the built-in rule-based keyword logic

### Step 4: Ambiguity Analysis

The ambiguity layer classifies a record into a higher-level interpretation such as:

- `definite_cemetery`
- `probable_cemetery`
- `ambiguous`
- `not_cemetery`

This helps separate true cemeteries from things like:

- memorial parks
- funeral homes
- cremation services
- generic memorial sites

### Step 5: Suspicious Entry Detection

This adds flags for suspicious patterns, for example:

- geo out of bounds
- too-short or numeric names
- missing location data
- likely funeral home misclassification

These flags can trigger human review even when the trust score is high.

### Step 6: Cemetery Activity Status

The engine also estimates whether a cemetery appears:

- `ACTIVE`
- `INACTIVE`
- `CLOSED`
- `UNKNOWN`

It uses a scoring-based detector in [services/activity_status_service.py](D:/WEB/Projects/AlgoSon's%20Intern/Data_Validation/validation_engine/services/activity_status_service.py) with safe fallbacks for missing data.

Signals checked:

- recent burial or interment year
- official status fields like active, operational, closed, abandoned, historic, inactive
- record freshness from fields like `updated_at` or `last_updated`
- plot availability such as `available_plots`, `plot_availability`, or full flags
- contact metadata such as website, phone, hours, and caretaker/operator fields

Example score behavior:

- `+40` recent burial within 5 years
- `+30` official active/open/operational signal
- `+15` recently updated
- `+10` contact metadata present
- `-40` no burial in 20+ years
- `-45` explicit closed signal

Output fields added to records:

- `activity_status`
- `activity_confidence_score`
- `activity_reasons`

### Step 7: Nominatim Locality Verification

The engine can also call the public OpenStreetMap Nominatim service to check:

- whether the coordinates resolve to the expected nearby locality
- whether a cemetery-like place name can be found from the record text

Important operational notes:

- no API key is required for the public Nominatim service
- a valid custom `User-Agent` is required
- the public policy limits usage to an absolute maximum of 1 request per second
- for heavier production volume, use your own Nominatim instance or another provider

Relevant stored fields:

- `nominatim_confidence`
- `nominatim_summary`
- `nearby_locality`

### Step 8: Duplicate Detection

The duplicate layer checks:

- exact duplicate
- near duplicate using fuzzy name match plus spatial proximity
- soft duplicate using address similarity plus alias-like name similarity

For duplicate clusters:

- the highest trust-score record becomes canonical
- related records store `canonical_id`
- non-canonical records store `merged_into`

### Step 9: Final Decision

The engine assigns:

- `valid`
- `review`
- `quarantine`

This decision is based on:

- predicted type
- ambiguity action
- trust score
- AI validation confidence
- suspicious flags
- review requirements
- duplicate signals

### Step 10: Decision Reason Storage

Every review or rejected record stores why it landed there.

Important fields:

- `decision_reasons`
- `decision_reason_codes`
- `decision_summary`

Examples:

- `LOW_TRUST_SCORE`
- `LOW_CLASSIFICATION_CONFIDENCE`
- `AMBIGUOUS_CEMETERY_SIGNAL`
- `POSSIBLE_DUPLICATE`
- `INVALID_TYPE_CLASSIFICATION`
- `SUSPICIOUS_FLAG`

This makes later analysis much easier in Mongo queries and daily reports.

## Mongo Collections

The engine uses these logical collections:

- raw collection
  Source records awaiting processing.

- good collection
  Auto-validated trusted records.

- review collection
  Human review queue.

- reject collection
  Quarantined or rejected records.

- validation audit collection
  Audit trail for explicit rejects and routing events.

Collection names come from environment variables in [config.py](D:/WEB/Projects/AlgoSon's%20Intern/Data_Validation/validation_engine/config.py).

## Output Data Fields

After validation, records may include fields like:

- `trust_score`
- `geo_valid`
- `predicted_type`
- `classification_confidence`
- `classification_source`
- `ambiguity_category`
- `ambiguity_confidence`
- `activity_status`
- `activity_confidence_score`
- `activity_reasons`
- `flags`
- `dq_flags`
- `is_duplicate`
- `duplicate_type`
- `canonical_id`
- `is_canonical`
- `merged_into`
- `validation_status`
- `ai_validation_score`
- `ai_validation_confidence_level`
- `ai_validation_action`
- `ai_validation_summary`
- `ai_validation_issues`
- `review_required`
- `decision_reasons`
- `decision_reason_codes`
- `decision_summary`

## Reporting Workflow

The daily reporting layer generates:

- total processed counts
- valid percentage
- review queue size
- quarantined count
- duplicate cluster metrics
- ambiguity counts
- per-state quality metrics
- top review, reject, and audit reason codes

Output location:

- `output/reports/report_YYYY-MM-DD.json`

## ML-Ready Workflow

This project is already structured so you can start with rules and later move to ML.

### Training Data Export

Export Mongo data into labeling CSVs:

```bash
python -m models.export_training_data --outdir models/exports
```

### Sample Labeling Files

Starter sample CSVs are available in:

- [models/sample_data/cemetery_training_sample.csv](D:/WEB/Projects/AlgoSon's%20Intern/Data_Validation/validation_engine/models/sample_data/cemetery_training_sample.csv)
- [models/sample_data/duplicate_pairs_sample.csv](D:/WEB/Projects/AlgoSon's%20Intern/Data_Validation/validation_engine/models/sample_data/duplicate_pairs_sample.csv)

### Train the Classifier

```bash
python -m models.train_classifier --dataset path/to/cemetery_training.csv
```

### Train the Duplicate Model

```bash
python -m models.train_duplicate_model --dataset path/to/duplicate_pairs.csv
```

### Runtime Behavior

If model artifacts exist:

- classifier service uses ML predictions
- duplicate service can use ML duplicate probability
- AI validation service can predict `HIGH`, `MEDIUM`, or `LOW` confidence

If artifacts or ML dependencies do not exist:

- the system falls back to built-in rule logic

## Tools and Libraries Used

### Core Runtime

- `Python`
  Main implementation language.

- `pymongo`
  MongoDB client for data access and indexing.

- `python-dotenv`
  Loads environment variables from `.env`.

### Validation and Matching

- `rapidfuzz`
  Fuzzy matching for duplicate detection and similarity scoring.

- `geopy`
  Included dependency for geo-related extension work.

### Reporting and Scheduling

- `pandas`
  Used for model training dataset handling.

- `apscheduler`
  Present for future scheduled jobs such as nightly dedup sweeps and reclassification passes.

### ML

- `scikit-learn`
  Training pipelines for classification and duplicate matching.

- `joblib`
  Model artifact persistence.

## Configuration

Set the required environment variables:

```env
MONGO_URI=
RAW_DB=
RAW_COLLECTION=
VALIDATION_DB=
GOOD_COLLECTION=
REVIEW_COLLECTION=
REJECT_COLLECTION=
AUDIT_COLLECTION=validation_audit
MODEL_DIR=models/artifacts
CLASSIFIER_MODEL_PATH=models/artifacts/cemetery_classifier.joblib
DUPLICATE_MODEL_PATH=models/artifacts/duplicate_matcher.joblib
AI_VALIDATION_MODEL_PATH=models/artifacts/ai_confidence_validator.joblib
AI_VALIDATION_ENABLED=true
AI_VALIDATION_LLM_ENABLED=false
AI_VALIDATION_LLM_PROVIDER=openai
AI_VALIDATION_LLM_MODEL=gpt-4.1-mini
AI_VALIDATION_API_KEY=
NOMINATIM_ENABLED=true
NOMINATIM_USER_AGENT=validation-engine/1.0
NOMINATIM_EMAIL=
```

You do not need an API key for the public Nominatim service. The official policy instead requires a valid identifying `User-Agent`, and asks bulk users to include an email address.

Gemini is also supported for the optional AI validation layer. To use it:

- set `AI_VALIDATION_LLM_PROVIDER=gemini`
- set `AI_VALIDATION_LLM_MODEL=gemini-2.5-flash` or another Gemini text model
- set `GEMINI_API_KEY` or `GOOGLE_API_KEY` in your environment, or reuse `AI_VALIDATION_API_KEY`

The current official Python SDK is `google-genai`, which is included in [requirements.txt](D:/WEB/Projects/AlgoSon's%20Intern/Data_Validation/validation_engine/requirements.txt).

## How To Run

### Install Dependencies

```bash
pip install -r requirements.txt
```

### Run the Pipeline

```bash
python main.py
```

The script will then ask:

- which CSV file to load, for example `DE_records.csv`
- how many rows to verify, for example `25` or `all`

### Compact Existing Validation Records

If older Mongo documents still contain the full verbose validation payload, you can trim them to the current compact schema:

```bash
python -m scripts.compact_validation_db --dry-run
python -m scripts.compact_validation_db
```

### Manual OSM Verification Check

For a small live Overpass/Nominatim-style diagnostic against local CSV data:

```bash
python -m scripts.osm_verification_check
```

### What Happens After Run

- indexes are created
- unprocessed raw records are fetched
- records are validated and routed
- source records are marked with `validation_processed = True`
- daily report JSON is generated

## Future Workflow Extensions

The structure is ready for:

- scheduled cron execution
- email reporting
- active learning from human review corrections
- retraining pipelines
- geo anomaly sweeps
- re-enrichment passes from external providers

## Summary

This validation engine is a structured cemetery data quality pipeline with:

- ingestion gating
- trust scoring
- cemetery classification
- ambiguity detection
- duplicate resolution
- reason-aware routing
- audit logging
- daily reporting
- ML-ready training and inference hooks

It is useful both as a production validation workflow and as a foundation for a smarter ML-assisted cemetery data platform.
