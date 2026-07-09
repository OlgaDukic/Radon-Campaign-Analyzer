def build_prediction_readiness(segments, quality_flag_counts, prediction_metrics_by_regime):
    regime_samples = {}
    for row in prediction_metrics_by_regime:
        if row.get("model") == "ridge":
            regime_samples[row.get("regime") or "unclassified"] = max(
                regime_samples.get(row.get("regime") or "unclassified", 0),
                row.get("samples") or 0,
            )

    readiness = []
    severe_flags = {"DUPLICATE_CONFLICT", "GAP_LONG", "DST_AMBIGUOUS"}
    severe_count = sum(quality_flag_counts.get(flag, 0) for flag in severe_flags)
    for segment in segments:
        reductions = []
        score = 1.0
        measurement_count = segment.get("measurement_count") or 0
        if measurement_count < 6:
            score -= 0.25
            reductions.append("segment length is short")
        if severe_count:
            score -= 0.25
            reductions.append("severe quality flags are present")
        if segment.get("dynamic_percent", 0) > 50:
            score -= 0.1
            reductions.append("regime dynamics are high")
        dominant = segment.get("dominant_regime") or "unclassified"
        if regime_samples.get(dominant, 0) < 3:
            score -= 0.2
            reductions.append("small regime sample for prediction metrics")
        env_stats = segment.get("statistics", {})
        if any((env_stats.get(field, {}).get("count") or 0) == 0 for field in ("temperature_c", "humidity_percent", "pressure_hpa")):
            score -= 0.1
            reductions.append("environmental covariates are incomplete")
        score = max(round(score, 2), 0.0)
        readiness.append(
            {
                "segment_id": segment.get("segment_id"),
                "regime": dominant,
                "prediction_readiness_score": score,
                "category": _category(score),
                "explanation": _explanation(score, reductions),
                "score_reduction_flags": reductions,
            }
        )
    return readiness


def _category(score):
    if score >= 0.75:
        return "high"
    if score >= 0.45:
        return "medium"
    return "low"


def _explanation(score, reductions):
    if not reductions:
        return "Research diagnostic suggests this segment is comparatively suitable for short-term prediction evaluation."
    return "Research diagnostic only; score reduced because " + ", ".join(reductions) + "."
