import importlib.util
from pathlib import Path
import sys
import unittest

if not all(importlib.util.find_spec(name) for name in ("pandas", "sklearn", "sksurv", "xgboost")):
    raise unittest.SkipTest("Install local benchmark dependencies")
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src/ml_model/longitudinal"))
import numpy as np
import pandas as pd
from improvement_data import prior_features
from improve_xgboost import confidence_mask, selective_policy


class ImprovementTests(unittest.TestCase):
    def test_future_measurement_cannot_change_current_delta(self):
        frame = pd.DataFrame(dict(group=["A"]*3, day=[0, 30, 90], last_gap_days=[np.nan, 30, 60], volume=[10., 20., 30.]))
        changed = frame.copy(); changed.loc[2, "volume"] = 9999.
        original, altered = prior_features(frame, ["volume"]), prior_features(changed, ["volume"])
        for key in ("previous_volume", "change_volume", "rate_volume"):
            self.assertEqual(original.loc[1, key], altered.loc[1, key])
        self.assertEqual(original.loc[1, "previous_volume"], 10.)
        self.assertAlmostEqual(original.loc[1, "rate_volume"], 1/3)
        self.assertTrue(np.isnan(original.loc[0, "previous_volume"]))

    def test_selective_policy_requires_both_classes_and_meaningful_coverage(self):
        frame = pd.DataFrame(dict(group=[f"P{i//4}" for i in range(120)], next_days=[30.]*60+[120.]*60))
        # Confident majority-only output cannot claim a useful selective score.
        p = np.array([.99]*60+[.51]*60)
        self.assertIsNone(selective_policy(frame, p, .5))
        # Perfectly separated predictions can accept the complete population.
        p = np.array([.9]*60+[.1]*60)
        policy = selective_policy(frame, p, .5)
        self.assertEqual(policy["inner_coverage"], 1.)
        self.assertTrue(confidence_mask(p, .5, policy["cutoff"]).all())


if __name__ == "__main__": unittest.main()
