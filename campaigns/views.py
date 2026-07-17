import logging
import json
from pathlib import Path

from django.conf import settings
from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Avg, Count, Max, Min
from django.http import FileResponse, Http404, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from django.views.decorators.http import require_POST

from .forms import (
    CampaignForm,
    Paper1AnalysisForm,
    ResearchContextForm,
    UploadedFileForm,
)
from .models import AnalysisReport, Campaign, CampaignResearchContext, Measurement, UploadedFile
from .services.analysis import run_campaign_analysis as run_basic_analysis
from .services.apparent_dynamics_audit import (
    build_apparent_dynamics_csv,
    build_apparent_dynamics_workbook,
    run_apparent_dynamics_audit,
)
from .services.baseline_prediction_experiment import (
    build_baseline_prediction_csv,
    build_baseline_prediction_workbook,
    run_baseline_prediction_experiment,
)
from .services.documented_events import (
    EventCycleDefinition,
    analyse_documented_cycles,
    build_documented_events_csv,
    build_documented_events_workbook,
    default_event_cycles_for_campaign,
)
from .services.excel_export import build_campaign_report_workbook, build_compact_campaign_report_workbook
from .services.paper1_analysis_runner import run_paper1_analysis
from .services.prediction_insights import build_prediction_insights, prediction_regime_badge
from .services.research_context import build_research_context_payload
from .services.reduced_state_space_experiment import (
    build_reduced_state_space_csv,
    build_reduced_state_space_workbook,
    run_reduced_state_space_experiment,
)
from .services.visualization import downsample_time_series

logger = logging.getLogger(__name__)
MAIN_PAGE_PREVIEW_LIMIT = 20
MEASUREMENT_PAGE_SIZES = {25, 50, 100, 200}

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
    campaigns = list(Campaign.objects.all())
    latest_reports = _latest_reports_by_campaign(campaigns)
    campaign_rows = [_campaign_home_row(campaign, latest_reports.get(campaign.id)) for campaign in campaigns]
    completed_campaigns = (
        Campaign.objects.filter(analysis_reports__status=AnalysisReport.Status.COMPLETE)
        .distinct()
        .order_by("-created_at")
    )
    selected_ids = _comparison_ids(request)
    comparison_rows = [_comparison_row(campaign) for campaign in completed_campaigns.filter(id__in=selected_ids)]
    comparison_rows.sort(key=lambda row: selected_ids.index(row["campaign"].id) if row["campaign"].id in selected_ids else 99)
    profile_versions = {row["profile_version"] for row in comparison_rows if row["profile_version"] != "N/A"}
    threshold_keys = {row["threshold_signature"] for row in comparison_rows if row["threshold_signature"] != "N/A"}
    return render(
        request,
        "campaigns/campaign_list.html",
        {
            "campaigns": campaigns,
            "campaign_rows": campaign_rows,
            "home_stats": _campaign_home_stats(campaign_rows),
            "completed_campaigns": completed_campaigns,
            "selected_compare_ids": selected_ids,
            "comparison_rows": comparison_rows,
            "comparison_ready": 2 <= len(comparison_rows) <= 4,
            "comparison_warning": len(selected_ids) not in (0, 2, 3, 4),
            "profile_version_mismatch": len(profile_versions) > 1,
            "threshold_mismatch": len(threshold_keys) > 1,
        },
    )


def _latest_reports_by_campaign(campaigns):
    campaign_ids = [campaign.id for campaign in campaigns]
    reports = {}
    queryset = (
        AnalysisReport.objects.filter(campaign_id__in=campaign_ids)
        .only("id", "campaign_id", "status", "created_at")
        .defer("summary", "summary_json", "html_report")
        .order_by("campaign_id", "-created_at")
    )
    for report in queryset:
        reports.setdefault(report.campaign_id, report)
    return reports


def _campaign_home_row(campaign, latest_report=None):
    stats = campaign.measurements.aggregate(
        count=Count("id"),
        first=Min("measured_at"),
        last=Max("measured_at"),
        mean=Avg("radon_bq_m3"),
        max=Max("radon_bq_m3"),
    )
    return {
        "campaign": campaign,
        "report_status": latest_report.get_status_display() if latest_report else "No report",
        "report_level": _status_level(latest_report.status if latest_report else None),
        "updated_at": latest_report.created_at if latest_report else campaign.updated_at,
        "measurement_count": stats["count"] or 0,
        "date_range": _time_range(stats["first"], stats["last"]),
        "mean_radon": _radon(stats["mean"]),
        "max_radon": _radon(stats["max"]),
        "uploaded_file_count": campaign.uploaded_files.count(),
        "major_gaps": "Open report",
        "profile_badge": "Open report" if latest_report else "N/A",
        "profile_level": _status_level(latest_report.status if latest_report else None),
    }


def _campaign_home_stats(campaign_rows):
    complete_count = sum(1 for row in campaign_rows if row["report_status"] == "Complete")
    measurement_count = sum(row["measurement_count"] for row in campaign_rows)
    uploaded_file_count = UploadedFile.objects.count()
    return {
        "campaign_count": len(campaign_rows),
        "complete_count": complete_count,
        "measurement_count": measurement_count,
        "uploaded_file_count": uploaded_file_count,
    }


def _status_level(status):
    if status == AnalysisReport.Status.COMPLETE:
        return "success"
    if status == AnalysisReport.Status.FAILED:
        return "danger"
    if status == AnalysisReport.Status.PENDING:
        return "warning"
    return "neutral"


def _volume_warning(context):
    if not context or context.room_volume_m3 is not None:
        return ""
    return "Room volume is optional and currently not available; descriptive and regime analyses can still run."


def _documented_event_definitions(campaign, request):
    if request.method == "POST":
        return [EventCycleDefinition.from_mapping(request.POST)]
    if request.GET.get("cycles"):
        try:
            rows = json.loads(request.GET["cycles"])
        except json.JSONDecodeError:
            return default_event_cycles_for_campaign(campaign)
        return [EventCycleDefinition.from_mapping(row) for row in rows]
    return default_event_cycles_for_campaign(campaign)


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


def _comparison_ids(request):
    ids = []
    for raw_id in request.GET.getlist("compare"):
        try:
            campaign_id = int(raw_id)
        except (TypeError, ValueError):
            continue
        if campaign_id not in ids:
            ids.append(campaign_id)
    return ids[:4]


