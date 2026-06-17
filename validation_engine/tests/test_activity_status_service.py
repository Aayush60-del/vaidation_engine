import unittest
from datetime import datetime, timezone

from services.activity_status_service import detect_activity_status


class ActivityStatusServiceTests(unittest.TestCase):

    def setUp(self):

        self.now = datetime(2026, 5, 25, tzinfo=timezone.utc)

    def test_marks_recent_active_cemetery_as_active(self):

        record = {
            "_id": "cem-1",
            "latest_burial_year": 2024,
            "active": True,
            "updated_at": "2025-07-01T00:00:00+00:00",
            "website": "https://example.org",
            "phone": "555-0101"
        }

        result = detect_activity_status(record, now=self.now)

        self.assertEqual(result["activity_status"], "ACTIVE")
        self.assertGreaterEqual(result["activity_confidence_score"], 60)
        self.assertIn("Recent burial activity found in 2024.", result["activity_reasons"])

    def test_marks_closed_cemetery_as_closed(self):

        record = {
            "_id": "cem-2",
            "status": "permanently closed",
            "latest_burial_year": 1980
        }

        result = detect_activity_status(record, now=self.now)

        self.assertEqual(result["activity_status"], "CLOSED")
        self.assertFalse(result["activity_status_needs_review"])

    def test_marks_old_unmaintained_cemetery_as_inactive(self):

        record = {
            "_id": "cem-3",
            "last_burial_year": 1989,
            "historic": True,
            "last_updated": "2000-01-01T00:00:00+00:00"
        }

        result = detect_activity_status(record, now=self.now)

        self.assertEqual(result["activity_status"], "INACTIVE")
        self.assertLess(result["activity_confidence_score"], 30)

    def test_returns_unknown_when_evidence_is_mixed(self):

        record = {
            "_id": "cem-4",
            "latest_burial_year": 2012,
            "updated_at": "2025-01-01T00:00:00+00:00",
            "website": "https://example.org",
            "phone_number": "555-0000"
        }

        result = detect_activity_status(record, now=self.now)

        self.assertEqual(result["activity_status"], "UNKNOWN")
        self.assertTrue(result["activity_status_needs_review"])

    def test_handles_missing_fields_safely(self):

        result = detect_activity_status({"_id": "cem-5"}, now=self.now)

        self.assertEqual(result["activity_status"], "UNKNOWN")
        self.assertEqual(result["latest_burial_year"], None)
        self.assertTrue(result["activity_reasons"])


if __name__ == "__main__":
    unittest.main()
