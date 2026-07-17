from collections import Counter
from statistics import median


def build_segment_v2_summaries(rows, episodes, gaps, config):
    summaries = []
    episodes_by_segment = {}
    for episode in episodes:
        episodes_by_segment.setdefault(episode["segment_id"], []).append(episode)
    for segment_id, segment_rows in _rows_by_segment(rows).items():
        ordered = sorted(segment_rows, key=lambda row: row["measured_at"])
        values = [float(row["radon_bq_m3"]) for row in ordered if row.get("radon_bq_m3") is not None]
        duration_hours = (ordered[-1]["measured_at"] - ordered[0]["measured_at"]).total_seconds() / 3600 if len(ordered) > 1 else 0
        segment_episodes = episodes_by_segment.get(segment_id, [])
        summaries.append(
            {
                "segment_id": segment_id,
                "start": ordered[0]["measured_at"].isoformat(),
                "end": ordered[-1]["measured_at"].isoformat(),
                "duration_hours": round(duration_hours, 3),
                "observation_count": len(ordered),
                "mean_radon": round(sum(values) / len(values), 3) if values else None,
                "median_radon": round(median(values), 3) if values else None,
                "min_radon": min(values) if values else None,
                "max_radon": max(values) if values else None,
                "concentration_level_proportions": _proportions(row.get("concentration_level") for row in ordered),
                "dynamic_state_proportions": _proportions(row.get("dynamic_state") for row in ordered),
                "episode_counts_by_type": dict(sorted(Counter(ep["episode_type"] for ep in segment_episodes).items())),
                "longest_elevated_episode_hours": _longest_episode(segment_episodes, {"stable elevated", "stable high", "STABLE_ELEVATED", "STABLE_HIGH"}),
                "longest_rising_episode_hours": _longest_episode(segment_episodes, {"accumulation", "sudden rise", "ACCUMULATION", "SUDDEN_RISE_EVENT"}),
                "longest_falling_episode_hours": _longest_episode(segment_episodes, {"controlled or natural decline", "sudden drop", "DECLINE", "SUDDEN_DROP_EVENT"}),
                "time_above_low_threshold_hours": _time_above(ordered, config.concentration_low_threshold_bq_m3),
                "time_above_high_threshold_hours": _time_above(ordered, config.concentration_high_threshold_bq_m3),
                "maximum_rise_rate": _max_slope(ordered),
                "maximum_fall_rate": _min_slope(ordered),
                "segment_quality_score": _quality_score(ordered, gaps),
                "gaps_before_or_after_segment": _nearby_gap_count(ordered, gaps),
            }
        )
    return summaries


def _rows_by_segment(rows):
    grouped = {}
    for row in rows:
        grouped.setdefault(row["segment_id"], []).append(row)
    return grouped


def _proportions(values):
    clean = [value for value in values if value]
    total = len(clean)
    if not total:
        return {}
    return {key: round((count / total) * 100, 2) for key, count in sorted(Counter(clean).items())}


def _longest_episode(episodes, episode_types):
    matches = [episode["duration_hours"] for episode in episodes if episode["episode_type"] in episode_types]
    return max(matches) if matches else 0


def _time_above(rows, threshold):
    count = sum(1 for row in rows if row.get("radon_bq_m3") is not None and float(row["radon_bq_m3"]) >= threshold)
    if len(rows) < 2:
        return 0
    expected_hours = _median_interval_hours(rows)
    return round(count * expected_hours, 3)


def _median_interval_hours(rows):
    intervals = [
        (current["measured_at"] - previous["measured_at"]).total_seconds() / 3600
        for previous, current in zip(rows, rows[1:])
        if current["measured_at"] > previous["measured_at"]
    ]
    return median(intervals) if intervals else 0


def _max_slope(rows):
    slopes = [row.get("slope_bq_m3_per_hour") for row in rows if row.get("slope_bq_m3_per_hour") is not None]
    return max(slopes) if slopes else None


def _min_slope(rows):
    slopes = [row.get("slope_bq_m3_per_hour") for row in rows if row.get("slope_bq_m3_per_hour") is not None]
    return min(slopes) if slopes else None


def _quality_score(rows, gaps):
    score = 1.0
    if any(row.get("dynamic_state") == "QUALITY_AFFECTED" for row in rows):
        score -= 0.25
    if _nearby_gap_count(rows, gaps):
        score -= 0.15
    low_confidence = sum(1 for row in rows if row.get("regime_confidence_label") == "LOW")
    if rows:
        score -= min(0.3, low_confidence / len(rows))
    return round(max(score, 0), 3)


def _nearby_gap_count(rows, gaps):
    if not rows:
        return 0
    start = rows[0]["measured_at"]
    end = rows[-1]["measured_at"]
    return sum(
        1 for gap in gaps
        if abs((gap["to"] - start).total_seconds()) <= 3600 or abs((gap["from"] - end).total_seconds()) <= 3600
    )
