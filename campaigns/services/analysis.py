from django.db import transaction

from campaigns.models import AnalysisReport, Campaign, Measurement
from campaigns.services.ingestion import read_uploaded_file
from campaigns.services.prediction import evaluate_prediction_models
from campaigns.services.quality import detect_time_gaps, merge_overlapping_timestamps
from campaigns.services.regimes import classify_regimes
from campaigns.services.reports import build_html_report, build_summary, summary_to_text
from campaigns.services.segmentation import assign_segment_ids


@transaction.atomic
def run_campaign_analysis(campaign: Campaign) -> AnalysisReport:
    rows = []
    ingestion_debug = []
    uploaded_files = list(campaign.uploaded_files.all())

    try:
        for uploaded_file in uploaded_files:
            file_rows, _column_map, file_debug = read_uploaded_file(uploaded_file)
            ingestion_debug.append(file_debug)
            rows.extend(file_rows)

        merged_rows = merge_overlapping_timestamps(rows)
        gaps = detect_time_gaps(merged_rows)
        segmented_rows = assign_segment_ids(merged_rows)
        classified_rows = classify_regimes(segmented_rows)
        Measurement.objects.filter(campaign=campaign).delete()
        _store_measurements(campaign, classified_rows)

        prediction_metrics = evaluate_prediction_models(classified_rows)
        summary_json = build_summary(
            classified_rows,
            gaps,
            len(uploaded_files),
            prediction_metrics,
            ingestion_debug,
        )
        return AnalysisReport.objects.create(
            campaign=campaign,
            status=AnalysisReport.Status.COMPLETE,
            summary=summary_to_text(summary_json),
            summary_json=summary_json,
            html_report=build_html_report(campaign, summary_json),
        )
    except Exception as exc:
        return AnalysisReport.objects.create(
            campaign=campaign,
            status=AnalysisReport.Status.FAILED,
            summary=f"Analysis failed: {exc}",
            summary_json={
                "error": str(exc),
                "uploaded_file_count": len(uploaded_files),
                "ingestion_debug": ingestion_debug,
            },
            html_report=f"<h1>Analysis failed</h1><p>{exc}</p>",
        )


def _store_measurements(campaign, rows):
    measurements = [
        Measurement(
            campaign=campaign,
            uploaded_file=row.get("source_file"),
            measured_at=row["measured_at"],
            radon_bq_m3=row.get("radon_bq_m3"),
            temperature_c=row.get("temperature_c"),
            humidity_percent=row.get("humidity_percent"),
            pressure_hpa=row.get("pressure_hpa"),
            segment_id=row["segment_id"],
            regime=row.get("regime", ""),
        )
        for row in rows
    ]
    Measurement.objects.bulk_create(measurements)