def _comparison_row(campaign):
    summary = _latest_summary(campaign)
    stats = campaign.measurements.aggregate(
        count=Count("id"),
        first=Min("measured_at"),
        last=Max("measured_at"),
        mean=Avg("radon_bq_m3"),
        min=Min("radon_bq_m3"),
        max=Max("radon_bq_m3"),
        total=Count("id"),
        temperature_count=Count("temperature_c"),
        humidity_count=Count("humidity_percent"),
        pressure_count=Count("pressure_hpa"),
    )
    duration_days = _duration_days(stats["first"], stats["last"])
    env = _environmental_coverage(stats)
    physical_count = len(_physical_episodes(summary))
    data_quality_count = _data_quality_event_count(summary)
    gap_metric = _overview_gap_metric(summary, summary.get("gaps", []))
    profile = _profile_status_parts(summary)
    profile_meta = summary.get("profile_metadata", {}) or {}
    config = summary.get("analysis_config", {}) or {}
    return {
        "campaign": campaign,
        "location": campaign.location or "N/A",
        "sensor": _comparison_sensor(summary),
        "start": stats["first"] or "N/A",
        "end": stats["last"] or "N/A",
        "duration": _duration_display(stats["first"], stats["last"]),
        "duration_days": duration_days,
        "measurement_count": stats["count"],
        "mean_radon": _radon(stats["mean"]),
        "max_radon": _radon(stats["max"]),
        "elevated_high_percent": _elevated_high_percent(summary),
        "major_gaps": gap_metric["count"] or 0,
        "physical_episodes": physical_count,
        "data_quality_events": data_quality_count,
        "major_gaps_per_30_days": _rate_per_days(gap_metric["count"] or 0, duration_days, 30),
        "physical_episodes_per_30_days": _rate_per_days(physical_count, duration_days, 30),
        "data_quality_events_per_1000": _rate_per_count(data_quality_count, stats["count"], 1000),
        "temperature_coverage": _coverage_display(env["temperature"]),
        "humidity_coverage": _coverage_display(env["humidity"]),
        "pressure_coverage": _coverage_display(env["pressure"]),
        "co2_coverage": env["co2"]["status"],
        "profile_status": profile["label"],
        "profile_version": profile_meta.get("profile_version") or config.get("profile_version") or "N/A",
        "profile_name": profile_meta.get("profile_name") or config.get("profile_name") or "N/A",
        "threshold_signature": _threshold_signature(config),
    }


def _comparison_sensor(summary):
    for item in summary.get("source_file_inventory", []) or []:
        if item.get("device_id"):
            return item["device_id"]
    return "N/A"


def _duration_days(start, end):
    if not start or not end:
        return None
    return max((end - start).total_seconds() / 86400, 0)


def _rate_per_days(count, duration_days, days):
    if not duration_days:
        return "N/A"
    return f"{(float(count) / duration_days) * days:.2f}"


def _rate_per_count(count, total, scale):
    if not total:
        return "N/A"
    return f"{(float(count) / float(total)) * scale:.2f}"


def _coverage_display(row):
    if row["percent"] is None:
        return row["status"]
    return f"{row['percent']}% ({row['available_rows']} rows)"


def _threshold_signature(config):
    low = config.get("concentration_low_threshold_bq_m3")
    high = config.get("concentration_high_threshold_bq_m3")
    if low is None and high is None:
        return "N/A"
    return f"low={low}; high={high}"


def campaign_detail(request, pk):
    campaign = get_object_or_404(Campaign, pk=pk)
    latest_report = _latest_report_meta(campaign)
    summary = _latest_summary(campaign)
    return render(
        request,
        "campaigns/campaign_overview.html",
        {
            "campaign": campaign,
            "latest_report": latest_report,
            "export_excel_url": f"/campaigns/{campaign.pk}/export.xlsx",
            "dashboard": _build_dashboard(campaign, latest_report, summary),
        },
    )


def campaign_quality(request, pk):
    campaign = get_object_or_404(Campaign, pk=pk)
    summary = _latest_summary(campaign)
    return render(request, "campaigns/campaign_quality.html", _section_context(campaign, "quality", summary))


def campaign_regimes(request, pk):
    campaign = get_object_or_404(Campaign, pk=pk)
    summary = _latest_summary(campaign)
    rows = [_episode_table_row(row) for row in _filtered_episode_rows(summary.get("episodes", []), request)]
    context = _section_context(campaign, "regimes", summary)
    context.update({"episode_page": _page_from_rows(rows, request), "episode_total": len(rows)})
    return render(request, "campaigns/campaign_regimes.html", context)


def campaign_prediction(request, pk):
    campaign = get_object_or_404(Campaign, pk=pk)
    summary = _latest_summary(campaign)
    rows = summary.get("largest_errors_v2", summary.get("prediction_errors", []))
    context = _section_context(campaign, "prediction", summary)
    context.update({"error_page": _page_from_rows(rows, request), "error_total": len(rows)})
    return render(request, "campaigns/campaign_prediction.html", context)


def baseline_prediction_experiment(request, pk):
    campaign = get_object_or_404(Campaign, pk=pk)
    payload = run_baseline_prediction_experiment(campaign)
    return render(
        request,
        "campaigns/baseline_prediction_experiment.html",
        {
            "campaign": campaign,
            "latest_report": _latest_report_meta(campaign),
            "active_section": "prediction",
            "payload": payload,
        },
    )


def baseline_prediction_experiment_json(request, pk):
    campaign = get_object_or_404(Campaign, pk=pk)
    return JsonResponse(run_baseline_prediction_experiment(campaign), json_dumps_params={"indent": 2})


def baseline_prediction_experiment_csv(request, pk):
    campaign = get_object_or_404(Campaign, pk=pk)
    response = HttpResponse(build_baseline_prediction_csv(run_baseline_prediction_experiment(campaign)), content_type="text/csv")
    response["Content-Disposition"] = f'attachment; filename="campaign_{campaign.pk}_baseline_prediction_experiment.csv"'
    return response


