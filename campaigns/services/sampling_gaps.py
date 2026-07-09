from collections import Counter


def detect_sampling_gaps(rows, config):
    ordered = sorted([row for row in rows if row.get("measured_at")], key=lambda row: row["measured_at"])
    if len(ordered) < 2:
        return []
    intervals = _intervals(ordered)
    nominal = _nominal_interval(intervals)
    common_intervals = _common_intervals(intervals)
    gaps = []
    for previous, current, minutes in intervals:
        if minutes in common_intervals:
            continue
        expected = _expected_interval(minutes, nominal, common_intervals)
        threshold = expected * config.gap_tolerance_multiplier
        if minutes > threshold:
            gaps.append(
                {
                    "from": previous["measured_at"],
                    "to": current["measured_at"],
                    "minutes": round(minutes, 2),
                    "expected_interval_minutes": round(expected, 2),
                    "threshold_minutes": round(threshold, 2),
                    "gap_class": "GAP_LONG" if minutes >= config.short_gap_minutes else "GAP_SHORT",
                    "reason": "sampling-aware interval exceeds configured tolerance",
                }
            )
    return gaps


def build_sampling_diagnostics(rows, gaps, config):
    ordered = sorted([row for row in rows if row.get("measured_at")], key=lambda row: row["measured_at"])
    intervals = _intervals(ordered)
    distribution = Counter(round(minutes, 2) for _previous, _current, minutes in intervals)
    nominal = _nominal_interval(intervals)
    return {
        "expected_interval_minutes": round(nominal, 2) if nominal else None,
        "gap_tolerance_multiplier": config.gap_tolerance_multiplier,
        "interval_distribution": {str(key): value for key, value in sorted(distribution.items())},
        "observed_interval_count": len(intervals),
        "irregular_interval_count": sum(
            count for minutes, count in distribution.items()
            if nominal and abs(minutes - nominal) > max(1.0, nominal * 0.1)
        ),
        "gap_count": len(gaps),
        "short_gap_count": sum(1 for gap in gaps if gap.get("gap_class") == "GAP_SHORT"),
        "long_gap_count": sum(1 for gap in gaps if gap.get("gap_class") == "GAP_LONG"),
        "gaps": [_serialize_gap(gap) for gap in gaps],
    }


def _intervals(ordered):
    return [
        (previous, current, (current["measured_at"] - previous["measured_at"]).total_seconds() / 60)
        for previous, current in zip(ordered, ordered[1:])
        if current["measured_at"] > previous["measured_at"]
    ]


def _nominal_interval(intervals):
    if not intervals:
        return None
    counts = Counter(round(minutes, 2) for _previous, _current, minutes in intervals)
    max_count = max(counts.values())
    candidates = [minutes for minutes, count in counts.items() if count == max_count]
    return min(candidates)


def _common_intervals(intervals):
    counts = Counter(round(minutes, 2) for _previous, _current, minutes in intervals)
    return {minutes for minutes, count in counts.items() if count >= 2}


def _expected_interval(minutes, nominal, common_intervals):
    if common_intervals:
        lower = [interval for interval in common_intervals if interval < minutes]
        if lower:
            return max(lower)
    return nominal or minutes


def _serialize_gap(gap):
    return {
        "from": gap["from"].isoformat(),
        "to": gap["to"].isoformat(),
        "minutes": gap["minutes"],
        "expected_interval_minutes": gap.get("expected_interval_minutes"),
        "threshold_minutes": gap.get("threshold_minutes"),
        "gap_class": gap.get("gap_class"),
        "reason": gap.get("reason"),
    }
