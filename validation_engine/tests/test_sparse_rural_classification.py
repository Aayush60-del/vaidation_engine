import unittest
from unittest.mock import patch

from services.duplicate_service import near_duplicate_score, soft_match
from services.ai_validation_service import _should_invoke_llm, run_ai_validation
from services.persistence_service import build_persisted_record
from utils.constants import VALID_STATUS
from validator.routing import route_record
from validator.validate_record import validate_record


def _sparse_alaska_record(name="Lost Harbor Cemetery"):

    return {
        "_id": f"ak-{name.lower().replace(' ', '-')}",
        "name": name,
        "country": "United States",
        "state": "Alaska",
        "county": "Aleutians East Borough",
        "city": "Lost Harbor (historical)",
        "street_address": "Lost Harbor (historical)",
        "zip_code": "",
        "latitude": 54.2453243,
        "longitude": -165.6148784,
        "email": "",
        "website": "",
        "phone_number": "",
        "type": "human",
        "is_operational": True,
        "description": "",
        "data_source": "GraveAngles",
    }


def _sparse_idaho_record(name="Miller Creek Cemetery"):

    return {
        "_id": f"id-{name.lower().replace(' ', '-')}",
        "name": name,
        "country": "United States",
        "state": "Idaho",
        "county": "Owyhee County",
        "city": "Miller Creek Settlement",
        "street_address": "Miller Creek Settlement",
        "zip_code": "",
        "latitude": 42.0687506,
        "longitude": -116.1477362,
        "email": "",
        "website": "",
        "phone_number": "",
        "type": "human",
        "is_operational": True,
        "description": "",
        "data_source": "GraveAngles",
    }


def _strong_osm_result(record):

    return {
        "overpass_checked": True,
        "osm_found": True,
        "osm_match": True,
        "osm_name": record["name"],
        "osm_id": 8178017546,
        "osm_type": "grave_yard",
        "osm_lat": record["latitude"],
        "osm_lon": record["longitude"],
        "osm_distance_m": 0.0,
        "osm_name_score": 100.0,
        "osm_tags": {"amenity": "grave_yard", "name": record["name"]},
        "osm_summary": "OSM cemetery object found.",
        "distance_meters": 0.0,
        "location_match": True,
        "fuzzy_match_score": 100.0,
        "name_match_passed": True,
        "type_match": True,
        "candidate_count": 1,
        "multiple_nearby_candidates": False,
        "confidence_score": 100,
        "verification_status": "VERIFIED",
        "verification_reasons": ["OSM cemetery object found."],
        "osm_data": {"osm_id": 8178017546},
    }


