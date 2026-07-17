# State-Space Scientific Validation and Ablation Audit

Campaign: 3 - RadonEye Salerno 2024 — pilot regime analysis
Algorithm: state_space_validation_audit_v1

This audit is read-only exploratory research software and does not change stored campaign data.

## Scientific decisions
- Does sequential updating improve open-loop transition? yes. Mean MAE reduced sequential=13.38; open-loop=54.112
- Does S.I.R.E.M.-informed transition improve generic local-level Kalman? yes. Mean MAE reduced sequential=13.38; local-level=13.966
- Are future-observation intervals separated from latent-state intervals? yes. Audit reports both latent_state and future_observation coverage; future-observation variance adds R.
- Is rapid-removal model stable enough for strong paper claim? caution. Rapid-removal training samples are small and boundary stability is reported separately.

## Interval note
Future-observation predictive intervals include observation noise R; latent-state intervals do not.
