from collections import Counter
from statistics import median

from campaigns.services.regime_v2 import REGIME_V2_VERSION


EPISODE_VERSION = "episode_analysis_v2.2"


def build_episodes(rows, gaps, config, campaign_id=None, analysis_report_id=None):
    episodes = []
    for segment_id, segment_rows in _rows_by_segment(rows).items():
        ordered = sorted(segment_rows, key=lambda row: row["measured_at"])
        start_index = 0
        sequence = 1
        while start_index < len(ordered):
            episode_type = _episode_type(ordered[start_index])
            end_index = start_index + 1
            while end_index < len(ordered) and _episode_type(ordered[end_index]) == episode_type:
                end_index += 1
            episode_rows = ordered[start_index:end_index]
            episode_type = _validated_episode_type(episode_type, episode_rows, config)
            episodes.append(
                _episode_summary(
                    campaign_id,
                    analysis_report_id,
                    segment_id,
                    sequence,
                    episode_type,
                    episode_rows,
                    gaps,
                    config,
                )
            )
            sequence += 1
            start_index = end_index
    return _merge_short_transition_episodes(episodes, config)


def episode_type_counts(episodes):
    return dict(sorted(Counter(episode["episode_type"] for episode in episodes).items()))


def important_episodes(episodes, limit=20):
    ranked = sorted(
        episodes,
        key=lambda episode: (
            episode.get("max_radon") or 0,
            abs(episode.get("absolute_concentration_change") or 0),
            abs(episode.get("robust_episode_slope_bq_m3_per_hour") or 0),
            episode.get("duration_hours") or 0,
        ),
        reverse=True,
    )
    keys = [
        "start",
        "end",
        "episode_type",
        "starting_radon",
        "ending_radon",
        "max_radon",
        "duration_hours",
        "robust_episode_slope_bq_m3_per_hour",
        "confidence_score",
        "confidence_category",
        "confidence_reason_codes",
        "distance_from_previous_gap_hours",
        "distance_to_next_gap_hours",
    ]
    return [{key: episode.get(key) for key in keys} for episode in ranked[:limit]]


def _merge_short_transition_episodes(episodes, config):
    if len(episodes) < 3:
        return episodes
    merged = []
    index = 0
    merge_sequence = 1
    while index < len(episodes):
        previous = merged[-1] if merged else None
        current = episodes[index]
        following = episodes[index + 1] if index + 1 < len(episodes) else None
        if _can_merge_transition(previous, current, following, config):
            previous["end"] = following["end"]
            previous["duration_hours"] = round((previous.get("duration_hours") or 0) + (current.get("duration_hours") or 0) + (following.get("duration_hours") or 0), 3)
            previous["measurement_count"] = (previous.get("measurement_count") or 0) + (current.get("measurement_count") or 0) + (following.get("measurement_count") or 0)
            previous["ending_radon"] = following.get("ending_radon")
            previous["max_radon"] = max(value for value in [previous.get("max_radon"), current.get("max_radon"), following.get("max_radon")] if value is not None)
            previous["min_radon"] = min(value for value in [previous.get("min_radon"), current.get("min_radon"), following.get("min_radon")] if value is not None)
            previous.setdefault("transition_merge_audit", []).append(
                {
                    "merge_id": merge_sequence,
                    "original_episode_ids": [
                        previous.get("episode_sequence_number"),
                        current.get("episode_sequence_number"),
                        following.get("episode_sequence_number"),
                    ],
                    "merge_decision": "MERGED_SHORT_TRANSITION",
                    "merge_reason": "short transition bridged two compatible episode types without a sudden or quality boundary",
                    "resulting_episode_id": previous.get("episode_sequence_number"),
                }
            )
            merge_sequence += 1
            index += 2
        else:
            merged.append(current)
            index += 1
    return merged


def _can_merge_transition(previous, current, following, config):
    if not previous or not following:
        return False
    if current.get("episode_type") != "UNSTABLE_TRANSITION":
        return False
    if previous.get("segment_id") != current.get("segment_id") or current.get("segment_id") != following.get("segment_id"):
        return False
    if previous.get("episode_type") != following.get("episode_type"):
        return False
    if previous.get("episode_type") in {"SUDDEN_RISE_EVENT", "SUDDEN_DROP_EVENT", "QUALITY_AFFECTED"}:
        return False
    threshold_hours = (config.isolated_state_merge_minutes or 60) / 60
    return (current.get("duration_hours") or 0) <= threshold_hours