class SparseRuralClassificationTests(unittest.TestCase):

    @patch("validator.validate_record.apply_canonical_decision")
    @patch("validator.validate_record.run_ai_validation")
    @patch("validator.validate_record.verify_with_overpass")
    @patch("validator.validate_record.enrich_with_nominatim")
    def test_sparse_osm_verified_alaska_cemetery_is_valid(
        self,
        mock_nominatim,
        mock_overpass,
        mock_ai_validation,
        mock_canonical,
    ):

        record = _sparse_alaska_record()
        mock_nominatim.return_value = {
            "nominatim_checked": False,
            "nominatim_confidence": 0.0,
            "nominatim_summary": "Nominatim disabled for unit test.",
            "nearby_locality": None,
            "osm_match": False,
        }
        mock_overpass.side_effect = lambda row: _strong_osm_result(row)
        mock_ai_validation.return_value = {
            "ai_validation_confidence_level": "HIGH",
            "ai_validation_action": "auto_approve",
            "ai_validation_score": 5,
            "ai_validation_issues": [],
        }

        def mark_canonical(row):
            row["is_duplicate"] = False
            row["is_canonical"] = True
            row["canonical_id"] = row.get("_id")
            row["merged_into"] = None
            return row

        mock_canonical.side_effect = mark_canonical

        validated = validate_record(record)

        self.assertEqual(validated["validation_status"], VALID_STATUS)
        self.assertGreaterEqual(validated["trust_score"], 75)
        self.assertTrue(validated["osm_found"])
        self.assertTrue(validated["name_match_passed"])
        self.assertTrue(validated["location_match"])
        self.assertGreaterEqual(validated["confidence_score"], 70)
        self.assertTrue(validated["sparse_dataset_mode"])
        self.assertTrue(validated["structurally_complete"])
        self.assertFalse(validated["metadata_penalty_applied"])

    @patch("validator.validate_record.apply_canonical_decision")
    @patch("validator.validate_record.run_ai_validation")
    @patch("validator.validate_record.verify_with_overpass")
    @patch("validator.validate_record.enrich_with_nominatim")
    def test_sparse_osm_verified_idaho_cemetery_is_valid(
        self,
        mock_nominatim,
        mock_overpass,
        mock_ai_validation,
        mock_canonical,
    ):

        record = _sparse_idaho_record()
        mock_nominatim.return_value = {
            "nominatim_checked": False,
            "nominatim_confidence": 0.0,
            "nominatim_summary": "Nominatim disabled for unit test.",
            "nearby_locality": None,
            "osm_match": False,
        }
        mock_overpass.side_effect = lambda row: _strong_osm_result(row)
        mock_ai_validation.return_value = {
            "ai_validation_confidence_level": "HIGH",
            "ai_validation_action": "auto_approve",
            "ai_validation_score": 5,
            "ai_validation_issues": [],
        }

        def mark_canonical(row):
            row["is_duplicate"] = False
            row["is_canonical"] = True
            row["canonical_id"] = row.get("_id")
            row["merged_into"] = None
            return row

        mock_canonical.side_effect = mark_canonical

        validated = validate_record(record)

        self.assertEqual(validated["validation_status"], VALID_STATUS)
        self.assertGreaterEqual(validated["trust_score"], 75)
        self.assertTrue(validated["sparse_dataset_mode"])
        self.assertTrue(validated["osm_found"])
        self.assertTrue(validated["name_match_passed"])
        self.assertTrue(validated["location_match"])

    def test_persistence_keeps_optional_metadata_policy_for_sparse_record(self):

        record = _sparse_alaska_record()
        record.update(_strong_osm_result(record))
        record.update({
            "validation_status": VALID_STATUS,
            "sparse_dataset_mode": True,
            "structurally_complete": True,
            "metadata_penalty_applied": False,
            "trust_score": 100,
            "validated_at": "2026-05-25T00:00:00Z",
        })

        persisted = build_persisted_record(record)

        self.assertEqual(persisted["optional_metadata_policy"], "optional_not_penalized")
        self.assertTrue(persisted["sparse_dataset_mode"])
        self.assertTrue(persisted["structurally_complete"])
        self.assertFalse(persisted["metadata_penalty_applied"])
        self.assertFalse(persisted["optional_metadata"]["has_phone"])
        self.assertFalse(persisted["optional_metadata"]["has_website"])
        self.assertFalse(persisted["optional_metadata"]["has_email"])
        self.assertFalse(persisted["optional_metadata"]["has_zip_code"])
        self.assertTrue(persisted["primary_trust_signals"]["osm_found"])

    @patch("validator.routing.audit_collection")
    @patch("validator.routing.reject_collection")
    @patch("validator.routing.review_collection")
    @patch("validator.routing.good_collection")
    def test_valid_sparse_record_routes_to_good_collection(
        self,
        mock_good,
        mock_review,
        mock_reject,
        mock_audit,
    ):

        record = _sparse_alaska_record()
        record.update(_strong_osm_result(record))
        record["validation_status"] = VALID_STATUS

        destination = route_record(record)

        self.assertEqual(destination, "good")
        mock_good.replace_one.assert_called_once()
        mock_review.delete_one.assert_called_once()
        mock_reject.delete_one.assert_called_once()
        mock_good.insert_one.assert_not_called()
        mock_review.insert_one.assert_not_called()
        mock_reject.insert_one.assert_not_called()
        mock_audit.insert_one.assert_not_called()

    @patch("services.ai_validation_service.predict_ai_validation", return_value=None)
    def test_ai_validation_does_not_flag_missing_optional_metadata(self, _mock_model):

        record = _sparse_alaska_record()
        record["osm_match"] = True

        result = run_ai_validation(record)

        self.assertEqual(result["ai_validation_confidence_level"], "HIGH")
        self.assertEqual(result["ai_validation_action"], "auto_approve")
        self.assertNotIn("missing_phone", result["ai_validation_issues"])
        self.assertNotIn("missing_website", result["ai_validation_issues"])
        self.assertNotIn("missing_zip_code", result["ai_validation_issues"])

    @patch("services.ai_validation_service.AI_VALIDATION_LLM_ENABLED", True)
    @patch("services.ai_validation_service._resolved_llm_api_key", return_value="test-key")
    def test_medium_trust_score_can_trigger_llm_escalation(self, _mock_api_key):

        record = {
            "trust_score": 50,
            "classification_confidence": 0.9,
        }

        self.assertTrue(_should_invoke_llm(record, 0, 0, 0, None))

    @patch("services.duplicate_service.predict_duplicate_probability", return_value=None)
    def test_common_cemetery_names_are_not_duplicates_across_counties(self, _mock_model):

        boise_pioneer = {
            "name": "Pioneer Cemetery",
            "state": "Idaho",
            "county": "Ada County",
            "city": "Boise",
            "latitude": 43.6109822,
            "longitude": -116.1895459,
        }
        horseshoe_pioneer = {
            "name": "Pioneer Cemetery",
            "state": "Idaho",
            "county": "Boise County",
            "city": "Horseshoe Bend",
            "latitude": 43.9033558,
            "longitude": -116.1918224,
        }

        self.assertEqual(near_duplicate_score(boise_pioneer, horseshoe_pioneer), 0)
        self.assertFalse(soft_match(boise_pioneer, horseshoe_pioneer))

    @patch("services.duplicate_service.predict_duplicate_probability", return_value=None)
    def test_common_cemetery_names_are_not_duplicates_when_far_apart(self, _mock_model):

        first = {
            "name": "Mountain View Cemetery",
            "state": "Idaho",
            "county": "Elmore County",
            "city": "Mountain Home",
            "latitude": 43.1367036,
            "longitude": -115.6793487,
            "street_address": "Mountain Home",
        }
        second = {
            "name": "Mountain View Cemetery",
            "state": "Idaho",
            "county": "Elmore County",
            "city": "Distant",
            "latitude": 43.2367036,
            "longitude": -115.6793487,
            "street_address": "Mountain Home",
        }

        self.assertEqual(near_duplicate_score(first, second), 0)
        self.assertFalse(soft_match(first, second))


if __name__ == "__main__":
    unittest.main()
