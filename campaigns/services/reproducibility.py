import subprocess

from django.utils import timezone


def build_reproducibility_config(campaign, uploaded_files, config, extra=None):
    data = {
        "campaign_id": campaign.id,
        "run_timestamp": timezone.now().isoformat(),
        "app_version_or_git_commit": _git_commit(),
        "timezone": config.timezone_name,
        "input_source_file_names": [uploaded_file.original_name for uploaded_file in uploaded_files],
        "canonicalisation_rules": [
            "sort_by_utc_timestamp",
            "deduplicate_exact_timestamp_value_rows",
            "flag_duplicate_conflicts",
            "merge_environmental_completeness_when_radon_agrees",
        ],
        "resampling_interval": config.resample_interval,
        "gap_tolerance_multiplier": config.gap_tolerance_multiplier,
        "completeness_threshold": config.completeness_threshold,
        "regime_thresholds": config.regime_thresholds,
        "sensitivity_multipliers": list(config.sensitivity_multipliers),
        "prediction_horizons": list(config.prediction_horizons),
        "train_test_split_policy": config.train_test_split_policy,
        "prediction_evaluation_description": (
            "chronological train/test split; training observations precede test observations in time"
        ),
        "included_quality_flags": "all non-excluded flags retained for reporting",
        "excluded_prediction_quality_flags": list(config.excluded_prediction_quality_flags),
    }
    if extra:
        data.update(extra)
    return data


def _git_commit():
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True,
            check=False,
            text=True,
            timeout=2,
        )
    except Exception:
        return "N/A"
    return result.stdout.strip() or "N/A"