def _episode_summary(campaign_id, analysis_report_id, segment_id, sequence, episode_type, rows, gaps, config):
    values = [_float(row["radon_bq_m3"]) for row in rows if row.get("radon_bq_m3") is not None]
    adjacent_slopes = [row.get("adjacent_slope_bq_m3_per_hour") for row in rows if row.get("adjacent_slope_bq_m3_per_hour") is not None]
    short_slopes = [row.get("short_slope_bq_m3_per_hour") for row in rows if row.get("short_slope_bq_m3_per_hour") is not None]
    start = rows[0]["measured_at"]
    end = rows[-1]["measured_at"]
    previous_gap = _previous_gap(start, gaps)
    next_gap = _next_gap(end, gaps)
    confidence_scores = [row.get("regime_confidence_score") for row in rows if row.get("regime_confidence_score") is not None]
    reason_codes = sorted({reason for row in rows for reason in (row.get("regime_confidence_reasons") or []) + (row.get("dynamic_reason_codes") or [])})
    reason_summary = _reason_summary(rows)
    absolute_change = round(values[-1] - values[0], 3) if len(values) >= 2 else 0
    relative_change = round((absolute_change / values[0]) * 100, 3) if values and values[0] not in (0, None) else None
    return {
        "campaign_id": campaign_id,
        "analysis_report_id": analysis_report_id,
        "segment_id": segment_id,
        "episode_sequence_number": sequence,
        "episode_type": episode_type,
        "start": start.isoformat(),
        "end": end.isoformat(),
        "duration_hours": round((end - start).total_seconds() / 3600, 3),
        "measurement_count": len(rows),
        "starting_radon": values[0] if values else None,
        "ending_radon": values[-1] if values else None,
        "min_radon": min(values) if values else None,
        "max_radon": max(values) if values else None,
        "mean_radon": round(sum(values) / len(values), 3) if values else None,
        "median_radon": round(median(values), 3) if values else None,
        "absolute_concentration_change": absolute_change,
        "relative_concentration_change_percent": relative_change,
        "mean_adjacent_slope_bq_m3_per_hour": round(sum(adjacent_slopes) / len(adjacent_slopes), 3) if adjacent_slopes else None,
        "robust_episode_slope_bq_m3_per_hour": _episode_slope(rows),
        "maximum_positive_slope": max(adjacent_slopes) if adjacent_slopes else None,
        "maximum_negative_slope": min(adjacent_slopes) if adjacent_slopes else None,
        "local_variability": round(sum(row.get("local_variability_mad") or 0 for row in rows) / len(rows), 3) if rows else None,
        "concentration_level_distribution": _distribution(row.get("concentration_level") for row in rows),
        "dynamic_state_distribution": _distribution(row.get("confirmed_dynamic_state") or row.get("dynamic_state") for row in rows),
        "distance_from_previous_gap_hours": _gap_distance(previous_gap, start, "previous"),
        "distance_to_next_gap_hours": _gap_distance(next_gap, end, "next"),
        "nearby_gap_count": int(previous_gap is not None) + int(next_gap is not None),
        "quality_status": _quality_status(rows, config),
        "confidence_score": round(sum(confidence_scores) / len(confidence_scores), 3) if confidence_scores else None,
        "confidence_category": _confidence_label(confidence_scores),
        "confidence_reason_codes": reason_codes or ["NO_MAJOR_LIMITATION"],
        "dominant_reason_codes": _dominant_reasons(reason_summary),
        "reason_code_summary": reason_summary,
        "positive_confidence_components": _component_summary(reason_summary, positive=True),
        "negative_confidence_components": _component_summary(reason_summary, positive=False),
        "start_transition_reasons": (rows[0].get("dynamic_reason_codes") or []) + (rows[0].get("regime_confidence_reasons") or []),
        "end_transition_reasons": (rows[-1].get("dynamic_reason_codes") or []) + (rows[-1].get("regime_confidence_reasons") or []),
        "regime_algorithm_version": REGIME_V2_VERSION,
        "episode_algorithm_version": EPISODE_VERSION,
        "parameter_set_identifier": _parameter_set_identifier(config),
        "legacy_episode_label": _legacy_episode_label(episode_type),
        "mean_slope_bq_m3_per_hour": round(sum(short_slopes) / len(short_slopes), 3) if short_slopes else None,
        "regime_confidence_score": round(sum(confidence_scores) / len(confidence_scores), 3) if confidence_scores else None,
        "regime_confidence_label": _confidence_label(confidence_scores),
        "algorithm_version": EPISODE_VERSION,
    }


def _episode_type(row):
    state = row.get("confirmed_dynamic_state") or row.get("dynamic_state")
    level = row.get("concentration_level")
    if state == "QUALITY_AFFECTED":
        return "QUALITY_AFFECTED"
    if state == "SUDDEN_RISE":
        return "SUDDEN_RISE_EVENT"
    if state == "SUDDEN_DROP":
        return "SUDDEN_DROP_EVENT"
    if state == "RISING":
        return "ACCUMULATION"
    if state == "FALLING":
        return "DECLINE"
    if state == "STABLE" and level == "HIGH":
        return "STABLE_HIGH"
    if state == "STABLE" and level == "ELEVATED":
        return "STABLE_ELEVATED"
    if state == "STABLE" and level == "LOW":
        return "STABLE_LOW"
    return "UNSTABLE_TRANSITION"


