"""Second, explicitly exploratory XGBoost improvement round. Local only.

The original grouped outer folds and all original evaluation labels are retained.
Full coverage and selective/abstaining performance are reported independently.
"""
import os
for key in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS"): os.environ.setdefault(key, "2")
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import pickle
import time
import numpy as np
import pandas as pd
from threadpoolctl import threadpool_limits
from benchmark import ROOT, grouped_folds, subject_weights, threshold_for, metrics, bootstrap, write_json
from improvement_data import build_improvement_frame
from improvement_model import ImprovedXGB

PREVIOUS_RUN = "local-12-models-20261020"
SEED = 20261020


def candidates():
    grids = [
        dict(n_estimators=300, max_depth=1, min_child_weight=3, reg_lambda=5, learning_rate=.05),
        dict(n_estimators=400, max_depth=2, min_child_weight=1, reg_lambda=1, learning_rate=.04),
        dict(n_estimators=250, max_depth=3, min_child_weight=3, reg_lambda=5, learning_rate=.05),
        dict(n_estimators=220, max_depth=3, min_child_weight=8, reg_lambda=10, learning_rate=.04),
        dict(n_estimators=400, max_depth=4, min_child_weight=10, reg_lambda=20, learning_rate=.04),
        dict(n_estimators=250, max_depth=5, min_child_weight=3, reg_lambda=10, learning_rate=.04)]
    result = []
    for features in ("original", "temporal", "temporal_radiomics"):
        for strategy in ("pooled", "specialists"):
            for label in ("hard", "soft"):
                for i, params in enumerate(grids):
                    result.append(dict(id=f"{features}_{strategy}_{label}_{i}", features=features, strategy=strategy,
                        week91=label, missing="native", params=dict(subsample=.85, colsample_bytree=.85, **params)))
    result.append(dict(id="original_pooled_hard_median_reference", features="original", strategy="pooled",
        week91="hard", missing="median", params=dict(subsample=.85, colsample_bytree=.85, **grids[3])))
    return result


def class_metrics(frame, probability, threshold):
    result = metrics(frame, probability, np.zeros(len(frame)), threshold)
    for key in ("mae_days", "subject_weighted_mae_days", "median_absolute_error_days", "within_28_days"):
        result.pop(key)
    return result


def confidence_mask(probability, threshold, cutoff):
    margin = np.where(probability >= threshold, (probability-threshold)/(1-threshold), (threshold-probability)/threshold)
    return margin >= cutoff


def selective_policy(frame, probability, threshold):
    """Tune acceptance only within inner OOF rows, never outer/test labels."""
    for cutoff in np.round(np.arange(0, .91, .1), 2):
        accept = confidence_mask(probability, threshold, cutoff)
        chosen = frame[accept]
        counts = (chosen.next_days <= 90).value_counts()
        if accept.mean() < .30 or chosen.group.nunique() < 15 or min(counts.get(False, 0), counts.get(True, 0)) < 15:
            continue
        score = class_metrics(chosen, probability[accept], threshold)
        if score["accuracy_90d"] >= .80 and score["subject_weighted_balanced_accuracy_90d"] >= .75:
            return dict(cutoff=float(cutoff), inner_coverage=float(accept.mean()), inner_metrics=score)
    return None


def select_full(records):
    return min(records, key=lambda c: (-c["metrics"]["subject_weighted_balanced_accuracy_90d"], c["metrics"]["subject_weighted_brier_90d"], c["id"]))


def select_cautious(records):
    eligible = [r for r in records if r["selective"] is not None]
    return min(eligible, key=lambda r: (-r["selective"]["inner_coverage"], -r["selective"]["inner_metrics"]["subject_weighted_balanced_accuracy_90d"], r["id"])) if eligible else None


