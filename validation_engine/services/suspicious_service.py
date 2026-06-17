from utils.helpers import coerce_float
from utils.constants import is_valid_us_location


def detect_suspicious(record):

    flags = []

    raw_lat = record.get("latitude")
    raw_lon = record.get("longitude")
    lat = coerce_float(raw_lat)
    lon = coerce_float(raw_lon)
    if raw_lat is None or raw_lon is None or raw_lat == "" or raw_lon == "":
        flags.append("missing_coordinates")
    elif lat is None or lon is None or not is_valid_us_location(lat, lon):
        flags.append("coordinates_out_of_us")

    name = str(record.get("name", "")).strip()
    normalized_name = name.lower()
    if len(name) < 4 or normalized_name.isdigit():
        flags.append("NAME_TOO_SHORT")
    if normalized_name in ["cemetery", "graveyard", "unknown"]:
        flags.append("NAME_GENERIC")

    if not record.get("city") and not record.get("zip_code"):
        flags.append("NO_LOCATION_DATA")

    if "funeral" in normalized_name and "cemetery" not in normalized_name:
        flags.append("POSSIBLE_FUNERAL_HOME")

    return flags
