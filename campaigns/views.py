import logging
from pathlib import Path

from django.conf import settings
from django.contrib import messages
from django.db.models import Avg, Max, Min
from django.http import FileResponse, Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from .forms import CampaignForm, Paper1AnalysisForm, UploadedFileForm
from .models import Campaign, Measurement
from .services.analysis import run_campaign_analysis as run_basic_analysis
from .services.excel_export import build_campaign_report_workbook
from .services.paper1_analysis_runner import run_paper1_analysis
from .services.prediction_insights import build_prediction_insights, prediction_regime_badge

logger = logging.getLogger(__name__)

PAPER_OUTPUT_FILES = {
    "radon_campaign_{campaign_id}_report.xlsx": "Download latest Excel report",
    "paper1_validation_report.md": "Open validation report",
    "row_reconciliation_summary.csv": "Download row reconciliation summary",
    "dst_diagnostics_compact_summary.csv": "Download compact DST summary",
    "sampling_gaps_compact_summary.csv": "Download compact sampling gap summary",
    "prediction_skill_by_regime.csv": "Download prediction skill by regime CSV",
    "reproducibility_config.csv": "Download reproducibility config",
    "source_file_inventory.csv": "Source file inventory CSV",
    "canonical_dataset_summary.csv": "Canonical dataset summary CSV",
    "quality_flag_counts.csv": "Quality flag counts CSV",
    "regime_counts.csv": "Regime counts CSV",
    "prediction_readiness.csv": "Prediction readiness CSV",
    "sirem_readiness.csv": "SIREM readiness CSV",
}


def campaign_list(request):
    campaigns = Campaign.objects.all()
    return render(request, "campaigns/campaign_list.html", {"campaigns": campaigns})


def campaign_create(request):
    if request.method == "POST":
        form = CampaignForm(request.POST)
        if form.is_valid():
            campaign = form.save()
            messages.success(request, "Campaign created.")
            return redirect("campaigns:campaign_detail", pk=campaign.pk)
    else:
        form = CampaignForm()
    return render(request, "campaigns/campaign_form.html", {"form": form})


def campaign_detail(request, pk):
    campaign = get_object_or_404(Campaign, pk=pk)
    upload_form = UploadedFileForm()
    paper1_form = Paper1AnalysisForm()
    latest_report = campaign.analysis_reports.first()
    return render(
        request,
        "campaigns/campaign_detail.html",
        {
            "campaign": campaign,
            "upload_form": upload_form,
            "paper1_form": paper1_form,
            "latest_report": latest_report,
            "export_excel_url": f"/campaigns/{campaign.pk}/export.xlsx",
            "dashboard": _build_dashboard(campaign, latest_report),
        },
    )


def upload_file(request, pk):
    campaign = get_object_or_404(Campaign, pk=pk)
    if request.method != "POST":
        return redirect("campaigns:campaign_detail", pk=campaign.pk)

    form = UploadedFileForm(request.POST, request.FILES)
    if form.is_valid():
        uploaded_file = form.save(commit=False)
        uploaded_file.campaign = campaign
        uploaded_file.original_name = uploaded_file.file.name
        uploaded_file.save()
        messages.success(request, "File uploaded.")
    else:
        messages.error(request, "Upload failed. Please choose a CSV or Excel file.")
    return redirect("campaigns:campaign_detail", pk=campaign.pk)


@require_POST
def run_analysis(request, pk):
    campaign = get_object_or_404(Campaign, pk=pk)
    report = run_basic_analysis(campaign)
    if report.status == report.Status.COMPLETE:
        messages.success(request, "Analysis report created.")
    else:
        messages.error(request, "Analysis failed. See the report summary for details.")
    return redirect("campaigns:campaign_detail", pk=campaign.pk)


