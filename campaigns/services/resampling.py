from collections import defaultdict
from decimal import Decimal
from statistics import median, pstdev


def build_hourly_resampling(rows, config):
    buckets = defaultdict(list)
    for row in rows:
        measured_at = row.get("measured_at")
        if measured_at:
            bucket = measured_at.replace(minute=0, second=0, microsecond=0)
            buckets[bucket].append(row)

    hourly_rows = []
    for bucket, bucket_rows in sorted(buckets.items()):
        radon_values = [_float(row.get("radon_bq_m3")) for row in bucket_rows if row.get("radon_bq_m3") is not None]
        expected_count = _expected_count(bucket_rows)
        completeness = len(radon_values) / expected_count if expected_count else 0
        flags = set()
        if completeness < config.completeness_threshold:
            flags.add("LOW_COMPLETENESS")
        hourly_rows.append(
            {
                "interval_start": bucket.isoformat(),
                "radon_mean": _mean(radon_values),
                "radon_median": round(median(radon_values), 3) if radon_values else None,
                "radon_min": min(radon_values) if radon_values else None,
                "radon_max": max(radon_values) if radon_values else None,
                "radon_std": round(pstdev(radon_values), 3) if len(radon_values) > 1 else 0 if radon_values else None,
                "radon_count": len(radon_values),
                "temperature_mean": _mean([_float(row.get("temperature_c")) for row in bucket_rows if row.get("temperature_c") is not None]),
                "humidity_mean": _mean([_float(row.get("humidity_percent")) for row in bucket_rows if row.get("humidity_percent") is not None]),
                "pressure_mean": _mean([_float(row.get("pressure_hpa")) for row in bucket_rows if row.get("pressure_hpa") is not None]),
                "completeness_ratio": round(completeness, 3),
                "quality_flags": sorted(flags),
            }
        )

    summary = {
        "resampling_interval": config.resample_interval,
        "interval_count": len(hourly_rows),
        "low_completeness_interval_count": sum(1 for row in hourly_rows if "LOW_COMPLETENESS" in row["quality_flags"]),
        "completeness_threshold": config.completeness_threshold,
    }
    return {"canonical_hourly_data": hourly_rows, "resampling_summary": summary}


def _expected_count(rows):
    if len(rows) < 2:
        return max(len(rows), 1)
    ordered = sorted(rows, key=lambda row: row["measured_at"])
    deltas = [
        (current["measured_at"] - previous["measured_at"]).total_seconds() / 60
        for previous, current in zip(ordered, ordered[1:])
        if current["measured_at"] > previous["measured_at"]
    ]
    if not deltas:
        return max(len(rows), 1)
    nominal = max(min(deltas), 1)
    return max(round(60 / nominal), 1)


def _mean(values):
    if not values:
        return None
    return round(sum(values) / len(values), 3)


def _float(value):
    if isinstance(value, Decimal):
        return float(value)
    return float(value)
