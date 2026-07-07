from io import BytesIO

from django.db.models import Avg, Max, Min
from openpyxl import Workbook
from openpyxl.styles import Font


SHEETS = [
    "Summary",
    "Segments",
    "Regime Counts",
    "Prediction Metrics",
    "Gaps",
    "Ingestion Diagnostics",
    "Measurements",
]


def build_campaign_report_workbook(campaign, report=None):
    summary = report.summary_json if report and report.summary_json else {}
    workbook = Workbook()
    workbook.remove(workbook.active)

    _write_summary(workbook.create_sheet("Summary"), campaign, report, summary)
    _write_segments(workbook.create_sheet("Segments"), summary)
    _write_regime_counts(workbook.create_sheet("Regime Counts"), summary)
    _write_prediction_metrics(workbook.create_sheet("Prediction Metrics"), summary)
    _write_gaps(workbook.create_sheet("Gaps"), summary)
    _write_ingestion_diagnostics(workbook.create_sheet("Ingestion Diagnostics"), summary)
    _write_measurements(workbook.create_sheet("Measurements"), campaign)

    for worksheet in workbook.worksheets:
        _format_sheet(worksheet)

    output = BytesIO()
    workbook.save(output)
    output.seek(0)
    return output


def _write_summary(worksheet, campaign, report, summary):
    stats = campaign.measurements.aggregate(
        first_at=Min("measured_at"),
        last_at=Max("measured_at"),
        mean_radon=Avg("radon_bq_m3"),
        max_radon=Max("radon_bq_m3"),
    )
    rows = [
        ("Field", "Value"),
        ("Campaign name", campaign.name),
        ("Location", _value(campaign.location)),
        ("Measurement date range", _date_range(stats["first_at"], stats["last_at"])),
        ("Uploaded file count", campaign.uploaded_files.count()),
        ("Imported measurement count", _value(summary.get("measurement_count"), campaign.measurements.count())),
        ("Segment count", _value(summary.get("segment_count"), len(summary.get("segments", [])) or None)),
        ("Gap count", _value(summary.get("gap_count"), len(summary.get("gaps", [])) or None)),
        ("Mean radon", _number(stats["mean_radon"])),
        ("Max radon", _number(stats["max_radon"])),
        ("Report created at", _timestamp(report.created_at if report else None)),
        ("Report updated at", "N/A"),
        ("Campaign created at", _timestamp(campaign.created_at)),
        ("Campaign updated at", _timestamp(campaign.updated_at)),
    ]
    for row in rows:
        worksheet.append(row)


def _write_segments(worksheet, summary):
    worksheet.append(
        [
            "Segment ID",
            "Start time",
            "End time",
            "Duration",
            "Mean radon",
            "Max radon",
            "Label",
            "Dominant regime",
            "Interpretation",
        ]
    )
    for segment in summary.get("segments", []):
        stats = segment.get("statistics", {}).get("radon_bq_m3", {})
        worksheet.append(
            [
                _value(segment.get("segment_id")),
                _value(segment.get("start")),
                _value(segment.get("end")),
                _duration(segment.get("start"), segment.get("end")),
                _number(stats.get("mean")),
                _number(stats.get("max")),
                _value(segment.get("segment_label")),
                _value(segment.get("dominant_regime")),
                _value(segment.get("interpretation_text")),
            ]
        )


def _write_regime_counts(worksheet, summary):
    worksheet.append(["Regime/Label", "Count"])
    for regime, count in summary.get("regime_counts", {}).items():
        worksheet.append([regime, count])


