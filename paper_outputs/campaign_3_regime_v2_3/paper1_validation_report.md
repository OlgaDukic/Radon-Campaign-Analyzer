# Paper 1 Workflow Validation Report

This validation report describes an exploratory research-software output package. It is not a certified radon risk assessment, medical, legal, or regulatory decision report.

## Campaign and Run
- Campaign ID: 3
- Campaign name: RadonEye Salerno 2024 — pilot regime analysis
- Analysis report ID: 16
- Analysis timestamp: 2026-07-16T12:02:26.424169+00:00
- Software version / git commit: ffd7455
- Command used: `python manage.py analyze_campaign 3 --timezone Europe/Rome --resample 1H --gap-tolerance 1.5 --rebuild-canonical --run-sensitivity --export-excel --profile default_radon_hourly --output-dir paper_outputs\campaign_3_regime_v2_3`
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
- Regime labels found: falling, high_episode, quality_affected, rising, stable_elevated, stable_low, sudden_drop, unstable_transition
- Prediction horizons evaluated: 1h, 6h
- Models evaluated: naive_baseline, ridge, rolling_mean_baseline
- Prediction evaluation policy: chronological train/test split; training observations precede test observations in time.
- Small-sample warnings: 6

## Regime Analysis v2
- Concentration-level distribution: {"ELEVATED": 66, "HIGH": 106, "LOW": 1411}
- Candidate-state distribution: {"FALLING": 61, "QUALITY_AFFECTED": 26, "RISING": 81, "STABLE": 1271, "SUDDEN_DROP": 4, "UNSTABLE_TRANSITION": 140}
- Confirmed-state distribution: {"FALLING": 47, "QUALITY_AFFECTED": 36, "RISING": 68, "STABLE": 1332, "SUDDEN_DROP": 4, "UNSTABLE_TRANSITION": 96}
- Episode count by type: {"ACCUMULATION": 12, "DECLINE": 8, "QUALITY_AFFECTED": 26, "STABLE_ELEVATED": 7, "STABLE_HIGH": 8, "STABLE_LOW": 38, "SUDDEN_DROP_EVENT": 3, "UNSTABLE_TRANSITION": 47}
- Median episode duration hours: 1.0
- Maximum episode duration hours: 130.0
- Confidence distribution: {"HIGH": 1036, "LOW": 45, "MEDIUM": 502}
- Low-confidence reasons: {"EXPLICIT_INSTABILITY_EVIDENCE": 59, "HIGH_LOCAL_VARIABILITY": 12, "INSUFFICIENT_WINDOW": 51, "LONG_STABLE_DURATION": 1258, "LOW_LOCAL_VARIABILITY": 1531, "NEAR_GAP": 51, "PERSISTENCE_ADJUSTED_STATE": 194, "RAW_SMOOTHED_DISAGREEMENT": 115, "SHORT_MEDIUM_SLOPE_AGREEMENT": 981, "SLOPE_NEAR_THRESHOLD": 56, "STRONG_PERSISTENT_TREND": 26, "SUFFICIENT_WINDOW": 1532}
- Dynamic-sensitivity agreement: dynamic_slope_x0.8: 98.17%; dynamic_slope_x1.0: 100.0%; dynamic_slope_x1.2: 98.17%; dynamic_short_window_2: 89.13%; dynamic_medium_window_plus1: 95.45%; dynamic_persistence_1: 87.74%; dynamic_persistence_plus1: 93.81%; dynamic_variability_x0.8: 97.22%; dynamic_variability_x1.2: 99.05%
- Regime algorithm version: regime_analysis_v2.2

## Portability
- Selected profile: default_radon_hourly 2026-07-v1
- Compatibility status: PROFILE_COMPATIBLE_WITH_WARNINGS
- Compatibility warnings: ["SENSOR_RESOLUTION_UNKNOWN"]
- Adaptive recommendations: [{"parameter": "trend_slope_bq_m3_per_hour", "active_threshold": 8.0, "recommended_threshold": 7.333, "source": "90th percentile absolute short-window slope", "override_accepted": false, "note": "Diagnostic recommendation only; active fixed-profile threshold was not changed silently."}, {"parameter": "medium_trend_slope_bq_m3_per_hour", "active_threshold": 4.5, "recommended_threshold": 4.333, "source": "90th percentile absolute medium-window slope", "override_accepted": false, "note": "Diagnostic recommendation only; active fixed-profile threshold was not changed silently."}, {"parameter": "variability_threshold_bq_m3", "active_threshold": 15.0, "recommended_threshold": 13.0, "source": "95th percentile local MAD", "override_accepted": false, "note": "Diagnostic recommendation only; active fixed-profile threshold was not changed silently."}]
- Transition merges performed: 25
- Normalized episode rates: {"ACCUMULATION": 7.203, "DECLINE": 4.802, "QUALITY_AFFECTED": 15.607, "STABLE_ELEVATED": 4.202, "STABLE_HIGH": 4.802, "STABLE_LOW": 22.811, "SUDDEN_DROP_EVENT": 1.801, "UNSTABLE_TRANSITION": 28.213}

## Excel and Output Validation
- Excel workbook: paper_outputs\campaign_3_regime_v2_3\radon_campaign_3_report.xlsx
- Missing Excel sheets: none
- Empty/suspicious sheets: Overlap Conflicts: header only

## Tests and Checks
- `python manage.py test`: passed, 57 tests OK
- `python manage.py check`: passed, no issues
- `python manage.py makemigrations --check --dry-run`: passed, no changes detected

## Limitations
- Timezone audit rows document reproducibility assumptions and should not be interpreted as data-quality errors.
- Inter-file and DST-related gap attribution is not separately classified by the current prototype.
- Reconciliation is based on report-level counts and is intended as a paper audit trail, not a regulatory data acceptance statement.
- Outputs remain exploratory research diagnostics, not certified radon risk-assessment results.
