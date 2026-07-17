from collections import Counter
from decimal import Decimal
from statistics import median


REGIME_V2_VERSION = "regime_analysis_v2.2"

GAP_CLASSES = {"SHORT_GAP", "MODERATE_GAP", "LONG_GAP"}
SUDDEN_STATES = {"SUDDEN_RISE", "SUDDEN_DROP"}
QUALITY_STATES = {"QUALITY_AFFECTED"}


def classify_regimes_v2(rows, config):
    classified = []
    for _segment_id, segment_rows in _rows_by_segment(rows).items():
        ordered = sorted(segment_rows, key=lambda row: row["measured_at"])
        features_by_index = [_local_features(index, ordered, config) for index in range(len(ordered))]
        candidate_results = [_candidate_state(ordered[index], features_by_index[index], config) for index in range(len(ordered))]
        candidate_states = [result["state"] for result in candidate_results]
        confirmed_states = _apply_persistence(candidate_states, config)
        previous_level = None
        for index, row in enumerate(ordered):
            features = features_by_index[index]
            candidate = candidate_results[index]
            confirmed_state = confirmed_states[index]
            level = _concentration_level(row.get("radon_bq_m3"), previous_level, config)
            previous_level = level
            confidence = _confidence(row, features, candidate["state"], confirmed_state, config)
            updated = row.copy()
            updated.update(features)
            updated["concentration_level"] = level
            updated["candidate_dynamic_state"] = candidate["state"]
            updated["confirmed_dynamic_state"] = confirmed_state
            updated["dynamic_state"] = confirmed_state
            updated["dynamic_reason_codes"] = sorted(set(candidate["reason_codes"] + confidence["reasons"]))
            updated["slope_bq_m3_per_hour"] = features["short_slope_bq_m3_per_hour"]
            updated["regime_confidence_score"] = confidence["score"]
            updated["regime_confidence_label"] = confidence["label"]
            updated["regime_confidence_reasons"] = confidence["reasons"]
            updated["regime_v2_label"] = f"{level}+{confirmed_state}"
            updated["regime_algorithm_version"] = REGIME_V2_VERSION
            updated["regime"] = _legacy_regime(level, confirmed_state)
            classified.append(updated)
    return sorted(classified, key=lambda row: row["measured_at"])


def concentration_level_counts(rows):
    return dict(sorted(Counter(row.get("concentration_level") for row in rows if row.get("concentration_level")).items()))


def dynamic_state_counts(rows, field="confirmed_dynamic_state"):
    return dict(sorted(Counter(row.get(field) or row.get("dynamic_state") for row in rows if row.get(field) or row.get("dynamic_state")).items()))


