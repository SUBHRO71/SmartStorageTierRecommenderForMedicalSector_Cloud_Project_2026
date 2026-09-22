import importlib.util
import sys
import types
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HANDLER_PATH = ROOT / "aws" / "lambda" / "tier_inference" / "handler.py"
if "boto3" not in sys.modules:
    sys.modules["boto3"] = types.SimpleNamespace(
        client=lambda *args, **kwargs: None,
        resource=lambda *args, **kwargs: None,
    )
spec = importlib.util.spec_from_file_location("tier_inference_handler", HANDLER_PATH)
handler = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = handler
spec.loader.exec_module(handler)


class FakeTable:
    def __init__(self, item=None):
        self.item = item
        self.update = None

    def get_item(self, **kwargs):
        return {"Item": self.item} if self.item else {}

    def update_item(self, **kwargs):
        self.update = kwargs


class FakeS3:
    def __init__(self):
        self.tags = [{"Key": "owner", "Value": "radiology"}]

    def get_object_tagging(self, **kwargs):
        return {"TagSet": self.tags}

    def put_object_tagging(self, **kwargs):
        self.tags = kwargs["Tagging"]["TagSet"]


class FakeCloudWatch:
    def put_metric_data(self, **kwargs):
        return None


class FakeAudit:
    def __init__(self):
        self.items = []

    def put_item(self, **kwargs):
        self.items.append(kwargs["Item"])


def event_record():
    return {
        "s3": {
            "bucket": {"name": "medical-image-store"},
            "object": {"key": "studies/patient-1/image.png", "size": 15 * 1024 * 1024},
        }
    }


class LambdaHandlerTests(unittest.TestCase):
    def resources(self, item=None):
        return {
            "table": FakeTable(item),
            "s3": FakeS3(),
            "cloudwatch": FakeCloudWatch(),
            "sns": object(),
            "audit": FakeAudit(),
        }

    def test_missing_features_are_blocked_and_not_tagged(self):
        resources = self.resources()
        result = handler.process_record(event_record(), resources, handler._engine())
        self.assertEqual(result["status"], "BLOCKED_MISSING_FEATURES")
        self.assertEqual(resources["s3"].tags, [{"Key": "owner", "Value": "radiology"}])

    def test_existing_tags_are_preserved_when_tier_is_added(self):
        resources = self.resources(
            {
                "scan_id": "placeholder",
                "patient_age": 65,
                "finding_labels": "Effusion",
                "pathology_scores": {"Effusion": 0.9},
            }
        )
        result = handler.process_record(event_record(), resources, handler._engine())
        tags = {entry["Key"]: entry["Value"] for entry in resources["s3"].tags}
        self.assertEqual(tags["owner"], "radiology")
        self.assertEqual(tags["tier"], result["tier"])
        self.assertEqual(result["status"], "PENDING_TRANSITION")


if __name__ == "__main__":
    unittest.main()
