from dataclasses import replace

from campaigns.services.analysis_config import AnalysisConfig


PROFILE_VERSION = "2026-07-v1"


PROFILES = {
    "default_radon_hourly": {
        "profile_name": "default_radon_hourly",
        "profile_version": PROFILE_VERSION,
        "expected_sampling_interval_minutes": 60.0,
        "minor_interval_tolerance": 1.25,
        "gap_tolerance_multiplier": 1.5,
        "short_gap_multiplier": 2.0,
        "moderate_gap_multiplier": 6.0,
        "concentration_low_threshold_bq_m3": 100.0,
        "concentration_high_threshold_bq_m3": 200.0,
        "concentration_hysteresis_bq_m3": 10.0,
        "short_window_minutes": 180.0,
        "medium_window_minutes": 360.0,
        "stable_slope_bq_m3_per_hour": 8.0,
        "trend_slope_bq_m3_per_hour": 8.0,
        "medium_trend_slope_bq_m3_per_hour": 4.5,
        "sudden_change_bq_m3_per_hour": 75.0,
        "variability_threshold_bq_m3": 15.0,
        "persistence_minutes": 120.0,
        "minimum_episode_duration_minutes": 120.0,
        "isolated_state_merge_minutes": 60.0,
        "gap_proximity_minutes": 60.0,
    },
    "default_radon_subhourly": {
        "profile_name": "default_radon_subhourly",
        "profile_version": PROFILE_VERSION,
        "expected_sampling_interval_minutes": 30.0,
        "minor_interval_tolerance": 1.35,
        "gap_tolerance_multiplier": 2.0,
        "short_gap_multiplier": 3.0,
        "moderate_gap_multiplier": 8.0,
        "concentration_low_threshold_bq_m3": 100.0,
        "concentration_high_threshold_bq_m3": 200.0,
        "concentration_hysteresis_bq_m3": 10.0,
        "short_window_minutes": 180.0,
        "medium_window_minutes": 360.0,
        "stable_slope_bq_m3_per_hour": 8.0,
        "trend_slope_bq_m3_per_hour": 8.0,
        "medium_trend_slope_bq_m3_per_hour": 4.5,
        "sudden_change_bq_m3_per_hour": 75.0,
        "variability_threshold_bq_m3": 15.0,
        "persistence_minutes": 120.0,
        "minimum_episode_duration_minutes": 120.0,
        "isolated_state_merge_minutes": 60.0,
        "gap_proximity_minutes": 60.0,
    },
    "default_radon_sparse": {
        "profile_name": "default_radon_sparse",
        "profile_version": PROFILE_VERSION,
        "expected_sampling_interval_minutes": 120.0,
        "minor_interval_tolerance": 1.25,
        "gap_tolerance_multiplier": 1.5,
        "short_gap_multiplier": 2.0,
        "moderate_gap_multiplier": 6.0,
        "concentration_low_threshold_bq_m3": 100.0,
        "concentration_high_threshold_bq_m3": 200.0,
        "concentration_hysteresis_bq_m3": 10.0,
        "short_window_minutes": 360.0,
        "medium_window_minutes": 720.0,
        "stable_slope_bq_m3_per_hour": 8.0,
        "trend_slope_bq_m3_per_hour": 8.0,
        "medium_trend_slope_bq_m3_per_hour": 4.5,
        "sudden_change_bq_m3_per_hour": 75.0,
        "variability_threshold_bq_m3": 18.0,
        "persistence_minutes": 240.0,
        "minimum_episode_duration_minutes": 240.0,
        "isolated_state_merge_minutes": 120.0,
        "gap_proximity_minutes": 120.0,
    },
    "high_noise_sensor": {
        "profile_name": "high_noise_sensor",
        "profile_version": PROFILE_VERSION,
        "expected_sampling_interval_minutes": 60.0,
        "minor_interval_tolerance": 1.35,
        "gap_tolerance_multiplier": 1.75,
        "short_gap_multiplier": 2.5,
        "moderate_gap_multiplier": 6.0,
        "concentration_low_threshold_bq_m3": 100.0,
        "concentration_high_threshold_bq_m3": 200.0,
        "concentration_hysteresis_bq_m3": 15.0,
        "short_window_minutes": 240.0,
        "medium_window_minutes": 480.0,
        "stable_slope_bq_m3_per_hour": 10.0,
        "trend_slope_bq_m3_per_hour": 10.0,
        "medium_trend_slope_bq_m3_per_hour": 6.0,
        "sudden_change_bq_m3_per_hour": 90.0,
        "variability_threshold_bq_m3": 25.0,
        "persistence_minutes": 180.0,
        "minimum_episode_duration_minutes": 180.0,
        "isolated_state_merge_minutes": 60.0,
        "gap_proximity_minutes": 60.0,
    },
}


def build_config(profile_name="default_radon_hourly", overrides=None, **base_options):
    overrides = overrides or {}
    if profile_name not in PROFILES:
        raise ValueError(f"Unknown analysis profile: {profile_name}")
    values = {**PROFILES[profile_name], **base_options, **overrides}
    tuple_fields = {"sensitivity_multipliers", "prediction_horizons", "excluded_prediction_quality_flags", "profile_warnings"}
    for field in tuple_fields:
        if field in values and isinstance(values[field], list):
            values[field] = tuple(values[field])
    config = AnalysisConfig(**{key: value for key, value in values.items() if hasattr(AnalysisConfig, key) or key in AnalysisConfig.__dataclass_fields__})
    return replace(config, profile_overrides=dict(overrides))


def profile_catalog():
    return {name: dict(values) for name, values in PROFILES.items()}


def parse_overrides(items):
    overrides = {}
    for item in items or []:
        if "=" not in item:
            raise ValueError(f"Invalid override '{item}'. Use key=value.")
        key, value = item.split("=", 1)
        overrides[key] = _coerce(value)
    return overrides


def _coerce(value):
    lowered = value.lower()
    if lowered in {"true", "false"}:
        return lowered == "true"
    try:
        if "." in value:
            return float(value)
        return int(value)
    except ValueError:
        return value
