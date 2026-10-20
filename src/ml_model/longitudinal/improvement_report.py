"""Explain the second XGBoost round with complete-coverage and selective scores."""
import argparse
import json
from pathlib import Path
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from benchmark import ROOT, write_json
from improve_xgboost import confidence_intervals


def report(run_id):
    folder = ROOT / "experiments/longitudinal" / run_id
    private = ROOT / "dataset/processed/longitudinal/benchmarks" / run_id
    result = json.loads((folder / "results.json").read_text())
    protocol = json.loads((folder / "protocol.json").read_text())
    diagnosis = json.loads((folder / "diagnosis.json").read_text())
    training = json.loads((folder / "previous_training_audit.json").read_text())
    partial = json.loads((folder / "partial_mask_audit.json").read_text())
    ablation = json.loads((folder / "ablation.json").read_text())
    old_folder = ROOT / "experiments/longitudinal/local-12-models-20261020"
    previous = json.loads((old_folder / "models/xgboost.json").read_text())["nested_cv"]
    frame = pd.read_pickle(private / "input_full_precision.pkl")
    dev = frame[frame.next_days.notna() & (frame.split != "test")].reset_index(drop=True)
    prediction = pd.read_csv(private / "nested_oof_predictions.csv").set_index("row_id").loc[dev.row_id]
    old = pd.read_csv(ROOT / "dataset/processed/longitudinal/benchmarks/local-12-models-20261020/xgboost_nested_oof_predictions.csv").set_index("row_id").loc[dev.row_id]
    truth = dev.next_days.to_numpy() <= 90
    old_ok = truth == (old.probability_90d.to_numpy() >= old.threshold.to_numpy())
    new_ok = truth == (prediction.probability_90d.to_numpy() >= prediction.threshold.to_numpy())
    paired = dict(previously_wrong_now_correct=int(sum(~old_ok & new_ok)), previously_correct_now_wrong=int(sum(old_ok & ~new_ok)))
    write_json(folder / "paired_error_changes.json", paired)
    old_ci = confidence_intervals(dev, old.probability_90d.to_numpy(), old.threshold.to_numpy())
    new, selective = result["nested_full"], result["selective"]
    keep_previous = new["subject_weighted_balanced_accuracy_90d"] <= previous["subject_weighted_balanced_accuracy_90d"]
    fixed = next(r["metrics"] for r in ablation["results"] if r["hypothesis"] == "Fixed median-imputed reference")
    write_json(folder / "recommendation.json", dict(retain_previous_local_xgboost=keep_previous,
        expanded_candidate_promoted=False, full_coverage_80pct_met=bool(new["accuracy_90d"] >= .8),
        selective_80pct_met=bool(selective["metrics"] and selective["metrics"]["accuracy_90d"] >= .8),
        original_subject_balanced_accuracy=previous["subject_weighted_balanced_accuracy_90d"],
        expanded_subject_balanced_accuracy=new["subject_weighted_balanced_accuracy_90d"],
        fixed_reference_raw_accuracy=fixed["accuracy_90d"], aws_actions="none",
        original_local_bundle="dataset/processed/longitudinal/benchmarks/local-12-models-20261020/models/xgboost.pkl"))
    fig, axes = plt.subplots(1, 2, figsize=(13, 5), constrained_layout=True)
    labels = ["Previous\nraw accuracy", "Expanded\nraw accuracy", "Previous\nsubject BA", "Expanded\nsubject BA"]
    values = [previous["accuracy_90d"], new["accuracy_90d"], previous["subject_weighted_balanced_accuracy_90d"], new["subject_weighted_balanced_accuracy_90d"]]
    axes[0].bar(labels, values, color=["#8a9aab", "#147c80", "#8a9aab", "#147c80"])
    cis = [old_ci["accuracy_95ci"], result["nested_confidence_intervals"]["accuracy_95ci"], old_ci["subject_weighted_balanced_accuracy_95ci"], result["nested_confidence_intervals"]["subject_weighted_balanced_accuracy_95ci"]]
    bounds = np.array(cis)
    axes[0].errorbar(np.arange(4), values, yerr=np.maximum(0, [np.array(values)-bounds[:, 0], bounds[:, 1]-np.array(values)]), fmt="none", capsize=4, ecolor="#25353a")
    axes[0].axhline(.8, color="#b94343", linestyle="--", label="80% goal")
    axes[0].set_ylim(0, 1); axes[0].set_title("All development intervals · grouped outer CV")
    axes[0].set_ylabel("Fraction · patient-bootstrap 95% intervals")
    axes[0].legend()
    for i, value in enumerate(values): axes[0].text(i, value+.015, f"{value:.1%}", ha="center", fontsize=9)
    if selective["accepted_intervals"]:
        accepted = prediction.accepted.to_numpy(dtype=bool)
        correct = truth[accepted] == (prediction.selective_probability.to_numpy()[accepted] >= prediction.selective_threshold.to_numpy()[accepted])
        correct_fraction = correct.sum()/len(dev)
        wrong_fraction = (~correct).sum()/len(dev)
        coverage = selective["coverage"]
        axes[1].barh(["All intervals"], [correct_fraction], color="#147c80", label="Accepted, correct")
        axes[1].barh(["All intervals"], [wrong_fraction], left=[correct_fraction], color="#bb6b49", label="Accepted, wrong")
        axes[1].barh(["All intervals"], [1-coverage], left=[coverage], color="#ced5db", label="Abstained")
        axes[1].set_title(f"Selective policy: {selective['metrics']['accuracy_90d']:.1%} accuracy\nat {coverage:.1%} coverage")
        axes[1].legend(loc="upper center", bbox_to_anchor=(.5, -.12), ncol=1)
    else:
        axes[1].text(.5, .5, "No selective policy met the inner-CV criteria\nCoverage: 0% · accuracy undefined", ha="center", va="center", transform=axes[1].transAxes)
        axes[1].set_title("Selective policy: 80% target with abstention")
    axes[1].set_xlim(0, 1); axes[1].set_xlabel("Fraction of the complete evaluation set")
    for ax in axes:
        ax.spines[["top", "right"]].set_visible(False)
    fig.suptitle("XGBoost improvement round · next recorded-visit proxy", fontsize=14)
    fig.savefig(folder / "comparison.png", dpi=160); plt.close(fig)
    lines = ["# XGBoost improvement round", "", f"Completed: {result['completed_utc']}. Local only; AWS and the production model artifact are unchanged.", "",
        "The target remains a next recorded imaging visit within 90 days, conditional on a later archived visit. **These are not actual file-retrieval labels.** This is a second exploratory round on previously studied cohorts; it does not create a new independent test set.", "",
        f"**80% was not achieved in this run.** The larger search scored {new['accuracy_90d']:.1%} full-set raw accuracy versus {previous['accuracy_90d']:.1%} previously. A fixed median-imputed setting reached {fixed['accuracy_90d']:.1%}, with subject-BA {fixed['subject_weighted_balanced_accuracy_90d']:.1%}. The expanded candidate is not promoted; the previous local model remains preferable under the original subject-BA criterion.", "",
        "## Why the earlier model was below 80%", "",
        f"1. **Small independent sample.** There are {protocol['development_subjects']} labelled development subjects and {protocol['development_intervals']} intervals. Several intervals from one person do not provide the same evidence as new independent people.",
        f"2. **A generalization gap.** The previous model scored {training['in_sample_subject_weighted_balanced_accuracy']:.1%} subject-weighted balanced accuracy on training patients, compared with {training['nested_cv_subject_weighted_balanced_accuracy']:.1%} in grouped outer validation. This is consistent with limited generalization; a training score of 80% is not unseen-patient performance.",
        f"3. **Missing/over-aggregated features and cohort differences.** TCGA has no mask summaries in the input release used here. The combined three-region summary is unavailable for {partial['combined_three_region_summary_missing']} of {partial['development_lumiere_intervals']} LUMIERE development intervals ({diagnosis['cohorts']['LUMIERE']['missing_mask_fraction']:.1%}). Of those, {partial['partial_summaries_lost_by_combined_aggregation']} still have one or two usable regional summaries, which the old aggregate did not preserve separately; {partial['no_region_summary_available']} have no region-volume summary. This does not prove the MRI or mask file is absent. The new regional feature columns preserve available information without inventing zero volumes. Earlier cohort accuracies were 77.0% TCGA and 64.8% LUMIERE.",
        f"4. **A coarse time boundary.** LUMIERE has {diagnosis['cohorts']['LUMIERE']['intervals_recorded_91_days']} development intervals recorded as 91 days. With week-floor anonymization, such a recorded difference can correspond to a true gap of 85–97 days. The true side of a 90-day calendar boundary is not identifiable from these data.",
        "5. **Omitted dynamic information.** The earlier compact model used current summaries and interval aggregates but not many current-versus-prior changes or detailed radiomics. This is a plausible feature limitation, tested below; it is not proof that every missing feature explains an error.", "",
        "Attendance, scheduling and actual file retrieval also depend on information absent from the dataset. The audit identifies limitations and hypotheses, not an estimated irreducible-error bound or proof that 80% is impossible.", "",
        "## What was changed and tested", "",
        f"- {len(protocol['configs'])} fixed candidate configurations, evaluated in five outer patient-group folds with three inner patient-group folds for tuning.",
        "- Original 17 predictors versus 49 temporal predictors versus 187 temporal/radiomic predictors. All derived changes use strictly earlier visits and the current visit; no future mask or outcome is included.",
        "- XGBoost native missing-value handling, alongside a fixed median-imputed reference.",
        "- Pooled training versus separate cohort models, six regularization/complexity settings, and thresholds tuned only on inner predictions.",
        "- A sensitivity experiment gives uncertain 91-day LUMIERE training intervals a soft label of 21/49 under independent uniform within-week offsets. This is an explicit assumption, not recovered ground truth. All original hard evaluation labels are unchanged in every headline score.",
        "- A separate abstaining policy: inner accuracy >=80%, subject-weighted balanced accuracy >=75%, coverage >=30%, at least 15 accepted subjects and at least 15 accepted examples of each class. Its predictions are evaluated separately; abstained cases remain in the coverage denominator.", "",
        "No difficult patients, long gaps or near-boundary cases were removed from the full evaluation. The original 118-interval holdout remains excluded from tuning and labelled diagnostic-only because it was inspected in previous rounds.", "",
        "## Complete-coverage results", "",
        "Scores below cover all 603 development intervals in the same original outer folds. BA gives equal total weight to each patient; row MAE weights intervals equally, subject MAE weights patients equally.", "",
        "| Metric | Previous XGBoost | Improvement search |", "| --- | ---: | ---: |",
        f"| Raw 90-day accuracy | {previous['accuracy_90d']:.1%} | {new['accuracy_90d']:.1%} |",
        f"| Subject-weighted balanced accuracy | {previous['subject_weighted_balanced_accuracy_90d']:.1%} | {new['subject_weighted_balanced_accuracy_90d']:.1%} |",
        f"| Subject-weighted AUC | {previous['subject_weighted_auc_90d']:.3f} | {new['subject_weighted_auc_90d']:.3f} |",
        f"| Subject-weighted Brier (lower better) | {previous['subject_weighted_brier_90d']:.3f} | {new['subject_weighted_brier_90d']:.3f} |",
        f"| Row timing MAE days | {previous['mae_days']:.1f} | {new['mae_days']:.1f} |",
        f"| Subject timing MAE days | {previous['subject_weighted_mae_days']:.1f} | {new['subject_weighted_mae_days']:.1f} |", "",
        f"New raw-accuracy 95% patient-bootstrap interval: {result['nested_confidence_intervals']['accuracy_95ci'][0]:.1%}–{result['nested_confidence_intervals']['accuracy_95ci'][1]:.1%}. Subject-BA interval: {result['nested_confidence_intervals']['subject_weighted_balanced_accuracy_95ci'][0]:.1%}–{result['nested_confidence_intervals']['subject_weighted_balanced_accuracy_95ci'][1]:.1%}.", "",
        f"Paired errors: {paired['previously_wrong_now_correct']} previously wrong predictions became correct; {paired['previously_correct_now_wrong']} previously correct predictions became wrong.", "",
        "| Cohort | Intervals | Raw accuracy | Subject BA |", "| --- | ---: | ---: | ---: |"]
    for cohort, m in result["nested_by_cohort"].items(): lines.append(f"| {cohort} | {m['n']} | {m['accuracy_90d']:.1%} | {m['subject_weighted_balanced_accuracy_90d']:.1%} |")
    lines += ["", "## Selective / uncertain predictions", ""]
    if selective["metrics"]:
        sm = selective["metrics"]; ci = selective["confidence_intervals"]
        lines += [f"The separately selected cautious policy accepted {selective['accepted_intervals']} of {selective['total_intervals']} intervals ({selective['coverage']:.1%} coverage), abstaining on {selective['abstained_intervals']}.", "",
            f"Accuracy on accepted cases: **{sm['accuracy_90d']:.1%}**, with a 95% interval of {ci['accuracy_95ci'][0]:.1%}–{ci['accuracy_95ci'][1]:.1%}. Subject-weighted balanced accuracy: {sm['subject_weighted_balanced_accuracy_90d']:.1%}.", "",
            "This is a selected-coverage result, not full-set accuracy. A point estimate above 80% would not establish an 80% lower confidence bound or validate actual retrieval. Remaining cases require abstention/fallback, not a silent prediction.", ""]
        if result["final_selective_config"] is None:
            lines += ["No single selective configuration met the inner criteria in all five training partitions. The final bundle therefore contains no supported selective head. The outer selective procedure also fell below 80%.", ""]
    else:
        lines += ["No candidate produced a supported selective policy under the fixed inner-CV criteria across the outer evaluations. Coverage is zero and selective accuracy is undefined. No 80% selective claim is made.", ""]
    lines += ["![Full versus selective evaluation](comparison.png)", "", "## Which hypotheses helped?", "",
        "Each restricted search below chooses configurations using inner folds only, then evaluates the outer rows. Groups overlap; these are exploratory comparisons, not causal effect estimates. The median reference has a single fixed configuration while other searches tune settings.", "",
        "| Restricted search | Raw accuracy | Subject BA | Subject AUC |", "| --- | ---: | ---: | ---: |"]
    for r in ablation["results"]:
        m = r["metrics"]; lines.append(f"| {r['hypothesis']} | {m['accuracy_90d']:.1%} | {m['subject_weighted_balanced_accuracy_90d']:.1%} | {m['subject_weighted_auc_90d']:.3f} |")
    lines += ["", "## What can be concluded", "",
        f"The unchanged full-coverage 80% target is **{'met as an exploratory point estimate' if new['accuracy_90d'] >= .8 else 'not met'}**. Any cohort-only or selective score must retain its cohort/coverage label. The previously viewed diagnostic holdout is not used to choose a successful headline.", "",
        f"The final model's in-sample accuracy is {result['in_sample_training']['accuracy_90d']:.1%}; grouped validation remains the relevant comparison for new patients. Further rounds on the same cohorts add researcher-selection optimism and need independent external evaluation.", "",
        "A valid next step toward reliable retrieval prediction needs timestamped access events, observation coverage and source-time scheduling/context information. The current experiment cannot infer those missing labels or exact calendar dates.", "",
        "## Saved files", "",
        "- `diagnosis.json`, `partial_mask_audit.json`, `previous_training_audit.json`: measured limitations, partial-region summary loss, and training-versus-validation gap.",
        "- `protocol.json`, `environment.json`, `original_sources/`: fixed candidate search, label/coverage rules, dependency versions and original code snapshots.",
        "- `folds/*.json`: all 73 inner candidate scores per outer fold, selected configurations and outer results.",
        "- `results.json`: full, cohort, selective, uncertainty and diagnostic-holdout results; model checksum and reload evidence.",
        "- `configuration_summary.csv`: all candidate inner scores; these are tuning scores, not the headline evaluation.",
        "- `ablation.csv`, `ablation.json`: restricted-search outer comparisons.",
        "- `feature_gain.json`: training-only model gain summaries; not causal feature importance.",
        "- `recommendation.json`: expanded model not promoted; previous local XGBoost retained. `model_reload_audit.json` verifies full/timing/available selective fold bundles reload with matching predictions.",
        f"- Private local path: `dataset/processed/longitudinal/benchmarks/{run_id}/` stores full-precision features, all candidate predictions, fold assignments, fold model bundles and final classifier/timing/selective models.",
        "- The final saved model reloads and reproduces its predictions. The production artifact checksum is unchanged, and no AWS API is called by this workflow.", "",
        "```powershell", f"python src/ml_model/longitudinal/improve_xgboost.py --run-id {run_id}",
        f"python src/ml_model/longitudinal/improvement_diagnose.py --run-id {run_id}",
        f"python src/ml_model/longitudinal/improvement_ablation.py --run-id {run_id}",
        f"python src/ml_model/longitudinal/improvement_report.py --run-id {run_id}", "```", "",
        "Sources: [XGBoost missing-value handling](https://xgboost.readthedocs.io/en/stable/faq.html#how-to-deal-with-missing-values), [XGBoost regularization parameters](https://xgboost.readthedocs.io/en/stable/parameter.html), [LUMIERE author documentation](https://github.com/ysuter/gbm-data-longitudinal).", ""]
    (folder / "REPORT.md").write_text("\n".join(lines), encoding="utf-8")
    print(json.dumps(dict(full_accuracy=new["accuracy_90d"], subject_balanced_accuracy=new["subject_weighted_balanced_accuracy_90d"], selective_accuracy=selective["metrics"]["accuracy_90d"] if selective["metrics"] else None, selective_coverage=selective["coverage"], report=str(folder / "REPORT.md")), indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(); parser.add_argument("--run-id", default="xgboost-improvement-20261020")
    report(parser.parse_args().run_id)
