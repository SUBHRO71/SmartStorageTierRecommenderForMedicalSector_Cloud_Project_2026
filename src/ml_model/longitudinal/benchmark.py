"""Local, resumable 12-family benchmark with nested patient-group validation.

No AWS calls. Existing test subjects remain excluded from development; that test
was already inspected in the previous experiment and is diagnostic, not pristine.
"""
import os
for key in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ.setdefault(key, "2")
import argparse
from datetime import datetime, timezone
import hashlib
import importlib.metadata
import json
from pathlib import Path
import pickle
import platform
import time
import traceback
import warnings

import numpy as np
import pandas as pd
from sklearn.metrics import (accuracy_score, balanced_accuracy_score, brier_score_loss,
    confusion_matrix, mean_absolute_error, roc_auc_score)
from sklearn.model_selection import StratifiedGroupKFold
from threadpoolctl import threadpool_limits

from benchmark_data import build_frame, FEATURE_SETS
from benchmark_models import ModelPair, FAMILIES, LABELS
from data import ROOT

PROTOCOL = dict(version=1, seed=20261020, outer_folds=5, inner_folds=3,
    families=FAMILIES, settings=[0, 1], feature_sets=FEATURE_SETS,
    thresholds=np.round(np.arange(.25, .751, .05), 2).tolist(),
    classification_selection="inner OOF subject-weighted balanced accuracy, then Brier; threshold tuned inside inner CV",
    timing_selection="inner OOF subject-weighted MAE, then unweighted MAE",
    family_ranking="nested outer OOF subject-weighted balanced accuracy; timing ranked separately by subject-weighted MAE",
    weights="equal total weight per subject where estimator supports sample weights; nearest neighbors has no fit sample weights",
    holdout="original inspected test split: diagnostic only, excluded from development and selection",
    target="next recorded visit conditional on a later archived visit; not actual retrieval",
    practical_screen=dict(subject_weighted_balanced_accuracy_90d=.70, subject_weighted_auc_90d=.75,
                          subject_weighted_mae_days=35., paired_improvement_ci_lower_bound=0.),
    note="The practical screen is exploratory, not evidence of clinical or retrieval safety. Multiple-family selection needs new external validation.")


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    pending = path.with_suffix(path.suffix + ".tmp")
    pending.write_text(json.dumps(value, indent=2, allow_nan=False), encoding="utf-8")
    pending.replace(path)


def subject_weights(frame):
    # Normalize the mean to one: regularization settings then have a comparable
    # scale to ordinary sklearn fits instead of shrinking all weights by ~5x.
    w = 1. / frame.groupby("group")["group"].transform("size").to_numpy(float)
    return w * len(w) / w.sum()


def grouped_folds(frame, splits, seed):
    strata = frame.cohort + "_" + (frame.next_days <= 90).astype(int).astype(str)
    folds = list(StratifiedGroupKFold(n_splits=splits, shuffle=True, random_state=seed).split(frame, strata, frame.group))
    coverage = np.zeros(len(frame), int)
    for a, b in folds:
        if set(frame.iloc[a].group) & set(frame.iloc[b].group):
            raise AssertionError("Patient leakage across folds")
        coverage[b] += 1
    if not np.all(coverage == 1): raise AssertionError("Invalid out-of-fold coverage")
    return folds


def metrics(frame, p, days, threshold=.5):
    y = frame.next_days.to_numpy(float)
    label = y <= 90
    prediction = np.asarray(p) >= threshold
    w = subject_weights(frame)
    tn, fp, fn, tp = confusion_matrix(label, prediction, labels=[False, True]).ravel()
    return dict(n=len(frame), subjects=int(frame.group.nunique()), prevalence_90d=float(label.mean()),
        accuracy_90d=float(accuracy_score(label, prediction)), balanced_accuracy_90d=float(balanced_accuracy_score(label, prediction)),
        subject_weighted_balanced_accuracy_90d=float(balanced_accuracy_score(label, prediction, sample_weight=w)),
        auc_90d=float(roc_auc_score(label, p)) if len(set(label)) == 2 else None,
        subject_weighted_auc_90d=float(roc_auc_score(label, p, sample_weight=w)) if len(set(label)) == 2 else None,
        brier_90d=float(brier_score_loss(label, p)), subject_weighted_brier_90d=float(brier_score_loss(label, p, sample_weight=w)),
        mae_days=float(mean_absolute_error(y, days)), subject_weighted_mae_days=float(mean_absolute_error(y, days, sample_weight=w)),
        median_absolute_error_days=float(np.median(np.abs(y-days))), within_28_days=float(np.mean(np.abs(y-days) <= 28)),
        confusion=dict(tn=int(tn), fp=int(fp), fn=int(fn), tp=int(tp)))


