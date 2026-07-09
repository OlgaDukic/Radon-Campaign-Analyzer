from django.db import transaction

from campaigns.models import AnalysisReport, Campaign, Measurement
from campaigns.services.analysis_config import AnalysisConfig
from campaigns.services.canonicalization import build_canonical_outputs
from campaigns.services.ingestion import read_uploaded_file
from campaigns.services.paper_outputs import enrich_paper_summary
from campaigns.services.prediction import evaluate_prediction_models
from campaigns.services.prediction_readiness import build_prediction_readiness
from campaigns.services.quality import detect_time_gaps, merge_overlapping_timestamps
from campaigns.services.quality_flags import build_quality_outputs
from campaigns.services.regime_sensitivity import build_regime_sensitivity
from campaigns.services.regimes import classify_regimes
from campaigns.services.reproducibility import build_reproducibility_config
from campaigns.services.reports import build_html_report, build_summary, summary_to_text
from campaigns.services.resampling import build_hourly_resampling
from campaigns.services.sampling_gaps import build_sampling_diagnostics, detect_sampling_gaps
from campaigns.services.segmentation import assign_segment_ids
from campaigns.services.sirem_readiness import build_sirem_readiness
from campaigns.services.source_inventory import build_source_file_inventory
from campaigns.services.time_diagnostics import build_dst_diagnostics


@transaction.atomic
def run_campaign_analysis(campaign: Campaign, config: AnalysisConfig | None = None) -> AnalysisReport:
    config = config or AnalysisConfig()
    rows = []
    ingestion_debug = []
    uploaded_files = list(campaign.uploaded_files.all())

    try:
        for uploaded_file in uploaded_files:
            file_rows, _column_map, file_debug = read_uploaded_file(uploaded_file)
            ingestion_debug.append(file_debug)
            rows.extend(file_rows)

        source_inventory = build_source_file_inventory(rows, ingestion_debug)
        canonical_outputs = build_canonical_outputs(rows, config)
        merged_rows = merge_overlapping_timestamps(rows)
        gaps = detect_sampling_gaps(merged_rows, config)
        if not gaps:
            gaps = detect_time_gaps(merged_rows)
        segmented_rows = assign_segment_ids(merged_rows)
        classified_rows = classify_regimes(segmented_rows)
        Measurement.objects.filter(campaign=campaign).delete()
        _store_measurements(campaign, classified_rows)

        prediction_evaluation = evaluate_prediction_models(classified_rows)
        base_summary = build_summary(
            classified_rows,
            gaps,
            len(uploaded_files),
            prediction_evaluation["overall"],
            ingestion_debug,
            prediction_evaluation["by_regime"],
            prediction_evaluation["errors"],
        )
        dst_diagnostics = build_dst_diagnostics(classified_rows, config)
        quality_outputs = build_quality_outputs(
            classified_rows,
            canonical_outputs["canonical_records_preview"],
            gaps,
            dst_diagnostics,
        )
        conflict_count = canonical_outputs["canonical_dataset_summary"].get("conflicts", 0)
        if conflict_count:
            quality_outputs["quality_flag_counts"]["DUPLICATE_CONFLICT"] = max(
                quality_outputs["quality_flag_counts"].get("DUPLICATE_CONFLICT", 0),
                conflict_count,
            )
        resampling_outputs = build_hourly_resampling(classified_rows, config)
        research_outputs = {
            "analysis_config": config.to_dict(),
            "source_file_inventory": source_inventory,
            "sampling_diagnostics": build_sampling_diagnostics(merged_rows, gaps, config),
            "dst_diagnostics": dst_diagnostics,
            "regime_sensitivity": build_regime_sensitivity(classified_rows, config),
            "prediction_skill_by_regime": _prediction_skill_by_regime(prediction_evaluation["by_regime"]),
            "prediction_readiness": build_prediction_readiness(
                base_summary["segments"],
                quality_outputs["quality_flag_counts"],
                prediction_evaluation["by_regime"],
            ),
        }
        research_outputs.update(canonical_outputs)
        research_outputs.update(quality_outputs)
        research_outputs.update(resampling_outputs)
        research_outputs["sirem_readiness"] = build_sirem_readiness(classified_rows, {**base_summary, **research_outputs})
        research_outputs["reproducibility_config"] = build_reproducibility_config(
            campaign,
            uploaded_files,
            config,
            {
                "raw_records": canonical_outputs["canonical_dataset_summary"]["raw_records"],
                "canonical_records": canonical_outputs["canonical_dataset_summary"]["canonical_valid_records"],
            },
        )
        research_outputs = enrich_paper_summary({**base_summary, **research_outputs})
        summary_json = build_summary(
            classified_rows,
            gaps,
            len(uploaded_files),
            prediction_evaluation["overall"],
            ingestion_debug,
            prediction_evaluation["by_regime"],
            prediction_evaluation["errors"],
            research_outputs,
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
                "analysis_config": config.to_dict(),
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


def _prediction_skill_by_regime(rows):
    return [
        {
            "horizon": row.get("horizon"),
            "model": row.get("model"),
            "regime": row.get("regime"),
            "samples": row.get("samples"),
            "mae": row.get("mae"),
            "rmse": row.get("rmse"),
            "skill_score_vs_persistence": row.get("skill_score_vs_persistence"),
            "small_sample_warning": row.get("small_sample_warning"),
        }
        for row in rows
    ]
