import importlib.util
import json
import sys
import types
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if "boto3" not in sys.modules:
    sys.modules["boto3"] = types.SimpleNamespace(client=lambda *a, **k: None, resource=lambda *a, **k: None)

path = ROOT / "aws" / "lambda" / "api_handler" / "handler.py"
spec = importlib.util.spec_from_file_location("cloud_api_handler", path)
cloud_api = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = cloud_api
spec.loader.exec_module(cloud_api)


class FakeTable:
    def __init__(self):
        self.item = {
            "scan_id": "scan-1",
            "bucket_name": "images",
            "object_key": "scans/one.png",
            "object_size_bytes": 15 * 1024 * 1024,
            "current_tier": "GLACIER",
            "finding_labels": "Effusion",
            "pathology_scores": {"Effusion": 0.8},
            "access_count": 1,
        }
        self.last_update = None

    def get_item(self, **kwargs):
        return {"Item": self.item} if kwargs["Key"]["scan_id"] == "scan-1" else {}

    def scan(self, **kwargs):
        return {"Items": [self.item]}

    def update_item(self, **kwargs):
        self.last_update = kwargs


class FakeS3:
    def __init__(self):
        self.tags = [{"Key": "owner", "Value": "radiology"}]
        self.restore_called = False
        self.copy_calls = []

    def get_object_tagging(self, **kwargs):
        return {"TagSet": self.tags}

    def put_object_tagging(self, **kwargs):
        self.tags = kwargs["Tagging"]["TagSet"]

    def restore_object(self, **kwargs):
        self.restore_called = True

    def copy_object(self, **kwargs):
        self.copy_calls.append(kwargs)


class FakeAuditTable:
    def __init__(self):
        self.items = []

    def put_item(self, **kwargs):
        self.items.append(kwargs["Item"])

    def query(self, **kwargs):
        return {"Items": list(reversed(self.items))}


class CloudApiHandlerTests(unittest.TestCase):
    def setUp(self):
        self.table, self.s3, self.audit = FakeTable(), FakeS3(), FakeAuditTable()
        cloud_api._resources = lambda: {"table": self.table, "s3": self.s3, "audit": self.audit}

    @staticmethod
    def event(resource, method="GET", payload=None, admin=False):
        return {
            "resource": resource,
            "httpMethod": method,
            "pathParameters": {"id": "scan-1"},
            "queryStringParameters": {},
            "body": json.dumps(payload or {}),
            "requestContext": {
                "authorizer": {"claims": {"cognito:groups": "archive-admin" if admin else "viewer"}}
            },
        }

    def payload(self, result):
        return json.loads(result["body"])

    def test_prediction_uses_real_policy_and_tags_object(self):
        self.table.item["current_tier"] = "STANDARD"
        result = cloud_api.lambda_handler(self.event("/api/scans/{id}/predict", "POST", admin=True), None)
        self.assertEqual(result["statusCode"], 200)
        self.assertIn(self.payload(result)["predicted_class"], cloud_api.VALID_TIERS)
        self.assertIn("tier", {tag["Key"] for tag in self.s3.tags})
        self.assertEqual(self.audit.items[-1]["event_type"], "PREDICTION_REQUESTED")

    def test_override_requires_admin_group(self):
        denied = cloud_api.lambda_handler(
            self.event("/api/scans/{id}/tier", "POST", {"tier": "STANDARD", "reason": "Urgent"}), None
        )
        self.assertEqual(denied["statusCode"], 403)
        restore_needed = cloud_api.lambda_handler(
            self.event("/api/scans/{id}/tier", "POST", {"tier": "STANDARD", "reason": "Urgent"}, admin=True), None
        )
        self.assertEqual(restore_needed["statusCode"], 409)
        self.table.item["restore_status"] = "COMPLETE"
        allowed = cloud_api.lambda_handler(
            self.event("/api/scans/{id}/tier", "POST", {"tier": "STANDARD", "reason": "Urgent"}, admin=True), None
        )
        self.assertEqual(allowed["statusCode"], 200)
        self.assertEqual(self.s3.copy_calls[-1]["StorageClass"], "STANDARD")

    def test_prediction_requires_mutation_role(self):
        result = cloud_api.lambda_handler(self.event("/api/scans/{id}/predict", "POST"), None)
        self.assertEqual(result["statusCode"], 403)

    def test_restore_calls_s3_for_archive(self):
        result = cloud_api.lambda_handler(
            self.event("/api/scans/{id}/restore", "POST", admin=True), None
        )
        self.assertEqual(result["statusCode"], 202)
        self.assertTrue(self.s3.restore_called)

    def test_dashboard_and_costs_are_computed(self):
        dashboard = cloud_api.lambda_handler(self.event("/api/dashboard/summary"), None)
        costs = cloud_api.lambda_handler(self.event("/api/costs"), None)
        self.assertEqual(self.payload(dashboard)["total_scans"], 1)
        self.assertEqual(len(self.payload(costs)["policies"]), 4)


if __name__ == "__main__":
    unittest.main()
