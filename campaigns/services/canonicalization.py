from collections import Counter, defaultdict
from datetime import timezone as datetime_timezone
from decimal import Decimal
from zoneinfo import ZoneInfo

from django.utils import timezone


VALUE_FIELDS = ("radon_bq_m3", "temperature_c", "humidity_percent", "pressure_hpa")


def build_canonical_outputs(rows, config):
    raw_archive = [_raw_record(row, config) for row in rows]
    grouped = defaultdict(list)
    for row in rows:
        utc_timestamp = _utc_timestamp(row.get("measured_at"))
        grouped[utc_timestamp].append(row)

    canonical_records = []
    summary_counts = Counter()
    overlap_conflicts = []
    for utc_timestamp, group in sorted(grouped.items(), key=lambda item: item[0] or timezone.datetime.min.replace(tzinfo=datetime_timezone.utc)):
        canonical, counts, conflict = _canonical_record(utc_timestamp, group, config)
        canonical_records.append(canonical)
        summary_counts.update(counts)
        if conflict:
            overlap_conflicts.append(conflict)

    summary = {
        "raw_records": len(rows),
        "unique_timestamps": len(grouped),
        "exact_duplicates_removed": summary_counts["exact_duplicates_removed"],
        "conflicts": summary_counts["conflicts"],
        "overlap_records": summary_counts["overlap_records"],
        "canonical_valid_records": summary_counts["canonical_valid_records"],
        "canonical_invalid_or_excluded_records": summary_counts["canonical_invalid_or_excluded_records"],
    }
    return {
        "raw_archive_preview": raw_archive[:200],
        "canonical_records_preview": canonical_records[:500],
        "canonical_dataset_summary": summary,
        "overlap_conflicts": overlap_conflicts[:200],
    }


def _raw_record(row, config):
    source_file = row.get("source_file")
    measured_at = row.get("measured_at")
    return {
        "campaign_id": getattr(row.get("campaign"), "id", None),
        "source_file_id": getattr(source_file, "id", row.get("source_file_id")),
        "source_file_name": getattr(source_file, "original_name", row.get("source_file_name")),
        "original_row_number": row.get("original_row_number"),
        "original_timestamp_string": str(row.get("original_timestamp_string") or ""),
        "parsed_local_timestamp": measured_at.isoformat() if measured_at else None,
        "timezone": config.timezone_name,
        "utc_timestamp": _utc_timestamp(measured_at).isoformat() if measured_at else None,
        "radon_bq_m3": _number(row.get("radon_bq_m3")),
        "temperature_c": _number(row.get("temperature_c")),
        "humidity_percent": _number(row.get("humidity_percent")),
        "pressure_hpa": _number(row.get("pressure_hpa")),
        "parser_warnings": row.get("parser_warnings", ""),
    }


def _canonical_record(utc_timestamp, group, config):
    base = group[0].copy()
    flags = set()
    counts = Counter()
    source_ids = sorted({_source_id(row) for row in group if _source_id(row) is not None})
    if len(group) > 1:
        counts["overlap_records"] += len(group)
        flags.add("OVERLAP_SOURCE")

    exact_signatures = {_signature(row) for row in group}
    if len(group) > 1 and len(exact_signatures) == 1:
        counts["exact_duplicates_removed"] += len(group) - 1
        flags.add("DUPLICATE_EXACT")
        note = "Exact duplicate timestamp/value rows collapsed with provenance preserved."
    elif len(group) > 1 and _radon_values_agree(group):
        flags.add("OVERLAP_SOURCE")
        base = _completeness_merge(group)
        note = "Duplicate timestamp merged because radon agreed and environmental completeness improved."
    elif len(group) > 1:
        flags.add("DUPLICATE_CONFLICT")
        counts["conflicts"] += 1
        note = "Duplicate timestamp with conflicting values; retained first row and flagged conflict."
    else:
        note = "Unique timestamp."

    for field, flag in (
        ("radon_bq_m3", "MISSING_RADON"),
        ("temperature_c", "MISSING_TEMPERATURE"),
        ("humidity_percent", "MISSING_RELATIVE_HUMIDITY"),
        ("pressure_hpa", "MISSING_PRESSURE"),
    ):
        if base.get(field) is None:
            flags.add(flag)
    if {"MISSING_TEMPERATURE", "MISSING_RELATIVE_HUMIDITY", "MISSING_PRESSURE"} & flags:
        flags.add("MISSING_ENVIRONMENTAL")

    if "DUPLICATE_CONFLICT" in flags or "MISSING_RADON" in flags:
        counts["canonical_invalid_or_excluded_records"] += 1
    else:
        counts["canonical_valid_records"] += 1
        flags.add("VALID")

    return (
        {
            "utc_timestamp": utc_timestamp.isoformat() if utc_timestamp else None,
            "local_timestamp": _local_timestamp(base.get("measured_at"), config.timezone_name),
            "source_count": len(source_ids),
            "source_file_ids": source_ids,
            "radon_bq_m3": _number(base.get("radon_bq_m3")),
            "temperature_c": _number(base.get("temperature_c")),
            "humidity_percent": _number(base.get("humidity_percent")),
            "pressure_hpa": _number(base.get("pressure_hpa")),
            "quality_flags": sorted(flags),
            "canonical_resolution_note": note,
        },
        counts,
        _conflict_row(utc_timestamp, group, flags, note) if "DUPLICATE_CONFLICT" in flags else None,
    )


def _utc_timestamp(value):
    if not value:
        return None
    if timezone.is_naive(value):
        value = timezone.make_aware(value, timezone.get_current_timezone())
    return value.astimezone(datetime_timezone.utc)


def _local_timestamp(value, timezone_name):
    if not value:
        return None
    if timezone.is_naive(value):
        value = timezone.make_aware(value, ZoneInfo(timezone_name))
    return value.astimezone(ZoneInfo(timezone_name)).isoformat()


def _source_id(row):
    source = row.get("source_file")
    return getattr(source, "id", row.get("source_file_id"))


def _signature(row):
    return tuple(row.get(field) for field in ("measured_at", *VALUE_FIELDS))


def _radon_values_agree(group):
    values = {row.get("radon_bq_m3") for row in group if row.get("radon_bq_m3") is not None}
    return len(values) <= 1


def _completeness_merge(group):
    merged = group[0].copy()
    for row in group[1:]:
        for field in VALUE_FIELDS:
            if merged.get(field) is None and row.get(field) is not None:
                merged[field] = row[field]
    return merged


def _conflict_row(utc_timestamp, group, flags, note):
    return {
        "utc_timestamp": utc_timestamp.isoformat() if utc_timestamp else None,
        "source_file_ids": sorted({_source_id(row) for row in group if _source_id(row) is not None}),
        "values": [
            {field: _number(row.get(field)) for field in VALUE_FIELDS}
            for row in group
        ],
        "quality_flags": sorted(flags),
        "note": note,
    }


def _number(value):
    if value is None:
        return None
    if isinstance(value, Decimal):
        return float(value)
    return value