def threshold_for(frame, prob):
    y, w = frame.next_days.to_numpy() <= 90, subject_weights(frame)
    return max(PROTOCOL["thresholds"], key=lambda t: (balanced_accuracy_score(y, prob >= t, sample_weight=w), -abs(t-.5)))


def config_id(setting, feature_set): return f"setting{setting}_{feature_set}"


def fit_predict(family, setting, features, train, valid):
    with warnings.catch_warnings(record=True) as observed:
        warnings.simplefilter("always")
        model = ModelPair(family, setting, features).fit(train, subject_weights(train))
        p, days = model.predict(valid)
    notes = sorted(set(f"{type(w.message).__name__}: {w.message}" for w in observed))
    if not np.all(np.isfinite(p)) or not np.all(np.isfinite(days)):
        raise AssertionError("Non-finite predictions")
    return model, p, days, notes


def choose(candidates, task):
    if task == "classification":
        return min(candidates, key=lambda c: (-c["metrics"]["subject_weighted_balanced_accuracy_90d"], c["metrics"]["subject_weighted_brier_90d"], c["id"]))
    return min(candidates, key=lambda c: (c["metrics"]["subject_weighted_mae_days"], c["metrics"]["mae_days"], c["id"]))


def nested_fold(family, number, train, valid, private, public):
    started = time.monotonic()
    inner = grouped_folds(train, PROTOCOL["inner_folds"], PROTOCOL["seed"]+number)
    candidates = []
    for feature_set, features in FEATURE_SETS.items():
        for setting in PROTOCOL["settings"]:
            identifier = config_id(setting, feature_set)
            probs, days = np.zeros(len(train)), np.zeros(len(train))
            notes = []
            for fit, evaluate in inner:
                _, p, d, observed = fit_predict(family, setting, features, train.iloc[fit], train.iloc[evaluate])
                probs[evaluate], days[evaluate] = p, d
                notes += observed
            threshold = threshold_for(train, probs)
            candidate = dict(id=identifier, setting=setting, feature_set=feature_set, threshold=float(threshold),
                             metrics=metrics(train, probs, days, threshold), warnings=sorted(set(notes)))
            candidates.append(candidate)
            predictions = train[["row_id", "group", "cohort", "next_days"]].copy()
            predictions["probability_90d"], predictions["predicted_days"] = probs, days
            predictions.to_csv(private / f"inner_{family}_fold{number}_{identifier}.csv", index=False)
    classifier, regressor = choose(candidates, "classification"), choose(candidates, "timing")
    fitted = {}
    notes = []
    for selected in (classifier, regressor):
        if selected["id"] not in fitted:
            model, p, d, observed = fit_predict(family, selected["setting"], FEATURE_SETS[selected["feature_set"]], train, valid)
            fitted[selected["id"]] = (model, p, d)
            notes += observed
    prob, days = fitted[classifier["id"]][1], fitted[regressor["id"]][2]
    predicted = valid[["row_id", "group", "cohort", "next_days"]].copy()
    predicted["probability_90d"], predicted["predicted_days"] = prob, days
    predicted["threshold"], predicted["outer_fold"] = classifier["threshold"], number
    predicted.to_csv(private / f"outer_{family}_fold{number}.csv", index=False)
    result = dict(family=family, fold=number, candidates=candidates, classifier=classifier, regressor=regressor,
        outer_metrics=metrics(valid, prob, days, classifier["threshold"]),
        fit_subjects=int(train.group.nunique()), evaluation_subjects=int(valid.group.nunique()),
        patient_overlap=0, seconds=time.monotonic()-started, warnings=sorted(set(notes)))
    write_json(public / f"folds/{family}_{number}.json", result)
    print(f"{LABELS[family]} fold {number+1}/5: balanced={result['outer_metrics']['subject_weighted_balanced_accuracy_90d']:.3f}, MAE={result['outer_metrics']['subject_weighted_mae_days']:.1f}d", flush=True)
    return result


def weighted_median(values, weights):
    order = np.argsort(values)
    return float(np.asarray(values)[order][np.searchsorted(np.cumsum(weights[order]), weights.sum()/2)])


