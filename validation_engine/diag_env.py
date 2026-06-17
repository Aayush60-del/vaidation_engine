import os

print("=== DIAGNOSTIC: Environment Variable Loading Order ===")
print()

# Step 1: Check BEFORE load_dotenv
print("STEP 1: BEFORE load_dotenv()")
raw_value = os.getenv("MONGO_URI")
print(f"  os.getenv('MONGO_URI') = {repr(raw_value)}")
print()

# Step 2: Load dotenv
from dotenv import load_dotenv
result = load_dotenv()
print(f"STEP 2: load_dotenv() returned: {result}")
after_value = os.getenv("MONGO_URI")
print(f"  os.getenv('MONGO_URI') = {repr(after_value)}")
print()

# Step 3: Import config (this is where config.MONGO_URI gets set)
import config
print(f"STEP 3: config.MONGO_URI = {repr(config.MONGO_URI)}")
print()

# Step 4: Now simulate what happens when main.py runs
print("=== SIMULATING main.py IMPORT ORDER ===")
print("In main.py, line 4 does: from validator.pipeline import run_pipeline")
print("This triggers the following import chain:")
print("  validator/pipeline.py -> services/ingestion_service.py -> db/mongo.py -> config.py")
print()
print("CRITICAL: config.py line 3 executes: MONGO_URI = os.getenv('MONGO_URI')")
print(f"At that moment, os.getenv('MONGO_URI') was: {repr(config.MONGO_URI)}")
print()

# Step 5: Check if the .env file is where we expect it
import pathlib
env_path = pathlib.Path(".env")
print(f"STEP 5: .env file exists at {env_path.resolve()}: {env_path.exists()}")
if env_path.exists():
    print(f"  Contents:")
    for line in env_path.read_text().splitlines():
        print(f"    {line}")