def regime_parameters(config):
    return {
        "algorithm_version": REGIME_V2_VERSION,
        "parameter_set_identifier": _parameter_set_identifier(config),
        "concentration_low_enter_threshold_bq_m3": config.concentration_low_threshold_bq_m3,
        "concentration_low_exit_threshold_bq_m3": config.concentration_low_threshold_bq_m3 - config.concentration_hysteresis_bq_m3,
        "concentration_high_enter_threshold_bq_m3": config.concentration_high_threshold_bq_m3,
        "concentration_high_exit_threshold_bq_m3": config.concentration_high_threshold_bq_m3 - config.concentration_hysteresis_bq_m3,
        "concentration_hysteresis_bq_m3": config.concentration_hysteresis_bq_m3,
        "short_window_observations": config.short_window_observations,
        "medium_window_observations": config.medium_window_observations,
        "minimum_short_window_observations": config.minimum_short_window_observations,
        "minimum_medium_window_observations": config.minimum_medium_window_observations,
        "stable_slope_bq_m3_per_hour": config.stable_slope_bq_m3_per_hour,
        "trend_slope_bq_m3_per_hour": config.trend_slope_bq_m3_per_hour,
        "medium_trend_slope_bq_m3_per_hour": config.medium_trend_slope_bq_m3_per_hour,
        "sudden_change_bq_m3_per_hour": config.sudden_change_bq_m3_per_hour,
        "variability_threshold_bq_m3": config.variability_threshold_bq_m3,
        "variability_normalization_floor_bq_m3": config.variability_normalization_floor_bq_m3,
        "instability_score_threshold": config.instability_score_threshold,
        "instability_sign_change_threshold": config.instability_sign_change_threshold,
        "material_slope_disagreement_bq_m3_per_hour": config.material_slope_disagreement_bq_m3_per_hour,
        "raw_smoothed_disagreement_threshold_bq_m3_per_hour": config.raw_smoothed_disagreement_threshold_bq_m3_per_hour,
        "slope_near_threshold_absolute_tolerance_bq_m3_per_hour": config.slope_near_threshold_absolute_tolerance_bq_m3_per_hour,
        "slope_near_threshold_relative_tolerance": config.slope_near_threshold_relative_tolerance,
        "minimum_state_persistence_observations": config.minimum_state_persistence_observations,
        "isolated_state_absorption_observations": config.isolated_state_absorption_observations,
        "minimum_trend_episode_observations": config.minimum_trend_episode_observations,
        "minimum_trend_episode_duration_hours": config.minimum_trend_episode_duration_hours,
        "short_window_minutes": config.short_window_minutes,
        "medium_window_minutes": config.medium_window_minutes,
        "persistence_minutes": config.persistence_minutes,
        "minimum_episode_duration_minutes": config.minimum_episode_duration_minutes,
        "isolated_state_merge_minutes": config.isolated_state_merge_minutes,
        "gap_proximity_minutes": config.gap_proximity_minutes,
        "near_gap_observations": config.near_gap_observations,
        "confidence_formula": (
            "Start at 0.60; add up to 0.20 for slope strength, 0.10 for short/medium trend agreement, "
            "0.10 for low variability in stable states, and 0.10 for sufficient local observations; subtract 0.25 near gaps, "
            "0.20 for insufficient window, 0.15 for high variability when it contradicts the label, 0.15 for near-threshold "
            "classification, 0.10 for raw/smoothed disagreement, and 0.10 per material instability criterion not represented "
            "by the assigned label. The score is clipped to [0, 1] and is not a probability."
        ),
        "instability_rule": (
            "UNSTABLE_TRANSITION requires at least instability_score_threshold explicit criteria among: local MAD above "
            "variability threshold, repeated medium-window slope sign changes, material opposite short/medium slopes, and "
            "material raw-vs-smoothed trend disagreement. It is not the generic fallback."
        ),
        "rules": [
            "Concentration level is classified independently from temporal dynamic state.",
            "Dynamic state uses past-and-current time-normalized features inside continuous segments only.",
            "Candidate dynamic states are preserved separately from persistence-smoothed confirmed states.",
            "Sudden changes are preserved and are not absorbed by persistence smoothing.",
            "Confidence is a deterministic audit score, not a posterior probability.",
        ],
    }


