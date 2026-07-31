# results/

Experiment outputs, metrics, graphs and execution screenshots. **Owner: Mehul Anand**, with
screenshots contributed by whoever ran the component.

This folder is the evidence that the project works. At review, claims made in the report need
something here to back them up.

## What goes here

| Path | Contents |
| --- | --- |
| `metrics/` | Per-run metrics as CSV or JSON — accuracy, precision, recall, F1, confusion matrix |
| `cost_analysis/` | Monthly storage cost under our model vs. each baseline |
| `graphs/` | Plots — cost comparison, confusion matrix, tier distribution, training curves |
| `screenshots/` | Execution screenshots, AWS console views, the running application |
| `experiments.md` | A running log of every experiment: date, config, result, conclusion |

## Metrics to report

**Classification quality**
- Accuracy, precision, recall, F1 — per tier, not only overall. A model that is 95% accurate
  because 95% of scans belong in one tier has learned nothing.
- Confusion matrix. The cell that matters most is *scans that needed fast access but were sent to
  archive* — call it out explicitly rather than leaving it buried in the matrix.

**Cost — the headline number**
- Projected monthly bill under our model
- Same, under each baseline (all-Standard, age-based rule, S3 Intelligent-Tiering)
- Percentage saved, with transition and retrieval charges included

**Operational**
- Time to produce a prediction
- Retrieval latency by tier
- How often a scan had to be pulled back out of archive

## Rules

- **Log every experiment in `experiments.md`, including the failed ones.** A record showing which
  approaches were tried and rejected is worth marks — it demonstrates method rather than luck.
- **Record the config with the result.** A metric with no configuration attached cannot be
  reproduced or explained three weeks later.
- **Name files with dates:** `2026-08-15_baseline_comparison.png`, not `final_graph.png`.
- **Label every graph** — axes, units, legend. An unlabelled chart in a report invites the question
  "what am I looking at?"
- Screenshots must be readable when printed. Crop to what matters.
- No patient-identifiable data in any screenshot. Check before committing — Git history is permanent.

## Note

Do not commit only the good results. If the model loses to a baseline on some measure, record that
too and explain it. An honest limitation section is far more defensible than a set of numbers that
looks too clean.
