from datetime import datetime


def downsample_time_series(points, max_points=2000):
    """Build a deterministic, peak-preserving subset for dashboard charts."""
    clean_points = [_normalise_point(point, index) for index, point in enumerate(points) if point.get("radon_bq_m3") is not None]
    clean_points.sort(key=lambda point: (point["timestamp"] or "", point["_index"]))
    if len(clean_points) <= max_points:
        return [_public_point(point) for point in clean_points]

    selected = {}

    def include(point):
        selected[point["_index"]] = point

    include(clean_points[0])
    include(clean_points[-1])
    include(min(clean_points, key=lambda point: point["radon_bq_m3"]))
    include(max(clean_points, key=lambda point: point["radon_bq_m3"]))

    if len(clean_points) > 1:
        deltas = []
        for previous, current in zip(clean_points, clean_points[1:]):
            delta = current["radon_bq_m3"] - previous["radon_bq_m3"]
            deltas.append((delta, previous, current))
        largest_rise = max(deltas, key=lambda item: item[0])
        largest_drop = min(deltas, key=lambda item: item[0])
        include(largest_rise[1])
        include(largest_rise[2])
        include(largest_drop[1])
        include(largest_drop[2])

    remaining_budget = max(max_points - len(selected), 0)
    bucket_count = max(1, remaining_budget // 2)
    bucket_size = max(1, len(clean_points) / bucket_count)

    for bucket_index in range(bucket_count):
        start = int(bucket_index * bucket_size)
        end = int((bucket_index + 1) * bucket_size)
        bucket = clean_points[start : max(end, start + 1)]
        if not bucket:
            continue
        include(min(bucket, key=lambda point: point["radon_bq_m3"]))
        include(max(bucket, key=lambda point: point["radon_bq_m3"]))

    reduced = sorted(selected.values(), key=lambda point: (point["timestamp"] or "", point["_index"]))
    if len(reduced) > max_points:
        reduced = reduced[:max_points]
    return [_public_point(point) for point in reduced]


def _normalise_point(point, index):
    timestamp = point.get("timestamp")
    if isinstance(timestamp, datetime):
        timestamp = timestamp.isoformat()
    return {
        "_index": index,
        "timestamp": timestamp,
        "radon_bq_m3": float(point["radon_bq_m3"]),
        "segment_id": point.get("segment_id"),
        "regime": point.get("regime") or "",
    }


def _public_point(point):
    return {
        "timestamp": point["timestamp"],
        "radon_bq_m3": round(point["radon_bq_m3"], 3),
        "segment_id": point.get("segment_id"),
        "regime": point.get("regime") or "",
    }