def _candidate_state(row, features, config):
    reasons = []
    if row.get("previous_interval_class") in GAP_CLASSES or features["distance_to_previous_gap_observations"] == 0:
        return {"state": "QUALITY_AFFECTED", "reason_codes": ["NEAR_GAP"]}
    if row.get("radon_bq_m3") is None:
        return {"state": "QUALITY_AFFECTED", "reason_codes": ["INVALID_RADON"]}
    if features["short_valid_observation_count"] < config.minimum_short_window_observations:
        return {"state": "QUALITY_AFFECTED", "reason_codes": ["INSUFFICIENT_WINDOW"]}

    adjacent = features["adjacent_slope_bq_m3_per_hour"]
    short = features["short_slope_bq_m3_per_hour"]
    medium = features["medium_slope_bq_m3_per_hour"]
    sudden_slope = adjacent
    if sudden_slope is not None and sudden_slope >= config.sudden_change_bq_m3_per_hour:
        return {"state": "SUDDEN_RISE", "reason_codes": ["SUDDEN_POSITIVE_CHANGE"]}
    if sudden_slope is not None and sudden_slope <= -config.sudden_change_bq_m3_per_hour:
        return {"state": "SUDDEN_DROP", "reason_codes": ["SUDDEN_NEGATIVE_CHANGE"]}

    instability = _instability_evidence(features, config)

    trend = _trend_slope(short, medium)
    if trend is None:
        return {"state": "QUALITY_AFFECTED", "reason_codes": ["INSUFFICIENT_WINDOW"]}
    if _is_rising(short, medium, config) and instability["score"] < config.instability_score_threshold:
        reasons = ["SHORT_SLOPE_POSITIVE" if short and short > 0 else "MEDIUM_SLOPE_POSITIVE"]
        if _same_direction(short, medium, positive=True):
            reasons.append("SHORT_MEDIUM_SLOPE_AGREEMENT")
        return {"state": "RISING", "reason_codes": reasons}
    if _is_falling(short, medium, config) and instability["score"] < config.instability_score_threshold:
        reasons = ["SHORT_SLOPE_NEGATIVE" if short and short < 0 else "MEDIUM_SLOPE_NEGATIVE"]
        if _same_direction(short, medium, positive=False):
            reasons.append("SHORT_MEDIUM_SLOPE_AGREEMENT")
        return {"state": "FALLING", "reason_codes": reasons}
    if _is_stable(short, medium, features, config):
        return {"state": "STABLE", "reason_codes": ["LOW_LOCAL_VARIABILITY", "SLOPE_WITHIN_STABLE_THRESHOLD"]}
    if instability["score"] >= config.instability_score_threshold:
        return {"state": "UNSTABLE_TRANSITION", "reason_codes": instability["reasons"]}
    if abs(trend) <= config.trend_slope_bq_m3_per_hour:
        return {"state": "STABLE", "reason_codes": ["AMBIGUOUS_BUT_LOW_INSTABILITY", "SLOPE_BELOW_TREND_THRESHOLD"]}
    return {"state": "UNSTABLE_TRANSITION", "reason_codes": ["MATERIAL_TREND_AMBIGUITY"]}


def _local_features(index, rows, config):
    short_window = rows[max(0, index - config.short_window_observations + 1): index + 1]
    medium_window = rows[max(0, index - config.medium_window_observations + 1): index + 1]
    short_values = [_float(row.get("radon_bq_m3")) for row in short_window if row.get("radon_bq_m3") is not None]
    medium_values = [_float(row.get("radon_bq_m3")) for row in medium_window if row.get("radon_bq_m3") is not None]
    rolling_median = round(median(short_values), 3) if short_values else None
    variability = _mad(medium_values)
    adjacent_slope = _slope(rows[index - 1: index + 1]) if index > 0 else None
    short_slope = _slope(short_window)
    medium_slope = _slope(medium_window)
    previous_adjacent = _slope(rows[index - 2: index]) if index > 1 else None
    previous_gap_distance = _distance_to_previous_gap(index, rows)
    next_gap_distance = _distance_to_next_gap(index, rows)
    smoothed_direction = _sign(short_slope if short_slope is not None else medium_slope)
    raw_smoothed_disagreement = bool(
        adjacent_slope is not None
        and abs(adjacent_slope) >= config.raw_smoothed_disagreement_threshold_bq_m3_per_hour
        and smoothed_direction
        and _sign(adjacent_slope)
        and _sign(adjacent_slope) != smoothed_direction
    )
    return {
        "observed_interval_hours": _interval_hours(rows[index - 1], rows[index]) if index > 0 else None,
        "adjacent_slope_bq_m3_per_hour": adjacent_slope,
        "short_slope_bq_m3_per_hour": short_slope,
        "medium_slope_bq_m3_per_hour": medium_slope,
        "slope_acceleration_bq_m3_per_hour2": round(adjacent_slope - previous_adjacent, 3) if adjacent_slope is not None and previous_adjacent is not None else None,
        "rolling_median_radon": rolling_median,
        "local_variability_mad": variability,
        "local_variability_normalized": _normalized_variability(variability, rolling_median, config),
        "short_valid_observation_count": len(short_values),
        "medium_valid_observation_count": len(medium_values),
        "distance_to_previous_gap_observations": previous_gap_distance["observations"],
        "distance_to_previous_gap_hours": previous_gap_distance["hours"],
        "distance_to_next_gap_observations": next_gap_distance["observations"],
        "distance_to_next_gap_hours": next_gap_distance["hours"],
        "raw_smoothed_disagreement": raw_smoothed_disagreement,
        "window_sign_change_count": _sign_change_count(medium_window),
    }


