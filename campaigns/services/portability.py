from collections import Counter


def build_portability_outputs(rows, gaps, episodes, continuity, config):
    return {
        "profile_applicability": profile_applicability(rows, gaps, continuity, config),
        "adaptive_recommendations": adaptive_recommendations(rows, config),
        "standardized_campaign_summary": standardized_campaign_summary(rows, gaps, episodes, continuity, config),
    }


def profile_applicability(rows, gaps, continuity, config):
    summary = continuity.get("summary", {}) if continuity else {}
    expected = summary.get("expected_sampling_interval_minutes") or config.expected_sampling_interval_minutes or 60
    interval_counts = summary.get("interval_class_counts", {})
    irregular = sum(count for key, count in interval_counts.items() if key != "REGULAR_INTERVAL")
    interval_count = summary.get("interval_count") or 0
    warnings = []
    if config.expected_sampling_interval_minutes and abs(expected - config.expected_sampling_interval_minutes) > config.expected_sampling_interval_minutes * 0.5:
        warnings.append("SAMPLING_INTERVAL_OUTSIDE_PROFILE_RANGE")
    if interval_count and irregular / interval_count > 0.10:
        warnings.append("HIGH_GAP_DENSITY")
    if len(rows) < config.medium_window_observations:
        warnings.append("CAMPAIGN_TOO_SHORT_FOR_MEDIUM_WINDOW")
    values = [float(row["radon_bq_m3"]) for row in rows if row.get("radon_bq_m3") is not None]
    if values:
        if max(values) < config.concentration_low_threshold_bq_m3 * 0.5:
            warnings.append("TOO_FEW_HIGH_EPISODES_FOR_VALIDATION")
        if (max(values) - min(values)) < 20:
            warnings.append("INSUFFICIENT_STABLE_BASELINE")
        if values.count(0.0) / len(values) > 0.05:
            warnings.append("HIGH_ZERO_VALUE_PROPORTION")
    else:
        warnings.append("NO_VALID_RADON_VALUES")
    warnings.append("SENSOR_RESOLUTION_UNKNOWN")
    if "NO_VALID_RADON_VALUES" in warnings or len(rows) < 3:
        status = "PROFILE_NOT_RECOMMENDED"
    elif warnings:
        status = "PROFILE_COMPATIBLE_WITH_WARNINGS"
    else:
        status = "PROFILE_COMPATIBLE"
    return {
        "status": status,
        "reason_codes": sorted(set(warnings)),
        "profile_name": config.profile_name,
        "profile_version": config.profile_version,
        "expected_sampling_interval_minutes": expected,
        "irregular_interval_percent": round((irregular / interval_count) * 100, 3) if interval_count else 0,
        "gap_count": len(gaps),
        "observation_count": len(rows),
    }


def adaptive_recommendations(rows, config):
    features = {
        "short_slope_bq_m3_per_hour": sorted(abs(row.get("short_slope_bq_m3_per_hour")) for row in rows if row.get("short_slope_bq_m3_per_hour") is not None),
        "medium_slope_bq_m3_per_hour": sorted(abs(row.get("medium_slope_bq_m3_per_hour")) for row in rows if row.get("medium_slope_bq_m3_per_hour") is not None),
        "local_variability_mad": sorted(row.get("local_variability_mad") for row in rows if row.get("local_variability_mad") is not None),
    }
    return [
        _recommendation("trend_slope_bq_m3_per_hour", config.trend_slope_bq_m3_per_hour, _quantile(features["short_slope_bq_m3_per_hour"], 0.90), "90th percentile absolute short-window slope"),
        _recommendation("medium_trend_slope_bq_m3_per_hour", config.medium_trend_slope_bq_m3_per_hour, _quantile(features["medium_slope_bq_m3_per_hour"], 0.90), "90th percentile absolute medium-window slope"),
        _recommendation("variability_threshold_bq_m3", config.variability_threshold_bq_m3, _quantile(features["local_variability_mad"], 0.95), "95th percentile local MAD"),
    ]


