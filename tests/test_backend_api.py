import os
import sys
import tempfile
import unittest
from pathlib import Path
from urllib.parse import quote

ROOT = Path(__file__).resolve().parents[1]
TEMP_DIR = tempfile.TemporaryDirectory()
os.environ["DATA_BACKEND"] = "sqlite"
os.environ["LOCAL_DB_PATH"] = str(Path(TEMP_DIR.name) / "test.db")
sys.path.insert(0, str(ROOT / "src" / "backend"))

from app import app  # noqa: E402


class BackendApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        app.config.update(TESTING=True)
        cls.client = app.test_client()

    def first_scan(self):
        response = self.client.get("/api/scans?limit=1")
        self.assertEqual(response.status_code, 200)
        return response.get_json()["scans"][0]

    def test_health_and_dashboard(self):
        health = self.client.get("/api/health")
        self.assertEqual(health.status_code, 200)
        self.assertEqual(health.get_json()["status"], "healthy")
        dashboard = self.client.get("/api/dashboard/summary")
        self.assertEqual(dashboard.status_code, 200)
        self.assertGreater(dashboard.get_json()["total_scans"], 0)

    def test_scan_detail_and_prediction(self):
        scan_id = quote(self.first_scan()["scan_id"], safe="")
        detail = self.client.get(f"/api/scans/{scan_id}")
        self.assertEqual(detail.status_code, 200)
        self.assertIn("cost_breakdown", detail.get_json())
        prediction = self.client.post(f"/api/scans/{scan_id}/predict")
        self.assertEqual(prediction.status_code, 200)
        self.assertIn(prediction.get_json()["predicted_class"], {"STANDARD", "STANDARD_IA", "GLACIER", "DEEP_ARCHIVE"})

    def test_override_requires_reason_and_restore_completes_locally(self):
        scan_id = quote(self.first_scan()["scan_id"], safe="")
        invalid = self.client.post(f"/api/scans/{scan_id}/tier", json={"tier": "GLACIER"})
        self.assertEqual(invalid.status_code, 400)
        override = self.client.post(
            f"/api/scans/{scan_id}/tier",
            json={"tier": "GLACIER", "reason": "Local integration test"},
        )
        self.assertEqual(override.status_code, 200)
        self.assertEqual(override.get_json()["decision_status"], "APPLIED_LOCAL")
        restore = self.client.post(f"/api/scans/{scan_id}/restore")
        self.assertEqual(restore.status_code, 200)
        self.assertEqual(restore.get_json()["restore_status"], "COMPLETE_LOCAL")
        detail = self.client.get(f"/api/scans/{scan_id}").get_json()
        self.assertGreaterEqual(len(detail["audit_history"]), 2)

    def test_costs_are_derived_from_current_records(self):
        response = self.client.get("/api/costs?horizon=12")
        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertEqual(payload["scope"], "simulation")
        self.assertEqual(len(payload["policies"]), 4)

    def test_invalid_query_is_rejected(self):
        response = self.client.get("/api/scans?limit=500")
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.get_json()["error"]["code"], "INVALID_PAGINATION")


if __name__ == "__main__":
    unittest.main()
