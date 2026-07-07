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
```

## Excel Report Contents

The Excel export creates a formatted workbook with these sheets:

- Summary
- Segments
- Regime Counts
- Prediction Metrics
- Prediction by Regime
- Prediction Errors
- Gaps
- Ingestion Diagnostics
- Measurements

The workbook includes bold headers, frozen top rows, autofilters, readable column widths, wrapped diagnostic text, and basic numeric/date formatting.

Screenshot placeholder:

```text
[Excel report screenshot]
```

## Prediction Metrics

The prototype compares short-term radon prediction approaches for 1-hour and 6-hour horizons where usable segment data is available.

Current models:

- naive baseline: future radon equals current radon
- radon-history Ridge-style baseline model

Current global metrics:

- MAE
- RMSE
- number of samples
- improvement percentage where a baseline comparison is available

These models are intentionally simple and interpretable. They are included for research exploration and baseline comparison, not production forecasting.

## Regime-Aware Prediction Evaluation

In addition to global prediction metrics, the prototype evaluates prediction performance separately for each radon regime label where prediction samples are available.

This helps researchers inspect whether model performance depends on the current radon dynamics. For example, a simple model may perform well during stable low-radon periods but become less reliable during rising, falling, elevated, or sudden-change periods.

The dashboard and Excel report include regime-level metrics such as:

- forecast horizon
- model name
- regime label
- sample count
- MAE
- RMSE
- improvement compared with the naive baseline where available

The interpretation is intentionally cautious. Regimes with small sample counts should not be overinterpreted.

## Prediction Error Analysis

The prototype also stores and displays the largest absolute prediction errors for each analysis run. This helps identify time periods where prediction was less reliable and supports further inspection of difficult campaign intervals.

The error analysis includes:

- timestamp
- forecast horizon
- model name
- actual radon value
- predicted radon value
- absolute error
- regime label
- segment ID where available

Only the top prediction errors are shown in the dashboard and exported report to keep the output deterministic and readable.

## Research Workflow

A typical workflow is:

1. Create a campaign with location and planned monitoring dates.
2. Upload one or more monitoring files.
3. Run the analysis pipeline.
4. Inspect ingestion diagnostics and data quality results.
5. Review detected gaps and measurement segments.
6. Inspect radon regimes and segment-level behavior.
7. Compare global prediction metrics.
8. Review prediction performance by radon regime.
9. Inspect the largest prediction errors.
10. Export the Excel report for further research review.

## Quick Start: Running the Prototype Locally

The prototype is currently available as source code and can be run locally as a Django application.

### 1. Clone the repository

```bash
git clone https://github.com/OlgaDukic/Radon-Campaign-Analyzer.git
cd Radon-Campaign-Analyzer
```

### 2. Create a virtual environment

```bash
python -m venv .venv
```

### 3. Activate the virtual environment

On Windows:

```bash
.venv\Scripts\activate
```

On macOS/Linux:

```bash
source .venv/bin/activate
```

### 4. Install dependencies

```bash
pip install -r requirements.txt
```

### 5. Apply database migrations

```bash
python manage.py migrate
```

### 6. Run the development server

```bash
python manage.py runserver
```

### 7. Open the application

Open the following address in a web browser:

```text
http://127.0.0.1:8000/
```

### 8. Optional: run tests

```bash
python manage.py test
python manage.py check
```

## Notes for Reviewers

The repository contains the source code of the research prototype. The application is not currently deployed online, so it should be run locally.

The current example analysis was performed locally using indoor radon monitoring files. Reviewers can upload their own CSV, XLS, or XLSX monitoring files through the application interface. Example input files and additional screenshots can be provided if needed.

## Installation

Create and activate a virtual environment, then install dependencies:

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

On systems where `python` is not on PATH, use the available Python executable directly.

## Running Locally

Apply migrations:

```bash
python manage.py migrate
```

Start the development server:

```bash
python manage.py runserver
```

Open:

```text
http://127.0.0.1:8000/
```

## Running Tests

Run the Django test suite:

```bash
python manage.py test
```

Run Django system checks:

```bash
python manage.py check
```

## Project Structure

```text
radon_campaign_analyzer/
├── manage.py
├── requirements.txt
├── README.md
├── radon_campaign_analyzer/
│   ├── settings.py
│   ├── urls.py
│   ├── asgi.py
│   └── wsgi.py
└── campaigns/
    ├── models.py
    ├── forms.py
    ├── views.py
    ├── urls.py
    ├── tests.py
    ├── services/
    │   ├── analysis.py
    │   ├── ingestion.py
    │   ├── quality.py
    │   ├── segmentation.py
    │   ├── regimes.py
    │   ├── prediction.py
    │   ├── reports.py
    │   └── excel_export.py
    ├── static/
    │   └── campaigns/
    │       └── dashboard.css
    └── templates/
        └── campaigns/
            ├── base.html
            ├── campaign_list.html
            ├── campaign_form.html
            └── campaign_detail.html
```

## Current Status / Limitations

- Research prototype only.
- Not certified for radon risk assessment, regulatory reporting, medical decision-making, radiation-protection decisions, or legal compliance.
- Column detection is heuristic and focused on common monitoring export patterns.
- Ingestion diagnostics are provided to help users verify what was parsed and why files may have been skipped.
- Segment labels and regime classifications are based on simple interpretable rules.
- Prediction models are baseline methods intended for comparison, not validated forecasting tools.
- Regime-aware prediction metrics depend on the availability and quality of regime labels.
- Regimes with small sample counts should be interpreted cautiously.
- Prediction error analysis is intended for exploratory interpretation, not automated decision-making.
- The current prediction models are simple baselines; more advanced models require validation on larger and more diverse datasets.
- The application currently uses plain Django views and templates without authentication.
- The prototype is currently not deployed online; it is intended to be reviewed by running it locally from the GitHub repository.

## Future Work

Potential future directions:

- add prediction reliability scoring
- compare multiple campaigns, rooms, or buildings
- include environmental and contextual features such as ventilation, occupancy, room metadata, or window-opening annotations
- evaluate additional models such as Random Forest, XGBoost, or recurrent neural networks
- validate regime-aware prediction on longer and more diverse indoor radon datasets
- add richer file validation and user-facing import previews
- support additional monitor export formats
- add configurable gap thresholds and segmentation rules
- add richer visualizations for radon dynamics
- support campaign-level annotations and room metadata
- add optional authentication for multi-user deployments
- improve deployment settings for production-like environments
- optionally add PDF or Word report export after the scientific workflow is stable