from collections import Counter
from datetime import timedelta
from decimal import Decimal


REGIME_STABLE_LOW = "stable_low"
REGIME_STABLE_ELEVATED = "stable_elevated"
REGIME_RISING = "rising"
REGIME_FALLING = "falling"
REGIME_SUDDEN_RISE = "sudden_rise"
REGIME_SUDDEN_DROP = "sudden_drop"
REGIME_HIGH_EPISODE = "high_episode"

LOW_THRESHOLD = Decimal("100")
HIGH_EPISODE_THRESHOLD = Decimal("300")
STABLE_CHANGE_THRESHOLD = Decimal("10")
TREND_CHANGE_THRESHOLD = Decimal("25")
SUDDEN_CHANGE_THRESHOLD = Decimal("100")


def classify_regimes(rows):
    classified = []
    rows_by_segment = {}
    for row in rows:
        rows_by_segment.setdefault(row["segment_id"], []).append(row)

    for segment_rows in rows_by_segment.values():
        ordered = sorted(segment_rows, key=lambda row: row["measured_at"])
        for row in ordered:
            updated = row.copy()
            updated["regime"] = classify_measurement(row, _one_hour_reference(row, ordered))
            classified.append(updated)
    return sorted(classified, key=lambda row: row["measured_at"])


def classify_measurement(row, reference_row=None):
    radon = row.get("radon_bq_m3")
    if radon is None:
        return REGIME_STABLE_LOW

    if radon >= HIGH_EPISODE_THRESHOLD:
        return REGIME_HIGH_EPISODE

    if reference_row and reference_row.get("radon_bq_m3") is not None:
        change = radon - reference_row["radon_bq_m3"]
        if change >= SUDDEN_CHANGE_THRESHOLD:
            return REGIME_SUDDEN_RISE
        if change <= -SUDDEN_CHANGE_THRESHOLD:
            return REGIME_SUDDEN_DROP
        if change >= TREND_CHANGE_THRESHOLD:
            return REGIME_RISING
        if change <= -TREND_CHANGE_THRESHOLD:
            return REGIME_FALLING

    if radon < LOW_THRESHOLD:
        return REGIME_STABLE_LOW
    return REGIME_STABLE_ELEVATED


def regime_counts(rows):
    counts = Counter(row.get("regime") for row in rows if row.get("regime"))
    return dict(sorted(counts.items()))


def _one_hour_reference(row, ordered_rows):
    target = row["measured_at"] - timedelta(hours=1)
    candidates = [
        candidate
        for candidate in ordered_rows
        if candidate["measured_at"] <= target and candidate["measured_at"] < row["measured_at"]
    ]
    if not candidates:
        return None
    return candidates[-1]