def _apply_persistence(states, config):
    minimum = config.minimum_state_persistence_observations
    if minimum <= 1 or len(states) < 3:
        return states[:]
    smoothed = states[:]
    index = 0
    while index < len(states):
        state = states[index]
        end = index + 1
        while end < len(states) and states[end] == state:
            end += 1
        run_length = end - index
        if (
            run_length <= config.isolated_state_absorption_observations
            and state not in SUDDEN_STATES | QUALITY_STATES
            and index > 0
            and end < len(states)
            and states[index - 1] == states[end]
            and states[index - 1] not in SUDDEN_STATES
        ):
            for replace_index in range(index, end):
                smoothed[replace_index] = states[index - 1]
        elif (
            run_length < minimum
            and state not in SUDDEN_STATES | QUALITY_STATES
            and index > 0
            and states[index - 1] not in SUDDEN_STATES
        ):
            for replace_index in range(index, end):
                smoothed[replace_index] = states[index - 1]
        index = end
    return smoothed


def _confidence(row, features, candidate_state, confirmed_state, config):
    score = 0.60
    reasons = []
    slope = features["short_slope_bq_m3_per_hour"]
    medium = features["medium_slope_bq_m3_per_hour"]
    variability = features["local_variability_mad"]
    if features["short_valid_observation_count"] >= config.minimum_short_window_observations and features["medium_valid_observation_count"] >= config.minimum_medium_window_observations:
        score += 0.10
        reasons.append("SUFFICIENT_WINDOW")
    else:
        score -= 0.20
        reasons.append("INSUFFICIENT_WINDOW")
    if row.get("previous_interval_class") in GAP_CLASSES or features["distance_to_previous_gap_observations"] <= config.near_gap_observations:
        score -= 0.25
        reasons.append("NEAR_GAP")
    if variability is not None and variability <= config.variability_threshold_bq_m3:
        score += 0.10
        reasons.append("LOW_LOCAL_VARIABILITY")
    elif variability is not None and confirmed_state in {"STABLE", "RISING", "FALLING"}:
        score -= 0.15
        reasons.append("HIGH_LOCAL_VARIABILITY")
    if slope is not None:
        strength = min(abs(slope) / max(config.trend_slope_bq_m3_per_hour, 1), 2) / 2
        score += round(strength * 0.20, 3)
        if _slope_near_threshold(slope, config):
            score -= 0.15
            reasons.append("SLOPE_NEAR_THRESHOLD")
    if _same_direction(slope, medium):
        score += 0.10
        reasons.append("SHORT_MEDIUM_SLOPE_AGREEMENT")
    if features["raw_smoothed_disagreement"]:
        score -= 0.10
        reasons.append("RAW_SMOOTHED_DISAGREEMENT")
    instability = _instability_evidence(features, config)
    if confirmed_state != "UNSTABLE_TRANSITION":
        score -= min(0.25, 0.10 * instability["score"])
    elif instability["score"] >= config.instability_score_threshold:
        score += 0.10
        reasons.append("EXPLICIT_INSTABILITY_EVIDENCE")
    if candidate_state != confirmed_state:
        reasons.append("PERSISTENCE_ADJUSTED_STATE")
    if confirmed_state in {"RISING", "FALLING", "SUDDEN_RISE", "SUDDEN_DROP"} and slope is not None and abs(slope) >= config.trend_slope_bq_m3_per_hour * 1.5:
        reasons.append("STRONG_PERSISTENT_TREND")
    if confirmed_state == "STABLE" and variability is not None and variability <= config.stable_slope_bq_m3_per_hour:
        reasons.append("LONG_STABLE_DURATION")
    score = round(min(max(score, 0.0), 1.0), 3)
    return {"score": score, "label": _confidence_label(score), "reasons": sorted(set(reasons or ["NO_MAJOR_LIMITATION"]))}