def fit_fold(number, train, valid, feature_sets, configs, private, public):
    started = time.monotonic()
    inner = grouped_folds(train, 3, SEED+number)
    records = []
    for count, config in enumerate(configs):
        probability = np.zeros(len(train))
        for a, b in inner:
            model = ImprovedXGB(config, feature_sets[config["features"]]).fit(train.iloc[a])
            probability[b] = model.predict(train.iloc[b])
        threshold = float(threshold_for(train, probability))
        record = dict(id=config["id"], config=config, threshold=threshold,
            metrics=class_metrics(train, probability, threshold), selective=selective_policy(train, probability, threshold))
        records.append(record)
        np.savez_compressed(private / f"inner_fold{number}_{config['id']}.npz", row_id=train.row_id.to_numpy(), probability_90d=probability)
        if (count+1)%12 == 0:
            write_json(public / f"progress_fold{number}.json", dict(fold=number, candidates_completed=count+1, candidates_total=len(configs), elapsed_seconds=time.monotonic()-started))
            print(f"Fold {number+1}/5: {count+1}/{len(configs)} candidates evaluated", flush=True)
    full, cautious = select_full(records), select_cautious(records)
    trained = ImprovedXGB(full["config"], feature_sets[full["config"]["features"]]).fit(train)
    timed = ImprovedXGB(full["config"], feature_sets[full["config"]["features"]], task="timing").fit(train)
    probability, days = trained.predict(valid), timed.predict(valid)
    result = valid[["row_id", "group", "cohort", "next_days"]].copy()
    result["probability_90d"], result["predicted_days"], result["threshold"] = probability, days, full["threshold"]
    cautious_model = None
    if cautious:
        cautious_model = trained if cautious["id"] == full["id"] else ImprovedXGB(cautious["config"], feature_sets[cautious["config"]["features"]]).fit(train)
        p = cautious_model.predict(valid)
        accept = confidence_mask(p, cautious["threshold"], cautious["selective"]["cutoff"])
        result["selective_probability"], result["selective_threshold"], result["accepted"] = p, cautious["threshold"], accept
    else:
        result["selective_probability"], result["selective_threshold"], result["accepted"] = .5, .5, False
    result["fold"] = number
    result.to_csv(private / f"outer_fold{number}.csv", index=False, float_format="%.17g")
    with (private / f"fold{number}_models.pkl").open("wb") as stream:
        pickle.dump(dict(full=trained, timing=timed, selective=cautious_model), stream)
    record = dict(fold=number, candidates=records, selected_full=full, selected_selective=cautious,
        outer_full=metrics(valid, probability, days, full["threshold"]),
        outer_selective_coverage=float(result.accepted.mean()),
        outer_selective=class_metrics(valid[result.accepted.to_numpy()], result.selective_probability.to_numpy()[result.accepted], result.selective_threshold.to_numpy()[result.accepted]) if result.accepted.any() else None,
        elapsed_seconds=time.monotonic()-started, patient_overlap=0)
    write_json(public / f"folds/fold{number}.json", record)
    print(f"DONE fold {number+1}: full accuracy={record['outer_full']['accuracy_90d']:.3f}, subject BA={record['outer_full']['subject_weighted_balanced_accuracy_90d']:.3f}; selective coverage={record['outer_selective_coverage']:.3f}", flush=True)
    return record


def aggregate_records(folds):
    grouped = {}
    for fold in folds:
        for record in fold["candidates"]: grouped.setdefault(record["id"], []).append(record)
    averaged = []
    for identifier, records in grouped.items():
        item = dict(id=identifier, config=records[0]["config"], threshold=float(np.median([r["threshold"] for r in records])),
            metrics={k: float(np.mean([r["metrics"][k] for r in records])) for k in ("subject_weighted_balanced_accuracy_90d", "subject_weighted_brier_90d", "accuracy_90d")})
        policies = [r["selective"] for r in records if r["selective"]]
        item["selective"] = dict(cutoff=float(np.median([p["cutoff"] for p in policies])),
            inner_coverage=float(np.mean([r["selective"]["inner_coverage"] if r["selective"] else 0 for r in records])),
            inner_metrics=dict(subject_weighted_balanced_accuracy_90d=float(np.mean([p["inner_metrics"]["subject_weighted_balanced_accuracy_90d"] for p in policies])))) if len(policies) == len(records) else None
        averaged.append(item)
    return averaged


def confidence_intervals(frame, probability, threshold):
    groups = list(frame.groupby("group").indices.values())
    w = subject_weights(frame); y = frame.next_days.to_numpy() <= 90; pred = probability >= threshold
    rng = np.random.default_rng(SEED)
    values = []
    for _ in range(1000):
        idx = np.concatenate([groups[i] for i in rng.integers(0, len(groups), len(groups))])
        a, p, s = y[idx], pred[idx], w[idx]
        ba = .5*(np.average(p[a], weights=s[a])+np.average(~p[~a], weights=s[~a])) if a.any() and (~a).any() else np.nan
        values.append((np.mean(a == p), ba))
    q = np.nanquantile(values, [.025, .975], axis=0)
    return dict(accuracy_95ci=q[:, 0].tolist(), subject_weighted_balanced_accuracy_95ci=q[:, 1].tolist())


