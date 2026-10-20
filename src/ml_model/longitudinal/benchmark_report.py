"""Render aggregate benchmark results; no patient-level rows enter the report."""
import argparse
import json
from pathlib import Path
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from data import ROOT


def report(run_id):
    folder = ROOT / "experiments/longitudinal" / run_id
    results = json.loads((folder / "results.json").read_text())
    meta = json.loads((folder / "protocol.json").read_text())
    baseline = json.loads((folder / "baselines.json").read_text())["cohort_prior_median"]
    selection = json.loads((folder / "selection.json").read_text())
    audit = json.loads((folder / "audit.json").read_text())
    last_gap = audit["deterministic_last_gap_rule"]["metrics"]
    by_id = {r["family"]: r for r in results}
    best = by_id[selection["classification"]]
    timing = by_id[selection["timing"]]
    rows = sorted(results, key=lambda r: -r["nested_cv"]["subject_weighted_balanced_accuracy_90d"])
    names = [r["label"] for r in rows]
    fig, axes = plt.subplots(1, 2, figsize=(15, 8), constrained_layout=True)
    for ax, key, interval, color, title in [
        (axes[0], "subject_weighted_balanced_accuracy_90d", "subject_weighted_balanced_accuracy_95ci", "#197c80", "90-day balanced accuracy · equal weight per subject"),
        (axes[1], "subject_weighted_mae_days", "subject_weighted_mae_days_95ci", "#a56c24", "Mean timing error · equal weight per subject")]:
        values = np.array([r["nested_cv"][key] for r in rows])
        bounds = np.array([r["bootstrap"][interval] for r in rows])
        ax.barh(names, values, color=color, alpha=.85)
        ax.errorbar(values, np.arange(len(rows)), xerr=np.maximum(0, np.array([values-bounds[:, 0], bounds[:, 1]-values])), fmt="none", ecolor="#25363a", capsize=3)
        ax.axvline(baseline[key], color="#b94343", linestyle="--", label="Cohort-prior baseline")
        ax.invert_yaxis(); ax.set_title(title, fontsize=11)
        ax.set_xlabel("Fraction · higher is better" if "accuracy" in key else "Days · lower is better")
        ax.spines[["top", "right"]].set_visible(False)
        ax.grid(axis="x", alpha=.15); ax.set_axisbelow(True)
        ax.legend(loc="lower right", fontsize=9)
    axes[0].set_xlim(0, 1)
    fig.suptitle("Next recorded-visit proxy: nested patient-group validation\nBars: out-of-fold estimates · whiskers: patient-cluster bootstrap 95% intervals", fontsize=14)
    fig.savefig(folder / "comparison.png", dpi=160)
    plt.close(fig)
    lines = ["# Local 12-model benchmark", "", f"Run: `{run_id}`. Completed {selection['completed_utc']}.", "",
        "All training and evaluation ran locally. The deployed model artifact and AWS deployment were unchanged.", "",
        "## Scope and evaluation", "",
        "The target remains the next recorded imaging visit **conditional on another visit appearing in the archive**. These are follow-up proxy results, not verified retrieval prediction.", "",
        f"Development contains {meta['development']['intervals']} known intervals from {meta['development']['labelled_subjects']} subjects. The original {meta['inspected_holdout']['intervals']}-interval / {meta['inspected_holdout']['labelled_subjects']}-subject holdout was inspected previously; it is excluded from development and reported only as a diagnostic. It is not a newly untouched test.", "",
        "- Five outer folds keep complete subjects together. Three inner grouped folds select settings and thresholds using only each outer training partition.",
        "- Twelve model families each compare two regularization/complexity settings and two feature sets: history alone; history plus available masks and current-scan technical metadata.",
        "- Preprocessing fits inside each fold. Patient ID, future dates, future scans, survival time and outcomes are excluded from predictors.",
        "- Classification and timing settings are selected separately within each family. The 90-day threshold is selected on inner out-of-fold predictions, never the outer evaluation labels.",
        "- Classification is ranked by patient-weighted balanced accuracy, then patient-weighted Brier score. Timing is ranked by patient-weighted MAE. Raw row-level metrics are also saved.",
        "- Sample weights give each training subject equal total weight when supported. Nearest neighbors does not support fit sample weights. SVM's built-in probability calibration uses its training rows; the external nested folds still keep patients separated.",
        "- Bootstrap intervals resample complete subjects 1,000 times. They quantify sampling uncertainty within these cohorts, not external validity or uncertainty from selecting among twelve families.", "",
        "Current-scan metadata includes series count; measured TCGA source bytes/image count; available LUMIERE original voxel counts/field strength; and publisher mask shape summaries. Unavailable cohort-specific features stay missing and are imputed inside training folds. No image sizes are fabricated.", "",
        "## Nested validation comparison", "",
        "`BA` below is balanced accuracy with equal total weight per subject. `AUC` and `Brier` are also subject weighted. `Row MAE` weights every interval equally; `Subject MAE` gives subjects equal total weight. Differences from the earlier single-split result reflect this wider evaluation and weighting.", "",
        "| Model family | Raw accuracy | Subject BA | Subject AUC | Subject Brier ↓ | Row MAE days ↓ | Subject MAE days ↓ |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: |"]
    for r in rows:
        m = r["nested_cv"]
        lines.append(f"| {r['label']} | {m['accuracy_90d']:.1%} | {m['subject_weighted_balanced_accuracy_90d']:.1%} | {m['subject_weighted_auc_90d']:.3f} | {m['subject_weighted_brier_90d']:.3f} | {m['mae_days']:.1f} | {m['subject_weighted_mae_days']:.1f} |")
    lines += [f"| Cohort-prior / median baseline | {baseline['accuracy_90d']:.1%} | {baseline['subject_weighted_balanced_accuracy_90d']:.1%} | {baseline['subject_weighted_auc_90d']:.3f} | {baseline['subject_weighted_brier_90d']:.3f} | {baseline['mae_days']:.1f} | {baseline['subject_weighted_mae_days']:.1f} |",
        f"| Last-gap rule (hard classification) | {last_gap['accuracy_90d']:.1%} | {last_gap['subject_weighted_balanced_accuracy_90d']:.1%} | {last_gap['subject_weighted_auc_90d']:.3f} | {last_gap['subject_weighted_brier_90d']:.3f} | {last_gap['mae_days']:.1f} | {last_gap['subject_weighted_mae_days']:.1f} |", "",
        "![Model comparison with uncertainty](comparison.png)", "", "## Leading candidates", ""]
    leaders = [("Classification and timing", best)] if best["family"] == timing["family"] else [("Classification", best), ("Timing", timing)]
    for label, r in leaders:
        m, ci = r["nested_cv"], r["bootstrap"]
        lines += [f"**{label}: {r['label']}.**", "",
            f"Nested subject-weighted BA {m['subject_weighted_balanced_accuracy_90d']:.1%} (95% interval {ci['subject_weighted_balanced_accuracy_95ci'][0]:.1%}–{ci['subject_weighted_balanced_accuracy_95ci'][1]:.1%}); raw accuracy {m['accuracy_90d']:.1%}; subject AUC {m['subject_weighted_auc_90d']:.3f}.", "",
            f"Row MAE {m['mae_days']:.1f} days; subject-weighted MAE {m['subject_weighted_mae_days']:.1f} days (95% interval {ci['subject_weighted_mae_days_95ci'][0]:.1f}–{ci['subject_weighted_mae_days_95ci'][1]:.1f}).", "",
            f"Paired improvement over the cohort baseline: BA interval {ci['balanced_accuracy_improvement_over_cohort_baseline_95ci'][0]*100:.1f} to {ci['balanced_accuracy_improvement_over_cohort_baseline_95ci'][1]*100:.1f} percentage points; timing improvement interval {ci['mae_improvement_over_cohort_baseline_days_95ci'][0]:.1f} to {ci['mae_improvement_over_cohort_baseline_days_95ci'][1]:.1f} days.", ""]
    lines += ["### Cohort breakdown for the classification leader", "",
        "| Cohort | Intervals / subjects | Raw accuracy | Subject BA | Subject AUC | Row MAE | Subject MAE |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: |"]
    for c, m in best["nested_cv_by_cohort"].items():
        auc = f"{m['subject_weighted_auc_90d']:.3f}" if m['subject_weighted_auc_90d'] is not None else "undefined"
        lines.append(f"| {c} | {m['n']} / {m['subjects']} | {m['accuracy_90d']:.1%} | {m['subject_weighted_balanced_accuracy_90d']:.1%} | {auc} | {m['mae_days']:.1f} | {m['subject_weighted_mae_days']:.1f} |")
    paired = audit["paired_comparisons_against_last_gap_rule"][best["family"]]["balanced_accuracy_improvement_over_cohort_baseline_95ci"]
    lines += ["", f"Against the deterministic last-gap rule, the classification leader's paired subject-BA improvement has a 95% interval of {paired[0]*100:.1f} to {paired[1]*100:.1f} percentage points. Its raw accuracy improvement is only {(best['nested_cv']['accuracy_90d']-last_gap['accuracy_90d'])*100:.1f} points. This stronger baseline comparison limits any headline claim.", "",
        f"There are {audit['development_long_tail']['intervals_over_365_days']} development intervals longer than a year, across {audit['development_long_tail']['subjects_with_interval_over_365_days']} subjects; the longest is {audit['development_long_tail']['maximum_interval_days']:.0f} days. These records remain in the evaluation. Sparse subjects with long gaps have greater influence under equal-subject weighting, widening the timing uncertainty."]
    screen = meta["protocol"]["practical_screen"]
    passes = (best["nested_cv"]["subject_weighted_balanced_accuracy_90d"] >= screen["subject_weighted_balanced_accuracy_90d"] and
              best["nested_cv"]["subject_weighted_auc_90d"] >= screen["subject_weighted_auc_90d"] and
              best["bootstrap"]["balanced_accuracy_improvement_over_cohort_baseline_95ci"][0] > 0 and
              best["nested_cv"]["subject_weighted_brier_90d"] < baseline["subject_weighted_brier_90d"])
    warning_counts = {}
    for r in rows:
        notes = set(r["warnings"])
        for fold in range(meta["protocol"]["outer_folds"]):
            saved = json.loads((folder / f"folds/{r['family']}_{fold}.json").read_text())
            notes.update(saved["warnings"])
            for candidate in saved["candidates"]: notes.update(candidate["warnings"])
        if notes: warning_counts[r["label"]] = sorted(notes)
    lines += ["", "## Can we rely on this accuracy?", "",
        "The predeclared exploratory classification screen requires at least 70% subject-weighted balanced accuracy, AUC 0.75, a positive lower confidence bound for baseline improvement, and lower Brier score than baseline.", "",
        f"Classification screen: **{'passes the exploratory screen' if passes else 'not met'}**. Even a pass requires new independent subjects and actual retrieval labels before relying on retrieval decisions.", "",
        f"The separate practical timing screen is subject-weighted MAE <=35 days. Best observed: {timing['nested_cv']['subject_weighted_mae_days']:.1f} days — **{'met' if timing['nested_cv']['subject_weighted_mae_days'] <= 35 else 'not met'}**.", "",
        "The terminal outcomes remain unknown; no synthetic negatives, oversampled copies in evaluation, favourable patient split, or edited targets were used to raise the reported accuracy. Source-specific acquisition patterns may limit transfer to a different archive. This run is exploratory model comparison, not new prospective evidence.", "",
        "Optimization warnings are retained in the fold/model files. " + ("The small neural network hit its configured iteration limit in some fits; its scores are reported with that limitation." if "Small neural network" in warning_counts else "No neural-network convergence warning was recorded."), "",
        "## Previously inspected holdout: diagnostic only", "",
        "These scores are saved for transparency and are not used for selection. Multiple comparisons on this already viewed set do not make its best score an independent accuracy claim.", "",
        "| Model | Raw accuracy | Subject BA | Row MAE days |",
        "| --- | ---: | ---: | ---: |"]
    for r in rows:
        m = r["previously_inspected_holdout_diagnostic"]
        lines.append(f"| {r['label']} | {m['accuracy_90d']:.1%} | {m['subject_weighted_balanced_accuracy_90d']:.1%} | {m['mae_days']:.1f} |")
    lines += ["", "## Saved evidence", "",
        "- `leaderboard.csv`, `results.json`: all twelve aggregate comparisons; all raw/weighted metrics.",
        "- `protocol.json`: fixed selection rules, input/code checksums, package versions and data counts.",
        "- `folds/*.json`: every candidate setting, inner-CV result, selected threshold, outer-fold result and convergence warning.",
        "- `models/*.json`: final configuration, full estimator representations, cohort metrics, bootstrap intervals and model artifact checksum.",
        f"- Private local outputs: `dataset/processed/longitudinal/benchmarks/{run_id}/` contains input rows, fold assignments, all candidate inner predictions, outer/holdout predictions and twelve final `.pkl` model bundles. These patient-level outputs and fitted binaries stay ignored by Git.",
        "- `selection.json`: exploratory classification/timing choices and proof that the deployed model artifact was unchanged.", "",
        f"- `audit.json`: all {audit['model_bundles_verified']} model bundles reload successfully and reproduce saved predictions within CSV storage precision (tolerance: 1e-6 probability, 0.001 day). A full-precision input snapshot is preserved privately; production artifact checksum is unchanged. Also includes the last-gap rule comparison and long-interval audit.", "",
        "Pickle bundles are local trusted Python artifacts tied to the saved package versions; they are not portable deployment artifacts. No production model or AWS storage setting was changed.", "",
        "## Reproduce / resume", "", "```powershell",
        "python -m pip install -r src/ml_model/longitudinal/requirements-benchmark.txt",
        "python -m pip install --no-deps scikit-survival==0.25.0",
        f"python src/ml_model/longitudinal/benchmark.py --run-id {run_id}",
        f"python src/ml_model/longitudinal/benchmark_audit.py --run-id {run_id}",
        f"python src/ml_model/longitudinal/benchmark_report.py --run-id {run_id}", "```", "",
        "Partial runs require identical input, protocol and benchmark code. Completed folds are checkpointed. Completed-run aggregation permits a runner-only reporting repair when model/data code is unchanged; original training source checksums remain intact and the reporting revision is recorded in `completed_resume_provenance.json`. `original_sources/` preserves the source used for training. Use a new run ID when changing the experiment.", "",
        "Method references: [scikit-learn grouped cross-validation](https://scikit-learn.org/stable/modules/cross_validation.html#stratifiedgroupkfold), [balanced accuracy](https://scikit-learn.org/stable/modules/model_evaluation.html#balanced-accuracy-score), [XGBoost parameters](https://xgboost.readthedocs.io/en/stable/parameter.html), [Random Survival Forests](https://doi.org/10.1214/08-AOAS169).", ""]
    (folder / "REPORT.md").write_text("\n".join(lines), encoding="utf-8")
    print(json.dumps(dict(classification=best["label"], timing=timing["label"], classification_screen_met=bool(passes), report=str(folder / "REPORT.md")), indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(); parser.add_argument("--run-id", required=True)
    report(parser.parse_args().run_id)
