from collections import Counter

from campaigns.services.episodes import build_episodes, episode_type_counts
from campaigns.services.regime_v2 import classify_regimes_v2


def build_sensitivity_v2(rows, config):
    baseline_levels = [row.get("concentration_level") for row in rows]
    baseline_states = [row.get("confirmed_dynamic_state") or row.get("dynamic_state") for row in rows]
    baseline_episodes = build_episodes(rows, [], config)
    dynamic_grid = _dynamic_parameter_grid(config)
    return {
        "level_sensitivity": [_level_run(rows, config, multiplier, baseline_levels) for multiplier in (0.9, 1.0, 1.1)],
        "dynamic_sensitivity": [_dynamic_run(rows, config, parameters, baseline_states, baseline_episodes) for parameters in dynamic_grid],
    }


def _level_run(rows, config, multiplier, baseline):
    adjusted = _replace_config(
        config,
        concentration_low_threshold_bq_m3=config.concentration_low_threshold_bq_m3 * multiplier,
        concentration_high_threshold_bq_m3=config.concentration_high_threshold_bq_m3 * multiplier,
    )
    classified = classify_regimes_v2(rows, adjusted)
    labels = [row.get("concentration_level") for row in classified]
    counts = Counter(labels)
    return {
        "parameter_set_identifier": f"level_threshold_multiplier_{multiplier}",
        "threshold_multiplier": multiplier,
        "level_counts": dict(sorted(counts.items())),
        "level_percentages": _percentages(counts),
        "agreement_with_baseline_percent": _agreement(baseline, labels),
        "elevated_or_high_observations": counts.get("ELEVATED", 0) + counts.get("HIGH", 0),
    }


def _dynamic_run(rows, config, parameters, baseline, baseline_episodes):
    adjusted = _replace_config(config, **parameters)
    classified = classify_regimes_v2(rows, adjusted)
    labels = [row.get("confirmed_dynamic_state") or row.get("dynamic_state") for row in classified]
    counts = Counter(labels)
    episodes = build_episodes(classified, [], adjusted)
    return {
        "parameter_set_identifier": parameters["parameter_set_identifier"],
        "slope_threshold_multiplier": parameters.get("slope_threshold_multiplier", 1.0),
        "short_window_observations": adjusted.short_window_observations,
        "medium_window_observations": adjusted.medium_window_observations,
        "minimum_state_persistence_observations": adjusted.minimum_state_persistence_observations,
        "variability_threshold_bq_m3": adjusted.variability_threshold_bq_m3,
        "state_counts": dict(sorted(counts.items())),
        "state_duration_hours": _duration_by_state(classified),
        "state_percentages": _percentages(counts),
        "episode_count_by_type": episode_type_counts(episodes),
        "episode_transition_count": sum(1 for previous, current in zip(labels, labels[1:]) if previous != current),
        "agreement_with_baseline_percent": _agreement(baseline, labels),
        "cohen_kappa": _cohen_kappa(baseline, labels),
        "baseline_episode_preservation_percent": _episode_preservation(baseline_episodes, episodes),
        "metric_note": "Deterministic sensitivity around dynamic-state parameters only; concentration thresholds are not changed here.",
    }


def _dynamic_parameter_grid(config):
    rows = []
    for multiplier in (0.8, 1.0, 1.2):
        rows.append(
            {
                "parameter_set_identifier": f"dynamic_slope_x{multiplier}",
                "slope_threshold_multiplier": multiplier,
                "stable_slope_bq_m3_per_hour": config.stable_slope_bq_m3_per_hour * multiplier,
                "trend_slope_bq_m3_per_hour": config.trend_slope_bq_m3_per_hour * multiplier,
                "sudden_change_bq_m3_per_hour": config.sudden_change_bq_m3_per_hour * multiplier,
            }
        )
    rows.extend(
        [
            {
                "parameter_set_identifier": "dynamic_short_window_2",
                "short_window_observations": max(2, config.short_window_observations - 1),
            },
            {
                "parameter_set_identifier": "dynamic_medium_window_plus1",
                "medium_window_observations": config.medium_window_observations + 1,
            },
            {
                "parameter_set_identifier": "dynamic_persistence_1",
                "minimum_state_persistence_observations": 1,
            },
            {
                "parameter_set_identifier": "dynamic_persistence_plus1",
                "minimum_state_persistence_observations": config.minimum_state_persistence_observations + 1,
            },
            {
                "parameter_set_identifier": "dynamic_variability_x0.8",
                "variability_threshold_bq_m3": config.variability_threshold_bq_m3 * 0.8,
            },
            {
                "parameter_set_identifier": "dynamic_variability_x1.2",
                "variability_threshold_bq_m3": config.variability_threshold_bq_m3 * 1.2,
            },
        ]
    )
    return rows


def _replace_config(config, **updates):
    values = config.to_dict()
    updates.pop("parameter_set_identifier", None)
    updates.pop("slope_threshold_multiplier", None)
    values.update(updates)
    tuple_fields = {"sensitivity_multipliers", "prediction_horizons", "excluded_prediction_quality_flags"}
    for field in tuple_fields:
        if field in values:
            values[field] = tuple(values[field])
    return type(config)(**values)


def _duration_by_state(rows):
    totals = Counter()
    ordered = sorted(rows, key=lambda row: row["measured_at"])
    for current, following in zip(ordered, ordered[1:]):
        state = current.get("confirmed_dynamic_state") or current.get("dynamic_state")
        if current.get("segment_id") != following.get("segment_id"):
            continue
        hours = (following["measured_at"] - current["measured_at"]).total_seconds() / 3600
        if hours > 0:
            totals[state] += hours
    return {key: round(value, 3) for key, value in sorted(totals.items())}


def _episode_preservation(baseline, candidate):
    if not baseline:
        return None
    baseline_keys = {_episode_key(episode) for episode in baseline}
    candidate_keys = {_episode_key(episode) for episode in candidate}
    preserved = len(baseline_keys & candidate_keys)
    return round((preserved / len(baseline_keys)) * 100, 2)


def _episode_key(episode):
    return (episode.get("segment_id"), episode.get("episode_type"), episode.get("start"), episode.get("end"))


def _percentages(counts):
    total = sum(counts.values())
    if not total:
        return {}
    return {key: round((value / total) * 100, 2) for key, value in sorted(counts.items())}


def _agreement(baseline, labels):
    if not baseline:
        return None
    return round(sum(1 for left, right in zip(baseline, labels) if left == right) / len(baseline) * 100, 2)


def _cohen_kappa(baseline, labels):
    if not baseline or not labels:
        return None
    observed = sum(1 for left, right in zip(baseline, labels) if left == right) / len(baseline)
    baseline_counts = Counter(baseline)
    label_counts = Counter(labels)
    expected = sum((baseline_counts[key] / len(baseline)) * (label_counts[key] / len(labels)) for key in set(baseline_counts) | set(label_counts))
    if expected == 1:
        return 1.0
    return round((observed - expected) / (1 - expected), 3)
