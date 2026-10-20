import copy
import importlib.util
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src/backend"))
sys.path.insert(0, str(ROOT / "src/ml_model/longitudinal"))
from temporal_forecast import forecast, features_from_history
from archive import policy

TRAINING_DEPS = all(importlib.util.find_spec(name) is not None for name in ("pandas", "sklearn"))


class TemporalTests(unittest.TestCase):
    @unittest.skipUnless(TRAINING_DEPS, "Install longitudinal training dependencies for data-building checks")
    def test_future_visit_cannot_change_current_features_and_terminal_unknown(self):
        import pandas as pd
        from data import examples
        first = pd.DataFrame([dict(cohort="LUMIERE", subject="A", day=d, timepoint=str(d)) for d in (0, 70, 140)])
        changed = first.copy(); changed.loc[2, "day"] = 280
        a, b = examples(first), examples(changed)
        for key in features_from_history([0, 70], "LUMIERE"):
            if pd.isna(a.iloc[1][key]): self.assertTrue(pd.isna(b.iloc[1][key]))
            else: self.assertEqual(a.iloc[1][key], b.iloc[1][key])
        self.assertTrue(pd.isna(a.iloc[-1].next_days))
        self.assertEqual(a.iloc[1].next_days, 70)
        self.assertEqual(b.iloc[1].next_days, 210)

    @unittest.skipUnless(TRAINING_DEPS and (ROOT / "dataset/raw/longitudinal/tcga/TCIA_TCGA-GBM_09-16-2015-nbia-digest.xlsx").is_file(), "Download publisher metadata for the source-audit integration check")
    def test_subjects_are_disjoint_and_source_counts_reproduce(self):
        from data import examples, assign_splits, load_visits
        visits, audit = load_visits()
        frame = assign_splits(examples(visits))
        self.assertEqual(frame.groupby(["cohort", "subject"]).split.nunique().max(), 1)
        self.assertEqual(int(frame.next_days.notna().sum()), 721)
        self.assertEqual(int(frame.next_days.isna().sum()), 350)
        self.assertEqual(audit["LUMIERE"]["distinct_weeks"], 589)

    def test_live_prediction_is_monotone_and_date_is_scenario_anchored(self):
        result = forecast([0, 49, 147], "LUMIERE", anchor="2026-10-20")
        self.assertLessEqual(result["probability_30d"], result["probability_60d"])
        self.assertLessEqual(result["probability_60d"], result["probability_90d"])
        self.assertFalse(result["actual_retrieval_model"])
        self.assertEqual(result["scenario_anchor_date"], "2026-10-20")
        self.assertLessEqual(result["interval_10_90_days"][0], result["median_days"])

    def test_invalid_context_is_rejected(self):
        for history in ([0, 0], [0, float("nan")], [0, -1], [0, "7"], [], "0,7"):
            with self.assertRaises(ValueError): forecast(history, "LUMIERE")
        with self.assertRaises(ValueError): forecast([0], "UNSEEN")
        with self.assertRaises(ValueError): forecast([0], "LUMIERE", masks=[])
        with self.assertRaises(ValueError): forecast([0], "LUMIERE", masks={"edema_fraction": 2})

    def test_hold_and_immediate_access_override_proxy_and_probability_is_not_count(self):
        study = dict(access=dict(hold=False, active=False, max_hours=12), complete=True,
                     clinical=dict(status="VERIFIED"), analysis=dict(status="NOT_RUN"), age_days=0,
                     objects=[dict(bytes=50*1024**2, tier="STANDARD") for _ in range(4)])
        study["forecast"] = dict(storage_scenario_enabled=True, probability_90d=.1, probability_30d=.01, model_id="test")
        decision = policy(study)
        self.assertEqual(decision["accesses"], .1)
        self.assertEqual(decision["horizon"], 3)
        self.assertFalse(next(c for c in decision["candidates"] if c["tier"] == "DEEP_ARCHIVE")["eligible"])
        study["access"]["hold"] = True
        self.assertEqual(policy(study)["tier"], "STANDARD")
        study["access"].update(hold=False, max_hours=0)
        self.assertEqual(policy(study)["tier"], "STANDARD")
        study["access"]["max_hours"] = 12
        study["forecast"]["probability_30d"] = .8
        self.assertEqual(policy(study)["tier"], "STANDARD")


if __name__ == "__main__": unittest.main()