def diagnose(dev, private, public):
    previous = ROOT / "dataset/processed/longitudinal/benchmarks" / PREVIOUS_RUN
    p = pd.read_csv(previous / "xgboost_nested_oof_predictions.csv").set_index("row_id").loc[dev.row_id]
    error = (dev.next_days.to_numpy() <= 90) != (p.probability_90d.to_numpy() >= p.threshold.to_numpy())
    cohorts = {}
    for cohort in sorted(dev.cohort.unique()):
        subset = dev[dev.cohort == cohort]; mask = dev.cohort.to_numpy() == cohort
        cohorts[cohort] = dict(intervals=len(subset), subjects=int(subset.group.nunique()),
            missing_mask_fraction=float(subset.log_mask_volume.isna().mean()),
            intervals_recorded_91_days=int(sum(subset.next_days == 91)), previous_error_rate=float(error[mask].mean()))
    info = dict(cohorts=cohorts, development_intervals=len(dev), development_subjects=int(dev.group.nunique()),
        causes_are_hypotheses=True, weekly_boundary_note="LUMIERE 91-day recorded gaps can represent true gaps of 85..97 days; original 90-day evaluation labels remain unchanged.",
        missing_note="TCGA has no published masks in this input set; absence is not a zero volume. Native XGBoost missingness is compared with median imputation.",
        feature_note="Past-to-current mask/metadata changes and richer current radiomics were omitted from the prior compact feature set.")
    write_json(public / "diagnosis.json", info)
    return p