def baseline_prediction_experiment_excel(request, pk):
    campaign = get_object_or_404(Campaign, pk=pk)
    workbook = build_baseline_prediction_workbook(run_baseline_prediction_experiment(campaign))
    response = HttpResponse(
        workbook.getvalue(),
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    response["Content-Disposition"] = f'attachment; filename="campaign_{campaign.pk}_baseline_prediction_experiment.xlsx"'
    return response


def apparent_dynamics_audit(request, pk):
    campaign = get_object_or_404(Campaign, pk=pk)
    payload = run_apparent_dynamics_audit(campaign)
    return render(
        request,
        "campaigns/apparent_dynamics_audit.html",
        {
            "campaign": campaign,
            "latest_report": _latest_report_meta(campaign),
            "active_section": "prediction",
            "payload": payload,
        },
    )


def apparent_dynamics_audit_json(request, pk):
    campaign = get_object_or_404(Campaign, pk=pk)
    return JsonResponse(run_apparent_dynamics_audit(campaign), json_dumps_params={"indent": 2})


def apparent_dynamics_audit_csv(request, pk):
    campaign = get_object_or_404(Campaign, pk=pk)
    response = HttpResponse(build_apparent_dynamics_csv(run_apparent_dynamics_audit(campaign)), content_type="text/csv")
    response["Content-Disposition"] = f'attachment; filename="campaign_{campaign.pk}_apparent_dynamics_audit.csv"'
    return response


def apparent_dynamics_audit_excel(request, pk):
    campaign = get_object_or_404(Campaign, pk=pk)
    workbook = build_apparent_dynamics_workbook(run_apparent_dynamics_audit(campaign))
    response = HttpResponse(
        workbook.getvalue(),
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    response["Content-Disposition"] = f'attachment; filename="campaign_{campaign.pk}_apparent_dynamics_audit.xlsx"'
    return response


def reduced_state_space_experiment(request, pk):
    campaign = get_object_or_404(Campaign, pk=pk)
    payload = run_reduced_state_space_experiment(campaign)
    return render(
        request,
        "campaigns/reduced_state_space_experiment.html",
        {
            "campaign": campaign,
            "latest_report": _latest_report_meta(campaign),
            "active_section": "prediction",
            "payload": payload,
        },
    )


def reduced_state_space_experiment_json(request, pk):
    campaign = get_object_or_404(Campaign, pk=pk)
    return JsonResponse(run_reduced_state_space_experiment(campaign), json_dumps_params={"indent": 2})


def reduced_state_space_experiment_csv(request, pk):
    campaign = get_object_or_404(Campaign, pk=pk)
    response = HttpResponse(build_reduced_state_space_csv(run_reduced_state_space_experiment(campaign)), content_type="text/csv")
    response["Content-Disposition"] = f'attachment; filename="campaign_{campaign.pk}_reduced_state_space_experiment.csv"'
    return response


def reduced_state_space_experiment_excel(request, pk):
    campaign = get_object_or_404(Campaign, pk=pk)
    workbook = build_reduced_state_space_workbook(run_reduced_state_space_experiment(campaign))
    response = HttpResponse(
        workbook.getvalue(),
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    response["Content-Disposition"] = f'attachment; filename="campaign_{campaign.pk}_reduced_state_space_experiment.xlsx"'
    return response


def campaign_sensitivity(request, pk):
    campaign = get_object_or_404(Campaign, pk=pk)
    summary = _latest_summary(campaign)
    return render(request, "campaigns/campaign_sensitivity.html", _section_context(campaign, "sensitivity", summary))


def campaign_provenance(request, pk):
    campaign = get_object_or_404(Campaign, pk=pk)
    summary = _latest_summary(campaign)
    return render(request, "campaigns/campaign_provenance.html", _section_context(campaign, "provenance", summary))


def campaign_reports(request, pk):
    campaign = get_object_or_404(Campaign, pk=pk)
    summary = _latest_summary(campaign)
    reports = campaign.analysis_reports.only("id", "campaign_id", "status", "created_at", "summary").defer("summary_json", "html_report")
    context = _section_context(campaign, "reports", summary)
    context.update({"reports": reports, "artifacts": _paper1_artifacts(campaign.pk)})
    return render(request, "campaigns/campaign_reports.html", context)


def campaign_research_context(request, pk):
    campaign = get_object_or_404(Campaign, pk=pk)
    context, _created = CampaignResearchContext.objects.get_or_create(campaign=campaign)
    if request.method == "POST":
        form = ResearchContextForm(request.POST, instance=context)
        if form.is_valid():
            form.save()
            messages.success(request, "Research context updated.")
            return redirect("campaigns:campaign_research_context", pk=campaign.pk)
    else:
        form = ResearchContextForm(instance=context)
    payload = build_research_context_payload(campaign)
    return render(
        request,
        "campaigns/campaign_research_context.html",
        {
            "campaign": campaign,
            "latest_report": _latest_report_meta(campaign),
            "active_section": "research_context",
            "export_excel_url": f"/campaigns/{campaign.pk}/export.xlsx",
            "context_form": form,
            "research_context": payload,
            "volume_warning": _volume_warning(context),
        },
    )


def research_context_json(request, pk):
    campaign = get_object_or_404(Campaign, pk=pk)
    return JsonResponse(build_research_context_payload(campaign), json_dumps_params={"indent": 2})


def documented_events(request, pk):
    campaign = get_object_or_404(Campaign, pk=pk)
    definitions = _documented_event_definitions(campaign, request)
    payload = analyse_documented_cycles(campaign, definitions)
    return render(
        request,
        "campaigns/documented_events.html",
        {
            "campaign": campaign,
            "latest_report": _latest_report_meta(campaign),
            "active_section": "documented_events",
            "payload": payload,
            "form_values": request.POST if request.method == "POST" else {},
        },
    )


def documented_events_json(request, pk):
    campaign = get_object_or_404(Campaign, pk=pk)
    payload = analyse_documented_cycles(campaign, _documented_event_definitions(campaign, request))
    return JsonResponse(payload, json_dumps_params={"indent": 2})


def documented_events_csv(request, pk):
    campaign = get_object_or_404(Campaign, pk=pk)
    payload = analyse_documented_cycles(campaign, _documented_event_definitions(campaign, request))
    response = HttpResponse(build_documented_events_csv(payload), content_type="text/csv")
    response["Content-Disposition"] = f'attachment; filename="campaign_{campaign.pk}_documented_event_analysis.csv"'
    return response


def documented_events_excel(request, pk):
    campaign = get_object_or_404(Campaign, pk=pk)
    payload = analyse_documented_cycles(campaign, _documented_event_definitions(campaign, request))
    workbook = build_documented_events_workbook(payload)
    response = HttpResponse(
        workbook.getvalue(),
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    response["Content-Disposition"] = f'attachment; filename="campaign_{campaign.pk}_documented_event_analysis.xlsx"'
    return response


def upload_file(request, pk):
    campaign = get_object_or_404(Campaign, pk=pk)
    if request.method != "POST":
        return render(
            request,
            "campaigns/campaign_upload.html",
            {
                "campaign": campaign,
                "latest_report": _latest_report_meta(campaign),
                "active_section": "overview",
                "form": UploadedFileForm(),
            },
        )

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


def run_campaign_analysis(request, campaign_id):
    campaign = get_object_or_404(Campaign, pk=campaign_id)
    if request.method != "POST":
        return render(
            request,
            "campaigns/campaign_run_analysis.html",
            {
                "campaign": campaign,
                "latest_report": _latest_report_meta(campaign),
                "active_section": "overview",
                "form": Paper1AnalysisForm(),
            },
        )

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
    mode = request.GET.get("mode", "full")
    workbook = (
        build_compact_campaign_report_workbook(campaign, report)
        if mode == "compact"
        else build_campaign_report_workbook(campaign, report)
    )
    filename = f"radon_campaign_{campaign.pk}_report.xlsx"
    if mode == "compact":
        filename = f"radon_campaign_{campaign.pk}_compact_report.xlsx"
    response = HttpResponse(
        workbook.getvalue(),
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    return response


def campaign_chart_data(request, pk):
    campaign = get_object_or_404(Campaign, pk=pk)
    max_points = _bounded_int(request.GET.get("max_points"), default=2000, minimum=50, maximum=5000)
    measurements = _filtered_measurements(campaign, request)
    rows = (
        measurements.exclude(radon_bq_m3=None)
        .values("measured_at", "radon_bq_m3", "segment_id", "regime")
        .iterator(chunk_size=2000)
    )
    points = [
        {
            "timestamp": row["measured_at"].isoformat() if row["measured_at"] else None,
            "radon_bq_m3": row["radon_bq_m3"],
            "segment_id": row["segment_id"],
            "regime": row["regime"],
        }
        for row in rows
    ]
    sampled = downsample_time_series(points, max_points=max_points)
    values = [float(point["radon_bq_m3"]) for point in points]
    return JsonResponse(
        {
            "points": sampled,
            "source_count": len(points),
            "returned_count": len(sampled),
            "max_points": max_points,
            "min_radon": round(min(values), 3) if values else None,
            "max_radon": round(max(values), 3) if values else None,
        }
    )


def campaign_measurements(request, pk):
    campaign = get_object_or_404(Campaign, pk=pk)
    page = _bounded_int(request.GET.get("page"), default=1, minimum=1, maximum=1000000)
    page_size = _measurement_page_size(request)
    filters = {
        "date_from": request.GET.get("date_from", ""),
        "date_to": request.GET.get("date_to", ""),
        "segment_id": request.GET.get("segment_id", ""),
        "concentration_level": request.GET.get("concentration_level", ""),
        "dynamic_state": request.GET.get("dynamic_state", request.GET.get("regime", "")),
    }
    rows = _filtered_measurements(campaign, request).values(
        "measured_at",
        "radon_bq_m3",
        "temperature_c",
        "humidity_percent",
        "pressure_hpa",
        "regime",
        "segment_id",
    )
    paginator = Paginator(rows, page_size)
    page_obj = paginator.get_page(page)
    if request.GET.get("format") == "json" or "application/json" in request.headers.get("Accept", ""):
        return JsonResponse(
            {
                "count": paginator.count,
                "page": page_obj.number,
                "num_pages": paginator.num_pages,
                "page_size": page_size,
                "results": [_measurement_json(row) for row in page_obj.object_list],
            }
        )
    page_params = request.GET.copy()
    page_params.pop("page", None)
    return render(
        request,
        "campaigns/measurement_list.html",
        {
            "campaign": campaign,
            "page_obj": page_obj,
            "paginator": paginator,
            "page_size": page_size,
            "page_sizes": sorted(MEASUREMENT_PAGE_SIZES),
            "filters": filters,
            "querystring_without_page": page_params.urlencode(),
        },
    )


def campaign_gaps(request, pk):
    campaign = get_object_or_404(Campaign, pk=pk)
    summary = _latest_summary(campaign)
    return _paginated_summary_rows(summary.get("gaps", []), request)


def campaign_episodes(request, pk):
    campaign = get_object_or_404(Campaign, pk=pk)
    summary = _latest_summary(campaign)
    return _paginated_summary_rows(summary.get("episodes", []), request)


def _build_dashboard(campaign, latest_report, summary=None):
    summary = summary or {}
    measurements = campaign.measurements.order_by("measured_at")
    measurement_stats = measurements.aggregate(
        total=Count("id"),
        first_at=Min("measured_at"),
        last_at=Max("measured_at"),
        mean_radon=Avg("radon_bq_m3"),
        max_radon=Max("radon_bq_m3"),
        temperature_count=Count("temperature_c"),
        humidity_count=Count("humidity_percent"),
        pressure_count=Count("pressure_hpa"),
    )
    segments = summary.get("segments", [])
    gaps = summary.get("gaps", [])
    ingestion_debug = summary.get("ingestion_debug", [])

    imported_count = summary.get("measurement_count")
    if imported_count is None:
        imported_count = measurements.count()

    elevated_high_percent = _elevated_high_percent(summary)
    physical_episodes = _physical_episodes(summary)
    episode_count = len(physical_episodes)
    gap_metric = _overview_gap_metric(summary, gaps)
    report_meta = _report_meta(summary, latest_report)
    important_episodes = _important_episodes(summary)
    profile_status = _profile_status_parts(summary)
    environmental_coverage = _environmental_coverage(measurement_stats)
    return {
        "cards": [
            {"label": "Measurements", "value": _display(imported_count), "icon": "Rows", "support": "Imported records", "action_label": "View measurements", "action_url": reverse("campaigns:campaign_measurements", args=[campaign.pk])},
            {"label": "Duration", "value": _duration_display(measurement_stats["first_at"], measurement_stats["last_at"]), "icon": "Time", "support": "Measurement span"},
            {"label": "Mean radon", "value": _radon(measurement_stats["mean_radon"]), "icon": "Trend", "support": "Average concentration"},
            {"label": "Maximum radon", "value": _radon(measurement_stats["max_radon"]), "icon": "Peak", "support": "Highest observation"},
            {"label": "Elevated/high", "value": elevated_high_percent, "icon": "Alert", "support": _elevated_high_support(summary)},
            {"label": "Major gaps", "value": _display(gap_metric["count"]), "icon": "Timeline", "support": gap_metric["label"], "action_label": "Review gaps", "action_url": reverse("campaigns:campaign_quality", args=[campaign.pk])},
            {"label": "Episodes", "value": _display(episode_count), "icon": "Pulse", "support": "Final valid physical episodes", "action_label": "View episodes", "action_url": reverse("campaigns:campaign_regimes", args=[campaign.pk])},
            {"label": "Profile status", "value": profile_status["main"], "badge": profile_status["badge"], "badge_class": profile_status["level"], "icon": "Shield", "support": "Analysis profile fit", "action_label": "Review profile", "action_url": reverse("campaigns:campaign_sensitivity", args=[campaign.pk])},
        ][:8],
        "time_series": _time_series_summary(measurements),
        "date_range": _time_range(measurement_stats["first_at"], measurement_stats["last_at"]),
        "report_meta": report_meta,
        "profile_badge": profile_status["label"],
        "profile_level": profile_status["level"],
        "warnings": _overview_warnings(summary, gaps, imported_count, campaign, environmental_coverage)[:3],
        "warning_total": len(_overview_warnings(summary, gaps, imported_count, campaign, environmental_coverage)),
        "important_episodes": important_episodes[:5],
        "important_episode_total": len(important_episodes),
        "findings": _overview_findings(summary, measurement_stats, gap_metric, imported_count, physical_episodes, environmental_coverage),
        "environmental_coverage": environmental_coverage,
        "episode_metrics": {
            "classified_observations": summary.get("measurement_count"),
            "raw_episode_runs": len(summary.get("episodes", [])),
            "final_valid_physical_episodes": episode_count,
            "data_quality_events": _data_quality_event_count(summary),
        },
    }


def _section_context(campaign, active_section, summary):
    latest_report = _latest_report_meta(campaign)
    return {
        "campaign": campaign,
        "latest_report": latest_report,
        "active_section": active_section,
        "export_excel_url": f"/campaigns/{campaign.pk}/export.xlsx",
        "summary": _compact_section_summary(summary),
        "quality": _quality_context(summary),
        "regimes": _regime_context(summary),
        "prediction": _prediction_context(summary),
        "sensitivity": _sensitivity_context(summary),
        "provenance": _provenance_context(summary),
    }


def _latest_report_meta(campaign):
    return campaign.analysis_reports.only("id", "campaign_id", "status", "created_at", "summary").defer("summary_json", "html_report").first()


def _report_meta(summary, report):
    profile = summary.get("profile_metadata", {})
    params = summary.get("regime_parameters", {})
    config = summary.get("analysis_config", {})
    return {
        "status": report.get_status_display() if report else "N/A",
        "timestamp": report.created_at if report else "N/A",
        "algorithm_version": params.get("algorithm_version") or summary.get("report_schema_version") or "N/A",
        "profile_name": profile.get("profile_name") or config.get("profile_name") or "N/A",
        "profile_version": profile.get("profile_version") or "N/A",
    }


def _overview_findings(summary, measurement_stats, gap_metric, imported_count, physical_episodes, environmental_coverage):
    findings = []
    dominant_level = _dominant_label(summary.get("concentration_level_counts", {}))
    if dominant_level != "N/A":
        findings.append(f"Most observations were classified as {dominant_level.lower()} concentration level.")
    dominant_state = _dominant_physical_state(summary)
    if dominant_state != "N/A":
        findings.append(f"The dominant dynamic state was {dominant_state.lower()}.")
    max_radon = measurement_stats.get("max_radon")
    if max_radon is not None:
        findings.append(f"The maximum observed radon concentration was {float(max_radon):.1f} Bq/m3.")
    episode_counts = _episode_counts(physical_episodes)
    accumulation = _count_for_keys(episode_counts, ["ACCUMULATION", "accumulation"])
    decline = _count_for_keys(episode_counts, ["DECLINE", "decline"])
    if accumulation or decline:
        findings.append(f"The episode summary includes {accumulation} accumulation and {decline} decline episodes.")
    if gap_metric["count"]:
        findings.append(f"{gap_metric['count']} major sampling gaps were detected and should be considered when interpreting continuity-sensitive results.")
    if _environmental_predictors_partly_available(environmental_coverage):
        findings.append("Environmental predictors are partially available; coverage varies by variable and period.")
    elif _environmental_predictors_unavailable_from_coverage(environmental_coverage):
        findings.append("Interpretation is limited by unavailable environmental predictors.")
    if not findings and not imported_count:
        findings.append("No imported measurements are available yet. Add monitoring files to generate campaign findings.")
    return findings[:4]


def _dominant_label(counts):
    if not counts:
        return "N/A"
    key, _value = max(counts.items(), key=lambda item: item[1] or 0)
    return _human_label(key)


def _human_label(value):
    mapping = {
        "QUALITY_AFFECTED": "Data quality affected",
        "UNSTABLE_TRANSITION": "Transitional / unstable",
        "STABLE_HIGH": "Stable high level",
        "STABLE_ELEVATED": "Stable elevated level",
        "STABLE_LOW": "Stable low level",
        "SUDDEN_RISE_EVENT": "Sudden rise event",
        "SUDDEN_DROP_EVENT": "Sudden drop event",
        "ACCUMULATION": "Accumulation",
        "DECLINE": "Decline",
        "LOW": "Low",
        "ELEVATED": "Elevated",
        "HIGH": "High",
        "MEDIUM": "Medium",
        "PROFILE_COMPATIBLE": "Profile compatible",
        "PROFILE_PARTIAL": "Profile partially compatible",
        "PROFILE_COMPATIBLE_WITH_WARNINGS": "Profile compatible with warnings",
        "PROFILE_INCOMPATIBLE": "Profile needs review",
    }
    if value is None or value == "":
        return "N/A"
    return mapping.get(str(value), str(value).replace("_", " ").title())


def _profile_status_label(summary):
    status = (summary.get("profile_applicability") or {}).get("status")
    return _human_label(status)


def _profile_status_parts(summary):
    status = (summary.get("profile_applicability") or {}).get("status")
    if status == "PROFILE_COMPATIBLE":
        return {"main": "Compatible", "badge": "", "label": "Profile compatible", "level": "success"}
    if status in {"PROFILE_PARTIAL", "PROFILE_COMPATIBLE_WITH_WARNINGS"}:
        return {"main": "Compatible", "badge": "With warnings", "label": "Compatible with warnings", "level": "warning"}
    if status == "PROFILE_INCOMPATIBLE":
        return {"main": "Needs review", "badge": "Limited fit", "label": "Profile needs review", "level": "danger"}
    return {"main": "N/A", "badge": "", "label": "N/A", "level": "neutral"}


def _count_for_keys(counts, keys):
    return sum(int(counts.get(key) or 0) for key in keys)


def _environmental_predictors_unavailable(summary):
    flags = summary.get("quality_flag_counts", {})
    names = " ".join(str(key).upper() for key in flags.keys())
    return any(token in names for token in ["TEMPERATURE", "HUMIDITY", "PRESSURE", "CO2", "CO_2"])


def _environmental_coverage(measurement_stats):
    total = int(measurement_stats.get("total") or 0)

    def row(label, count, unit_label="available"):
        count = int(count or 0)
        percent = (count / total * 100) if total else None
        if not total:
            status = "not assessed"
        elif count == 0:
            status = "unavailable"
        elif count == total:
            status = "available"
        else:
            status = "partially available"
        return {
            "label": label,
            "available_rows": count,
            "percent": round(percent, 1) if percent is not None else None,
            "status": status,
            "unit_label": unit_label,
        }

    return {
        "total_rows": total,
        "temperature": row("Temperature", measurement_stats.get("temperature_count")),
        "humidity": row("Relative humidity", measurement_stats.get("humidity_count")),
        "pressure": row("Atmospheric pressure", measurement_stats.get("pressure_count")),
        "co2": {
            "label": "CO2",
            "available_rows": 0,
            "percent": None,
            "status": "not measured",
            "unit_label": "not measured by source device/model",
        },
    }


def _environmental_predictors_partly_available(coverage):
    rows = [coverage["temperature"], coverage["humidity"], coverage["pressure"]]
    return any(row["status"] == "partially available" for row in rows)


def _environmental_predictors_unavailable_from_coverage(coverage):
    rows = [coverage["temperature"], coverage["humidity"], coverage["pressure"]]
    return all(row["status"] == "unavailable" for row in rows)


def _elevated_high_percent(summary):
    counts = summary.get("concentration_level_counts", {})
    if not counts:
        return "N/A"
    total = sum(int(value or 0) for value in counts.values())
    elevated_high = _count_for_keys(counts, ["ELEVATED", "HIGH", "elevated", "high"])
    if not total:
        return "N/A"
    return f"{(elevated_high / total) * 100:.1f}%"


def _elevated_high_support(summary):
    config = summary.get("analysis_config") or {}
    low = config.get("concentration_low_threshold_bq_m3")
    high = config.get("concentration_high_threshold_bq_m3")
    if low is not None and high is not None:
        return f"Profile categories: >= {low:g} and >= {high:g} Bq/m3"
    return "Elevated + high profile categories"


def _episode_count(summary):
    counts = summary.get("episode_type_counts", {})
    if counts:
        return sum(int(value or 0) for value in counts.values())
    episodes = summary.get("important_episodes") or summary.get("episodes")
    if episodes is not None:
        return len(episodes)
    return None


def _physical_episodes(summary):
    return [
        episode
        for episode in summary.get("episodes", [])
        if _is_final_physical_episode(episode)
    ]


def _is_final_physical_episode(episode):
    if episode.get("episode_type") == "QUALITY_AFFECTED" or episode.get("quality_status") == "QUALITY_AFFECTED":
        return False
    if episode.get("confidence_category") == "LOW":
        return False
    if float(episode.get("duration_hours") or 0) < 2:
        return False
    if int(episode.get("measurement_count") or 0) < 3:
        return False
    return True


def _data_quality_event_count(summary):
    return sum(1 for episode in summary.get("episodes", []) if episode.get("episode_type") == "QUALITY_AFFECTED" or episode.get("quality_status") == "QUALITY_AFFECTED")


def _episode_counts(episodes):
    counts = {}
    for episode in episodes:
        key = episode.get("episode_type") or "UNKNOWN"
        counts[key] = counts.get(key, 0) + 1
    return counts


def _overview_gap_metric(summary, gaps):
    compact = summary.get("sampling_gaps_compact_summary") or {}
    long_gaps = compact.get("long_gaps")
    if isinstance(long_gaps, int):
        return {"count": long_gaps, "label": "Long campaign breaks"}
    return {"count": summary.get("gap_count", len(gaps) if gaps else None), "label": "Validated sampling interruptions"}


def _dominant_physical_state(summary):
    confidence = (summary.get("regime_confidence_summary") or {}).get("confidence_distribution_by_dynamic_state") or {}
    counts = {}
    for state, distribution in confidence.items():
        if state == "QUALITY_AFFECTED":
            continue
        counts[state] = int(distribution.get("HIGH") or 0) + int(distribution.get("MEDIUM") or 0)
    return _dominant_label(counts)


def _duration_display(start, end):
    if not start or not end:
        return "N/A"
    hours = (end - start).total_seconds() / 3600
    if hours < 48:
        return f"{hours:.1f} h"
    return f"{hours / 24:.1f} d"


def _overview_warnings(summary, gaps, imported_count, campaign, environmental_coverage):
    urls = {
        "quality": reverse("campaigns:campaign_quality", args=[campaign.pk]),
        "sensitivity": reverse("campaigns:campaign_sensitivity", args=[campaign.pk]),
        "prediction": reverse("campaigns:campaign_prediction", args=[campaign.pk]),
    }
    warnings = []
    profile_status = (summary.get("profile_applicability") or {}).get("status")
    if profile_status and profile_status != "PROFILE_COMPATIBLE":
        warnings.append(
            {
                "level": "warning",
                "title": "Profile compatibility needs review",
                "text": f"Profile applicability is marked as {_human_label(profile_status).lower()}.",
                "action_label": "View profile details",
                "action_url": urls["sensitivity"],
            }
        )
    gap_count = summary.get("gap_count", len(gaps))
    if imported_count and gap_count and gap_count / max(float(imported_count), 1) > 0.05:
        warnings.append(
            {
                "level": "warning",
                "title": "Sampling gaps detected",
                "text": "Sampling gaps may affect continuity-sensitive analysis.",
                "action_label": "Review gaps",
                "action_url": urls["quality"],
            }
        )
    if summary.get("quality_flag_counts", {}).get("UNKNOWN_SENSOR_RESOLUTION"):
        warnings.append(
            {
                "level": "warning",
                "title": "Sensor resolution unknown",
                "text": "Small signal changes cannot yet be fully separated from sensor noise.",
                "action_label": "View profile details",
                "action_url": urls["sensitivity"],
            }
        )
    if _environmental_predictors_partly_available(environmental_coverage):
        available = [
            row["label"].lower()
            for row in (environmental_coverage["temperature"], environmental_coverage["humidity"], environmental_coverage["pressure"])
            if row["available_rows"]
        ]
        warnings.append(
            {
                "level": "note",
                "title": "Environmental predictors partially available",
                "text": f"Coverage varies by variable and period; available fields include {', '.join(available) or 'none'}. CO2 is not measured.",
                "action_label": "Review data availability",
                "action_url": urls["quality"],
            }
        )
    elif _environmental_predictors_unavailable_from_coverage(environmental_coverage):
        warnings.append(
            {
                "level": "note",
                "title": "Environmental predictors unavailable",
                "text": "Temperature, humidity and pressure predictors are unavailable; CO2 is not measured by the source device/model.",
                "action_label": "Review data availability",
                "action_url": urls["quality"],
            }
        )
    if not summary.get("prediction_metrics") and imported_count:
        warnings.append(
            {
                "level": "note",
                "title": "Prediction metrics unavailable",
                "text": "Prediction metrics are not available for the latest report.",
                "action_label": "View prediction page",
                "action_url": urls["prediction"],
            }
        )
    low_confidence = _confidence_low_percent(summary)
    if low_confidence not in ("N/A", "0.0%"):
        warnings.append(
            {
                "level": "note",
                "title": "Low-confidence labels present",
                "text": f"Low-confidence regime labels account for {low_confidence} of classified observations.",
                "action_label": "Review confidence",
                "action_url": urls["sensitivity"],
            }
        )
    return warnings[:5]


def _important_episodes(summary):
    episodes = _physical_episodes(summary)
    prepared = []
    for episode in episodes:
        row = episode.copy()
        row["episode_type_display"] = _human_label(row.get("episode_type") or row.get("type"))
        row["confidence_display"] = _human_label(row.get("confidence_category") or row.get("confidence"))
        row["period_display"] = _format_episode_period(row.get("start"), row.get("end"))
        row["duration_display"] = _format_hours(row.get("duration_hours"))
        prepared.append(row)
    return sorted(prepared, key=lambda row: (float(row.get("max_radon") or 0), float(row.get("duration_hours") or 0)), reverse=True)


def _format_episode_period(start_value, end_value):
    start = _parse_datetime_any(start_value)
    end = _parse_datetime_any(end_value)
    if not start or not end:
        return "N/A"
    start = timezone.localtime(start) if timezone.is_aware(start) else start
    end = timezone.localtime(end) if timezone.is_aware(end) else end
    if start.date() == end.date():
        return f"{start:%d %b %Y, %H:%M}-{end:%H:%M}"
    return f"{start:%d %b %H:%M} - {end:%d %b %H:%M}"


def _parse_datetime_any(value):
    if not value:
        return None
    if hasattr(value, "date"):
        return value
    return parse_datetime(str(value))


def _format_hours(value):
    try:
        hours = float(value)
    except (TypeError, ValueError):
        return "N/A"
    if hours < 24:
        return f"{hours:.1f} h"
    return f"{hours / 24:.1f} d"


def _confidence_low_percent(summary):
    counts = (summary.get("regime_confidence_summary") or {}).get("confidence_category_counts") or {}
    if not counts:
        return "N/A"
    total = sum(int(value or 0) for value in counts.values())
    low = int(counts.get("LOW") or counts.get("low") or counts.get("LOW_CONFIDENCE") or 0)
    if not total:
        return "N/A"
    return f"{(low / total) * 100:.1f}%"


def _compact_section_summary(summary):
    return {
        "measurement_count": summary.get("measurement_count"),
        "segment_count": summary.get("segment_count"),
        "gap_count": summary.get("gap_count"),
        "profile": summary.get("profile_metadata", {}),
        "regime_counts": summary.get("regime_counts", {}),
    }


def _quality_context(summary):
    run_summary = summary.get("paper1_run_summary", {})
    return {
        "row_reconciliation": summary.get("row_reconciliation_summary", {}),
        "quality_flag_counts": summary.get("quality_flag_counts", {}),
        "sampling": summary.get("sampling_gaps_compact_summary") or {
            "total_sampling_irregularities": run_summary.get("total_sampling_irregularities"),
            "short_gaps": run_summary.get("short_gaps"),
            "long_gaps": run_summary.get("long_gaps"),
            **(summary.get("sampling_diagnostics", {}) or {}),
        },
        "dst": summary.get("dst_diagnostics_compact_summary") or {
            "timezone_audit_rows": run_summary.get("timezone_audit_rows"),
            "dst_ambiguous_count": run_summary.get("dst_ambiguous_count"),
            "dst_nonexistent_count": run_summary.get("dst_nonexistent_count"),
        },
        "gaps": summary.get("gaps", [])[:MAIN_PAGE_PREVIEW_LIMIT],
        "gap_total": len(summary.get("gaps", [])),
        "conflicts": summary.get("overlap_conflicts", [])[:MAIN_PAGE_PREVIEW_LIMIT],
        "conflict_total": len(summary.get("overlap_conflicts", [])),
        "source_files": summary.get("source_file_inventory", [])[:MAIN_PAGE_PREVIEW_LIMIT],
        "source_file_total": len(summary.get("source_file_inventory", [])),
    }


def _regime_context(summary):
    return {
        "regime_counts": summary.get("regime_counts", {}),
        "concentration_level_counts": summary.get("concentration_level_counts", {}),
        "dynamic_state_counts": summary.get("dynamic_state_counts", {}),
        "dynamic_state_diagnostics": _dynamic_state_diagnostics(summary),
        "episode_type_counts": summary.get("episode_type_counts", {}),
        "confidence_counts": _confidence_counts(summary),
        "profile": summary.get("profile_metadata", {}),
        "algorithm_version": (summary.get("regime_parameters") or {}).get("algorithm_version", "N/A"),
    }


def _dynamic_state_diagnostics(summary):
    raw = summary.get("dynamic_state_counts", {}) or {}
    confidence = (summary.get("regime_confidence_summary") or {}).get("confidence_distribution_by_dynamic_state") or {}
    raw_total = sum(int(value or 0) for value in raw.values())
    filtered_counts = {}
    for state, distribution in confidence.items():
        if state == "QUALITY_AFFECTED":
            continue
        filtered_counts[state] = int(distribution.get("HIGH") or 0) + int(distribution.get("MEDIUM") or 0)
    filtered_total = sum(filtered_counts.values())
    rows = []
    for state in sorted(set(raw) | set(filtered_counts)):
        raw_count = int(raw.get(state) or 0)
        filtered_count = int(filtered_counts.get(state) or 0)
        rows.append(
            {
                "state": _human_label(state),
                "raw_count": raw_count,
                "raw_percent": round(raw_count / raw_total * 100, 1) if raw_total else None,
                "filtered_count": filtered_count,
                "filtered_percent": round(filtered_count / filtered_total * 100, 1) if filtered_total else None,
            }
        )
    return rows


def _prediction_context(summary):
    return {
        "metrics": summary.get("prediction_metrics", {}),
        "summary_v2": summary.get("prediction_summary_v2", [])[:MAIN_PAGE_PREVIEW_LIMIT],
        "by_regime": summary.get("prediction_metrics_by_regime", summary.get("prediction_skill_by_regime", []))[:MAIN_PAGE_PREVIEW_LIMIT],
        "intervals": summary.get("prediction_intervals", [])[:MAIN_PAGE_PREVIEW_LIMIT],
        "readiness": summary.get("prediction_readiness", [])[:MAIN_PAGE_PREVIEW_LIMIT],
        "insights": build_prediction_insights(summary),
    }


def _sensitivity_context(summary):
    return {
        "dynamic": summary.get("dynamic_sensitivity", [])[:MAIN_PAGE_PREVIEW_LIMIT],
        "level": summary.get("level_sensitivity", summary.get("regime_sensitivity", []))[:MAIN_PAGE_PREVIEW_LIMIT],
        "adaptive": summary.get("adaptive_recommendations", [])[:MAIN_PAGE_PREVIEW_LIMIT],
        "profile": summary.get("profile_applicability", {}),
        "confidence": summary.get("regime_confidence_summary", {}),
    }


def _provenance_context(summary):
    return {
        "source_files": summary.get("source_file_inventory", [])[:MAIN_PAGE_PREVIEW_LIMIT],
        "source_file_total": len(summary.get("source_file_inventory", [])),
        "ingestion": summary.get("ingestion_debug", [])[:MAIN_PAGE_PREVIEW_LIMIT],
        "ingestion_total": len(summary.get("ingestion_debug", [])),
        "reproducibility": summary.get("reproducibility_config", {}),
        "standardized": summary.get("standardized_campaign_summary", {}),
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


def _time_series_summary(measurements):
    stats = measurements.exclude(radon_bq_m3=None).aggregate(
        min_value=Min("radon_bq_m3"),
        max_value=Max("radon_bq_m3"),
    )
    if stats["min_value"] is None:
        return {"has_data": False, "min": "N/A", "max": "N/A"}
    return {
        "has_data": True,
        "min": f"{float(stats['min_value']):.1f}",
        "max": f"{float(stats['max_value']):.1f}",
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


def _confidence_counts(summary):
    existing_counts = (summary.get("regime_confidence_summary") or {}).get("confidence_category_counts")
    if existing_counts:
        return dict(sorted(existing_counts.items()))
    rows = summary.get("regime_confidence", [])
    counts = {}
    for row in rows:
        label = row.get("label") or "UNKNOWN"
        counts[label] = counts.get(label, 0) + 1
    return dict(sorted(counts.items()))


def _filtered_measurements(campaign, request):
    queryset = campaign.measurements.order_by("measured_at", "id")
    date_from = _parse_datetime_param(request.GET.get("date_from"))
    date_to = _parse_datetime_param(request.GET.get("date_to"))
    segment_id = request.GET.get("segment_id")
    dynamic_state = request.GET.get("dynamic_state") or request.GET.get("regime")
    concentration_level = request.GET.get("concentration_level")

    if date_from:
        queryset = queryset.filter(measured_at__gte=date_from)
    if date_to:
        queryset = queryset.filter(measured_at__lte=date_to)
    if segment_id:
        queryset = queryset.filter(segment_id=segment_id)
    if dynamic_state:
        queryset = queryset.filter(regime__iexact=dynamic_state)
    if concentration_level:
        queryset = queryset.filter(regime__icontains=concentration_level)
    return queryset


def _parse_datetime_param(value):
    if not value:
        return None
    return parse_datetime(value)


def _bounded_int(value, default, minimum, maximum):
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default
    return max(minimum, min(parsed, maximum))


def _measurement_page_size(request):
    raw_value = request.GET.get("page_size", request.GET.get("per_page"))
    try:
        requested = int(raw_value)
    except (TypeError, ValueError):
        return 50
    if requested > 200:
        return 200
    return requested if requested in MEASUREMENT_PAGE_SIZES else 50


def _measurement_json(row):
    return {
        "timestamp": row["measured_at"].isoformat() if row["measured_at"] else None,
        "radon_bq_m3": float(row["radon_bq_m3"]) if row["radon_bq_m3"] is not None else None,
        "temperature_c": float(row["temperature_c"]) if row["temperature_c"] is not None else None,
        "humidity_percent": float(row["humidity_percent"]) if row["humidity_percent"] is not None else None,
        "pressure_hpa": float(row["pressure_hpa"]) if row["pressure_hpa"] is not None else None,
        "regime": row["regime"] or "",
        "segment_id": row["segment_id"],
    }


def _latest_summary(campaign):
    return campaign.analysis_reports.values_list("summary_json", flat=True).first() or {}


def _paginated_summary_rows(rows, request):
    page = _bounded_int(request.GET.get("page"), default=1, minimum=1, maximum=1000000)
    per_page = _bounded_int(request.GET.get("per_page"), default=100, minimum=25, maximum=500)
    paginator = Paginator(rows, per_page)
    page_obj = paginator.get_page(page)
    return JsonResponse(
        {
            "count": paginator.count,
            "page": page_obj.number,
            "num_pages": paginator.num_pages,
            "results": list(page_obj.object_list),
        }
    )


def _summary_preview(summary):
    preview_keys = [
        "measurement_count",
        "segment_count",
        "gap_count",
        "regime_counts",
        "concentration_level_counts",
        "dynamic_state_counts",
        "episode_type_counts",
        "canonical_dataset_summary",
        "row_reconciliation_summary",
        "dst_diagnostics_compact_summary",
        "sampling_gaps_compact_summary",
        "paper1_run_summary",
    ]
    return {key: summary.get(key) for key in preview_keys if key in summary}


def _text_preview(value, limit=6000):
    if not value:
        return ""
    text = str(value)
    if len(text) <= limit:
        return text
    return f"{text[:limit]}\n\n[Preview truncated. Download the Excel report or paper output package for the full report.]"


def _filtered_episode_rows(rows, request):
    episode_type = request.GET.get("episode_type")
    confidence = request.GET.get("confidence")
    date_from = request.GET.get("date_from")
    date_to = request.GET.get("date_to")
    min_duration = _optional_float(request.GET.get("min_duration"))
    min_max_radon = _optional_float(request.GET.get("min_max_radon"))
    filtered = []
    for row in rows:
        if episode_type and row.get("episode_type") != episode_type:
            continue
        if confidence and (row.get("confidence_category") or row.get("confidence")) != confidence:
            continue
        if date_from and str(row.get("start", "")) < date_from:
            continue
        if date_to and str(row.get("end", "")) > date_to:
            continue
        if min_duration is not None and float(row.get("duration_hours") or 0) < min_duration:
            continue
        if min_max_radon is not None and float(row.get("max_radon") or 0) < min_max_radon:
            continue
        filtered.append(row)
    return filtered


def _episode_table_row(episode):
    row = episode.copy()
    stored_slope = row.get("robust_episode_slope_bq_m3_per_hour")
    classification_slope = row.get("mean_slope_bq_m3_per_hour")
    if classification_slope is None:
        classification_slope = row.get("mean_adjacent_slope_bq_m3_per_hour")
    endpoint_delta = _endpoint_delta(row.get("starting_radon"), row.get("ending_radon"))
    elapsed_hours = _elapsed_hours(row.get("start"), row.get("end"))
    endpoint_slope = _endpoint_slope(endpoint_delta, elapsed_hours)
    row["v2_episode_label"] = row.get("episode_type") or "N/A"
    row["legacy_label"] = row.get("legacy_episode_label") or "N/A"
    row["elapsed_timestamp_span_hours"] = elapsed_hours
    row["observation_count"] = row.get("measurement_count")
    row["effective_observed_duration_hours"] = row.get("duration_hours")
    row["raw_endpoint_delta"] = endpoint_delta
    row["raw_endpoint_slope"] = endpoint_slope
    row["stored_delta_field"] = row.get("absolute_concentration_change")
    row["stored_slope_field"] = stored_slope
    row["classification_trend_slope"] = classification_slope
    row["classification_state_distribution"] = _format_distribution(row.get("dynamic_state_distribution"))
    row["algorithm_versions"] = " / ".join(
        value
        for value in [row.get("regime_algorithm_version"), row.get("episode_algorithm_version") or row.get("algorithm_version")]
        if value
    ) or "N/A"
    row["display_reason_codes"] = row.get("dominant_reason_codes") or row.get("confidence_reason_codes") or []
    row["raw_trend_note"] = _raw_trend_note(endpoint_slope, classification_slope)
    row["stored_delta_note"] = _stored_delta_note(endpoint_delta, row.get("absolute_concentration_change"))
    return row


def _format_distribution(distribution):
    if not distribution:
        return "N/A"
    parts = []
    for label, values in distribution.items():
        if isinstance(values, dict):
            parts.append(f"{label}: {values.get('count', 'N/A')} ({values.get('percent', 'N/A')}%)")
        else:
            parts.append(f"{label}: {values}")
    return "; ".join(parts)


def _raw_trend_note(raw_slope, classification_slope):
    if raw_slope is None or classification_slope is None:
        return ""
    try:
        raw = float(raw_slope)
        classification = float(classification_slope)
    except (TypeError, ValueError):
        return ""
    if (raw > 0 > classification) or (raw < 0 < classification):
        return "Raw start/end trend and v2 classification trend have opposite signs."
    return ""


def _endpoint_delta(start_value, end_value):
    if start_value is None or end_value is None:
        return None
    try:
        return round(float(end_value) - float(start_value), 3)
    except (TypeError, ValueError):
        return None


def _elapsed_hours(start_value, end_value):
    start = _parse_datetime_any(start_value)
    end = _parse_datetime_any(end_value)
    if not start or not end:
        return None
    return round((end - start).total_seconds() / 3600, 3)


def _endpoint_slope(endpoint_delta, elapsed_hours):
    if endpoint_delta is None or not elapsed_hours or elapsed_hours <= 0:
        return None
    return round(float(endpoint_delta) / float(elapsed_hours), 3)


def _stored_delta_note(endpoint_delta, stored_delta):
    if endpoint_delta is None or stored_delta is None:
        return ""
    try:
        if abs(float(endpoint_delta) - float(stored_delta)) > 0.001:
            return "Stored delta field differs from displayed endpoint delta; endpoint delta is End radon minus Start radon."
    except (TypeError, ValueError):
        return ""
    return ""


def _optional_float(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _page_from_rows(rows, request):
    page = _bounded_int(request.GET.get("page"), default=1, minimum=1, maximum=1000000)
    page_size = _measurement_page_size(request)
    return Paginator(rows, page_size).get_page(page)
