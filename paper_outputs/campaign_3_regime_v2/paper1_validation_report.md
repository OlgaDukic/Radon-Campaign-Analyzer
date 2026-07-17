# Paper 1 Workflow Validation Report

This validation report describes an exploratory research-software output package. It is not a certified radon risk assessment, medical, legal, or regulatory decision report.

## Campaign and Run
- Campaign ID: 3
- Campaign name: RadonEye Salerno 2024 — pilot regime analysis
- Analysis report ID: 12
- Analysis timestamp: 2026-07-16T11:30:50.421217+00:00
- Software version / git commit: ffd7455
- Command used: `python manage.py analyze_campaign 3 --timezone Europe/Rome --resample 1H --gap-tolerance 1.5 --rebuild-canonical --run-sensitivity --export-excel --output-dir paper_outputs\campaign_3_regime_v2`
- Timezone: Europe/Rome
- Resampling interval: 1H
- Gap tolerance: 1.5

## Row Reconciliation
- raw_imported_rows: 1583
- exact_duplicate_rows_removed: 0
- duplicate_conflict_rows: 0
- rows_removed_due_to_conflict_resolution: 0
- rows_removed_due_to_missing_or_invalid_radon: 0
- rows_removed_due_to_other_quality_rules: 0
- canonical_valid_rows: 1583
- canonical_hourly_rows: 1581
- notes: Reconciliation is computed from report JSON. Canonical valid rows exclude exact duplicate removals and rows marked invalid by canonical conflict or radon validity rules; hourly rows are aggregate intervals.

## Compact DST Summary
- timezone_audit_rows: 1583
- dst_ambiguous_count: 0
- dst_nonexistent_count: 0
- dst_transition_related_count: 0
- dst_problem_count: 0
- dst_notes: Timezone audit rows document assumptions for reproducible ordering and are not all DST problems. Problem counts include ambiguous/nonexistent local timestamps and timestamp parse warnings.

## Compact Sampling Gap Summary
- total_sampling_irregularities: 25
- minor_interval_deviations: 0
- short_gaps: 15
- moderate_gaps: 5
- long_gaps: 5
- inter_file_gaps: N/A
- dst_related_gaps: N/A
- prediction_breaking_gaps: 25
- notes: Compact counts use the central time-continuity classification when available. Inter-file and DST-related gap attribution is not separately classified by the current prototype.

## Regimes and Prediction
- Regime labels found: falling, quality_affected, rising, stable_low, sudden_drop, unstable_transition
- Prediction horizons evaluated: 1h, 6h
- Models evaluated: naive_baseline, ridge, rolling_mean_baseline
- Prediction evaluation policy: chronological train/test split; training observations precede test observations in time.
- Small-sample warnings: 0

## Regime Analysis v2
- Concentration-level distribution: {"ELEVATED": 66, "HIGH": 106, "LOW": 1411}
- Candidate-state distribution: {"FALLING": 8, "QUALITY_AFFECTED": 26, "RISING": 7, "STABLE": 160, "SUDDEN_DROP": 5, "UNSTABLE_TRANSITION": 1377}
- Confirmed-state distribution: {"FALLING": 5, "QUALITY_AFFECTED": 29, "RISING": 3, "STABLE": 124, "SUDDEN_DROP": 5, "UNSTABLE_TRANSITION": 1417}
- Episode count by type: {"ACCUMULATION": 2, "DECLINE": 2, "QUALITY_AFFECTED": 26, "STABLE_LOW": 45, "SUDDEN_DROP_EVENT": 3, "UNSTABLE_TRANSITION": 57}
- Median episode duration hours: 2.0
- Maximum episode duration hours: 147.0
- Confidence distribution: {"HIGH": 1340, "LOW": 51, "MEDIUM": 192}
- Low-confidence reasons: {"HIGH_LOCAL_VARIABILITY": 22, "INSUFFICIENT_WINDOW": 51, "LONG_STABLE_DURATION": 113, "LOW_LOCAL_VARIABILITY": 1561, "NEAR_GAP": 51, "PERSISTENCE_ADJUSTED_STATE": 55, "RAW_SMOOTHED_DISAGREEMENT": 332, "SHORT_MEDIUM_SLOPE_AGREEMENT": 932, "SLOPE_NEAR_THRESHOLD": 118, "STRONG_PERSISTENT_TREND": 7, "SUFFICIENT_WINDOW": 1532}
- Dynamic-sensitivity agreement: dynamic_slope_x0.8: 96.53%; dynamic_slope_x1.0: 100.0%; dynamic_slope_x1.2: 98.48%; dynamic_short_window_2: 94.88%; dynamic_medium_window_plus1: 96.53%; dynamic_persistence_1: 96.53%; dynamic_persistence_plus1: 95.7%; dynamic_variability_x0.8: 99.87%; dynamic_variability_x1.2: 99.68%
- Regime algorithm version: regime_analysis_v2.1

## Excel and Output Validation
- Excel workbook: paper_outputs\campaign_3_regime_v2\radon_campaign_3_report.xlsx
- Missing Excel sheets: none
- Empty/suspicious sheets: Overlap Conflicts: header only

## Tests and Checks
- `python manage.py test`: not recorded in this report
- `python manage.py check`: not recorded in this report
- `python manage.py makemigrations --check --dry-run`: not recorded in this report

## Limitations
- Timezone audit rows document reproducibility assumptions and should not be interpreted as data-quality errors.
- Inter-file and DST-related gap attribution is not separately classified by the current prototype.
- Reconciliation is based on report-level counts and is intended as a paper audit trail, not a regulatory data acceptance statement.
- Outputs remain exploratory research diagnostics, not certified radon risk-assessment results.
