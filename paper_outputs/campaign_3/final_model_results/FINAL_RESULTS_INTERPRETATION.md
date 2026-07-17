# Final Results Interpretation

Campaign: 3 - RadonEye Salerno 2024 — pilot regime analysis

This package reports exploratory case-study evidence from a reduced one-state linear state-space model. It is not a certified radon risk assessment, regulatory prediction system, or autonomous ventilation-control system.

## Locked Model
`C_(k+1) = a_r C_k + b_r + w_k`; `y_k = C_k + v_k`; state vector `x_k = [C_k]`.
The model does not identify physical ventilation, ACH, yellow-tuff exhalation, beta, lambda_v, C_bm, or C_out.

## Main Findings
1. Sequential updating descriptively reduces error versus open-loop transition. For the primary 1 h Experiment A result, relative MAE reduction is 71.971%.
2. The reduced S.I.R.E.M.-informed transition gives a small to moderate improvement over generic local-level Kalman in the primary direction: MAE 13.088 versus 13.895.
3. One-hour F1 prediction is the most consistent result across both train/test directions.
4. Longer horizons have larger and less consistent errors.
5. The Future-observation predictive interval is the appropriate interval for forecasting a future sensor measurement.
6. Intervals provide explicit but imperfectly calibrated uncertainty.
7. Rapid-removal results are limited by small N and provisional event boundaries.
8. Results are case-study evidence and should not be generalized across sites without additional campaigns.

## Primary Uncertainty Rows
- 1h: future-observation coverage=0.952, width=80.514
- 3h: future-observation coverage=0.982, width=116.295
- 6h: future-observation coverage=0.969, width=153.19

## Model-Validity Flags
- SMALL_PHASE_SAMPLE: 12 occurrences. Limits strength of parameter interpretation.
- PARAMETER_NEAR_BOUNDARY: 5 occurrences. Limits strength of parameter interpretation.
- PROVISIONAL_EVENT_BOUNDARY: 6480 occurrences. Event timing should be interpreted as documented-window evidence, not confirmed opening time.
- LARGE_INNOVATION: 126 occurrences. Indicates possible model discrepancy during the affected phase.
- SUSTAINED_SIGNED_INNOVATION: 48 occurrences. Indicates possible model discrepancy during the affected phase.
- OUTSIDE_TRAINING_REGIME: 120 occurrences. Use caution for affected rows.
