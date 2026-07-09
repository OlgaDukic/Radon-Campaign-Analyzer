SIREM_ITEMS = [
    ("room_volume", "high"),
    ("surfaces_in_contact_with_soil", "high"),
    ("building_materials", "medium"),
    ("sensor_position", "high"),
    ("ventilation_mode", "high"),
    ("known_opening_ventilation_events", "medium"),
    ("pressure_data", "high"),
    ("temperature_data", "medium"),
    ("relative_humidity_data", "medium"),
    ("continuous_radon_data", "high"),
    ("quality_flags", "high"),
    ("regime_labels", "medium"),
    ("contextual_event_log", "medium"),
    ("source_file_provenance", "high"),
]


def build_sirem_readiness(rows, summary):
    has_rows = bool(rows)
    has_pressure = any(row.get("pressure_hpa") is not None for row in rows)
    has_temperature = any(row.get("temperature_c") is not None for row in rows)
    has_humidity = any(row.get("humidity_percent") is not None for row in rows)
    availability = {
        "pressure_data": ("yes" if has_pressure else "no", "file" if has_pressure else "unknown"),
        "temperature_data": ("yes" if has_temperature else "no", "file" if has_temperature else "unknown"),
        "relative_humidity_data": ("yes" if has_humidity else "no", "file" if has_humidity else "unknown"),
        "continuous_radon_data": ("yes" if has_rows else "no", "file" if has_rows else "unknown"),
        "quality_flags": ("yes", "derived"),
        "regime_labels": ("yes" if summary.get("regime_counts") else "no", "derived"),
        "source_file_provenance": ("yes" if summary.get("uploaded_file_count") else "no", "file"),
    }
    checklist = []
    for item, importance in SIREM_ITEMS:
        available, source = availability.get(item, ("unknown", "unknown"))
        checklist.append(
            {
                "item": item,
                "available": available,
                "source": source,
                "notes": _notes(item, available),
                "importance_for_sirem": importance,
            }
        )
    return checklist


def _notes(item, available):
    if available == "unknown":
        return "Not captured by the current prototype; can be added manually for future SIREM-informed validation."
    if available == "no":
        return "Not available in the current campaign data."
    return "Available from current campaign data or derived research outputs."
