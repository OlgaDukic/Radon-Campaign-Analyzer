from dataclasses import asdict, dataclass, field


@dataclass(frozen=True)
class AnalysisConfig:
    timezone_name: str = "Europe/Rome"
    resample_interval: str = "1H"
    gap_tolerance_multiplier: float = 1.5
    short_gap_minutes: float = 180.0
    completeness_threshold: float = 0.75
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
        return data


def config_from_options(**options):
    clean_options = {key: value for key, value in options.items() if value is not None}
    return AnalysisConfig(**clean_options)
