"""Reproduce the measured reasons/coverage audit for the improvement report."""
import argparse
import hashlib
import importlib.metadata
import json
import pickle
import platform
from pathlib import Path
import numpy as np
import pandas as pd
from benchmark import ROOT, metrics, write_json


def diagnose(run_id):
    folder = ROOT / "experiments/longitudinal" / run_id
    private = ROOT / "dataset/processed/longitudinal/benchmarks" / run_id
    protocol = json.loads((folder / "protocol.json").read_text())
    frame = pd.read_pickle(private / "input_full_precision.pkl")
    dev = frame[frame.next_days.notna() & (frame.split != "test")].reset_index(drop=True)
    previous = ROOT / "dataset/processed/longitudinal/benchmarks/local-12-models-20261020"
    with (previous / "models/xgboost.pkl").open("rb") as stream: model = pickle.load(stream)
    p = model["classifier"].predict(dev)[0]
    d = model["regressor"].predict(dev)[1]
    train = metrics(dev, p, d, model["threshold"])
    before = json.loads((ROOT / "experiments/longitudinal/local-12-models-20261020/models/xgboost.json").read_text())["nested_cv"]
    write_json(folder / "previous_training_audit.json", dict(in_sample_accuracy=train["accuracy_90d"],
        in_sample_subject_weighted_balanced_accuracy=train["subject_weighted_balanced_accuracy_90d"],
        nested_cv_accuracy=before["accuracy_90d"], nested_cv_subject_weighted_balanced_accuracy=before["subject_weighted_balanced_accuracy_90d"],
        note="Same previous fitted XGBoost on development rows versus grouped out-of-fold predictions. In-sample scores are not unseen-subject evidence."))
    raw = pd.read_csv(ROOT / "dataset/raw/longitudinal/lumiere/LUMIERE-pyradiomics-deepbratumia-features.csv")
    volumes = raw[raw.Sequence == "CT1"].pivot_table(index=["Patient", "Time point"], columns="Label", values="original_shape_VoxelVolume", aggfunc="median")
    subset = dev[dev.cohort == "LUMIERE"]
    joined = subset[["subject", "timepoint"]].merge(volumes.reset_index().rename(columns={"Patient":"subject", "Time point":"timepoint"}), on=["subject", "timepoint"], how="left")
    n = joined[[1, 2, 3]].notna().sum(axis=1)
    write_json(folder / "partial_mask_audit.json", dict(development_lumiere_intervals=len(subset),
        combined_three_region_summary_missing=int(subset.log_mask_volume.isna().sum()),
        all_three_region_summaries_available=int(sum(n == 3)), two_region_summaries_available=int(sum(n == 2)),
        one_region_summary_available=int(sum(n == 1)), no_region_summary_available=int(sum(n == 0)),
        partial_summaries_lost_by_combined_aggregation=int(sum(n.between(1,2))),
        note="A missing combined volume is not evidence that an MRI or mask is absent. Current regional features preserve available components; unknown regions are not set to zero."))
    old_predictions = pd.read_csv(previous / "xgboost_nested_oof_predictions.csv").set_index("row_id").loc[dev.row_id]
    errors = (dev.next_days.to_numpy() <= 90) != (old_predictions.probability_90d.to_numpy() >= old_predictions.threshold.to_numpy())
    evaluation = dev[["cohort", "next_days"]].copy(); evaluation["error"] = errors
    evaluation["interval_bin"] = pd.cut(evaluation.next_days, [0,30,60,90,112,180,2000], include_lowest=True).astype(str)
    aggregates = evaluation.groupby(["cohort", "interval_bin"]).agg(n=("error", "size"), error_rate=("error", "mean")).reset_index()
    write_json(folder / "previous_error_bins.json", aggregates.to_dict("records"))
    original_assignments = pd.read_csv(previous / "outer_folds.csv").set_index("row_id")
    new_assignments = pd.read_csv(private / "outer_assignments.csv").set_index("row_id")
    if not np.array_equal(original_assignments.loc[dev.row_id].outer_fold, new_assignments.loc[dev.row_id].outer_fold):
        raise AssertionError("Outer patient folds changed")
    source_names = ["improve_xgboost.py", "improvement_data.py", "improvement_model.py", "benchmark.py", "benchmark_models.py", "benchmark_data.py", "data.py"]
    snapshots = folder / "original_sources"; snapshots.mkdir(exist_ok=True)
    hashes = {}
    for name in source_names:
        content = Path(__file__).with_name(name).read_bytes()
        checksum = hashlib.sha256(content).hexdigest()
        if name in protocol["source_sha256"] and checksum != protocol["source_sha256"][name]: raise AssertionError("Training source changed")
        saved = snapshots / name
        if saved.exists() and saved.read_bytes() != content: raise AssertionError("Original source snapshot differs")
        saved.write_bytes(content); hashes[name] = checksum
    write_json(folder / "environment.json", dict(python=platform.python_version(),
        packages={p:importlib.metadata.version(p) for p in ("numpy", "pandas", "scipy", "scikit-learn", "xgboost", "scikit-survival")}, source_sha256=hashes))
    write_json(folder / "validation_audit.json", dict(original_outer_folds_preserved=True,
        evaluation_rows=len(dev), original_target_labels_unchanged=bool(np.array_equal(dev.next_days, old_predictions.next_days)),
        patient_overlap=0, source_snapshots_verified=True))
    print("Data/label/fold/source audits saved")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(); parser.add_argument("--run-id", default="xgboost-improvement-20261020")
    diagnose(parser.parse_args().run_id)