def _concentration_level(value, previous_level, config):
    if value is None:
        return "UNKNOWN"
    value = _float(value)
    low_enter = config.concentration_low_threshold_bq_m3
    low_exit = low_enter - config.concentration_hysteresis_bq_m3
    high_enter = config.concentration_high_threshold_bq_m3
    high_exit = high_enter - config.concentration_hysteresis_bq_m3
    if previous_level == "HIGH":
        if value >= high_exit:
            return "HIGH"
        if value >= low_exit:
            return "ELEVATED"
        return "LOW"
    if previous_level == "ELEVATED":
        if value >= high_enter:
            return "HIGH"
        if value >= low_exit:
            return "ELEVATED"
        return "LOW"
    if value >= high_enter:
        return "HIGH"
    if value >= low_enter:
        return "ELEVATED"
    return "LOW"


def _legacy_regime(level, state):
    if state == "RISING":
        return "rising"
    if state == "FALLING":
        return "falling"
    if state == "SUDDEN_RISE":
        return "sudden_rise"
    if state == "SUDDEN_DROP":
        return "sudden_drop"
    if state == "QUALITY_AFFECTED":
        return "quality_affected"
    if state == "UNSTABLE_TRANSITION":
        return "unstable_transition"
    if state == "STABLE" and level == "HIGH":
        return "high_episode"
    if state == "STABLE" and level == "ELEVATED":
        return "stable_elevated"
    if state == "STABLE" and level == "LOW":
        return "stable_low"
    return "unknown"


def _slope(window):
    usable = [row for row in window if row.get("radon_bq_m3") is not None]
    if len(usable) < 2:
        return None
    first = usable[0]
    last = usable[-1]
    hours = (last["measured_at"] - first["measured_at"]).total_seconds() / 3600
    if hours <= 0:
        return None
    return round((_float(last["radon_bq_m3"]) - _float(first["radon_bq_m3"])) / hours, 3)


def _interval_hours(previous, current):
    hours = (current["measured_at"] - previous["measured_at"]).total_seconds() / 3600
    return round(hours, 3) if hours >= 0 else None


def _distance_to_previous_gap(index, rows):
    for distance in range(0, index + 1):
        current = rows[index - distance]
        if current.get("previous_interval_class") in GAP_CLASSES:
            return {"observations": distance, "hours": round((rows[index]["measured_at"] - current["measured_at"]).total_seconds() / 3600, 3)}
    return {"observations": index + 1, "hours": None}


def _distance_to_next_gap(index, rows):
    for distance in range(1, len(rows) - index):
        current = rows[index + distance]
        if current.get("previous_interval_class") in GAP_CLASSES:
            return {"observations": distance, "hours": round((current["measured_at"] - rows[index]["measured_at"]).total_seconds() / 3600, 3)}
    return {"observations": len(rows) - index, "hours": None}


def _sign_change_count(window):
    slopes = [_slope([previous, current]) for previous, current in zip(window, window[1:])]
    signs = [_sign(value) for value in slopes if _sign(value)]
    return sum(1 for left, right in zip(signs, signs[1:]) if left != right)


def _trend_slope(short, medium):
    if short is not None and medium is not None:
        if _opposite_signs(short, medium):
            return 0
        return short if abs(short) >= abs(medium) else medium
    return short if short is not None else medium


def _is_rising(short, medium, config):
    return (
        (short is not None and short >= config.trend_slope_bq_m3_per_hour)
        or (medium is not None and medium >= config.medium_trend_slope_bq_m3_per_hour and (short is None or short > 0))
    )


