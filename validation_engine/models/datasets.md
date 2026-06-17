# Training Dataset Formats

Starter CSVs are available in [models/sample_data](D:/WEB/Projects/AlgoSon's%20Intern/Data_Validation/validation_engine/models/sample_data).

## Cemetery Classifier CSV

Each row should represent one cemetery candidate record and include at minimum:

`label,name,notes,labels,address,city,state,zip_code,latitude,longitude,data_source,type,phone,website,opening_hours`

Example labels:

- `human_cemetery`
- `pet_cemetery`
- `ambiguous`
- `invalid`

The export script also adds helpful review columns like:

- `record_id`
- `source_collection`
- `predicted_type`
- `validation_status`
- `auto_label_hint`

## Duplicate Matcher CSV

Each row should represent a pair of records and include at minimum:

`label,left_name,right_name,left_address,right_address,left_city,right_city,left_state,right_state,left_zip_code,right_zip_code,left_type,right_type,left_latitude,left_longitude,right_latitude,right_longitude,left_trust_score,right_trust_score`

Where:

- `label=1` means duplicate
- `label=0` means not duplicate

The export script also includes hints to speed up labeling:

- `existing_duplicate_flag`
- `name_similarity_hint`
- `address_similarity_hint`
- `distance_km_hint`

## Export From Mongo

Generate labeling CSVs from your current Mongo data:

`python -m models.export_training_data --outdir models/exports`

Useful options:

- `--limit-per-collection 250`
- `--duplicate-limit 500`

## AI Confidence Validator CSV

Each row should represent one cemetery candidate record and include at minimum:

`label,name,city,county,state,zip_code,latitude,longitude,type,phone,website,email,gnis_match,findagrave_match,osm_match`

Where:

- `label=HIGH` means strong evidence the record is a legitimate cemetery
- `label=MEDIUM` means mixed evidence and likely spot-check flow
- `label=LOW` means weak or suspicious record needing manual review

Starter sample:

- [models/sample_data/ai_validation_training_sample.csv](D:/WEB/Projects/AlgoSon's%20Intern/Data_Validation/validation_engine/models/sample_data/ai_validation_training_sample.csv)

Train the confidence validator with:

`python -m models.train_ai_validator --dataset path/to/ai_validation_training.csv`