def main():
    parser = argparse.ArgumentParser(); parser.add_argument("--run-id", default="xgboost-improvement-20261020")
    args = parser.parse_args()
    if not args.run_id.replace("-", "").replace("_", "").isalnum(): raise ValueError("Invalid run ID")
    public = ROOT / "experiments/longitudinal" / args.run_id
    private = ROOT / "dataset/processed/longitudinal/benchmarks" / args.run_id
    public.mkdir(parents=True, exist_ok=True); private.mkdir(parents=True, exist_ok=True)
    frame, feature_sets, audit = build_improvement_frame()
    known = frame[frame.next_days.notna()]
    dev, test = [known[known.split != "test"].reset_index(drop=True), known[known.split == "test"].reset_index(drop=True)]
    if set(dev.group) & set(test.group): raise AssertionError("Patient leakage")
    artifact = ROOT / "src/ml_model/longitudinal_model.json"
    production_sha = hashlib.sha256(artifact.read_bytes()).hexdigest()
    configs = candidates()
    protocol = dict(version=1, evaluation="exploratory second round, same original nested 5x3 grouped folds; previous test diagnostic only", seed=SEED,
        target="next recorded visit <=90 days conditional on a later recorded visit; evaluation target unchanged",
        full_selection="inner subject-weighted balanced accuracy, then Brier", selective_selection="inner accuracy >=80%, subject BA >=75%, coverage >=30%, >=15 subjects, >=15 rows each class; choose largest coverage",
        outer_evaluation_labels="original hard labels for ALL rows; no deletions or confidence filtering in full score",
        selective_note="Selective score covers only accepted cases; abstentions remain in denominator for coverage and require a fallback. No 80% full-coverage claim from selective performance.",
        training_week91_soft_label_assumption="21/49 chance <=90 days under independent uniform within-week offsets; sensitivity experiment, not recovered ground truth",
        feature_sets=feature_sets, configs=configs, production_model_sha256=production_sha,
        development_intervals=len(dev), development_subjects=int(dev.group.nunique()), inspected_holdout_intervals=len(test),
        input_sha256=hashlib.sha256(frame.to_json(orient="records", double_precision=15).encode()).hexdigest(),
        source_sha256={name: hashlib.sha256(Path(__file__).with_name(name).read_bytes()).hexdigest() for name in ("improve_xgboost.py", "improvement_data.py", "improvement_model.py")})
    path = public / "protocol.json"
    if path.exists() and json.loads(path.read_text()) != protocol: raise ValueError("Resume mismatch; choose a new run ID")
    write_json(path, protocol)
    frame.to_pickle(private / "input_full_precision.pkl")
    previous = diagnose(dev, private, public)
    outer = grouped_folds(dev, 5, SEED)
    assignment = dev[["row_id", "group", "cohort"]].copy()
    for i, (_, b) in enumerate(outer): assignment.loc[b, "outer_fold"] = i
    assignment.to_csv(private / "outer_assignments.csv", index=False)
    print(f"{len(configs)} XGBoost candidates, {len(dev)} development intervals, {len(feature_sets['temporal_radiomics'])} expanded features; nested 5x3 group CV", flush=True)
    folds = []
    with threadpool_limits(limits=2):
        for i, (a, b) in enumerate(outer):
            checkpoint = public / f"folds/fold{i}.json"
            folds.append(json.loads(checkpoint.read_text()) if checkpoint.exists() else fit_fold(i, dev.iloc[a].reset_index(drop=True), dev.iloc[b].reset_index(drop=True), feature_sets, configs, private, public))
        predictions = pd.concat([pd.read_csv(private / f"outer_fold{i}.csv") for i in range(5)]).set_index("row_id").loc[dev.row_id].reset_index()
        predictions.to_csv(private / "nested_oof_predictions.csv", index=False, float_format="%.17g")
        probability, days, thresholds = [predictions[c].to_numpy() for c in ("probability_90d", "predicted_days", "threshold")]
        full = metrics(dev, probability, days, thresholds)
        by_cohort = {c: metrics(dev[dev.cohort == c], probability[dev.cohort.to_numpy() == c], days[dev.cohort.to_numpy() == c], thresholds[dev.cohort.to_numpy() == c]) for c in sorted(dev.cohort.unique())}
        accepted = predictions.accepted.to_numpy(dtype=bool)
        selective = dict(coverage=float(accepted.mean()), accepted_intervals=int(accepted.sum()), total_intervals=len(dev),
            accepted_subjects=int(dev[accepted].group.nunique()), abstained_intervals=int((~accepted).sum()),
            metrics=class_metrics(dev[accepted], predictions.selective_probability.to_numpy()[accepted], predictions.selective_threshold.to_numpy()[accepted]) if accepted.any() else None,
            confidence_intervals=confidence_intervals(dev[accepted], predictions.selective_probability.to_numpy()[accepted], predictions.selective_threshold.to_numpy()[accepted]) if accepted.any() else None,
            by_cohort={c: dict(coverage=float(accepted[dev.cohort.to_numpy() == c].mean()), accepted=int(sum(accepted & (dev.cohort.to_numpy() == c)))) for c in sorted(dev.cohort.unique())})
        averaged = aggregate_records(folds)
        final, cautious = select_full(averaged), select_cautious(averaged)
        model = ImprovedXGB(final["config"], feature_sets[final["config"]["features"]]).fit(dev)
        timer = ImprovedXGB(final["config"], feature_sets[final["config"]["features"]], task="timing").fit(dev)
        cautious_model = ImprovedXGB(cautious["config"], feature_sets[cautious["config"]["features"]]).fit(dev) if cautious else None
        bundle = dict(classifier=model, timing=timer, selective=cautious_model, full_config=final, selective_config=cautious, protocol=protocol)
        with (private / "final_models.pkl").open("wb") as stream: pickle.dump(bundle, stream)
        with (private / "final_models.pkl").open("rb") as stream: loaded = pickle.load(stream)
        ptest, dtest = model.predict(test), timer.predict(test)
        if not np.allclose(ptest, loaded["classifier"].predict(test)): raise AssertionError("Saved model roundtrip mismatch")
        diagnostic = metrics(test, ptest, dtest, final["threshold"])
        test_predictions = test[["row_id", "group", "cohort", "next_days"]].copy()
        test_predictions["probability_90d"], test_predictions["predicted_days"] = ptest, dtest
        test_predictions.to_csv(private / "inspected_holdout_predictions.csv", index=False, float_format="%.17g")
        changes = bootstrap(dev, probability, days, thresholds, previous.probability_90d.to_numpy(), previous.predicted_days.to_numpy())
        changed_ci = {key.replace("cohort_baseline", "previous_xgboost"): value for key, value in changes.items()}
        results = dict(nested_full=full, nested_full_threshold_05=metrics(dev, probability, days), nested_by_cohort=by_cohort,
            nested_confidence_intervals=confidence_intervals(dev, probability, thresholds),
            selective=selective, paired_comparison=changed_ci, final_config=final, final_selective_config=cautious,
            previously_inspected_holdout_diagnostic=diagnostic,
            in_sample_training=class_metrics(dev, model.predict(dev), final["threshold"]),
            selected_features_by_fold=[dict(fold=f["fold"], full=f["selected_full"]["id"], selective=f["selected_selective"]["id"] if f["selected_selective"] else None) for f in folds],
            model_bundle_sha256=hashlib.sha256((private / "final_models.pkl").read_bytes()).hexdigest(),
            saved_model_roundtrip_verified=True, production_model_unchanged=hashlib.sha256(artifact.read_bytes()).hexdigest() == production_sha,
            completed_utc=datetime.now(timezone.utc).isoformat())
        if not results["production_model_unchanged"]: raise AssertionError("Production artifact changed")
        write_json(public / "results.json", results)
        write_json(public / "inner_configuration_summary.json", averaged)
        pd.DataFrame([dict(config=r["id"], inner_balanced_accuracy=r["metrics"]["subject_weighted_balanced_accuracy_90d"], inner_brier=r["metrics"]["subject_weighted_brier_90d"], selective_coverage=r["selective"]["inner_coverage"] if r["selective"] else 0) for r in averaged]).to_csv(public / "configuration_summary.csv", index=False)
    print(json.dumps({k: results[k] for k in ("nested_full", "nested_by_cohort", "nested_confidence_intervals", "selective", "paired_comparison", "final_config", "in_sample_training", "production_model_unchanged")}, indent=2), flush=True)


if __name__ == "__main__": main()