@require_POST
def run_campaign_analysis(request, campaign_id):
    campaign = get_object_or_404(Campaign, pk=campaign_id)
    if not campaign.uploaded_files.exists():
        messages.error(request, "Upload at least one monitoring file before running Paper 1 analysis.")
        return redirect("campaigns:campaign_detail", pk=campaign.pk)

    form = Paper1AnalysisForm(request.POST)
    if not form.is_valid():
        messages.error(request, "Paper 1 analysis could not start. Please check the analysis parameters.")
        return redirect("campaigns:campaign_detail", pk=campaign.pk)

    try:
        result = run_paper1_analysis(
            campaign_id=campaign.pk,
            timezone=form.cleaned_data["timezone"],
            resample=form.cleaned_data["resample"],
            gap_tolerance=form.cleaned_data["gap_tolerance"],
            rebuild_canonical=form.cleaned_data["rebuild_canonical"],
            run_sensitivity=form.cleaned_data["run_sensitivity"],
            export_excel=form.cleaned_data["export_excel"],
            requested_by="dashboard",
        )
    except Exception:
        logger.exception("Paper 1 dashboard analysis failed for campaign %s", campaign.pk)
        messages.error(request, "Paper 1 analysis failed. Review the campaign files and try again.")
        return redirect("campaigns:campaign_detail", pk=campaign.pk)

    if result.get("status") == "success":
        messages.success(
            request,
            (
                "Paper 1 analysis complete. "
                f"Canonical rows: {result.get('canonical_valid_rows', 'N/A')}; "
                f"hourly rows: {result.get('canonical_hourly_rows', 'N/A')}."
            ),
        )
    else:
        logger.warning("Paper 1 analysis returned failure for campaign %s: %s", campaign.pk, result.get("error_message"))
        messages.error(request, result.get("error_message") or "Paper 1 analysis could not be completed.")
    return redirect("campaigns:campaign_detail", pk=campaign.pk)


def download_paper_output(request, campaign_id, filename):
    campaign = get_object_or_404(Campaign, pk=campaign_id)
    allowed = _paper_output_filenames(campaign.pk)
    if filename not in allowed:
        raise Http404("Output file not found.")
    path = _paper_output_dir(campaign.pk) / filename
    try:
        resolved = path.resolve()
        resolved.relative_to(_paper_output_dir(campaign.pk).resolve())
    except ValueError as exc:
        raise Http404("Output file not found.") from exc
    if not resolved.exists() or not resolved.is_file():
        raise Http404("Output file not found.")
    return FileResponse(open(resolved, "rb"), as_attachment=filename != "paper1_validation_report.md", filename=filename)


