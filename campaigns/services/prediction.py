from collections import defaultdict
from datetime import timedelta
from math import sqrt


HORIZONS = {
    "1h": timedelta(hours=1),
    "6h": timedelta(hours=6),
}


def evaluate_prediction_models(rows):
    results = {}
    rows_by_segment = defaultdict(list)
    for row in rows:
        rows_by_segment[row["segment_id"]].append(row)

    for label, horizon in HORIZONS.items():
        samples = []
        for segment_rows in rows_by_segment.values():
            samples.extend(_build_samples(segment_rows, horizon))
        results[label] = _evaluate_samples(samples)
    return results


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
                "features": [current, current - prior_1h, prior_1h - prior_2h],
                "current": current,
                "target": float(future["radon_bq_m3"]),
            }
        )
    return samples


def _evaluate_samples(samples):
    if not samples:
        return {
            "naive_baseline": _empty_metrics(),
            "ridge": _empty_metrics(),
        }

    targets = [sample["target"] for sample in samples]
    baseline_predictions = [sample["current"] for sample in samples]
    ridge_predictions = _ridge_predictions(samples)

    return {
        "naive_baseline": _metrics(targets, baseline_predictions),
        "ridge": _metrics(targets, ridge_predictions),
    }


def _ridge_predictions(samples, alpha=1.0):
    features = [sample["features"] for sample in samples]
    targets = [sample["target"] for sample in samples]
    coefficients = _fit_ridge(features, targets, alpha=alpha)
    return [_predict(coefficients, feature_row) for feature_row in features]


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
    }


def _empty_metrics():
    return {"samples": 0, "mae": None, "rmse": None}
