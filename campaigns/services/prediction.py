from collections import defaultdict
from datetime import timedelta
from math import sqrt


HORIZONS = {
    "1h": timedelta(hours=1),
    "6h": timedelta(hours=6),
}


def evaluate_prediction_models(rows):
    results = {}
    by_regime = []
    errors = []
    rows_by_segment = defaultdict(list)
    for row in rows:
        rows_by_segment[row["segment_id"]].append(row)

    for label, horizon in HORIZONS.items():
        samples = []
        for segment_rows in rows_by_segment.values():
            samples.extend(_build_samples(segment_rows, horizon))
        results[label] = _evaluate_samples(samples)
        evaluation_samples, model_predictions = _model_predictions(samples)
        by_regime.extend(_evaluate_samples_by_regime(label, evaluation_samples, model_predictions))
        errors.extend(_prediction_errors(label, evaluation_samples, model_predictions))
    return {
        "overall": results,
        "by_regime": by_regime,
        "errors": sorted(errors, key=lambda row: (-row["absolute_error"], row["timestamp"], row["model"]))[:20],
    }


def _build_samples(rows, horizon):
    ordered = sorted(
        [row for row in rows if row.get("radon_bq_m3") is not None],
        key=lambda row: row["measured_at"],
    )
    by_time = {row["measured_at"]: row for row in ordered}
    samples = []
    for row in ordered:
        future = by_time.get(row["measured_at"] + horizon)
        previous_1h = by_time.get(row["measured_at"] - timedelta(hours=1))
        previous_2h = by_time.get(row["measured_at"] - timedelta(hours=2))
        if not future or not previous_1h or not previous_2h:
            continue
        current = float(row["radon_bq_m3"])
        prior_1h = float(previous_1h["radon_bq_m3"])
        prior_2h = float(previous_2h["radon_bq_m3"])
        samples.append(
            {
                "timestamp": row["measured_at"],
                "regime": row.get("regime") or "unclassified",
                "segment_id": row.get("segment_id"),
                "features": [current, current - prior_1h, prior_1h - prior_2h],
                "current": current,
                "prior_1h": prior_1h,
                "prior_2h": prior_2h,
                "target": float(future["radon_bq_m3"]),
            }
        )
    return samples


def _evaluate_samples(samples):
    if not samples:
        return {
            "naive_baseline": _empty_metrics(),
            "rolling_mean_baseline": _empty_metrics(),
            "ridge": _empty_metrics(),
        }

    evaluation_samples, model_predictions = _model_predictions(samples)
    return {
        model_name: _metrics([sample["target"] for sample in evaluation_samples], predictions)
        for model_name, predictions in model_predictions.items()
    }


def _model_predictions(samples):
    if not samples:
        return [], {"naive_baseline": [], "rolling_mean_baseline": [], "ridge": []}
    training_samples, evaluation_samples = _chronological_split(samples)
    return evaluation_samples, {
        "naive_baseline": [sample["current"] for sample in evaluation_samples],
        "rolling_mean_baseline": [
            round((sample["current"] + sample["prior_1h"] + sample["prior_2h"]) / 3, 3)
            for sample in evaluation_samples
        ],
        "ridge": _ridge_predictions(training_samples, evaluation_samples),
    }


def _evaluate_samples_by_regime(horizon, evaluation_samples, model_predictions):
    rows = []
    baseline_by_regime = _metrics_by_regime(evaluation_samples, model_predictions["naive_baseline"])
    for model_name, predictions in model_predictions.items():
        for regime, metrics in _metrics_by_regime(evaluation_samples, predictions).items():
            baseline_metrics = baseline_by_regime.get(regime, _empty_metrics())
            rows.append(
                {
                    "horizon": horizon,
                    "model": model_name,
                    "regime": regime,
                    "samples": metrics["samples"],
                    "mae": metrics["mae"],
                    "rmse": metrics["rmse"],
                    "mae_improvement_percent": _improvement(baseline_metrics["mae"], metrics["mae"]),
                    "rmse_improvement_percent": _improvement(baseline_metrics["rmse"], metrics["rmse"]),
                    "skill_score_vs_persistence": _skill_score(baseline_metrics["mae"], metrics["mae"]),
                    "small_sample_warning": metrics["samples"] < 3,
                }
            )
    return rows


