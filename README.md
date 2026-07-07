# Radon Campaign Analyzer

Radon Campaign Analyzer is a Django research prototype for organizing, ingesting, analyzing, predicting, and reporting indoor radon monitoring campaigns.

The project is intended for exploratory research workflows where investigators need to upload monitoring files, inspect data quality, detect gaps, segment time series, summarize radon dynamics, evaluate simple prediction models, and export structured reports for further analysis.

This is a research prototype. It is not a certified radon risk assessment tool and should not be used as a substitute for qualified professional, legal, medical, radiation-protection, or regulatory guidance.

## Main Features

- Create and manage indoor radon monitoring campaigns.
- Upload CSV, XLS, and XLSX monitoring files.
- Ingest timestamped radon measurements with optional temperature, humidity, and pressure values.
- Normalize decimal comma values commonly found in regional spreadsheet exports.
- Detect columns from practical Aranet-style export variants.
- Skip metadata rows before the measurement table.
- Inspect all sheets in uploaded Excel workbooks.
- Merge overlapping timestamps by keeping the first available non-empty values.
- Sort measurements chronologically.
- Detect time gaps larger than 60 minutes.
- Assign segment IDs to usable continuous measurement periods.
- Compute basic segment statistics.
- Classify per-measurement radon regimes using simple interpretable rules.
- Add segment-level interpretation labels for research review.
- Compare simple short-term prediction models.
- Evaluate prediction performance globally and by radon dynamic regime.
- Identify the largest prediction errors for research interpretation.
- Generate cautious prediction insights from regime-aware metrics.
- Display results in a research dashboard.
- Export analysis results to a formatted Excel workbook.

## Research Use Case

The application is designed for university researchers and technical teams evaluating indoor radon monitoring campaigns. It supports early-stage investigation of uploaded monitoring data by making data quality, gaps, segment behavior, regime distribution, prediction performance, and prediction errors visible in one place.

Typical use cases include:

- reviewing whether monitoring files were ingested correctly
- identifying gaps or discontinuities in measurement campaigns
- comparing low, elevated, dynamic, and high-episode segment behavior
- inspecting simple prediction performance before designing more advanced models
- checking whether prediction quality differs across radon dynamic regimes
- identifying campaign intervals where prediction errors are largest
- exporting a reproducible workbook for offline review or collaboration

## Scientific Contribution

The key research idea of this prototype is that indoor radon prediction should not be evaluated only with global error metrics. Radon concentration may behave differently during stable, rising, falling, elevated, or sudden-change periods, and prediction reliability may vary across these dynamic regimes.

The application therefore combines campaign ingestion, data quality control, gap detection, segmentation, regime detection, baseline prediction, regime-aware prediction evaluation, and prediction error analysis in one reproducible workflow.

This makes the prototype useful not only as a reporting tool, but also as an exploratory research tool for investigating when indoor radon prediction models are more or less reliable.

## Current Dashboard Outputs

The campaign detail dashboard currently shows:

- uploaded file count
- imported measurement count
- campaign time range
- segment count
- gap count
- mean radon
- max radon
- data quality summary
- radon time series chart
- segment mean/max radon chart
- regime distribution chart
- segment interpretation table
- regime counts table
- global prediction metrics table
- prediction insights
- prediction performance by regime
- prediction error analysis
- detected gaps table
- ingestion diagnostics table
- measurement record count
- raw summary JSON for debugging
- generated HTML report preview

Screenshot placeholder:

```text
[Dashboard screenshot]