def _validated_episode_type(episode_type, rows, config):
    if episode_type not in {"ACCUMULATION", "DECLINE"}:
        return episode_type
    duration = (rows[-1]["measured_at"] - rows[0]["measured_at"]).total_seconds() / 3600 if len(rows) > 1 else 0
    if (
        len(rows) < config.minimum_trend_episode_observations
        or duration < config.minimum_trend_episode_duration_hours
        or _episode_slope(rows) is None
    ):
        return "UNSTABLE_TRANSITION"
    return episode_type


def _episode_slope(rows):
    usable = [row for row in rows if row.get("radon_bq_m3") is not None]
    if len(usable) < 2:
        return None
    start = usable[0]
    end = usable[-1]
    hours = (end["measured_at"] - start["measured_at"]).total_seconds() / 3600
    if hours <= 0:
        return None
    return round((_float(end["radon_bq_m3"]) - _float(start["radon_bq_m3"])) / hours, 3)


def _previous_gap(start, gaps):
    previous = [gap for gap in gaps if gap.get("to") and gap["to"] <= start]
    return max(previous, key=lambda gap: gap["to"]) if previous else None


def _next_gap(end, gaps):
    upcoming = [gap for gap in gaps if gap.get("from") and gap["from"] >= end]
    return min(upcoming, key=lambda gap: gap["from"]) if upcoming else None


def _gap_distance(gap, timestamp, direction):
    if not gap:
        return None
    gap_time = gap["to"] if direction == "previous" else gap["from"]
    return round(abs((timestamp - gap_time).total_seconds()) / 3600, 3)


def _quality_status(rows, config):
    if any((row.get("confirmed_dynamic_state") or row.get("dynamic_state")) == "QUALITY_AFFECTED" for row in rows):
        return "QUALITY_AFFECTED"
    if len(rows) < config.minimum_episode_observations:
        return "LOW_CONFIDENCE_SHORT_EPISODE"
    if any(row.get("regime_confidence_label") == "LOW" for row in rows):
        return "LOW_CONFIDENCE"
    return "OK"


def _confidence_label(scores):
    if not scores:
        return "LOW"
    average = sum(scores) / len(scores)
    if average >= 0.75:
        return "HIGH"
    if average >= 0.45:
        return "MEDIUM"
    return "LOW"


def _distribution(values):
    clean = [value for value in values if value]
    total = len(clean)
    if not total:
        return {}
    return {key: {"count": count, "percent": round((count / total) * 100, 2)} for key, count in sorted(Counter(clean).items())}


def _reason_summary(rows):
    counter = Counter()
    for row in rows:
        for reason in set((row.get("regime_confidence_reasons") or []) + (row.get("dynamic_reason_codes") or [])):
            counter[reason] += 1
    total = len(rows) or 1
    return {
        reason: {"count": count, "percent": round((count / total) * 100, 2)}
        for reason, count in sorted(counter.items())
    }


def _dominant_reasons(summary):
    return [
        reason for reason, values in sorted(summary.items(), key=lambda item: (-item[1]["count"], item[0]))[:5]
    ]


def _component_summary(summary, positive):
    positive_codes = {
        "LOW_LOCAL_VARIABILITY",
        "SHORT_MEDIUM_SLOPE_AGREEMENT",
        "STRONG_PERSISTENT_TREND",
        "SUFFICIENT_WINDOW",
        "LONG_STABLE_DURATION",
        "EXPLICIT_INSTABILITY_EVIDENCE",
    }
    selected = positive_codes if positive else set(summary) - positive_codes
    return {reason: values for reason, values in summary.items() if reason in selected}


def _legacy_episode_label(episode_type):
    return {
        "STABLE_LOW": "stable low",
        "STABLE_ELEVATED": "stable elevated",
        "STABLE_HIGH": "stable high",
        "ACCUMULATION": "accumulation",
        "DECLINE": "controlled or natural decline",
        "SUDDEN_RISE_EVENT": "sudden rise",
        "SUDDEN_DROP_EVENT": "sudden drop",
        "UNSTABLE_TRANSITION": "unstable transition",
        "QUALITY_AFFECTED": "quality affected",
    }.get(episode_type, episode_type)


def _rows_by_segment(rows):
    grouped = {}
    for row in rows:
        grouped.setdefault(row["segment_id"], []).append(row)
    return grouped


def _parameter_set_identifier(config):
    return (
        f"v2.2_low{config.concentration_low_threshold_bq_m3}_high{config.concentration_high_threshold_bq_m3}_"
        f"trend{config.trend_slope_bq_m3_per_hour}_short{config.short_window_observations}_"
        f"medium{config.medium_window_observations}_persist{config.minimum_state_persistence_observations}"
    )


def _float(value):
    return float(value)