def _metrics_by_regime(samples, predictions):
    grouped = defaultdict(lambda: {"targets": [], "predictions": []})
    for sample, prediction in zip(samples, predictions):
        regime = sample.get("regime") or "unclassified"
        grouped[regime]["targets"].append(sample["target"])
        grouped[regime]["predictions"].append(prediction)
    return {
        regime: _metrics(values["targets"], values["predictions"])
        for regime, values in sorted(grouped.items())
    }


def _prediction_errors(horizon, evaluation_samples, model_predictions):
    rows = []
    for model_name, predictions in model_predictions.items():
        for sample, prediction in zip(evaluation_samples, predictions):
            rows.append(
                {
                    "timestamp": sample["timestamp"].isoformat(),
                    "horizon": horizon,
                    "model": model_name,
                    "actual_radon": round(sample["target"], 3),
                    "predicted_radon": round(prediction, 3),
                    "absolute_error": round(abs(sample["target"] - prediction), 3),
                    "regime": sample.get("regime") or "unclassified",
                    "segment_id": sample.get("segment_id"),
                }
            )
    return rows


def _ridge_predictions(training_samples, evaluation_samples, alpha=1.0):
    if len(training_samples) < 3:
        return [sample["current"] for sample in evaluation_samples]
    features = [sample["features"] for sample in training_samples]
    targets = [sample["target"] for sample in training_samples]
    coefficients = _fit_ridge(features, targets, alpha=alpha)
    return [_predict(coefficients, sample["features"]) for sample in evaluation_samples]


def _chronological_split(samples):
    ordered = sorted(samples, key=lambda sample: sample["timestamp"])
    if len(ordered) < 8:
        return ordered, ordered
    split_index = max(3, int(len(ordered) * 0.7))
    if split_index >= len(ordered):
        split_index = len(ordered) - 1
    return ordered[:split_index], ordered[split_index:]


def _fit_ridge(features, targets, alpha):
    design = [[1.0, *feature_row] for feature_row in features]
    column_count = len(design[0])
    xtx = [[0.0 for _ in range(column_count)] for _ in range(column_count)]
    xty = [0.0 for _ in range(column_count)]

    for row, target in zip(design, targets):
        for i in range(column_count):
            xty[i] += row[i] * target
            for j in range(column_count):
                xtx[i][j] += row[i] * row[j]

    for index in range(1, column_count):
        xtx[index][index] += alpha

    return _solve_linear_system(xtx, xty)


def _solve_linear_system(matrix, vector):
    size = len(vector)
    augmented = [matrix[row][:] + [vector[row]] for row in range(size)]

    for pivot_index in range(size):
        pivot_row = max(range(pivot_index, size), key=lambda row: abs(augmented[row][pivot_index]))
        augmented[pivot_index], augmented[pivot_row] = augmented[pivot_row], augmented[pivot_index]
        pivot = augmented[pivot_index][pivot_index]
        if abs(pivot) < 1e-12:
            augmented[pivot_index][pivot_index] = 1e-12
            pivot = augmented[pivot_index][pivot_index]

        for column in range(pivot_index, size + 1):
            augmented[pivot_index][column] /= pivot

        for row in range(size):
            if row == pivot_index:
                continue
            factor = augmented[row][pivot_index]
            for column in range(pivot_index, size + 1):
                augmented[row][column] -= factor * augmented[pivot_index][column]

    return [augmented[row][-1] for row in range(size)]


def _predict(coefficients, feature_row):
    return coefficients[0] + sum(
        coefficient * value
        for coefficient, value in zip(coefficients[1:], feature_row)
    )


def _metrics(targets, predictions):
    errors = [target - prediction for target, prediction in zip(targets, predictions)]
    absolute_errors = [abs(error) for error in errors]
    squared_errors = [error * error for error in errors]
    return {
        "samples": len(targets),
        "mae": round(sum(absolute_errors) / len(absolute_errors), 3),
        "rmse": round(sqrt(sum(squared_errors) / len(squared_errors)), 3),
        "bias": round(sum(errors) / len(errors), 3),
    }


def _empty_metrics():
    return {"samples": 0, "mae": None, "rmse": None, "bias": None}


def _improvement(baseline_value, model_value):
    if baseline_value in (None, "", 0) or model_value in (None, ""):
        return None
    baseline = float(baseline_value)
    if baseline == 0:
        return None
    return round(((baseline - float(model_value)) / baseline) * 100, 2)


def _skill_score(baseline_value, model_value):
    improvement = _improvement(baseline_value, model_value)
    if improvement is None:
        return None
    return round(improvement / 100, 3)