def standardized_campaign_summary(rows, gaps, episodes, continuity, config):
    duration = _campaign_duration_hours(rows)
    values = [float(row["radon_bq_m3"]) for row in rows if row.get("radon_bq_m3") is not None]
    slopes = sorted(abs(row.get("adjacent_slope_bq_m3_per_hour")) for row in rows if row.get("adjacent_slope_bq_m3_per_hour") is not None)
    confidence = sorted(row.get("regime_confidence_score") for row in rows if row.get("regime_confidence_score") is not None)
    levels = Counter(row.get("concentration_level") for row in rows)
    states = Counter(row.get("confirmed_dynamic_state") or row.get("dynamic_state") for row in rows)
    return {
        "profile_name": config.profile_name,
        "profile_version": config.profile_version,
        "algorithm_version": (rows[0].get("regime_algorithm_version") if rows else "N/A"),
        "sampling_interval_minutes": (continuity.get("summary", {}) or {}).get("expected_sampling_interval_minutes"),
        "campaign_duration_hours": duration,
        "valid_row_count": len(rows),
        "gap_rate_per_1000_hours": round((len(gaps) / duration) * 1000, 3) if duration else "N/A",
        "concentration_level_percentages": _percentages(levels),
        "dynamic_state_percentages": _percentages(states),
        "episode_counts_per_1000_hours": _episode_rates(episodes, duration),
        "median_episode_duration_by_type": _median_episode_duration(episodes),
        "maximum_radon": max(values) if values else None,
        "time_above_low_threshold_hours": _time_above(rows, config.concentration_low_threshold_bq_m3),
        "time_above_high_threshold_hours": _time_above(rows, config.concentration_high_threshold_bq_m3),
        "median_absolute_slope": _quantile(slopes, 0.50),
        "p90_absolute_slope": _quantile(slopes, 0.90),
        "median_confidence": _quantile(confidence, 0.50),
        "low_confidence_percent": round(sum(1 for row in rows if row.get("regime_confidence_label") == "LOW") / len(rows) * 100, 3) if rows else 0,
    }


def _recommendation(field, active, recommended, source):
    return {
        "parameter": field,
        "active_threshold": active,
        "recommended_threshold": recommended,
        "source": source,
        "override_accepted": False,
        "note": "Diagnostic recommendation only; active fixed-profile threshold was not changed silently.",
    }


def _campaign_duration_hours(rows):
    if len(rows) < 2:
        return 0
    ordered = sorted(rows, key=lambda row: row["measured_at"])
    return round((ordered[-1]["measured_at"] - ordered[0]["measured_at"]).total_seconds() / 3600, 3)


def _time_above(rows, threshold):
    total = 0
    ordered = sorted(rows, key=lambda row: row["measured_at"])
    for current, following in zip(ordered, ordered[1:]):
        if current.get("segment_id") != following.get("segment_id"):
            continue
        if current.get("radon_bq_m3") is not None and float(current["radon_bq_m3"]) >= threshold:
            total += max((following["measured_at"] - current["measured_at"]).total_seconds() / 3600, 0)
    return round(total, 3)


def _episode_rates(episodes, duration):
    counts = Counter(episode.get("episode_type") for episode in episodes)
    if not duration:
        return {}
    return {key: round((value / duration) * 1000, 3) for key, value in sorted(counts.items())}


def _median_episode_duration(episodes):
    grouped = {}
    for episode in episodes:
        grouped.setdefault(episode.get("episode_type"), []).append(episode.get("duration_hours") or 0)
    return {key: _quantile(sorted(values), 0.50) for key, values in sorted(grouped.items())}


def _percentages(counts):
    total = sum(counts.values())
    if not total:
        return {}
    return {key: round((value / total) * 100, 3) for key, value in sorted(counts.items()) if key}


def _quantile(values, probability):
    values = [value for value in values if value is not None]
    if not values:
        return None
    values = sorted(values)
    index = min(int((len(values) - 1) * probability), len(values) - 1)
    return values[index]