def export_excel_report(request, pk):
    campaign = get_object_or_404(Campaign, pk=pk)
    report = campaign.analysis_reports.first()
    workbook = build_campaign_report_workbook(campaign, report)
    filename = f"radon_campaign_{campaign.pk}_report.xlsx"
    response = HttpResponse(
        workbook.getvalue(),
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    return response


def _build_dashboard(campaign, latest_report):
    summary = latest_report.summary_json if latest_report and latest_report.summary_json else {}
    measurements = campaign.measurements.order_by("measured_at")
    measurement_stats = measurements.aggregate(
        first_at=Min("measured_at"),
        last_at=Max("measured_at"),
        mean_radon=Avg("radon_bq_m3"),
        max_radon=Max("radon_bq_m3"),
    )
    segments = summary.get("segments", [])
    gaps = summary.get("gaps", [])
    regime_counts = summary.get("regime_counts", {})
    prediction_metrics = summary.get("prediction_metrics", {})
    prediction_metrics_by_regime = summary.get("prediction_metrics_by_regime", [])
    prediction_errors = summary.get("prediction_errors", [])
    ingestion_debug = summary.get("ingestion_debug", [])

    imported_count = summary.get("measurement_count")
    if imported_count is None:
        imported_count = measurements.count()

    return {
        "cards": [
            {"label": "Uploaded files", "value": campaign.uploaded_files.count(), "marker": "📁"},
            {"label": "Imported measurements", "value": _display(imported_count), "marker": "▦"},
            {"label": "Campaign time range", "value": _time_range(measurement_stats["first_at"], measurement_stats["last_at"]), "marker": "◷"},
            {"label": "Segments", "value": _display(summary.get("segment_count", len(segments) if segments else None)), "marker": "▤"},
            {"label": "Gaps > 60 min", "value": _display(summary.get("gap_count", len(gaps) if gaps else None)), "marker": "⚠"},
            {"label": "Mean radon", "value": _radon(measurement_stats["mean_radon"]), "marker": "μ"},
            {"label": "Max radon", "value": _radon(measurement_stats["max_radon"]), "marker": "▲"},
        ],
        "data_quality": {
            "uploaded_file_count": campaign.uploaded_files.count(),
            "imported_measurement_count": _display(imported_count),
            "gap_count": _display(summary.get("gap_count", len(gaps) if gaps else None)),
            "parsed_file_count": sum(1 for file_debug in ingestion_debug if file_debug.get("parsed_measurement_rows", 0) > 0),
            "skipped_file_count": sum(1 for file_debug in ingestion_debug if file_debug.get("skipped_reason")),
        },
        "segments": _dashboard_segments(segments),
        "regime_counts": regime_counts,
        "regime_bars": _bars(regime_counts),
        "prediction_metrics": prediction_metrics,
        "prediction_metrics_by_regime": _dashboard_prediction_by_regime(prediction_metrics_by_regime),
        "prediction_insights": build_prediction_insights(summary),
        "prediction_errors": prediction_errors[:20],
        "gaps": gaps,
        "ingestion_debug": ingestion_debug,
        "time_series": _time_series_chart(measurements),
        "segment_bars": _segment_bars(segments),
        "summary": summary,
        "source_file_inventory": summary.get("source_file_inventory", []),
        "canonical_dataset_summary": summary.get("canonical_dataset_summary", {}),
        "quality_flag_counts": summary.get("quality_flag_counts", {}),
        "sampling_diagnostics": summary.get("sampling_diagnostics", {}),
        "overlap_conflicts": summary.get("overlap_conflicts", []),
        "dst_diagnostics": summary.get("dst_diagnostics", []),
        "regime_sensitivity": summary.get("regime_sensitivity", []),
        "prediction_skill_by_regime": summary.get("prediction_skill_by_regime", []),
        "prediction_readiness": summary.get("prediction_readiness", []),
        "sirem_readiness": summary.get("sirem_readiness", []),
        "paper1_run_summary": _paper1_run_summary(summary),
        "paper1_artifacts": _paper1_artifacts(campaign.pk),
    }


def _display(value):
    return "N/A" if value is None or value == "" else value


def _radon(value):
    if value is None:
        return "N/A"
    return f"{float(value):.1f} Bq/m³"


def _time_range(start, end):
    if not start or not end:
        return "N/A"
    return f"{start:%Y-%m-%d %H:%M} to {end:%Y-%m-%d %H:%M}"


def _bars(values):
    if not values:
        return []
    max_value = max(values.values()) or 1
    return [
        {"label": key, "value": value, "width": round((value / max_value) * 100, 1)}
        for key, value in values.items()
    ]


def _segment_bars(segments):
    bars = []
    max_radon = 0
    for segment in segments:
        stats = segment.get("statistics", {}).get("radon_bq_m3", {})
        max_radon = max(max_radon, float(stats.get("max") or 0))
    scale = max_radon or 1
    for segment in segments:
        stats = segment.get("statistics", {}).get("radon_bq_m3", {})
        mean_value = float(stats.get("mean") or 0)
        max_value = float(stats.get("max") or 0)
        bars.append(
            {
                "segment_id": segment.get("segment_id", "N/A"),
                "label": segment.get("segment_label") or "N/A",
                "mean": _number_or_na(stats.get("mean")),
                "max": _number_or_na(stats.get("max")),
                "mean_width": round((mean_value / scale) * 100, 1),
                "max_width": round((max_value / scale) * 100, 1),
            }
        )
    return bars


def _time_series_chart(measurements):
    rows = list(measurements.exclude(radon_bq_m3=None).values("measured_at", "radon_bq_m3"))
    if not rows:
        return {"points": "", "has_data": False, "min": "N/A", "max": "N/A"}
    width = 700
    height = 220
    padding = 28
    values = [float(row["radon_bq_m3"]) for row in rows]
    min_value = min(values)
    max_value = max(values)
    span = max(max_value - min_value, 1)
    x_step = (width - padding * 2) / max(len(rows) - 1, 1)
    points = []
    for index, value in enumerate(values):
        x = padding + index * x_step
        y = height - padding - ((value - min_value) / span) * (height - padding * 2)
        points.append(f"{round(x, 1)},{round(y, 1)}")
    return {
        "points": " ".join(points),
        "has_data": True,
        "min": f"{min_value:.1f}",
        "max": f"{max_value:.1f}",
    }


def _number_or_na(value):
    if value is None:
        return "N/A"
    return round(float(value), 1)


def _dashboard_segments(segments):
    prepared = []
    for segment in segments:
        row = segment.copy()
        row["percent_above_100_display"] = _percent_or_na(segment.get("percent_above_100"))
        row["percent_above_200_display"] = _percent_or_na(segment.get("percent_above_200"))
        row["dynamic_percent_display"] = _percent_or_na(segment.get("dynamic_percent"))
        prepared.append(row)
    return prepared


def _percent_or_na(value):
    if value is None or value == "":
        return "N/A"
    return f"{value}%"


def _dashboard_prediction_by_regime(rows):
    prepared = []
    for row in rows:
        updated = row.copy()
        updated["mae_improvement_display"] = _signed_percent_or_na(row.get("mae_improvement_percent"))
        updated["rmse_improvement_display"] = _signed_percent_or_na(row.get("rmse_improvement_percent"))
        updated["improved"] = (
            row.get("model") != "naive_baseline"
            and row.get("mae_improvement_percent") is not None
            and row.get("mae_improvement_percent") > 0
        )
        updated["badge"] = prediction_regime_badge(row)
        prepared.append(updated)
    return prepared


def _signed_percent_or_na(value):
    if value is None or value == "":
        return "N/A"
    return f"{value}%"


def _paper1_run_summary(summary):
    run_summary = summary.get("paper1_run_summary")
    if run_summary:
        return run_summary
    return {
        "status": "N/A",
        "run_timestamp": "N/A",
        "timezone": summary.get("analysis_config", {}).get("timezone_name", "N/A"),
        "resample": summary.get("analysis_config", {}).get("resample_interval", "N/A"),
        "gap_tolerance": summary.get("analysis_config", {}).get("gap_tolerance_multiplier", "N/A"),
        "rebuild_canonical": None,
        "run_sensitivity": bool(summary.get("regime_sensitivity")),
        "export_excel": None,
        "raw_imported_rows": summary.get("canonical_dataset_summary", {}).get("raw_records", "N/A"),
        "exact_duplicate_rows_removed": summary.get("row_reconciliation_summary", {}).get("exact_duplicate_rows_removed", "N/A"),
        "duplicate_conflict_rows": summary.get("row_reconciliation_summary", {}).get("duplicate_conflict_rows", "N/A"),
        "canonical_valid_rows": summary.get("canonical_dataset_summary", {}).get("canonical_valid_records", "N/A"),
        "canonical_hourly_rows": len(summary.get("canonical_hourly_data", [])),
        "timezone_audit_rows": summary.get("dst_diagnostics_compact_summary", {}).get("timezone_audit_rows", "N/A"),
        "dst_ambiguous_count": summary.get("dst_diagnostics_compact_summary", {}).get("dst_ambiguous_count", "N/A"),
        "dst_nonexistent_count": summary.get("dst_diagnostics_compact_summary", {}).get("dst_nonexistent_count", "N/A"),
        "total_sampling_irregularities": summary.get("sampling_gaps_compact_summary", {}).get("total_sampling_irregularities", "N/A"),
        "short_gaps": summary.get("sampling_gaps_compact_summary", {}).get("short_gaps", "N/A"),
        "long_gaps": summary.get("sampling_gaps_compact_summary", {}).get("long_gaps", "N/A"),
        "regime_labels_found": list((summary.get("regime_counts") or {}).keys()),
        "prediction_horizons_evaluated": sorted((summary.get("prediction_metrics") or {}).keys()),
        "models_evaluated": sorted({model for results in (summary.get("prediction_metrics") or {}).values() for model in results.keys()}),
        "small_sample_warning_count": sum(1 for row in summary.get("prediction_skill_by_regime", []) if row.get("small_sample_warning")),
    }


def _paper1_artifacts(campaign_id):
    output_dir = _paper_output_dir(campaign_id)
    artifacts = []
    for filename, label in PAPER_OUTPUT_FILES.items():
        resolved_name = filename.format(campaign_id=campaign_id)
        exists = (output_dir / resolved_name).is_file()
        artifacts.append(
            {
                "filename": resolved_name,
                "label": label,
                "exists": exists,
                "url": f"/campaigns/{campaign_id}/paper-output/{resolved_name}/" if exists else "",
            }
        )
    return artifacts


def _paper_output_filenames(campaign_id):
    return {filename.format(campaign_id=campaign_id) for filename in PAPER_OUTPUT_FILES}


def _paper_output_dir(campaign_id):
    return settings.BASE_DIR / "paper_outputs" / f"campaign_{campaign_id}"
