from django.db import transaction

from datetime import date, datetime
from decimal import Decimal

from django.db.models import Model

from campaigns.models import AnalysisReport, Campaign, Measurement
from campaigns.services.analysis_config import AnalysisConfig
from campaigns.services.canonicalization import build_canonical_outputs
from campaigns.services.ingestion import read_uploaded_file
from campaigns.services.paper_outputs import enrich_paper_summary
from campaigns.services.portability import build_portability_outputs
from campaigns.services.prediction import evaluate_prediction_models
from campaigns.services.prediction_v2 import evaluate_prediction_v2
from campaigns.services.prediction_readiness import build_prediction_readiness
from campaigns.services.quality import detect_time_gaps, merge_overlapping_timestamps
from campaigns.services.quality_flags import build_quality_outputs
from campaigns.services.regime_sensitivity import build_regime_sensitivity
from campaigns.services.regime_v2 import (
    classify_regimes_v2,
    concentration_level_counts,
    dynamic_state_counts,
    regime_parameters,
)
from campaigns.services.regimes import classify_regimes
from campaigns.services.reproducibility import build_reproducibility_config
from campaigns.services.reports import build_html_report, build_summary, summary_to_text
from campaigns.services.resampling import build_hourly_resampling
from campaigns.services.sampling_gaps import build_sampling_diagnostics, detect_sampling_gaps
from campaigns.services.segment_v2 import build_segment_v2_summaries
from campaigns.services.episodes import build_episodes, episode_type_counts, important_episodes
from campaigns.services.sirem_readiness import build_sirem_readiness
from campaigns.services.source_inventory import build_source_file_inventory
from campaigns.services.sensitivity_v2 import build_sensitivity_v2
from campaigns.services.time_diagnostics import build_dst_diagnostics
from campaigns.services.time_continuity import analyze_time_continuity


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
        continuity = analyze_time_continuity(merged_rows, config)
        config = config.with_time_windows(continuity["summary"].get("expected_sampling_interval_minutes"))
        continuity = analyze_time_continuity(merged_rows, config)
        gaps = continuity["gaps"]
        if not gaps:
            gaps = detect_time_gaps(merged_rows)
        segmented_rows = continuity["rows"]
        classified_rows = classify_regimes(segmented_rows)
        classified_rows = classify_regimes_v2(classified_rows, config)
        episodes = build_episodes(classified_rows, gaps, config, campaign_id=campaign.id)
        segment_v2_summaries = build_segment_v2_summaries(classified_rows, episodes, gaps, config)
        Measurement.objects.filter(campaign=campaign).delete()
        _store_measurements(campaign, classified_rows)

        prediction_evaluation = evaluate_prediction_models(classified_rows)
        prediction_v2 = evaluate_prediction_v2(classified_rows, config)
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
            "profile_metadata": {
                "profile_name": config.profile_name,
                "profile_version": config.profile_version,
                "threshold_mode": config.threshold_mode,
                "effective_parameters": config.to_dict(),
                "overrides": config.profile_overrides,
                "validation_warnings": list(config.profile_warnings),
            },
            "report_schema_version": "regime_analysis_v2",
            "time_continuity": continuity,
            "source_file_inventory": source_inventory,
            "sampling_diagnostics": build_sampling_diagnostics(merged_rows, gaps, config),
            "dst_diagnostics": dst_diagnostics,
            "regime_sensitivity": build_regime_sensitivity(classified_rows, config),
            "concentration_level_counts": concentration_level_counts(classified_rows),
            "candidate_dynamic_state_counts": dynamic_state_counts(classified_rows, field="candidate_dynamic_state"),
            "confirmed_dynamic_state_counts": dynamic_state_counts(classified_rows, field="confirmed_dynamic_state"),
            "dynamic_state_counts": dynamic_state_counts(classified_rows, field="confirmed_dynamic_state"),
            "quality_flag_details": _quality_flag_details(classified_rows, resampling_outputs, quality_outputs),
            "measurement_regimes_v2": _measurement_regimes_v2(classified_rows),
            "episodes": episodes,
            "important_episodes": important_episodes(episodes),
            "feature_distribution_diagnostics": _feature_distribution_diagnostics(classified_rows),
            "sudden_event_audit": _sudden_event_audit(classified_rows, config),
            "episode_reason_summary": _episode_reason_summary(episodes),
            "transition_merge_audit": _transition_merge_audit(episodes),
            "elevated_period_phase_table": _elevated_period_phase_table(episodes),
            "episode_type_counts": episode_type_counts(episodes),
            "regime_parameters": regime_parameters(config),
            "regime_confidence": _regime_confidence_rows(classified_rows),
            "regime_confidence_summary": _regime_confidence_summary(classified_rows, episodes),
            "segment_v2_summaries": segment_v2_summaries,
            "prediction_skill_by_regime": _prediction_skill_by_regime(prediction_evaluation["by_regime"]),
            "prediction_readiness": build_prediction_readiness(
                base_summary["segments"],
                quality_outputs["quality_flag_counts"],
                prediction_evaluation["by_regime"],
            ),
        }
        research_outputs.update(canonical_outputs)
        research_outputs.update(build_portability_outputs(classified_rows, gaps, episodes, continuity, config))
        research_outputs.update(build_sensitivity_v2(classified_rows, config))
        research_outputs.update(prediction_v2)
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
        summary_json = _json_safe(summary_json)
        report = AnalysisReport.objects.create(
            campaign=campaign,
            status=AnalysisReport.Status.COMPLETE,
            summary=summary_to_text(summary_json),
            summary_json=summary_json,
            html_report=build_html_report(campaign, summary_json),
        )
        _attach_report_id_to_episode_outputs(report)
        return report
    except Exception as exc:
        failure_summary = _json_safe(
            {
                "error": str(exc),
                "uploaded_file_count": len(uploaded_files),
                "ingestion_debug": ingestion_debug,
                "analysis_config": config.to_dict(),
            }
        )
        return AnalysisReport.objects.create(
            campaign=campaign,
            status=AnalysisReport.Status.FAILED,
            summary=f"Analysis failed: {exc}",
            summary_json=failure_summary,
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


def _attach_report_id_to_episode_outputs(report):
    summary = dict(report.summary_json or {})
    changed = False
    for key in ("episodes", "important_episodes"):
        rows = summary.get(key) or []
        for row in rows:
            if row.get("analysis_report_id") in (None, "N/A"):
                row["analysis_report_id"] = report.id
                changed = True
    if changed:
        report.summary_json = summary
        report.html_report = build_html_report(report.campaign, summary)
        report.save(update_fields=["summary_json", "html_report"])


def _json_safe(value):
    if isinstance(value, dict):
        return {key: _json_safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    if isinstance(value, tuple):
        return [_json_safe(item) for item in value]
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, Model):
        return {
            "id": value.pk,
            "label": str(value),
        }
    return value


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


def _measurement_regimes_v2(rows):
    return [
        {
            "timestamp": row["measured_at"].isoformat(),
            "segment_id": row.get("segment_id"),
            "radon_bq_m3": float(row["radon_bq_m3"]) if row.get("radon_bq_m3") is not None else None,
            "legacy_regime": row.get("regime"),
            "concentration_level": row.get("concentration_level"),
            "candidate_dynamic_state": row.get("candidate_dynamic_state"),
            "confirmed_dynamic_state": row.get("confirmed_dynamic_state") or row.get("dynamic_state"),
            "dynamic_state": row.get("confirmed_dynamic_state") or row.get("dynamic_state"),
            "observed_interval_hours": row.get("observed_interval_hours"),
            "adjacent_slope_bq_m3_per_hour": row.get("adjacent_slope_bq_m3_per_hour"),
            "slope_bq_m3_per_hour": row.get("slope_bq_m3_per_hour"),
            "short_slope_bq_m3_per_hour": row.get("short_slope_bq_m3_per_hour"),
            "medium_slope_bq_m3_per_hour": row.get("medium_slope_bq_m3_per_hour"),
            "slope_acceleration_bq_m3_per_hour2": row.get("slope_acceleration_bq_m3_per_hour2"),
            "rolling_median_radon": row.get("rolling_median_radon"),
            "local_variability_mad": row.get("local_variability_mad"),
            "local_variability_normalized": row.get("local_variability_normalized"),
            "short_valid_observation_count": row.get("short_valid_observation_count"),
            "medium_valid_observation_count": row.get("medium_valid_observation_count"),
            "distance_to_previous_gap_observations": row.get("distance_to_previous_gap_observations"),
            "distance_to_previous_gap_hours": row.get("distance_to_previous_gap_hours"),
            "distance_to_next_gap_observations": row.get("distance_to_next_gap_observations"),
            "distance_to_next_gap_hours": row.get("distance_to_next_gap_hours"),
            "raw_smoothed_disagreement": row.get("raw_smoothed_disagreement"),
            "confidence_score": row.get("regime_confidence_score"),
            "confidence_label": row.get("regime_confidence_label"),
            "confidence_reasons": row.get("regime_confidence_reasons"),
            "dynamic_reason_codes": row.get("dynamic_reason_codes"),
            "quality_flags": row.get("quality_flags"),
        }
        for row in rows[:20000]
    ]


def _regime_confidence_rows(rows):
    return [
        {
            "timestamp": row["measured_at"].isoformat(),
            "segment_id": row.get("segment_id"),
            "concentration_level": row.get("concentration_level"),
            "candidate_dynamic_state": row.get("candidate_dynamic_state"),
            "confirmed_dynamic_state": row.get("confirmed_dynamic_state") or row.get("dynamic_state"),
            "dynamic_state": row.get("confirmed_dynamic_state") or row.get("dynamic_state"),
            "score": row.get("regime_confidence_score"),
            "label": row.get("regime_confidence_label"),
            "reason_codes": row.get("regime_confidence_reasons"),
        }
        for row in rows[:20000]
    ]


def _regime_confidence_summary(rows, episodes):
    confidence_counts = {}
    confidence_by_state = {}
    reason_counts = {}
    for row in rows:
        label = row.get("regime_confidence_label") or "UNKNOWN"
        state = row.get("confirmed_dynamic_state") or row.get("dynamic_state") or "UNKNOWN"
        confidence_counts[label] = confidence_counts.get(label, 0) + 1
        confidence_by_state.setdefault(state, {}).setdefault(label, 0)
        confidence_by_state[state][label] += 1
        for reason in row.get("regime_confidence_reasons") or []:
            reason_counts[reason] = reason_counts.get(reason, 0) + 1
    confidence_by_episode = {}
    low_confidence_episodes = []
    for episode in episodes:
        episode_type = episode.get("episode_type") or "UNKNOWN"
        label = episode.get("confidence_category") or episode.get("regime_confidence_label") or "UNKNOWN"
        confidence_by_episode.setdefault(episode_type, {}).setdefault(label, 0)
        confidence_by_episode[episode_type][label] += 1
        if label == "LOW":
            low_confidence_episodes.append(episode)
    return {
        "confidence_category_counts": dict(sorted(confidence_counts.items())),
        "confidence_distribution_by_dynamic_state": {key: dict(sorted(value.items())) for key, value in sorted(confidence_by_state.items())},
        "confidence_distribution_by_episode_type": {key: dict(sorted(value.items())) for key, value in sorted(confidence_by_episode.items())},
        "reason_code_counts": dict(sorted(reason_counts.items())),
        "low_confidence_row_count": confidence_counts.get("LOW", 0),
        "low_confidence_rows_preview": [
            {
                "timestamp": row["measured_at"].isoformat(),
                "segment_id": row.get("segment_id"),
                "confirmed_dynamic_state": row.get("confirmed_dynamic_state") or row.get("dynamic_state"),
                "score": row.get("regime_confidence_score"),
                "reason_codes": row.get("regime_confidence_reasons"),
            }
            for row in rows
            if row.get("regime_confidence_label") == "LOW"
        ][:100],
        "low_confidence_episode_count": len(low_confidence_episodes),
        "low_confidence_episodes_preview": low_confidence_episodes[:100],
    }


def _feature_distribution_diagnostics(rows):
    fields = [
        "adjacent_slope_bq_m3_per_hour",
        "short_slope_bq_m3_per_hour",
        "medium_slope_bq_m3_per_hour",
        "local_variability_mad",
    ]
    probabilities = [0.01, 0.05, 0.10, 0.25, 0.50, 0.75, 0.90, 0.95, 0.99]
    diagnostics = []
    for field in fields:
        values = sorted(row.get(field) for row in rows if row.get(field) is not None)
        item = {"feature": field, "sample_count": len(values)}
        for probability in probabilities:
            item[f"q{int(probability * 100):02d}"] = _quantile(values, probability)
        diagnostics.append(item)
    return diagnostics


def _sudden_event_audit(rows, config):
    audit = []
    ordered = sorted(rows, key=lambda row: row["measured_at"])
    by_key = {(row.get("segment_id"), row["measured_at"]): row for row in ordered}
    for row in ordered:
        state = row.get("confirmed_dynamic_state") or row.get("dynamic_state")
        if state not in {"SUDDEN_RISE", "SUDDEN_DROP"}:
            continue
        previous_time = None
        previous_row = None
        if row.get("observed_interval_hours"):
            previous_time = row["measured_at"] - _hours_to_delta(row["observed_interval_hours"])
            previous_row = by_key.get((row.get("segment_id"), previous_time))
        current = float(row["radon_bq_m3"]) if row.get("radon_bq_m3") is not None else None
        previous = float(previous_row["radon_bq_m3"]) if previous_row and previous_row.get("radon_bq_m3") is not None else None
        absolute_change = current - previous if current is not None and previous is not None else None
        audit.append(
            {
                "timestamp": row["measured_at"].isoformat(),
                "segment_id": row.get("segment_id"),
                "event_state": state,
                "previous_radon": previous,
                "current_radon": current,
                "observed_interval_hours": row.get("observed_interval_hours"),
                "absolute_change": round(absolute_change, 3) if absolute_change is not None else None,
                "relative_change_percent": round((absolute_change / previous) * 100, 3) if absolute_change is not None and previous not in (None, 0) else None,
                "adjacent_slope_bq_m3_per_hour": row.get("adjacent_slope_bq_m3_per_hour"),
                "short_slope_bq_m3_per_hour": row.get("short_slope_bq_m3_per_hour"),
                "threshold_used_bq_m3_per_hour": config.sudden_change_bq_m3_per_hour,
                "trigger_rule": "adjacent_slope_exceeds_sudden_threshold",
                "threshold_satisfied": abs(row.get("adjacent_slope_bq_m3_per_hour") or 0) >= config.sudden_change_bq_m3_per_hour,
            }
        )
    return audit


def _episode_reason_summary(episodes):
    rows = []
    for episode in episodes:
        for reason, values in (episode.get("reason_code_summary") or {}).items():
            rows.append(
                {
                    "segment_id": episode.get("segment_id"),
                    "episode_sequence_number": episode.get("episode_sequence_number"),
                    "episode_type": episode.get("episode_type"),
                    "reason_code": reason,
                    "row_count": values.get("count"),
                    "row_percent": values.get("percent"),
                }
            )
    return rows


def _transition_merge_audit(episodes):
    rows = []
    for episode in episodes:
        for audit in episode.get("transition_merge_audit") or []:
            row = dict(audit)
            row["segment_id"] = episode.get("segment_id")
            row["episode_type"] = episode.get("episode_type")
            rows.append(row)
    return rows


def _elevated_period_phase_table(episodes):
    periods = [
        ("2024-05-25", "2024-05-30"),
        ("2024-06-07", "2024-06-14"),
    ]
    rows = []
    for period_start, period_end in periods:
        for episode in episodes:
            start = str(episode.get("start", ""))
            end = str(episode.get("end", ""))
            if start[:10] <= period_end and end[:10] >= period_start:
                rows.append(
                    {
                        "inspection_period": f"{period_start} to {period_end}",
                        "phase_start": episode.get("start"),
                        "phase_end": episode.get("end"),
                        "concentration_level_distribution": episode.get("concentration_level_distribution"),
                        "dynamic_state_distribution": episode.get("dynamic_state_distribution"),
                        "episode_type": episode.get("episode_type"),
                        "start_radon": episode.get("starting_radon"),
                        "end_radon": episode.get("ending_radon"),
                        "min_radon": episode.get("min_radon"),
                        "max_radon": episode.get("max_radon"),
                        "robust_slope": episode.get("robust_episode_slope_bq_m3_per_hour"),
                        "local_variability": episode.get("local_variability"),
                        "confidence": episode.get("confidence_category"),
                        "reason_codes": episode.get("dominant_reason_codes"),
                    }
                )
    return rows


def _quantile(values, probability):
    if not values:
        return None
    index = min(int((len(values) - 1) * probability), len(values) - 1)
    return values[index]


def _hours_to_delta(hours):
    from datetime import timedelta

    return timedelta(hours=float(hours))


def _quality_flag_details(rows, resampling_outputs, quality_outputs):
    total_measurements = len(rows) or 1
    hourly_rows = resampling_outputs.get("canonical_hourly_data", [])
    details = []
    for flag, count in sorted((quality_outputs.get("quality_flag_counts") or {}).items()):
        canonical_affected = sum(1 for row in rows if flag in (row.get("quality_flags") or []))
        hourly_affected = sum(1 for row in hourly_rows if flag in (row.get("quality_flags") or []))
        details.append(
            {
                "quality_flag": flag,
                "flag_occurrences": count,
                "unique_raw_measurements_affected": canonical_affected,
                "unique_canonical_measurements_affected": canonical_affected,
                "hourly_or_analysis_rows_affected": hourly_affected,
                "percentage_of_measurements_affected": round((canonical_affected / total_measurements) * 100, 3),
                "meaning": _quality_flag_meaning(flag),
            }
        )
    if not any(row["quality_flag"] == "ENVIRONMENTAL_PREDICTORS_UNAVAILABLE" for row in details):
        env_missing = all(row.get("temperature_c") is None and row.get("humidity_percent") is None and row.get("pressure_hpa") is None for row in rows)
        if env_missing and rows:
            details.append(
                {
                    "quality_flag": "ENVIRONMENTAL_PREDICTORS_UNAVAILABLE",
                    "flag_occurrences": len(rows),
                    "unique_raw_measurements_affected": 0,
                    "unique_canonical_measurements_affected": 0,
                    "hourly_or_analysis_rows_affected": 0,
                    "percentage_of_measurements_affected": 0,
                    "meaning": "Environmental predictors are absent from the source file; radon measurements are not invalid solely for this reason.",
                }
            )
    return details


def _quality_flag_meaning(flag):
    if flag == "VALID":
        return "Measurement row has no currently blocking quality issue for radon analysis."
    if flag.startswith("MISSING_") and flag != "MISSING_RADON":
        return "Environmental covariate missing; this limits environmental predictor analyses but does not invalidate radon concentration."
    return "Research quality diagnostic flag; see Quality Flag Dictionary for general description."
