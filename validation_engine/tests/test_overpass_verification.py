import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import pandas as pd

from services.overpass_service import build_overpass_query, verify_with_overpass


DATA_FOLDER = Path(__file__).resolve().parents[2] / "Final_states_data 1 (1)" / "Final_states_data"


class OverpassVerificationTests(unittest.TestCase):

    def setUp(self):

        self.sample_record = _load_ak_sample("Lost Harbor Cemetery")

    @patch("services.overpass_service.time.sleep", return_value=None)
    @patch("services.overpass_service.requests.Session.post")
    def test_exact_node_match_verifies(self, mock_post, _mock_sleep):

        mock_post.return_value = _response({
            "elements": [{
                "type": "node",
                "id": 8178017546,
                "lat": self.sample_record["latitude"],
                "lon": self.sample_record["longitude"],
                "tags": {
                    "amenity": "grave_yard",
                    "name": self.sample_record["name"],
                },
            }]
        })

        result = verify_with_overpass(self.sample_record)

        self.assertTrue(result["osm_found"])
        self.assertTrue(result["name_match_passed"])
        self.assertTrue(result["location_match"])
        self.assertTrue(result["type_match"])
        self.assertEqual(result["verification_status"], "VERIFIED")
        self.assertGreaterEqual(result["confidence_score"], 90)

    @patch("services.overpass_service.time.sleep", return_value=None)
    @patch("services.overpass_service.requests.Session.post")
    def test_fuzzy_name_match_passes(self, mock_post, _mock_sleep):

        record = dict(self.sample_record)
        record["name"] = "Saint Mary Cemetery"
        mock_post.return_value = _response({
            "elements": [{
                "type": "node",
                "id": 1,
                "lat": record["latitude"],
                "lon": record["longitude"],
                "tags": {"landuse": "cemetery", "name": "St. Mary's Cemetery"},
            }]
        })

        result = verify_with_overpass(record)

        self.assertGreaterEqual(result["fuzzy_match_score"], 70)
        self.assertTrue(result["name_match_passed"])

    def test_missing_coordinates_does_not_call_api(self):

        result = verify_with_overpass({"name": "Missing Coordinates", "type": "human"})

        self.assertFalse(result["overpass_checked"])
        self.assertFalse(result["osm_found"])
        self.assertEqual(result["verification_status"], "WEAK_MATCH")

    @patch("services.overpass_service.time.sleep", return_value=None)
    @patch("services.overpass_service.requests.Session.post")
    def test_invalid_csv_type_does_not_type_match(self, mock_post, _mock_sleep):

        record = dict(self.sample_record)
        record["type"] = "parking"
        mock_post.return_value = _response({
            "elements": [{
                "type": "node",
                "id": 2,
                "lat": record["latitude"],
                "lon": record["longitude"],
                "tags": {"amenity": "grave_yard", "name": record["name"]},
            }]
        })

        result = verify_with_overpass(record)

        self.assertFalse(result["type_match"])
        self.assertEqual(result["confidence_score"], 90)

    @patch("services.overpass_service.time.sleep", return_value=None)
    @patch("services.overpass_service.requests.Session.post")
    def test_no_nearby_cemetery_returns_weak_match(self, mock_post, _mock_sleep):

        mock_post.return_value = _response({"elements": []})

        result = verify_with_overpass(self.sample_record)

        self.assertTrue(result["overpass_checked"])
        self.assertFalse(result["osm_found"])
        self.assertEqual(result["verification_status"], "WEAK_MATCH")

    @patch("services.overpass_service.time.sleep", return_value=None)
    @patch("services.overpass_service.requests.Session.post")
    def test_way_center_coordinates_are_used(self, mock_post, _mock_sleep):

        mock_post.return_value = _response({
            "elements": [{
                "type": "way",
                "id": 292071003,
                "center": {
                    "lat": self.sample_record["latitude"],
                    "lon": self.sample_record["longitude"],
                },
                "tags": {"landuse": "cemetery", "name": self.sample_record["name"]},
            }]
        })

        result = verify_with_overpass(self.sample_record)

        self.assertEqual(result["osm_lat"], self.sample_record["latitude"])
        self.assertEqual(result["osm_lon"], self.sample_record["longitude"])
        self.assertTrue(result["location_match"])

    @patch("services.overpass_service.time.sleep", return_value=None)
    @patch("services.overpass_service.requests.Session.post")
    def test_radius_validation_fails_when_object_is_too_far(self, mock_post, _mock_sleep):

        mock_post.return_value = _response({
            "elements": [{
                "type": "node",
                "id": 3,
                "lat": self.sample_record["latitude"] + 0.1,
                "lon": self.sample_record["longitude"],
                "tags": {"landuse": "cemetery", "name": self.sample_record["name"]},
            }]
        })

        result = verify_with_overpass(self.sample_record, radius_meters=500)

        self.assertFalse(result["location_match"])
        self.assertLess(result["confidence_score"], 90)

    @patch("services.overpass_service.time.sleep", return_value=None)
    @patch("services.overpass_service.requests.Session.post")
    def test_multiple_nearby_candidates_are_reported(self, mock_post, _mock_sleep):

        mock_post.return_value = _response({
            "elements": [
                {
                    "type": "node",
                    "id": 10,
                    "lat": self.sample_record["latitude"],
                    "lon": self.sample_record["longitude"],
                    "tags": {"amenity": "grave_yard", "name": self.sample_record["name"]},
                },
                {
                    "type": "node",
                    "id": 11,
                    "lat": self.sample_record["latitude"],
                    "lon": self.sample_record["longitude"],
                    "tags": {"landuse": "cemetery", "name": "Nearby Cemetery"},
                },
            ]
        })

        result = verify_with_overpass(self.sample_record)

        self.assertEqual(result["candidate_count"], 2)
        self.assertTrue(result["multiple_nearby_candidates"])

    def test_query_uses_nwr_and_out_center(self):

        query = build_overpass_query(55.3425964, -160.4969301, 500)

        self.assertIn('nwr["amenity"="grave_yard"]', query)
        self.assertIn('nwr["landuse"="cemetery"]', query)
        self.assertIn('nwr["historic"="cemetery"]', query)
        self.assertIn('nwr["cemetery"="yes"]', query)
        self.assertIn("out center;", query)


def _load_ak_sample(name):

    df = pd.read_csv(DATA_FOLDER / "AK_records.csv").fillna("")
    row = df[df["name"].astype(str) == name].iloc[0].to_dict()
    row["type"] = "human"
    return row


def _response(payload):

    response = Mock()
    response.status_code = 200
    response.json.return_value = payload
    response.raise_for_status.return_value = None
    return response


if __name__ == "__main__":
    unittest.main()