def baseline_predictions(dev, outer):
    prior, med, last = np.zeros(len(dev)), np.zeros(len(dev)), np.zeros(len(dev))
    for a, b in outer:
        train, valid = dev.iloc[a], dev.iloc[b]
        for cohort in valid.cohort.unique():
            subset = train[train.cohort == cohort]
            w = subject_weights(subset)
            idx = b[valid.cohort.to_numpy() == cohort]
            prior[idx] = np.average(subset.next_days <= 90, weights=w)
            med[idx] = weighted_median(subset.next_days.to_numpy(), w)
        last[b] = valid.last_gap_days.fillna(pd.Series(med[b], index=valid.index)).to_numpy()
    return prior, med, last


def bootstrap(frame, prob, days, thresholds, base_prob, base_days, repeats=1000):
    y = frame.next_days.to_numpy(float)
    labels, predicted, base_predicted = y <= 90, prob >= thresholds, base_prob >= .5
    w = subject_weights(frame)
    groups = list(frame.groupby("group").indices.values())
    rng = np.random.default_rng(20261020)
    def ba(label, pred, weights):
        if len(set(label)) < 2: return np.nan
        return .5*(np.average(pred[label], weights=weights[label])+np.average(~pred[~label], weights=weights[~label]))
    samples = []
    for _ in range(repeats):
        idx = np.concatenate([groups[i] for i in rng.integers(0, len(groups), len(groups))])
        score = ba(labels[idx], predicted[idx], w[idx])
        reference = ba(labels[idx], base_predicted[idx], w[idx])
        error = np.average(np.abs(y[idx]-days[idx]), weights=w[idx])
        base_error = np.average(np.abs(y[idx]-base_days[idx]), weights=w[idx])
        samples.append((score, error, score-reference, base_error-error))
    intervals = np.nanquantile(samples, [.025, .975], axis=0)
    return {name: intervals[:, i].tolist() for i, name in enumerate(("subject_weighted_balanced_accuracy_95ci",
        "subject_weighted_mae_days_95ci", "balanced_accuracy_improvement_over_cohort_baseline_95ci",
        "mae_improvement_over_cohort_baseline_days_95ci"))}


def final_config(folds, task):
    grouped = {}
    for fold in folds:
        for c in fold["candidates"]: grouped.setdefault(c["id"], []).append(c)
    averaged = []
    for identifier, candidates in grouped.items():
        record = {k: candidates[0][k] for k in ("id", "setting", "feature_set")}
        record["threshold"] = float(np.median([c["threshold"] for c in candidates]))
        keys = ("subject_weighted_balanced_accuracy_90d", "subject_weighted_brier_90d", "subject_weighted_mae_days", "mae_days")
        record["metrics"] = {key: float(np.mean([c["metrics"][key] for c in candidates])) for key in keys}
        averaged.append(record)
    return choose(averaged, task)


