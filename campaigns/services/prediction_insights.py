from collections import Counter


MIN_INTERPRETABLE_SAMPLES = 3


def build_prediction_insights(summary):
    metrics_by_regime = summary.get("prediction_metrics_by_regime") or []
    overall_metrics = summary.get("prediction_metrics") or {}
    prediction_errors = summary.get("prediction_errors") or []

    insights = []
    ridge_rows = [
        row
        for row in metrics_by_regime
        if row.get("model") == "ridge"
    ]
    interpretable_rows = [
        row
        for row in ridge_rows
        if _sample_count(row) >= MIN_INTERPRETABLE_SAMPLES
        and _number(row.get("mae_improvement_percent")) is not None
    ]

    improving_rows = [
        row for row in interpretable_rows if _number(row.get("mae_improvement_percent")) > 0
    ]
    if improving_rows:
        best = max(improving_rows, key=lambda row: _number(row.get("mae_improvement_percent")))
        insights.append(
            "In this campaign, the strongest Ridge improvement over the naive baseline is "
            f"seen for {_label(best.get('regime'))} at {_label(best.get('horizon'))} "
            f"({_format_percent(best.get('mae_improvement_percent'))} MAE improvement, "
            f"n={_label(best.get('samples'))})."
        )
    elif ridge_rows:
        insights.append(
            "In this campaign, Ridge does not show a clear MAE improvement over the naive "
            "baseline within the regime groups that have enough samples for interpretation."
        )
    else:
        insights.append(
            "Regime-level Ridge comparisons are not available for this campaign."
        )

    no_improvement_rows = [
        row for row in interpretable_rows if _number(row.get("mae_improvement_percent")) <= 0
    ]
    if no_improvement_rows:
        worst = min(no_improvement_rows, key=lambda row: _number(row.get("mae_improvement_percent")))
        insights.append(
            "Little or no Ridge improvement is visible for "
            f"{_label(worst.get('regime'))} at {_label(worst.get('horizon'))} "
            f"({_format_percent(worst.get('mae_improvement_percent'))} MAE improvement, "
            f"n={_label(worst.get('samples'))}); this should be read as descriptive, not causal."
        )

    small_sample_groups = [
        f"{_label(row.get('regime'))} / {_label(row.get('horizon'))}"
        for row in ridge_rows
        if _sample_count(row) < MIN_INTERPRETABLE_SAMPLES
    ]
    if small_sample_groups:
        insights.append(
            "Some regime and horizon groups have fewer than "
            f"{MIN_INTERPRETABLE_SAMPLES} samples, so their metrics are exploratory: "
            f"{_short_list(small_sample_groups)}."
        )

    horizon_insight = _horizon_insight(overall_metrics)
    if horizon_insight:
        insights.append(horizon_insight)

    error_insight = _error_concentration_insight(prediction_errors)
    if error_insight:
        insights.append(error_insight)

    return insights


def prediction_regime_badge(row):
    samples = _sample_count(row)
    improvement = _number(row.get("mae_improvement_percent"))
    if samples < MIN_INTERPRETABLE_SAMPLES:
        return {"label": "Small sample", "class": "badge-sample"}
    if row.get("model") == "naive_baseline" or improvement is None:
        return {"label": "N/A", "class": "badge-na"}
    if improvement > 0:
        return {"label": "Improves", "class": "badge-improves"}
    return {"label": "No improvement", "class": "badge-neutral"}


def _horizon_insight(overall_metrics):
    one_hour = _ridge_mae(overall_metrics.get("1h"))
    six_hour = _ridge_mae(overall_metrics.get("6h"))
    if one_hour is None or six_hour is None:
        return (
            "The available overall metrics are not sufficient to compare 1h and 6h "
            "prediction performance in this campaign."
        )
    if one_hour < six_hour:
        return (
            "In this campaign, the overall 1h Ridge MAE is lower than the 6h Ridge MAE, "
            "which is consistent with shorter-horizon forecasts being easier to estimate."
        )
    if six_hour < one_hour:
        return (
            "In this campaign, the overall 6h Ridge MAE is lower than the 1h Ridge MAE; "
            "this may reflect the specific data available rather than a general rule."
        )
    return "In this campaign, the overall 1h and 6h Ridge MAE values are similar."


def _error_concentration_insight(prediction_errors):
    if not prediction_errors:
        return "Largest-error rows are not available for this campaign."
    top_errors = prediction_errors[:20]
    regimes = [_label(row.get("regime")) for row in top_errors if _label(row.get("regime")) != "N/A"]
    if not regimes:
        return "Largest-error rows do not include usable regime labels in this campaign."
    regime, count = Counter(regimes).most_common(1)[0]
    share = count / len(top_errors)
    if count >= 3 and share >= 0.5:
        return (
            "Among the largest absolute prediction errors in this campaign, "
            f"{regime} appears most often ({count} of {len(top_errors)} rows)."
        )
    return (
        "The largest absolute prediction errors in this campaign are not strongly "
        "concentrated in a single regime label."
    )


def _ridge_mae(model_results):
    if not model_results:
        return None
    return _number(model_results.get("ridge", {}).get("mae"))


def _number(value):
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _sample_count(row):
    return _number(row.get("samples")) or 0


def _label(value):
    if value is None or value == "":
        return "N/A"
    return value


def _format_percent(value):
    number = _number(value)
    if number is None:
        return "N/A"
    return f"{number:g}%"


def _short_list(values, limit=4):
    unique_values = []
    for value in values:
        if value not in unique_values:
            unique_values.append(value)
    if len(unique_values) <= limit:
        return ", ".join(unique_values)
    visible = ", ".join(unique_values[:limit])
    return f"{visible}, and {len(unique_values) - limit} more"
