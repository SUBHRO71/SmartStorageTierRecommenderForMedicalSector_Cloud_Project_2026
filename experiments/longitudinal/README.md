# Local longitudinal model experiments

These experiments predict the next recorded visit conditional on a later archived
visit. They do not use actual file-retrieval labels. All training runs locally.

## Second round: diagnose and improve XGBoost

Run: `xgboost-improvement-20261020`.

- [Reasons, attempted corrections and full results](xgboost-improvement-20261020/REPORT.md)
- [Controlled feature/model comparisons](xgboost-improvement-20261020/ablation.csv)
- [Exact full/cohort/selective results](xgboost-improvement-20261020/results.json)
- [Recommendation](xgboost-improvement-20261020/recommendation.json)

73 XGBoost candidate configurations tested temporal/radiomic features, native
missingness, cohort-specific models, regularization and uncertain weekly labels.
A partial-region aggregation limitation was identified; the expanded features
preserve regional measurements that the previous combined summary lost.

The expanded search reached 66.0% raw accuracy / 67.7% subject-weighted balanced
accuracy, below the previous XGBoost. A fixed setting reached 69.3% raw accuracy;
neither the full-set nor selective result reached 80%. The previous local model
is retained. All attempts and fitted candidates remain saved; no AWS operation
or production-model replacement was performed.

## Completed: 12 model families

Run: `local-12-models-20261020`.

- [Full report and limitations](local-12-models-20261020/REPORT.md)
- [All-model leaderboard](local-12-models-20261020/leaderboard.csv)
- [Exact aggregate results](local-12-models-20261020/results.json)
- [Fixed evaluation protocol and environment](local-12-models-20261020/protocol.json)
- [Model reload / baseline audit](local-12-models-20261020/audit.json)
- [Comparison chart](local-12-models-20261020/comparison.png)

XGBoost leads nested patient-group validation: 68.5% subject-weighted balanced
accuracy, 68.7% raw accuracy, and 42.6-day per-interval mean absolute timing error
(57.2 days with equal subject weighting). Its balanced-accuracy 95% interval is
63.1–74.0%. The run does not meet the predeclared practical classification or
timing screen. The report keeps the already inspected holdout separate.

All 12 fitted bundles, candidate predictions and subject assignments are saved
locally under the Git-ignored path
`dataset/processed/longitudinal/benchmarks/local-12-models-20261020/`.
Aggregate results and protocol records can be reviewed here without raw subject
tables. The deployed artifact's checksum is unchanged; this run performed no AWS
operations.