def summarize_family(family, folds, dev, test, baseline, private, public):
    predictions = pd.concat([pd.read_csv(private / f"outer_{family}_fold{i}.csv") for i in range(PROTOCOL["outer_folds"])], ignore_index=True)
    predictions = predictions.set_index("row_id").loc[dev.row_id].reset_index()
    if not np.array_equal(predictions.next_days, dev.next_days): raise AssertionError("OOF row alignment mismatch")
    prob, days, thresholds = [predictions[c].to_numpy() for c in ("probability_90d", "predicted_days", "threshold")]
    predictions.to_csv(private / f"{family}_nested_oof_predictions.csv", index=False)
    result = dict(family=family, label=LABELS[family], nested_cv=metrics(dev, prob, days, thresholds),
        nested_cv_threshold_05=metrics(dev, prob, days),
        nested_cv_by_cohort={c: metrics(dev[dev.cohort == c], prob[dev.cohort.to_numpy() == c], days[dev.cohort.to_numpy() == c], thresholds[dev.cohort.to_numpy() == c]) for c in sorted(dev.cohort.unique())},
        bootstrap=bootstrap(dev, prob, days, thresholds, baseline[0], baseline[1]),
        outer_fold_metrics=[f["outer_metrics"] for f in folds],
        final_classifier=final_config(folds, "classification"), final_regressor=final_config(folds, "timing"),
        runtime_seconds=sum(f["seconds"] for f in folds))
    selected = (result["final_classifier"], result["final_regressor"])
    fitted = {}
    notes = []
    for c in selected:
        if c["id"] not in fitted:
            model, p, d, observed = fit_predict(family, c["setting"], FEATURE_SETS[c["feature_set"]], dev, test)
            fitted[c["id"]] = (model, p, d)
            notes += observed
    cls, reg = [fitted[c["id"]] for c in selected]
    result["previously_inspected_holdout_diagnostic"] = metrics(test, cls[1], reg[2], selected[0]["threshold"])
    result["warnings"] = sorted(set(notes))
    result["final_estimator_parameters"] = {
        "classification": repr(getattr(cls[0], "forest", getattr(cls[0], "classifier", None))),
        "timing": repr(getattr(reg[0], "forest", getattr(reg[0], "regressor", None)))}
    models = private / "models"; models.mkdir(exist_ok=True)
    artifact = models / f"{family}.pkl"
    with artifact.open("wb") as stream:
        pickle.dump(dict(classifier=cls[0], regressor=reg[0], threshold=selected[0]["threshold"], protocol=PROTOCOL), stream)
    result["artifact_sha256"] = hashlib.sha256(artifact.read_bytes()).hexdigest()
    diagnostic = test[["row_id", "group", "cohort", "next_days"]].copy()
    diagnostic["probability_90d"], diagnostic["predicted_days"], diagnostic["threshold"] = cls[1], reg[2], selected[0]["threshold"]
    diagnostic.to_csv(private / f"{family}_inspected_holdout_predictions.csv", index=False)
    write_json(public / f"models/{family}.json", result)
    return result


