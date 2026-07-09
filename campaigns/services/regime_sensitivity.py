from collections import Counter
from decimal import Decimal


def build_regime_sensitivity(rows, config):
    baseline = [_threshold_label(row, 1.0, config) for row in rows]
    results = []
    for multiplier in config.sensitivity_multipliers:
        labels = [_threshold_label(row, multiplier, config) for row in rows]
        agreement = _agreement(baseline, labels)
        results.append(
            {
                "threshold_multiplier": multiplier,
                "regime_counts": dict(sorted(Counter(labels).items())),
                "regime_durations": dict(sorted(Counter(labels).items())),
                "percentage_agreement_with_baseline": agreement,
                "transitions_count": _transition_count(labels),
                "most_sensitive_regimes": _sensitive_regimes(baseline, labels),
                "adjusted_rand_index": None,
            }
        )
    return results


def _threshold_label(row, multiplier, config):
    value = row.get("radon_bq_m3")
    if value is None:
        return "unclassified"
    value = Decimal(str(value))
    thresholds = config.regime_thresholds
    high = Decimal(str(thresholds["high_radon_bq_m3"] * multiplier))
    elevated = Decimal(str(thresholds["low_radon_bq_m3"] * multiplier))
    if value >= high:
        return "high_episode"
    if value >= elevated:
        return "stable_elevated"
    return "stable_low"


def _agreement(baseline, labels):
    if not baseline:
        return None
    matches = sum(1 for left, right in zip(baseline, labels) if left == right)
    return round((matches / len(baseline)) * 100, 2)


def _transition_count(labels):
    return sum(1 for previous, current in zip(labels, labels[1:]) if previous != current)


def _sensitive_regimes(baseline, labels):
    changed = Counter(
        baseline_label
        for baseline_label, label in zip(baseline, labels)
        if baseline_label != label
    )
    return [label for label, _count in changed.most_common(3)]
