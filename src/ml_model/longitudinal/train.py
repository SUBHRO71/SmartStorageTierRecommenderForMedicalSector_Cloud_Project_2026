"""Reproducible grouped holdout experiment. Run from the repository root.

Selection: lowest validation day MAE, then 90-day Brier score. The test set
is evaluated once after selection. No terminal visit is labelled as a negative.
"""
import hashlib
import json
from pathlib import Path
import sys
import numpy as np
import pandas as pd
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, balanced_accuracy_score, brier_score_loss, mean_absolute_error, roc_auc_score
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from sksurv.ensemble import RandomSurvivalForest
from sksurv.util import Surv

from data import FEATURES, MASK_FEATURES, ROOT, assign_splits, examples, load_visits
sys.path.insert(0, str(ROOT / "src/backend"))
from temporal_forecast import predict_cdf, quantile

OUT = ROOT / "dataset/processed/longitudinal"
GRID = sorted(set([0, 30, 60, 90, 365, 540, 730, 1095, 1460] + list(range(7, 365, 7))))


def metrics(frame, probabilities, predicted_days):
    y = frame.next_days.to_numpy()
    label = y <= 90
    return dict(n=len(y), subjects=int(frame.subject.nunique()), prevalence_90d=float(label.mean()),
                accuracy_90d=float(accuracy_score(label, probabilities >= .5)),
                balanced_accuracy_90d=float(balanced_accuracy_score(label, probabilities >= .5)),
                auc_90d=float(roc_auc_score(label, probabilities)) if len(set(label)) == 2 else None,
                brier_90d=float(brier_score_loss(label, probabilities)), mae_days=float(mean_absolute_error(y, predicted_days)),
                median_absolute_error_days=float(np.median(np.abs(y-predicted_days))),
                within_28_days=float(np.mean(np.abs(y-predicted_days) <= 28)),
                calibration_observed_minus_predicted=float(label.mean()-np.mean(probabilities)))


def evaluate(frame, cdf):
    probs = cdf[:, GRID.index(90)]
    medians = np.array([quantile(GRID, row, .5) or GRID[-1] for row in cdf])
    result = metrics(frame, probs, medians)
    lo = np.array([quantile(GRID, row, .1) or GRID[-1] for row in cdf])
    hi = np.array([quantile(GRID, row, .9) or GRID[-1] for row in cdf])
    result["interval_10_90_coverage"] = float(np.mean((frame.next_days >= lo) & (frame.next_days <= hi)))
    result["interval_10_90_mean_width_days"] = float(np.mean(hi-lo))
    return result, probs, medians


def forest_cdf(forest, x):
    survival = forest.predict_survival_function(x)
    return np.array([[1.-float(s(min(day, forest.unique_times_[-1]))) if day >= forest.unique_times_[0] else 0. for day in GRID] for s in survival])


