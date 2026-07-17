# Baseline Prediction Experiment Audit

Campaign: 3 - RadonEye Salerno 2024 — pilot regime analysis
Algorithm version: baseline_prediction_experiment_v1
Sampling interval: 1.0 h
Duplicate forecast keys: 0
Phase assignment: Existing phase_metrics use forecast-origin phase; target_phase_metrics use target timestamp phase and are primary for paper-ready evaluation.
Threshold note: Direct 1h/3h/6h forecasts are not a continuous or recursive trajectory, so threshold-crossing time is not identifiable from this output.

## Forecast Row Counts
- Experiment A: 1482 forecast rows; selected alphas {'1h': 10.0, '3h': 0.01, '6h': 0.01}
- Experiment B: 1698 forecast rows; selected alphas {'1h': 0.01, '3h': 0.01, '6h': 0.01}

## Leakage Audit
- forecast_origin_before_target: True
- direct_horizon_construction: True
- feature_rule: lag, difference and rolling features are constructed only from observations at or before forecast origin t
- ridge_training_rule: Ridge is fit only on the development cycle for each experiment; test cycle rows are not used for fitting or alpha selection.
- validation_rule: alpha selection uses blocked chronological validation inside the training cycle only
- preprocessing_rule: no scaler or standardisation is used; no test-cycle preprocessing is fitted
- recursive_forecasting: False

## Output Files
- alpha_selection_audit.csv
- baseline_prediction_audit_summary.md
- baseline_prediction_experiment.json
- baseline_prediction_experiment.xlsx
- exclusion_audit.csv
- experiment_a_observed_vs_predicted.svg
- experiment_a_rapid_removal_focus.svg
- experiment_b_observed_vs_predicted.svg
- experiment_b_rapid_removal_focus.svg
- fair_comparison_metrics.csv
- forecast_rows.csv
- intervention_response_audit.csv
- table_a_overall_predictive_performance.csv
- table_b_fair_comparison_performance.csv
- table_c_phase_specific_performance.csv
- table_d_intervention_response_audit.csv
- target_phase_metrics.csv
