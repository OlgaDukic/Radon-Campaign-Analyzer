# Paper 1 Workflow Validation Report

This validation report describes an exploratory research-software output package. It is not a certified radon risk assessment, medical, legal, or regulatory decision report.

## Campaign and Run
- Campaign ID: 1
- Campaign name: Test analysis
- Analysis report ID: 7
- Analysis timestamp: 2026-07-09T09:00:43.841766+00:00
- Software version / git commit: 6e41940
- Command used: `python manage.py analyze_campaign 1 --timezone Europe/Rome --resample 1H --gap-tolerance 1.5 --rebuild-canonical --run-sensitivity --export-excel --output-dir paper_outputs\campaign_1`
- Timezone: Europe/Rome
- Resampling interval: 1H
- Gap tolerance: 1.5

## Row Reconciliation
- raw_imported_rows: 45977
- exact_duplicate_rows_removed: 9165
- duplicate_conflict_rows: 6
- rows_removed_due_to_conflict_resolution: 6
- rows_removed_due_to_missing_or_invalid_radon: 0
- rows_removed_due_to_other_quality_rules: 9
- canonical_valid_rows: 36797
- canonical_hourly_rows: 6681
- notes: Reconciliation is computed from report JSON. Canonical valid rows exclude exact duplicate removals and rows marked invalid by canonical conflict or radon validity rules; hourly rows are aggregate intervals.

## Compact DST Summary
- timezone_audit_rows: 36804
- dst_ambiguous_count: 12
- dst_nonexistent_count: 1
- dst_transition_related_count: 13
- dst_problem_count: 13
- dst_notes: Timezone audit rows document assumptions for reproducible ordering and are not all DST problems. Problem counts include ambiguous/nonexistent local timestamps and timestamp parse warnings.

## Compact Sampling Gap Summary
- total_sampling_irregularities: 8356
- short_gaps: 403
- long_gaps: 3
- inter_file_gaps: N/A
- dst_related_gaps: N/A
- prediction_breaking_gaps: 3
- notes: Sampling gaps are detected with the configured tolerance multiplier. Inter-file and DST-related gap attribution is not separately classified by the current prototype.

## Regimes and Prediction
- Regime labels found: falling, high_episode, rising, stable_elevated, stable_low, sudden_drop, sudden_rise
- Prediction horizons evaluated: 1h, 6h
- Models evaluated: naive_baseline, ridge, rolling_mean_baseline
- Prediction evaluation policy: chronological train/test split; training observations precede test observations in time.
- Small-sample warnings: 12

## Excel and Output Validation
- Excel workbook: C:\Users\HP\Documents\New project\radon_campaign_analyzer\paper_outputs\campaign_1\radon_campaign_1_report.xlsx
- Missing Excel sheets: none
- Empty/suspicious sheets: none

## Tests and Checks
- `python manage.py test`: not recorded in this report
- `python manage.py check`: not recorded in this report
- `python manage.py makemigrations --check --dry-run`: not recorded in this report

## Limitations
- Timezone audit rows document reproducibility assumptions and should not be interpreted as data-quality errors.
- Inter-file and DST-related gap attribution is not separately classified by the current prototype.
- Reconciliation is based on report-level counts and is intended as a paper audit trail, not a regulatory data acceptance statement.
- Outputs remain exploratory research diagnostics, not certified radon risk-assessment results.
