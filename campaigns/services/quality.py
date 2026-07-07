from datetime import timedelta


def merge_overlapping_timestamps(rows):
    merged = {}
    for row in rows:
        timestamp = row["measured_at"]
        if timestamp not in merged:
            merged[timestamp] = row.copy()
            continue
        for field, value in row.items():
            if _is_empty(merged[timestamp].get(field)) and not _is_empty(value):
                merged[timestamp][field] = value
    return sorted(merged.values(), key=lambda row: row["measured_at"])


def detect_time_gaps(rows, threshold_minutes=60):
    gaps = []
    threshold = timedelta(minutes=threshold_minutes)
    ordered = sorted(rows, key=lambda row: row["measured_at"])
    for previous, current in zip(ordered, ordered[1:]):
        delta = current["measured_at"] - previous["measured_at"]
        if delta > threshold:
            gaps.append(
                {
                    "from": previous["measured_at"],
                    "to": current["measured_at"],
                    "minutes": round(delta.total_seconds() / 60, 2),
                }
            )
    return gaps


def _is_empty(value):
    return value is None or value == ""
