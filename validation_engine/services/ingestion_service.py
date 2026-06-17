from pathlib import Path

import pandas as pd
from bson import ObjectId


DATA_FOLDER = Path(__file__).resolve().parents[2] / "Final_states_data 1 (1)" / "Final_states_data"


def fetch_records(limit=100):

    csv_files = sorted(DATA_FOLDER.glob("*.csv"))
    if not csv_files:
        raise FileNotFoundError(f"No CSV files found in {DATA_FOLDER}")

    selected_file = _prompt_for_csv(csv_files)
    selected_limit = _prompt_for_limit(limit)

    df = pd.read_csv(selected_file).fillna("")
    if selected_limit is not None:
        df = df.head(selected_limit)

    records = [
        _normalize_record(row, selected_file.name, index)
        for index, row in enumerate(df.to_dict(orient="records"), start=1)
    ]

    print(f"Loaded {len(records)} records from {selected_file.name}")
    return records


def _prompt_for_csv(csv_files):

    print("\nAvailable CSV files:")
    for index, csv_file in enumerate(csv_files, start=1):
        print(f"{index}. {csv_file.name}")

    while True:
        choice = input("\nEnter CSV number or exact file name: ").strip()
        if not choice:
            print("Please choose a CSV file.")
            continue

        if choice.isdigit():
            position = int(choice)
            if 1 <= position <= len(csv_files):
                return csv_files[position - 1]

        for csv_file in csv_files:
            if choice.lower() in {csv_file.name.lower(), csv_file.stem.lower()}:
                return csv_file

        print("Invalid selection. Please enter a listed number or exact file name.")


def _prompt_for_limit(default_limit):

    while True:
        choice = input(
            f"How many records do you want to verify? Press Enter for {default_limit}, or type 'all': "
        ).strip().lower()

        if not choice:
            return default_limit
        if choice == "all":
            return None
        if choice.isdigit() and int(choice) > 0:
            return int(choice)

        print("Please enter a positive number or 'all'.")


def _normalize_record(row, source_file, row_number):

    record = dict(row)
    record["_id"] = ObjectId()
    record["source_file"] = source_file
    record["source_row_number"] = row_number
    record["data_source"] = record.get("data_source") or f"csv:{source_file}"

    if not record.get("address") and record.get("street_address"):
        record["address"] = record.get("street_address")

    if not record.get("phone") and record.get("phone_number"):
        record["phone"] = record.get("phone_number")

    if "is_operational" in record:
        record["is_operational"] = _coerce_bool(record.get("is_operational"))

    return record


def _coerce_bool(value):

    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "y"}
