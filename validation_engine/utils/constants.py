VALID_THRESHOLD = 75
REVIEW_THRESHOLD = 40

US_BOUNDS = [
    (24.396308, 49.384358, -124.848974, -66.885444),  # contiguous
    (51.214183, 71.365162, -179.148909, -129.9795),   # Alaska
    (18.910361, 28.402123, -178.334698, -154.806773), # Hawaii
]


def is_valid_us_location(lat, lon):

    try:
        lat, lon = float(lat), float(lon)
    except (TypeError, ValueError):
        return False

    return any(
        min_lat <= lat <= max_lat and min_lon <= lon <= max_lon
        for min_lat, max_lat, min_lon, max_lon in US_BOUNDS
    )

VALID_STATUS = "valid"
REVIEW_STATUS = "review"
QUARANTINE_STATUS = "quarantine"
REJECTED_STATUS = "rejected"

ACTIVE_CEMETERY_STATUS = "ACTIVE"
INACTIVE_CEMETERY_STATUS = "INACTIVE"
CLOSED_CEMETERY_STATUS = "CLOSED"
UNKNOWN_CEMETERY_STATUS = "UNKNOWN"

HUMAN_CEMETERY_KEYWORDS = [
    "cemetery",
    "cemetary",
    "burial",
    "grave",
    "graveyard",
    "burial ground",
    "memorial garden",
    "mausoleum",
    "rest",
    "eternal"
]

PET_KEYWORDS = [
    "pet",
    "animal",
    "dog",
    "cat",
    "beloved companion"
]

AMBIGUOUS_KEYWORDS = [
    "memorial park",
    "veterans memorial",
    "crematory",
    "funeral home",
    "cremation services",
    "memorial",
    "garden",
    "park"
]

INVALID_KEYWORDS = [
    "parking",
    "park and ride",
    "storage",
    "plaza",
    "mortuary"
]

AMBIGUITY_HIERARCHY = {
    "definite_cemetery": {
        "osm_tags": ["amenity=grave_yard", "landuse=cemetery", "historic=cemetery", "cemetery=yes"],
        "name_patterns": ["cemetery", "cemetary", "graveyard", "burial ground"],
        "confidence": 0.95
    },
    "probable_cemetery": {
        "name_patterns": ["memorial garden", "rest haven", "eternal rest"],
        "requires_geo_confirm": True,
        "confidence": 0.75
    },
    "ambiguous": {
        "name_patterns": ["memorial park", "memorial", "garden", "park"],
        "confidence": 0.4,
        "escalate_to_human": True
    },
    "not_cemetery": {
        "name_patterns": ["funeral home", "cremation services", "mortuary"],
        "confidence": 0.85,
        "action": "reject"
    }
}

CLEAR_TYPES = ["cemetery", "grave_yard", "burial_ground"]
DUPLICATE_NAME_THRESHOLD = 80
DUPLICATE_DISTANCE_KM = 0.5
SOFT_DUPLICATE_ADDRESS_THRESHOLD = 85
SOFT_DUPLICATE_NAME_THRESHOLD = 70

ACTIVITY_STATUS_HIGH_THRESHOLD = 60
ACTIVITY_STATUS_UNKNOWN_THRESHOLD = 30