def export(forest, imputer, features):
    indices = np.maximum(0, np.searchsorted(forest.unique_times_, GRID, side="right")-1)
    trees = []
    for estimator in forest.estimators_:
        t = estimator.tree_
        leaves = np.flatnonzero(t.children_left == -1)
        values = {}
        for leaf in leaves:
            s = t.value[leaf, indices, 1].copy()
            s[np.array(GRID) < forest.unique_times_[0]] = 1.
            values[str(leaf)] = np.round(s, 9).tolist()
        trees.append(dict(left=t.children_left.tolist(), right=t.children_right.tolist(), feature=t.feature.tolist(),
                          threshold=t.threshold.tolist(), survival=values))
    return dict(kind="random_survival_forest", features=features, medians=imputer.statistics_.tolist(),
                missing_indicators=imputer.indicator_.features_.tolist(), trees=trees)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    visits, audit = load_visits()
    frame = assign_splits(examples(visits))
    frame.to_json(OUT / "examples.json", orient="records", indent=2)
    frame[["cohort", "subject", "split"]].drop_duplicates().to_csv(OUT / "subject_splits.csv", index=False)
    known = frame[frame.next_days.notna()].copy()
    train, val, test = [known[known.split == s].copy() for s in ("train", "validation", "test")]
    for c in audit:
        audit[c]["known_intervals"] = int(sum(known.cohort == c))
        audit[c]["unknown_terminal_visits"] = int(sum((frame.cohort == c) & frame.next_days.isna()))
    split_audit = {s: dict(subjects=int(frame[frame.split == s][["cohort", "subject"]].drop_duplicates().shape[0]),
                          labelled_subjects=int(known[known.split == s].subject.nunique()),
                          known_intervals=int(sum(known.split == s)), unknown_terminal=int(sum((frame.split == s) & frame.next_days.isna()))) for s in ("train", "validation", "test")}
    train_counts = train.groupby(["cohort", "subject"]).next_days.transform("size")
    weights = 1./train_counts.to_numpy()
    # The empirical baseline is subject weighted, matching the forest training objective.
    baseline_cdf = np.array([np.average(train.next_days <= d, weights=weights) for d in GRID])
    baseline = dict(kind="empirical", cdf=baseline_cdf.tolist())
    base_val = evaluate(val, np.tile(baseline_cdf, (len(val), 1)))[0]
    candidates = [dict(id="subject-weighted empirical baseline", validation=base_val)]
    best_score = (base_val["mae_days"], base_val["brier_90d"])
    best, best_id, chosen_cdf = baseline, candidates[0]["id"], np.tile(baseline_cdf, (len(test), 1))
    best_forest = None
    y = Surv.from_arrays(np.ones(len(train), dtype=bool), train.next_days.to_numpy(float))
    for use_masks in (False, True):
        features = FEATURES + (MASK_FEATURES if use_masks else [])
        imp = SimpleImputer(strategy="median", add_indicator=True)
        x = imp.fit_transform(train[features])
        for leaf in (5, 10, 20):
            for depth in (4, 8):
                forest = RandomSurvivalForest(n_estimators=100, min_samples_leaf=leaf, max_depth=depth, max_features=1., random_state=42, n_jobs=2)
                forest.fit(x, y, sample_weight=weights)
                stats = evaluate(val, forest_cdf(forest, imp.transform(val[features])))[0]
                name = f"RSF {'history+published_masks' if use_masks else 'history'} leaf={leaf} depth={depth}"
                candidates.append(dict(id=name, validation=stats))
                score = (stats["mae_days"], stats["brier_90d"])
                if score < best_score:
                    best_score, best_id, best_forest = score, name, forest
                    best = export(forest, imp, features)
                    chosen_cdf = forest_cdf(forest, imp.transform(test[features]))
                print(name, 'validation MAE', round(stats['mae_days'],2), 'Brier', round(stats['brier_90d'],4), flush=True)
    # LR-LRU motivates a transparent logistic baseline; its target here is a proxy.
    logit_candidates = []
    for c in (.1, 1., 10.):
        model = make_pipeline(SimpleImputer(strategy="median", add_indicator=True), StandardScaler(), LogisticRegression(C=c, max_iter=2000, random_state=42))
        model.fit(train[FEATURES], train.next_days <= 90, logisticregression__sample_weight=weights)
        prob = model.predict_proba(val[FEATURES])[:, 1]
        logit_candidates.append((brier_score_loss(val.next_days <= 90, prob), c, model))
    _, logit_c, logit = min(logit_candidates, key=lambda x: x[0])
    logistic_test = metrics(test, logit.predict_proba(test[FEATURES])[:, 1], np.full(len(test), np.median(train.next_days)))
    best.update(grid_days=GRID, model_id="visit-proxy-v1", selected=best_id, target="conditional_next_recorded_visit", seed=42,
                selection="validation MAE, then Brier90; no refit after test", train_subjects=split_audit["train"]["subjects"])
    # Verify the portable runtime against the library BEFORE shipping it.
    portable = np.array([predict_cdf(best, {f: None if pd.isna(row[f]) else row[f] for f in FEATURES+MASK_FEATURES}) for _, row in test.iterrows()])
    error = float(np.max(np.abs(chosen_cdf-portable)))
    if error > 1e-7:
        raise AssertionError(f"Portable forest differs by {error}")
    stats, prob, days = evaluate(test, portable)
    per_cohort = {c: evaluate(test[test.cohort == c], portable[test.cohort.to_numpy() == c])[0] for c in sorted(test.cohort.unique())}
    test_baseline = evaluate(test, np.tile(baseline_cdf, (len(test), 1)))[0]
    test["p90"], test["predicted_days"] = prob, days
    test.to_json(OUT / "test_predictions.json", orient="records", indent=2)
    # Cluster bootstrap keeps repeated examples from the same subject together.
    rng = np.random.default_rng(2026)
    groups = list(test.groupby(["cohort", "subject"]).indices.values())
    boot = []
    for _ in range(500):
        indices = np.concatenate([groups[i] for i in rng.integers(0, len(groups), len(groups))])
        boot.append((accuracy_score(test.next_days.to_numpy()[indices] <= 90, prob[indices] >= .5), mean_absolute_error(test.next_days.to_numpy()[indices], days[indices])))
    intervals = np.quantile(boot, [.025, .975], axis=0)
    stats["subject_bootstrap_95ci_accuracy_90d"] = intervals[:, 0].tolist()
    stats["subject_bootstrap_95ci_mae_days"] = intervals[:, 1].tolist()
    model_bytes = json.dumps(best, separators=(",", ":"), allow_nan=False).encode()
    (ROOT / "src/ml_model/longitudinal_model.json").write_bytes(model_bytes)
    report = dict(audit=audit, split=split_audit, selected=best_id, validation_candidates=candidates,
                  test=stats, test_by_cohort=per_cohort, empirical_baseline_test=test_baseline,
                  logistic_baseline_test=logistic_test, logistic_selected_c=logit_c,
                  historical_interval_baselines_test={c: dict(mae_days=float(np.mean(np.abs(test.next_days-test[c].fillna(float(train.next_days.median()))))), fallback_train_median_days=float(train.next_days.median())) for c in ("last_gap_days", "median_gap_days")},
                  portable_max_absolute_error=error, model_bytes=len(model_bytes), model_sha256=hashlib.sha256(model_bytes).hexdigest(),
                  limitations=["No retrieval ground truth", "Conditional on a subsequent archived visit; terminal outcomes excluded, not negative",
                               "TCGA 2015 metadata snapshot; pixel downloads controlled", "LUMIERE rounded to weeks; same-week visits collapsed",
                               "Small cohorts and subject-level holdout; internal validation only", "No survival-time, outcome, future rating, future mask, or patient ID predictor"],
                  references=["https://doi.org/10.1214/08-AOAS169", "https://doi.org/10.1109/ACCESS.2019.2913961", "https://doi.org/10.1038/s41597-022-01881-7"])
    (ROOT / "architecture/longitudinal_metrics.json").write_text(json.dumps(report, indent=2, allow_nan=False))
    print(json.dumps({k: report[k] for k in ("audit", "split", "selected", "test", "test_by_cohort", "empirical_baseline_test", "logistic_baseline_test", "model_bytes", "portable_max_absolute_error")}, indent=2))


if __name__ == "__main__":
    main()