def _write_prediction_metrics(worksheet, summary):
    worksheet.append(
        [
            "Forecast horizon",
            "Model",
            "Samples",
            "Baseline MAE",
            "Model MAE",
            "MAE improvement %",
            "Baseline RMSE",
            "Model RMSE",
            "RMSE improvement %",
            "R2",
        ]
    )
    for horizon, model_results in summary.get("prediction_metrics", {}).items():
        baseline = model_results.get("naive_baseline", {})
        for model_name, metrics in model_results.items():
            worksheet.append(
                [
                    horizon,
                    model_name,
                    _value(metrics.get("samples")),
                    _number(baseline.get("mae")),
                    _number(metrics.get("mae")),
                    _improvement(baseline.get("mae"), metrics.get("mae")),
                    _number(baseline.get("rmse")),
                    _number(metrics.get("rmse")),
                    _improvement(baseline.get("rmse"), metrics.get("rmse")),
                    _number(metrics.get("r2")),
                ]
            )


def _write_gaps(worksheet, summary):
    worksheet.append(["Gap start time", "Gap end time", "Duration minutes", "Reason/source"])
    for gap in summary.get("gaps", []):
        worksheet.append(
            [
                _value(gap.get("from")),
                _value(gap.get("to")),
                _number(gap.get("minutes")),
                _value(gap.get("reason") or gap.get("source")),
            ]
        )


def _write_ingestion_diagnostics(worksheet, summary):
    worksheet.append(
        [
            "Uploaded file name",
            "Imported rows/measurements",
            "Skipped rows",
            "Warnings/errors",
            "Detected overlap information",
            "Detected sheets",
            "Header row",
            "Mapped columns",
        ]
    )
    for file_debug in summary.get("ingestion_debug", []):
        mapped_columns = ", ".join(
            f"{key}: {value or 'N/A'}"
            for key, value in file_debug.get("mapped_columns", {}).items()
        )
        skipped_rows = file_debug.get("skipped_rows")
        worksheet.append(
            [
                _value(file_debug.get("filename")),
                _value(file_debug.get("parsed_measurement_rows")),
                _value(skipped_rows),
                _value(file_debug.get("skipped_reason") or file_debug.get("warning") or file_debug.get("error")),
                _value(file_debug.get("overlap_info") or file_debug.get("overlap") or file_debug.get("detected_overlap_information")),
                ", ".join(file_debug.get("detected_sheets", [])) or "N/A",
                _value(file_debug.get("detected_header_row")),
                mapped_columns or "N/A",
            ]
        )


def _write_measurements(worksheet, campaign):
    worksheet.append(["Timestamp", "Radon", "Temperature", "Humidity", "Pressure", "Regime/Label", "Segment ID"])
    for measurement in campaign.measurements.order_by("measured_at", "id"):
        worksheet.append(
            [
                _timestamp(measurement.measured_at),
                _number(measurement.radon_bq_m3),
                _number(measurement.temperature_c),
                _number(measurement.humidity_percent),
                _number(measurement.pressure_hpa),
                _value(measurement.regime),
                _value(measurement.segment_id),
            ]
        )


def _format_sheet(worksheet):
    worksheet.freeze_panes = "A2"
    for cell in worksheet[1]:
        cell.font = Font(bold=True)
    for column_cells in worksheet.columns:
        max_length = max(len(str(cell.value)) if cell.value is not None else 0 for cell in column_cells)
        worksheet.column_dimensions[column_cells[0].column_letter].width = min(max(max_length + 2, 12), 45)


def _value(value, fallback="N/A"):
    if value is None or value == "":
        return fallback
    return value


def _number(value):
    if value is None or value == "":
        return "N/A"
    return round(float(value), 3)


def _timestamp(value):
    if not value:
        return "N/A"
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return value


def _date_range(start, end):
    if not start or not end:
        return "N/A"
    return f"{_timestamp(start)} to {_timestamp(end)}"


def _duration(start, end):
    if not start or not end:
        return "N/A"
    return f"{start} to {end}"


def _improvement(baseline_value, model_value):
    if baseline_value in (None, "", 0) or model_value in (None, ""):
        return "N/A"
    baseline = float(baseline_value)
    if baseline == 0:
        return "N/A"
    return round(((baseline - float(model_value)) / baseline) * 100, 2)
