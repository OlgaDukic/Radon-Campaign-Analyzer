from django.contrib import messages
from django.db.models import Avg, Max, Min
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from .forms import CampaignForm, UploadedFileForm
from .models import Campaign, Measurement
from .services.analysis import run_campaign_analysis
from .services.excel_export import build_campaign_report_workbook


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
    latest_report = campaign.analysis_reports.first()
    return render(
        request,
        "campaigns/campaign_detail.html",
        {
            "campaign": campaign,
            "upload_form": upload_form,
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
    report = run_campaign_analysis(campaign)
    if report.status == report.Status.COMPLETE:
        messages.success(request, "Analysis report created.")
    else:
        messages.error(request, "Analysis failed. See the report summary for details.")
    return redirect("campaigns:campaign_detail", pk=campaign.pk)


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
        "gaps": gaps,
        "ingestion_debug": ingestion_debug,
        "time_series": _time_series_chart(measurements),
        "segment_bars": _segment_bars(segments),
        "summary": summary,
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
