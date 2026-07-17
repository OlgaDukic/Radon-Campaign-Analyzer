from collections import Counter
from statistics import median


REGULAR_INTERVAL = "REGULAR_INTERVAL"
MINOR_INTERVAL_DEVIATION = "MINOR_INTERVAL_DEVIATION"
SHORT_GAP = "SHORT_GAP"
MODERATE_GAP = "MODERATE_GAP"
LONG_GAP = "LONG_GAP"
DUPLICATED_TIMESTAMP = "DUPLICATED_TIMESTAMP"
OUT_OF_ORDER_TIMESTAMP = "OUT_OF_ORDER_TIMESTAMP"


def analyze_time_continuity(rows, config):
    original_positions = {id(row): index for index, row in enumerate(rows)}
    ordered = sorted(rows, key=lambda row: (row["measured_at"], original_positions[id(row)]))
    expected = config.expected_sampling_interval_minutes or _infer_expected_interval(ordered)
    intervals = []
    gaps = []
    segmented = []
    current_segment = 1
    previous = None
    seen = set()
    out_of_order_count = _out_of_order_count(rows)

    for row in ordered:
        updated = row.copy()
        timestamp = row["measured_at"]
        flags = set(updated.get("quality_flags", []))
        boundary_reason = "campaign_start" if previous is None else ""

        if timestamp in seen:
            interval_class = DUPLICATED_TIMESTAMP
            flags.add("DUPLICATE_EXACT")
            boundary = False
            observed_minutes = 0.0
        elif previous is not None:
            observed_minutes = round((timestamp - previous["measured_at"]).total_seconds() / 60, 3)
            interval_class = classify_interval(observed_minutes, expected, config)
            boundary = interval_class in {SHORT_GAP, MODERATE_GAP, LONG_GAP}
            if boundary:
                current_segment += 1
                boundary_reason = interval_class
                flags.add(interval_class)
                gaps.append(
                    {
                        "from": previous["measured_at"],
                        "to": timestamp,
                        "minutes": round(observed_minutes, 2),
                        "expected_interval_minutes": expected,
                        "threshold_minutes": round(expected * config.gap_tolerance_multiplier, 2),
                        "gap_class": interval_class,
                        "reason": "time-continuity analysis segment boundary",
                    }
                )
            elif interval_class == MINOR_INTERVAL_DEVIATION:
                flags.add("IRREGULAR_INTERVAL")
            intervals.append(
                {
                    "from": previous["measured_at"].isoformat(),
                    "to": timestamp.isoformat(),
                    "observed_interval_minutes": observed_minutes,
                    "expected_interval_minutes": expected,
                    "interval_class": interval_class,
                    "creates_segment_boundary": boundary,
                    "segment_boundary_reason": boundary_reason,
                }
            )
        else:
            observed_minutes = None
            interval_class = REGULAR_INTERVAL

        updated["segment_id"] = current_segment
        updated["segment_boundary_reason"] = boundary_reason
        updated["previous_interval_minutes"] = observed_minutes
        updated["previous_interval_class"] = interval_class
        updated["quality_flags"] = sorted(flags)
        segmented.append(updated)
        seen.add(timestamp)
        previous = updated

    return {
        "rows": segmented,
        "intervals": intervals,
        "gaps": gaps,
        "summary": {
            "expected_sampling_interval_minutes": expected,
            "interval_count": len(intervals),
            "interval_class_counts": dict(sorted(Counter(item["interval_class"] for item in intervals).items())),
            "gap_count": len(gaps),
            "segment_count": len({row["segment_id"] for row in segmented}),
            "out_of_order_timestamp_count": out_of_order_count,
            "duplicated_timestamp_count": sum(1 for row in segmented if row["previous_interval_class"] == DUPLICATED_TIMESTAMP),
            "algorithm": "time_continuity_v2",
        },
    }


def classify_interval(observed_minutes, expected_minutes, config):
    if observed_minutes == 0:
        return DUPLICATED_TIMESTAMP
    if observed_minutes <= expected_minutes * config.minor_interval_tolerance:
        return REGULAR_INTERVAL
    if observed_minutes <= expected_minutes * config.gap_tolerance_multiplier:
        return MINOR_INTERVAL_DEVIATION
    if observed_minutes <= expected_minutes * config.short_gap_multiplier:
        return SHORT_GAP
    if observed_minutes <= expected_minutes * config.moderate_gap_multiplier:
        return MODERATE_GAP
    return LONG_GAP


def _infer_expected_interval(rows):
    intervals = [
        (current["measured_at"] - previous["measured_at"]).total_seconds() / 60
        for previous, current in zip(rows, rows[1:])
        if current["measured_at"] > previous["measured_at"]
    ]
    if not intervals:
        return 60.0
    counts = Counter(round(value, 3) for value in intervals)
    most_common_count = counts.most_common(1)[0][1]
    candidates = [value for value, count in counts.items() if count == most_common_count]
    return round(min(candidates) if candidates else median(intervals), 3)


def _out_of_order_count(rows):
    count = 0
    previous = None
    for row in rows:
        timestamp = row.get("measured_at")
        if previous and timestamp and timestamp < previous:
            count += 1
        if timestamp:
            previous = timestamp
    return count