def save_leaderboard(results, public):
    rows = []
    for result in results:
        metrics_ = result["nested_cv"]
        rows.append(dict(model=result["label"], family=result["family"], **{k: metrics_[k] for k in (
            "accuracy_90d", "balanced_accuracy_90d", "subject_weighted_balanced_accuracy_90d", "auc_90d",
            "subject_weighted_auc_90d", "brier_90d", "subject_weighted_brier_90d", "mae_days", "subject_weighted_mae_days", "within_28_days")},
            diagnostic_holdout_accuracy_90d=result["previously_inspected_holdout_diagnostic"]["accuracy_90d"],
            diagnostic_holdout_mae_days=result["previously_inspected_holdout_diagnostic"]["mae_days"]))
    table = pd.DataFrame(rows).sort_values(["subject_weighted_balanced_accuracy_90d", "subject_weighted_brier_90d"], ascending=[False, True])
    table.to_csv(public / "leaderboard.csv", index=False)
    write_json(public / "results.json", results)
    return table


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-id", default=datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ"))
    args = parser.parse_args()
    if not args.run_id.replace("-", "").replace("_", "").isalnum(): raise ValueError("Invalid run ID")
    public = ROOT / "experiments/longitudinal" / args.run_id
    private = ROOT / "dataset/processed/longitudinal/benchmarks" / args.run_id
    public.mkdir(parents=True, exist_ok=True); private.mkdir(parents=True, exist_ok=True)
    frame, audit = build_frame()
    known = frame[frame.next_days.notna()].copy()
    dev = known[known.split != "test"].reset_index(drop=True)
    test = known[known.split == "test"].reset_index(drop=True)
    if set(dev.group) & set(test.group): raise AssertionError("Original test patient leakage")
    input_hash = hashlib.sha256(frame.to_json(orient="records").encode()).hexdigest()
    runtime_artifact = ROOT / "src/ml_model/longitudinal_model.json"
    production_hash = hashlib.sha256(runtime_artifact.read_bytes()).hexdigest()
    source_hashes = {name: hashlib.sha256(Path(__file__).with_name(name).read_bytes()).hexdigest() for name in ("benchmark.py", "benchmark_models.py", "benchmark_data.py")}
    metadata = dict(protocol=PROTOCOL, input_sha256=input_hash, source_sha256=source_hashes,
        production_model_sha256_before=production_hash, dataset_audit=audit,
        development=dict(intervals=len(dev), labelled_subjects=int(dev.group.nunique())),
        inspected_holdout=dict(intervals=len(test), labelled_subjects=int(test.group.nunique())),
        unknown_terminal_outcomes=int(frame.next_days.isna().sum()), python=platform.python_version(),
        packages={p: importlib.metadata.version(p) for p in ("numpy", "pandas", "scipy", "scikit-learn", "scikit-survival", "xgboost", "joblib")})
    meta_path = public / "protocol.json"
    if meta_path.exists():
        previous = json.loads(meta_path.read_text())
        for key in ("protocol", "input_sha256", "source_sha256"):
            if previous[key] != metadata[key]:
                completed = all((public / f"models/{family}.json").exists() for family in FAMILIES)
                same_model_data_code = all(previous["source_sha256"][name] == source_hashes[name] for name in ("benchmark_models.py", "benchmark_data.py"))
                if key == "source_sha256" and completed and same_model_data_code:
                    # A completed-run reporting/resume repair cannot trigger fits.
                    # Keep the original training source checksum immutable.
                    write_json(public / "completed_resume_provenance.json", dict(
                        original_training_sha256=previous["source_sha256"],
                        completed_resume_sha256=source_hashes,
                        scope="Completed-model aggregation only; all model/data code unchanged; no training performed"))
                else:
                    raise ValueError(f"Resume mismatch: {key}; use a new run ID")
    else: write_json(meta_path, metadata)
    frame.to_json(private / "input_examples.json", orient="records", indent=2)
    dev[["row_id", "group", "cohort", "split"]].to_csv(private / "development_rows.csv", index=False)
    outer = grouped_folds(dev, PROTOCOL["outer_folds"], PROTOCOL["seed"])
    assignments = dev[["row_id", "group", "cohort"]].copy()
    for i, (_, b) in enumerate(outer): assignments.loc[b, "outer_fold"] = i
    assignments.to_csv(private / "outer_folds.csv", index=False)
    baseline = baseline_predictions(dev, outer)
    baseline_stats = dict(cohort_prior_median=metrics(dev, baseline[0], baseline[1]),
                          cohort_prior_last_gap=metrics(dev, baseline[0], baseline[2]))
    write_json(public / "baselines.json", baseline_stats)
    pd.DataFrame(dict(row_id=dev.row_id, group=dev.group, probability_90d=baseline[0], median_days=baseline[1], last_gap_days=baseline[2])).to_csv(private / "baseline_oof_predictions.csv", index=False)
    print(f"Run {args.run_id}: {len(dev)} development intervals / {dev.group.nunique()} subjects; {len(test)} previously inspected holdout intervals. 12 families, nested 5x3 group CV.", flush=True)
    results = []
    with threadpool_limits(limits=2):
        for family in FAMILIES:
            final_path = public / f"models/{family}.json"
            if final_path.exists():
                results.append(json.loads(final_path.read_text()))
                table = save_leaderboard(results, public)
                continue
            print(f"START {LABELS[family]}", flush=True)
            try:
                folds = []
                for i, (a, b) in enumerate(outer):
                    checkpoint = public / f"folds/{family}_{i}.json"
                    folds.append(json.loads(checkpoint.read_text()) if checkpoint.exists() else nested_fold(family, i, dev.iloc[a].reset_index(drop=True), dev.iloc[b].reset_index(drop=True), private, public))
                result = summarize_family(family, folds, dev, test, baseline, private, public)
                results.append(result)
                table = save_leaderboard(results, public)
                print(f"DONE {LABELS[family]}: nested balanced={result['nested_cv']['subject_weighted_balanced_accuracy_90d']:.3f}, MAE={result['nested_cv']['subject_weighted_mae_days']:.1f}d; {len(results)}/12 families saved", flush=True)
            except Exception:
                write_json(public / f"failure_{family}.json", dict(family=family, traceback=traceback.format_exc()))
                raise
    if len(results) != 12: raise AssertionError("Incomplete benchmark")
    after_hash = hashlib.sha256(runtime_artifact.read_bytes()).hexdigest()
    if after_hash != production_hash: raise AssertionError("Production artifact changed unexpectedly")
    classification = min(results, key=lambda r: (-r["nested_cv"]["subject_weighted_balanced_accuracy_90d"], r["nested_cv"]["subject_weighted_brier_90d"]))
    timing = min(results, key=lambda r: r["nested_cv"]["subject_weighted_mae_days"])
    write_json(public / "selection.json", dict(classification=classification["family"], timing=timing["family"],
        selection_scope="exploratory nested CV; not ranked by the previously inspected test", production_model_unchanged=True,
        production_model_sha256_after=after_hash, completed_utc=datetime.now(timezone.utc).isoformat(),
        completed_families=len(results)))
    print(table.to_string(index=False), flush=True)
    print("SAVED " + str(public), flush=True)


if __name__ == "__main__": main()
