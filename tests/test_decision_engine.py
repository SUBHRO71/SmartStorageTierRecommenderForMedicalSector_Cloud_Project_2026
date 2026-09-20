import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src" / "ml_model"))

from decision_engine import DecisionEngine  # noqa: E402


class DecisionEngineTests(unittest.TestCase):
    def setUp(self):
        self.engine = DecisionEngine()

    def test_probability_increases_with_access_and_pathology_scores(self):
        low = self.engine.retrieval_probability(
            {"patient_age": 50, "finding_labels": "No Finding"}
        )["probability"]
        high = self.engine.retrieval_probability(
            {
                "patient_age": 50,
                "finding_labels": "Effusion",
                "access_count": 4,
                "follow_up_number": 2,
            },
            {"Effusion": 0.9},
        )["probability"]
        self.assertGreater(high, low)

    def test_monetary_cost_is_separate_from_access_penalty(self):
        result = self.engine.recommend(
            {"finding_labels": "Effusion"},
            {"Effusion": 0.8},
            size_bytes=15 * 1024 * 1024,
        )
        for costs in result["cost_breakdown"].values():
            self.assertAlmostEqual(
                costs["policy_score"],
                costs["monetary_cost"] + costs["access_delay_penalty"],
            )

    def test_small_objects_stay_in_standard(self):
        result = self.engine.recommend({}, size_bytes=64 * 1024)
        self.assertEqual(result["predicted_class"], "STANDARD")
        self.assertEqual(list(result["cost_breakdown"]), ["STANDARD"])

    def test_artifact_is_json_serializable(self):
        json.dumps(self.engine.recommend({}, size_bytes=1024 * 1024))


if __name__ == "__main__":
    unittest.main()
