from utils.helpers import coerce_float
from utils.constants import is_valid_us_location


def validate_geo(record):

    lat = coerce_float(record.get("latitude"))
    lon = coerce_float(record.get("longitude"))

    if lat is None or lon is None:
        return False

    return is_valid_us_location(lat, lon)
