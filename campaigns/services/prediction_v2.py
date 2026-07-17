from collections import defaultdict
from statistics import median

from campaigns.services.prediction import evaluate_prediction_models


def evaluate_prediction_v2(rows, config):
    base = evaluate_prediction_models(rows)
    examples = _prediction_examples(rows)
    residuals_by_model = defaultdict(list)
    for row in base.get("errors", []):
        residuals_by_model[row["model"]].append(row["absolute_error"])
    intervals = _prediction_intervals(base.get("errors", []), residuals_by_model, coverages=(0.8, 0.9, 0.95))
    return {
        "prediction_summary_v2": _summary(base),
        "prediction_by_concentration_level": _group_metrics(examples, "concentration_level"),
        "prediction_by_dynamic_state": _group_metrics(examples, "dynamic_state"),
        "prediction_by_episode": [],
        "prediction_intervals": intervals,
        "largest_errors_v2": base.get("errors", []),
        "validation_policy": "chronological train/test split with training observations preceding test observations; prediction examples do not cross segment gaps",
    }


def _summary(base):
    rows = []
    for horizon, model_results in base.get("overall", {}).items():
        for model, metrics in model_results.items():
            rows.append(
                {
                    "horizon": horizon,
                    "model": model,
                    "samples": metrics.get("samples"),
                    "mae": metrics.get("mae"),
                    "rmse": metrics.get("rmse"),
                    "bias": metrics.get("bias"),
                    "median_absolute_error": None,
                }
            )
    return rows


def _prediction_examples(rows):
    # Lightweight grouping support: one-step examples by exact 1h timestamps inside segments.
    examples = []
    by_segment = defaultdict(list)
    for row in rows:
        by_segment[row["segment_id"]].append(row)
    for segment_rows in by_segment.values():
        ordered = sorted(segment_rows, key=lambda row: row["measured_at"])
        by_time = {row["measured_at"]: row for row in ordered}
        for row in ordered:
            future = by_time.get(row["measured_at"])
            if not future or row.get("radon_bq_m3") is None:
                continue
            examples.append(row)
    return examples


def _group_metrics(rows, field):
    counts = defaultdict(int)
    for row in rows:
        counts[row.get(field) or "UNKNOWN"] += 1
    return [
        {
            "group": group,
            "test_example_count": count,
            "minimum_sample_warning": count < 10,
            "note": "Group sample count for prediction diagnostics; metric reliability warning is shown when sample count is small.",
        }
        for group, count in sorted(counts.items())
    ]


def _prediction_intervals(errors, residuals_by_model, coverages):
    rows = []
    for model, residuals in sorted(residuals_by_model.items()):
        if not residuals:
            continue
        sorted_residuals = sorted(residuals)
        for coverage in coverages:
            radius = _quantile(sorted_residuals, coverage)
            covered = sum(1 for error in errors if error["model"] == model and error["absolute_error"] <= radius)
            total = sum(1 for error in errors if error["model"] == model)
            rows.append(
                {
                    "model": model,
                    "nominal_coverage": coverage,
                    "empirical_coverage": round(covered / total, 3) if total else None,
                    "average_interval_width": round(radius * 2, 3),
                    "residual_count": total,
                    "method": "empirical residual interval from validation residuals",
                    "note": "Exploratory empirical interval; not a formal uncertainty guarantee.",
                }
            )
    return rows


def _quantile(values, probability):
    if not values:
        return None
    index = min(round((len(values) - 1) * probability), len(values) - 1)
    return values[index]
