from collections import Counter, defaultdict


QUALITY_FLAG_DICTIONARY = {
    "VALID": "Record is suitable for the current research analysis.",
    "MISSING_RADON": "Radon concentration is missing.",
    "MISSING_TEMPERATURE": "Temperature is missing.",
    "MISSING_RELATIVE_HUMIDITY": "Relative humidity is missing.",
    "MISSING_PRESSURE": "Pressure is missing.",
    "MISSING_ENVIRONMENTAL": "At least one environmental covariate is missing.",
    "DUPLICATE_EXACT": "Duplicate timestamp and values were detected.",
    "DUPLICATE_CONFLICT": "Duplicate timestamp with conflicting values was detected.",
    "OVERLAP_SOURCE": "Timestamp is represented in more than one source file.",
    "IRREGULAR_INTERVAL": "Sampling interval differs from the nominal interval.",
    "GAP_SHORT": "Sampling-aware short gap detected.",
    "GAP_LONG": "Sampling-aware long gap detected.",
    "DST_AMBIGUOUS": "Local timestamp may be ambiguous during daylight-saving fallback.",
    "DST_MISSING": "Local timestamp interval may cross daylight-saving spring forward.",
    "SUSPECT_SPIKE": "Potential isolated radon spike detected by a simple local rule.",
    "SENSOR_PLATEAU": "Repeated identical radon values suggest a possible plateau.",
    "LOW_COMPLETENESS": "Resampled interval completeness is below configured threshold.",
    "IMPUTED": "Value was imputed.",
    "QUALITY_LIMITED_REGIME": "Regime label should be interpreted with quality limitations.",
    "SMALL_REGIME_SAMPLE": "Regime-conditioned metric is based on a small sample.",
}


def build_quality_outputs(rows, canonical_records, gaps, dst_diagnostics):
    timeline = []
    flag_counts = Counter()
    by_source = defaultdict(Counter)
    by_segment = defaultdict(Counter)

    for row in rows:
        flags = set(_row_flags(row))
        flag_counts.update(flags)
        source_id = getattr(row.get("source_file"), "id", row.get("source_file_id") or "unknown")
        by_source[source_id].update(flags)
        by_segment[row.get("segment_id", "unassigned")].update(flags)
        timeline.append(
            {
                "timestamp": row.get("measured_at").isoformat() if row.get("measured_at") else None,
                "source_file_id": source_id,
                "segment_id": row.get("segment_id"),
                "flags": sorted(flags),
            }
        )

    for record in canonical_records:
        flag_counts.update(record.get("quality_flags", []))
    for gap in gaps:
        if gap.get("gap_class"):
            flag_counts.update([gap.get("gap_class")])
    for diagnostic in dst_diagnostics:
        flag_counts.update(diagnostic.get("flags", []))

    return {
        "quality_flag_counts": dict(sorted(flag_counts.items())),
        "quality_flags_by_source_file": {
            str(source): dict(sorted(counts.items())) for source, counts in sorted(by_source.items(), key=lambda item: str(item[0]))
        },
        "quality_flags_by_segment": {
            str(segment): dict(sorted(counts.items())) for segment, counts in sorted(by_segment.items(), key=lambda item: str(item[0]))
        },
        "quality_flag_timeline_preview": timeline[:500],
        "quality_flag_dictionary": QUALITY_FLAG_DICTIONARY,
    }


def _row_flags(row):
    flags = []
    if row.get("radon_bq_m3") is None:
        flags.append("MISSING_RADON")
    if row.get("temperature_c") is None:
        flags.append("MISSING_TEMPERATURE")
    if row.get("humidity_percent") is None:
        flags.append("MISSING_RELATIVE_HUMIDITY")
    if row.get("pressure_hpa") is None:
        flags.append("MISSING_PRESSURE")
    if any(flag in flags for flag in ("MISSING_TEMPERATURE", "MISSING_RELATIVE_HUMIDITY", "MISSING_PRESSURE")):
        flags.append("MISSING_ENVIRONMENTAL")
    if not flags:
        flags.append("VALID")
    return flags
