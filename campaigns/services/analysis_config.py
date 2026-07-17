from dataclasses import asdict, dataclass, field, replace


@dataclass(frozen=True)
class AnalysisConfig:
    profile_name: str = "default_radon_hourly"
    profile_version: str = "2026-07-v1"
    threshold_mode: str = "fixed_profile"
    profile_overrides: dict = field(default_factory=dict)
    profile_warnings: tuple[str, ...] = ()
    timezone_name: str = "Europe/Rome"
    resample_interval: str = "1H"
    gap_tolerance_multiplier: float = 1.5
    short_gap_minutes: float = 180.0
    completeness_threshold: float = 0.75
    expected_sampling_interval_minutes: float | None = None
    minor_interval_tolerance: float = 1.25
    short_gap_multiplier: float = 2.0
    moderate_gap_multiplier: float = 6.0
    concentration_low_threshold_bq_m3: float = 100.0
    concentration_high_threshold_bq_m3: float = 200.0
    concentration_hysteresis_bq_m3: float = 10.0
    short_window_minutes: float = 180.0
    medium_window_minutes: float = 360.0
    persistence_minutes: float = 120.0
    isolated_state_merge_minutes: float = 60.0
    minimum_episode_duration_minutes: float = 120.0
    gap_proximity_minutes: float = 60.0
    short_window_observations: int = 3
    medium_window_observations: int = 6
    minimum_short_window_observations: int = 2
    minimum_medium_window_observations: int = 3
    stable_slope_bq_m3_per_hour: float = 8.0
    trend_slope_bq_m3_per_hour: float = 8.0
    medium_trend_slope_bq_m3_per_hour: float = 4.5
    sudden_change_bq_m3_per_hour: float = 75.0
    variability_threshold_bq_m3: float = 15.0
    instability_score_threshold: int = 2
    instability_sign_change_threshold: int = 2
    material_slope_disagreement_bq_m3_per_hour: float = 5.0
    raw_smoothed_disagreement_threshold_bq_m3_per_hour: float = 8.0
    slope_near_threshold_absolute_tolerance_bq_m3_per_hour: float = 1.0
    slope_near_threshold_relative_tolerance: float = 0.10
    variability_normalization_floor_bq_m3: float = 50.0
    minimum_state_persistence_observations: int = 2
    isolated_state_absorption_observations: int = 1
    minimum_episode_observations: int = 2
    minimum_trend_episode_observations: int = 3
    minimum_trend_episode_duration_hours: float = 2.0
    near_gap_observations: int = 1
    sensitivity_multipliers: tuple[float, ...] = (0.8, 0.9, 1.0, 1.1, 1.2)
    prediction_horizons: tuple[str, ...] = ("1h", "6h")
    train_test_split_policy: str = "chronological_train_test_split"
    excluded_prediction_quality_flags: tuple[str, ...] = (
        "DUPLICATE_CONFLICT",
        "LOW_COMPLETENESS",
        "DST_AMBIGUOUS",
    )
    regime_thresholds: dict = field(
        default_factory=lambda: {
            "low_radon_bq_m3": 100.0,
            "elevated_radon_bq_m3": 200.0,
            "high_radon_bq_m3": 300.0,
            "stable_change_bq_m3": 20.0,
            "rising_change_bq_m3": 30.0,
            "falling_change_bq_m3": -30.0,
            "sudden_change_bq_m3": 100.0,
            "minimum_segment_size": 3,
            "quality_limited_sample_count": 3,
        }
    )

    def to_dict(self):
        data = asdict(self)
        data["sensitivity_multipliers"] = list(self.sensitivity_multipliers)
        data["prediction_horizons"] = list(self.prediction_horizons)
        data["excluded_prediction_quality_flags"] = list(self.excluded_prediction_quality_flags)
        data["profile_warnings"] = list(self.profile_warnings)
        return data

    def with_time_windows(self, expected_interval_minutes):
        interval = float(expected_interval_minutes or self.expected_sampling_interval_minutes or 60.0)
        if interval <= 0:
            interval = 60.0
        return replace(
            self,
            expected_sampling_interval_minutes=interval,
            short_window_observations=max(self.minimum_short_window_observations, round(self.short_window_minutes / interval) + 1),
            medium_window_observations=max(self.minimum_medium_window_observations, round(self.medium_window_minutes / interval) + 1),
            minimum_state_persistence_observations=max(1, round(self.persistence_minutes / interval)),
            isolated_state_absorption_observations=max(1, round(self.isolated_state_merge_minutes / interval)),
            near_gap_observations=max(1, round(self.gap_proximity_minutes / interval)),
        )


def config_from_options(**options):
    clean_options = {key: value for key, value in options.items() if value is not None}
    return AnalysisConfig(**clean_options)
