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
from benchmark import metrics, grouped_folds


class BenchmarkTests(unittest.TestCase):
    def test_repeated_intervals_do_not_change_equal_subject_metrics(self):
        base = pd.DataFrame(dict(group=["A", "B", "C"], next_days=[70., 120., 150.]))
        repeated = pd.concat([base.iloc[[0]]] * 30 + [base.iloc[1:]], ignore_index=True)
        one = metrics(base, np.array([.9, .8, .1]), np.array([80., 100., 140.]))
        many = metrics(repeated, np.array([.9]*30+[.8, .1]), np.array([80.]*30+[100., 140.]))
        self.assertAlmostEqual(one["subject_weighted_balanced_accuracy_90d"], many["subject_weighted_balanced_accuracy_90d"])
        self.assertAlmostEqual(one["subject_weighted_mae_days"], many["subject_weighted_mae_days"])
        self.assertNotAlmostEqual(one["accuracy_90d"], many["accuracy_90d"])

    def test_outer_validation_never_shares_subjects_with_training(self):
        frame = pd.DataFrame([dict(group=f"P{i}", cohort="LUMIERE" if i%2 else "TCGA-GBM", next_days=30 if (i+j)%2 else 140) for i in range(30) for j in range(3)])
        folds = grouped_folds(frame, 5, 42)
        covered = []
        for train, valid in folds:
            self.assertFalse(set(frame.iloc[train].group) & set(frame.iloc[valid].group))
            covered.extend(valid)
        self.assertEqual(sorted(covered), list(range(len(frame))))


if __name__ == "__main__": unittest.main()
