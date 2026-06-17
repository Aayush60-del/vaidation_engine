from pymongo import MongoClient
from pymongo.errors import ServerSelectionTimeoutError
import mongomock
from config import *

try:
    client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=2000)
    client.server_info()
except Exception as e:
    print(f"WARNING: Could not connect to MongoDB. Using in-memory mongomock database. Error: {e}")
    client = mongomock.MongoClient()

validation_db = client[VALIDATION_DB]

raw_collection = None
if RAW_DB and RAW_COLLECTION:
    raw_db = client[RAW_DB]
    raw_collection = raw_db[RAW_COLLECTION]

good_collection = validation_db[GOOD_COLLECTION]
review_collection = validation_db[REVIEW_COLLECTION]
reject_collection = validation_db[REJECT_COLLECTION]
audit_collection = validation_db[AUDIT_COLLECTION]
