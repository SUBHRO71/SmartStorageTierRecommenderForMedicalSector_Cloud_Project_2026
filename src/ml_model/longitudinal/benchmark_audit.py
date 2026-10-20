"""Verify local model persistence and compare a deterministic history rule."""
import argparse
import hashlib
import json
import pickle
from pathlib import Path
import numpy as np
import pandas as pd
from benchmark import ROOT, metrics, bootstrap, write_json
from benchmark_data import build_frame


def audit(run_id):
    public = ROOT / "experiments/longitudinal" / run_id
    private = ROOT / "dataset/processed/longitudinal/benchmarks" / run_id
    meta = json.loads((public / "protocol.json").read_text())
    results = json.loads((public / "results.json").read_text())
    # Rebuild from the unmodified publisher files. The human-readable JSON
    # snapshot rounds floats; exact inference verification uses original inputs.
    frame, _ = build_frame()
    if hashlib.sha256(frame.to_json(orient="records").encode()).hexdigest() != meta["input_sha256"]:
        raise AssertionError("Publisher inputs differ from the completed run")
    frame.to_pickle(private / "input_examples_full_precision.pkl")
    dev = frame[frame.next_days.notna() & (frame.split != "test")].reset_index(drop=True)
    test = frame[frame.next_days.notna() & (frame.split == "test")].reset_index(drop=True)
    baseline = pd.read_csv(private / "baseline_oof_predictions.csv").set_index("row_id").loc[dev.row_id]
    rule_days = baseline.last_gap_days.to_numpy()
    rule_prob = (rule_days <= 90).astype(float)
    rule_metrics = metrics(dev, rule_prob, rule_days)
    model_checks, comparisons = {}, {}
    for result in results:
        family = result["family"]
        path = private / f"models/{family}.pkl"
        if hashlib.sha256(path.read_bytes()).hexdigest() != result["artifact_sha256"]:
            raise AssertionError("Artifact checksum mismatch")
        # Only load artifacts just produced by this local trusted benchmark.
        with path.open("rb") as stream: bundle = pickle.load(stream)
        p = bundle["classifier"].predict(test)[0]
        d = bundle["regressor"].predict(test)[1]
        saved = pd.read_csv(private / f"{family}_inspected_holdout_predictions.csv").set_index("row_id").loc[test.row_id]
        p_error = float(np.max(np.abs(p-saved.probability_90d)))
        d_error = float(np.max(np.abs(d-saved.predicted_days)))
        # XGBoost returns float32; its CSV output retains float32 display
        # precision. Compare at its storage precision, not float64 bit accuracy.
        if p_error > 1e-6 or d_error > .001: raise AssertionError("Reloaded model predictions differ")
        model_checks[family] = dict(probability_max_error=p_error, timing_max_error_days=d_error, checksum_verified=True)
        prediction = pd.read_csv(private / f"{family}_nested_oof_predictions.csv").set_index("row_id").loc[dev.row_id]
        comparisons[family] = bootstrap(dev, prediction.probability_90d.to_numpy(), prediction.predicted_days.to_numpy(),
                                       prediction.threshold.to_numpy(), rule_prob, rule_days)
    production_sha = hashlib.sha256((ROOT / "src/ml_model/longitudinal_model.json").read_bytes()).hexdigest()
    if production_sha != meta["production_model_sha256_before"]: raise AssertionError("Production model changed")
    summary = dict(model_bundles_verified=len(model_checks), roundtrip=model_checks,
        production_artifact_unchanged=True, production_sha256=production_sha,
        development_long_tail=dict(intervals_over_365_days=int(sum(dev.next_days > 365)),
            subjects_with_interval_over_365_days=int(dev[dev.next_days > 365].group.nunique()),
            maximum_interval_days=float(dev.next_days.max()),
            note="All long intervals are retained; archive coverage and attendance can make timing uncertain."),
        deterministic_last_gap_rule=dict(description="Predict next interval equal to last interval; first visits fall back to outer-training cohort median. Classify <=90 days; hard probabilities are uncalibrated.", metrics=rule_metrics),
        paired_comparisons_against_last_gap_rule=comparisons)
    write_json(public / "audit.json", summary)
    print(json.dumps({k: summary[k] for k in ("model_bundles_verified", "production_artifact_unchanged", "development_long_tail", "deterministic_last_gap_rule")}, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(); parser.add_argument("--run-id", required=True)
    audit(parser.parse_args().run_id)
