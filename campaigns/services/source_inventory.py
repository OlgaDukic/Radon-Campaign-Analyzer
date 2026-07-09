from collections import Counter, defaultdict
from statistics import median


ENV_FIELDS = {
    "temperature_c": "temperature",
    "humidity_percent": "humidity",
    "pressure_hpa": "pressure",
}


def build_source_file_inventory(rows, ingestion_debug):
    rows_by_file = defaultdict(list)
    for row in rows:
        source_file = row.get("source_file")
        key = getattr(source_file, "id", None) or row.get("source_file_id") or row.get("source_file_name") or "unknown"
        rows_by_file[key].append(row)

    timestamp_file_counts = defaultdict(set)
    for row in rows:
        source_file = row.get("source_file")
        key = getattr(source_file, "id", None) or row.get("source_file_id") or row.get("source_file_name") or "unknown"
        timestamp_file_counts[row.get("measured_at")].add(key)

    inventory = []
    debug_by_name = {debug.get("filename"): debug for debug in ingestion_debug}
    all_keys = set(rows_by_file)
    for debug in ingestion_debug:
        all_keys.add(debug.get("source_file_id") or debug.get("filename"))

    for key in all_keys:
        file_rows = sorted(rows_by_file.get(key, []), key=lambda row: row.get("measured_at"))
        source = file_rows[0].get("source_file") if file_rows else None
        filename = getattr(source, "original_name", None) or key
        debug = debug_by_name.get(filename) or _debug_for_key(ingestion_debug, key)
        timestamps = [row["measured_at"] for row in file_rows if row.get("measured_at")]
        distribution = _interval_distribution(timestamps)
        duplicate_count = _duplicate_timestamps(timestamps)
        overlap_timestamps = [
            timestamp for timestamp in timestamps if len(timestamp_file_counts[timestamp]) > 1
        ]
        available_env = [
            label for field, label in ENV_FIELDS.items() if any(row.get(field) is not None for row in file_rows)
        ]
        inventory.append(
            {
                "source_file_id": getattr(source, "id", key),
                "filename": filename,
                "device_id": _detect_device_id(str(filename)),
                "parsed_start": timestamps[0].isoformat() if timestamps else None,
                "parsed_end": timestamps[-1].isoformat() if timestamps else None,
                "raw_rows": debug.get("raw_rows_read", len(file_rows)) if debug else len(file_rows),
                "imported_measurement_rows": len(file_rows) or (debug or {}).get("parsed_measurement_rows", 0),
                "detected_columns": (debug or {}).get("detected_columns", []),
                "radon_unit": _detect_radon_unit((debug or {}).get("detected_columns", [])),
                "environmental_columns_available": available_env,
                "missing_values": _missing_values(file_rows),
                "duplicate_timestamps_within_file": duplicate_count,
                "nominal_sampling_interval_minutes": _nominal_interval(distribution),
                "sampling_interval_distribution": distribution,
                "irregular_intervals": _irregular_interval_count(distribution),
                "overlap_duration_minutes": _overlap_duration(overlap_timestamps),
                "overlap_timestamp_count": len(set(overlap_timestamps)),
                "warnings_errors": (debug or {}).get("skipped_reason", ""),
            }
        )
    return sorted(inventory, key=lambda item: str(item["filename"]))


def _debug_for_key(ingestion_debug, key):
    for debug in ingestion_debug:
        if debug.get("source_file_id") == key or debug.get("filename") == key:
            return debug
    return {}


def _detect_device_id(filename):
    parts = filename.replace("_", " ").split()
    for index, part in enumerate(parts):
        if part.lower().startswith("aranetrn") and index + 1 < len(parts):
            return parts[index + 1]
    return None


def _detect_radon_unit(columns):
    joined = " ".join(str(column).lower() for column in columns)
    if "bq" in joined and ("m3" in joined or "m³" in joined):
        return "Bq/m3"
    return None


def _missing_values(rows):
    fields = ("radon_bq_m3", "temperature_c", "humidity_percent", "pressure_hpa")
    return {
        field: sum(1 for row in rows if row.get(field) in (None, ""))
        for field in fields
    }


def _duplicate_timestamps(timestamps):
    counts = Counter(timestamps)
    return sum(count - 1 for count in counts.values() if count > 1)


def _interval_distribution(timestamps):
    if len(timestamps) < 2:
        return {}
    deltas = [
        round((current - previous).total_seconds() / 60, 2)
        for previous, current in zip(timestamps, timestamps[1:])
        if current and previous and current > previous
    ]
    return {str(minutes): count for minutes, count in sorted(Counter(deltas).items())}


def _nominal_interval(distribution):
    if not distribution:
        return None
    expanded = []
    for minutes, count in distribution.items():
        expanded.extend([float(minutes)] * count)
    return round(median(expanded), 2) if expanded else None


def _irregular_interval_count(distribution):
    nominal = _nominal_interval(distribution)
    if not nominal:
        return 0
    return sum(
        count for minutes, count in distribution.items()
        if abs(float(minutes) - nominal) > max(1.0, nominal * 0.1)
    )


def _overlap_duration(timestamps):
    unique = sorted(set(timestamps))
    if len(unique) < 2:
        return 0.0
    return round((unique[-1] - unique[0]).total_seconds() / 60, 2)
