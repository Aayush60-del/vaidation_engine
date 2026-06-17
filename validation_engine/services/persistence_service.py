def build_persisted_record(record):

    # Contact/profile metadata is optional for many rural and historical
    # cemeteries. Persist its completeness for reporting, but never treat empty
    # optional fields as a reason to drop an otherwise OSM-verified record.
    primary_trust_signals = {
        "osm_found": record.get("osm_found"),
        "name_match_passed": record.get("name_match_passed"),
        "location_match": record.get("location_match"),
        "type_match": record.get("type_match"),
        "candidate_count": record.get("candidate_count"),
        "multiple_nearby_candidates": record.get("multiple_nearby_candidates"),
        "confidence_score": record.get("confidence_score")
    }
    optional_metadata = {
        "has_phone": bool(record.get("phone") or record.get("phone_number")),
        "has_website": bool(record.get("website")),
        "has_email": bool(record.get("email")),
        "has_zip_code": bool(record.get("zip_code")),
        "has_description": bool(record.get("description"))
    }

    persisted = {
        "_id": record.get("_id"),
        "name": record.get("name"),
        "country": record.get("country"),
        "state": record.get("state"),
        "county": record.get("county"),
        "city": record.get("city"),
        "address": record.get("address") or record.get("street_address"),
        "street_address": record.get("street_address"),
        "zip_code": record.get("zip_code"),
        "latitude": _safe_float(record.get("latitude")),
        "longitude": _safe_float(record.get("longitude")),
        "phone": record.get("phone") or record.get("phone_number"),
        "phone_number": record.get("phone_number"),
        "website": record.get("website"),
        "email": record.get("email"),
        "type": record.get("type"),
        "is_operational": record.get("is_operational"),
        "description": record.get("description"),
        "source_file": record.get("source_file"),
        "source_row_number": record.get("source_row_number"),
        "data_source": record.get("data_source"),
        "sparse_dataset_mode": record.get("sparse_dataset_mode"),
        "structurally_complete": record.get("structurally_complete"),
        "metadata_penalty_applied": record.get("metadata_penalty_applied"),
        "trust_score": record.get("trust_score"),
        "validation_status": record.get("validation_status"),
        "validated_at": record.get("validated_at"),
        "geo_valid": record.get("geo_valid"),
        "location": record.get("location"),
        "nominatim_checked": record.get("nominatim_checked"),
        "nominatim_confidence": record.get("nominatim_confidence"),
        "nominatim_summary": record.get("nominatim_summary"),
        "nearby_locality": record.get("nearby_locality"),
        "city_coordinate_check": record.get("city_coordinate_check"),
        "overpass_checked": record.get("overpass_checked"),
        "osm_found": record.get("osm_found"),
        "osm_match": record.get("osm_match"),
        "osm_name": record.get("osm_name"),
        "osm_id": record.get("osm_id"),
        "osm_type": record.get("osm_type"),
        "osm_lat": record.get("osm_lat"),
        "osm_lon": record.get("osm_lon"),
        "osm_distance_m": record.get("osm_distance_m"),
        "osm_name_score": record.get("osm_name_score"),
        "osm_summary": record.get("osm_summary"),
        "osm_tags": record.get("osm_tags"),
        "distance_meters": record.get("distance_meters"),
        "location_match": record.get("location_match"),
        "fuzzy_match_score": record.get("fuzzy_match_score"),
        "name_match_passed": record.get("name_match_passed"),
        "type_match": record.get("type_match"),
        "candidate_count": record.get("candidate_count"),
        "multiple_nearby_candidates": record.get("multiple_nearby_candidates"),
        "confidence_score": record.get("confidence_score"),
        "verification_status": record.get("verification_status"),
        "verification_reasons": record.get("verification_reasons"),
        "osm_data": record.get("osm_data"),
        "primary_trust_signals": primary_trust_signals,
        "optional_metadata": optional_metadata,
        "optional_metadata_policy": "optional_not_penalized",
        "predicted_type": record.get("predicted_type"),
        "classification_confidence": record.get("classification_confidence"),
        "classification_source": record.get("classification_source"),
        "ambiguity_category": record.get("ambiguity_category"),
        "ambiguity_confidence": record.get("ambiguity_confidence"),
        "activity_status": record.get("activity_status"),
        "activity_confidence_score": record.get("activity_confidence_score"),
        "activity_reasons": record.get("activity_reasons"),
        "ai_validation_score": record.get("ai_validation_score"),
        "ai_validation_external_matches": record.get("ai_validation_external_matches"),
        "ai_validation_confidence_level": record.get("ai_validation_confidence_level"),
        "ai_validation_action": record.get("ai_validation_action"),
        "ai_validation_summary": record.get("ai_validation_summary"),
        "flags": record.get("flags"),
        "review_required": record.get("review_required"),
        "dq_flags": record.get("dq_flags"),
        "is_duplicate": record.get("is_duplicate"),
        "duplicate_type": record.get("duplicate_type"),
        "is_canonical": record.get("is_canonical"),
        "canonical_id": record.get("canonical_id"),
        "merged_into": record.get("merged_into"),
        "decision_reasons": record.get("decision_reasons"),
        "decision_reason_codes": record.get("decision_reason_codes"),
        "decision_summary": record.get("decision_summary")
    }

    return drop_empty_values(persisted)


def _safe_float(value):

    try:
        if value is None or value == "":
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def drop_empty_values(value):

    if isinstance(value, dict):
        cleaned = {}
        for key, item in value.items():
            normalized = drop_empty_values(item)
            if normalized in (None, "", [], {}):
                continue
            cleaned[key] = normalized
        return cleaned

    if isinstance(value, list):
        return [
            item for item in (drop_empty_values(entry) for entry in value)
            if item not in (None, "", [], {})
        ]

    return value