def _is_falling(short, medium, config):
    return (
        (short is not None and short <= -config.trend_slope_bq_m3_per_hour)
        or (medium is not None and medium <= -config.medium_trend_slope_bq_m3_per_hour and (short is None or short < 0))
    )


def _is_stable(short, medium, features, config):
    variability = features["local_variability_mad"]
    sign_changes = features["window_sign_change_count"]
    return (
        short is not None
        and abs(short) <= config.stable_slope_bq_m3_per_hour
        and (medium is None or abs(medium) <= config.medium_trend_slope_bq_m3_per_hour)
        and (variability is None or variability <= config.variability_threshold_bq_m3)
        and sign_changes < config.instability_sign_change_threshold
    )


def _instability_evidence(features, config):
    reasons = []
    variability = features["local_variability_mad"]
    short = features["short_slope_bq_m3_per_hour"]
    medium = features["medium_slope_bq_m3_per_hour"]
    if variability is not None and variability > config.variability_threshold_bq_m3:
        reasons.append("HIGH_LOCAL_VARIABILITY")
    if features["window_sign_change_count"] >= config.instability_sign_change_threshold:
        reasons.append("REPEATED_SIGN_CHANGES")
    if (
        _opposite_signs(short, medium)
        and abs(short) >= config.material_slope_disagreement_bq_m3_per_hour
        and abs(medium) >= config.material_slope_disagreement_bq_m3_per_hour
    ):
        reasons.append("SHORT_MEDIUM_SLOPE_DISAGREEMENT")
    if features["raw_smoothed_disagreement"]:
        reasons.append("RAW_SMOOTHED_DISAGREEMENT")
    return {"score": len(reasons), "reasons": reasons}


def _slope_near_threshold(slope, config):
    if slope is None:
        return False
    band = min(
        config.slope_near_threshold_absolute_tolerance_bq_m3_per_hour,
        abs(config.trend_slope_bq_m3_per_hour) * config.slope_near_threshold_relative_tolerance,
    )
    return abs(abs(slope) - config.trend_slope_bq_m3_per_hour) <= band


def _normalized_variability(variability, rolling_median, config):
    if variability is None:
        return None
    denominator = max(abs(rolling_median or 0), config.variability_normalization_floor_bq_m3)
    return round(variability / denominator, 4)


def _same_direction(left, right, positive=None):
    if left is None or right is None:
        return False
    if positive is True:
        return left > 0 and right > 0
    if positive is False:
        return left < 0 and right < 0
    return _sign(left) and _sign(left) == _sign(right)


def _opposite_signs(left, right):
    return left is not None and right is not None and _sign(left) and _sign(right) and _sign(left) != _sign(right)


def _sign(value):
    if value is None or abs(value) < 1e-9:
        return 0
    return 1 if value > 0 else -1


def _largest_magnitude(values):
    usable = [value for value in values if value is not None]
    if not usable:
        return None
    return max(usable, key=lambda value: abs(value))


def _confidence_label(score):
    if score >= 0.75:
        return "HIGH"
    if score >= 0.45:
        return "MEDIUM"
    return "LOW"


def _mad(values):
    if not values:
        return None
    center = median(values)
    return round(median([abs(value - center) for value in values]), 3)


def _rows_by_segment(rows):
    grouped = {}
    for row in rows:
        grouped.setdefault(row["segment_id"], []).append(row)
    return grouped


def _parameter_set_identifier(config):
    return (
        f"v2.2_low{config.concentration_low_threshold_bq_m3}_high{config.concentration_high_threshold_bq_m3}_"
        f"trend{config.trend_slope_bq_m3_per_hour}_sudden{config.sudden_change_bq_m3_per_hour}_"
        f"short{config.short_window_observations}_medium{config.medium_window_observations}_persist{config.minimum_state_persistence_observations}"
    )


def _float(value):
    if isinstance(value, Decimal):
        return float(value)
    return float(value)
