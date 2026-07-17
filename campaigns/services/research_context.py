from decimal import Decimal

from django.core.exceptions import ObjectDoesNotExist


CONTEXT_FIELDS = [
    "floor_level",
    "height_above_ground_m",
    "room_volume_m3",
    "room_volume_source",
    "dominant_material",
    "sensor_height_m",
    "distance_from_nearest_opening_m",
    "sensor_moved_during_campaign",
    "direct_connection_to_soil",
    "event_log_availability",
    "notes",
    "evidence_status",
]


def build_research_context_payload(campaign):
    context = _context_or_none(campaign)
    metadata = {field: _clean(getattr(context, field, None)) for field in CONTEXT_FIELDS}
    return {
        "metadata": metadata,
        "readiness": build_model_readiness(campaign, metadata),
    }


def build_model_readiness(campaign, metadata=None):
    metadata = metadata if metadata is not None else build_research_context_payload(campaign)["metadata"]
    latest_summary = campaign.analysis_reports.values_list("summary_json", flat=True).first() or {}
    env = _environmental_predictors_available(campaign, latest_summary)
    has_measurements = campaign.measurements.exists()
    has_regimes = bool(latest_summary.get("regime_counts") or latest_summary.get("dynamic_state_counts"))
    has_volume = metadata.get("room_volume_m3") is not None
    has_material = bool(metadata.get("dominant_material"))
    fixed_sensor = metadata.get("sensor_moved_during_campaign") == "NO"
    has_sensor_height = metadata.get("sensor_height_m") is not None
    has_events = metadata.get("event_log_availability") in (
        "DOCUMENTED",
        "PARTIAL",
        "NATURALISTIC_FREQUENT_INTERVENTIONS",
    )
    return {
        "descriptive_analysis_ready": has_measurements,
        "regime_analysis_ready": has_regimes,
        "grey_box_modelling_possible": has_volume and has_sensor_height,
        "physically_parameterised_modelling_ready": all([has_volume, has_material, fixed_sensor, has_sensor_height, has_events, env]),
        "room_volume_available": has_volume,
        "dominant_material_available": has_material,
        "fixed_sensor_available": fixed_sensor,
        "sensor_height_available": has_sensor_height,
        "event_log_available": has_events,
        "environmental_predictors_available": env,
        "note": "Missing research-context metadata does not block descriptive or regime analysis.",
    }


def research_context_rows(campaign):
    payload = build_research_context_payload(campaign)
    rows = [
        {"section": "metadata", "field": field, "value": value, "evidence_status": payload["metadata"].get("evidence_status")}
        for field, value in payload["metadata"].items()
    ]
    rows.extend(
        {"section": "model_readiness", "field": field, "value": value, "evidence_status": None}
        for field, value in payload["readiness"].items()
    )
    return rows


def _environmental_predictors_available(campaign, summary):
    coverage = summary.get("environmental_coverage", {})
    if coverage:
        return any((coverage.get(key) or {}).get("available_rows") for key in ("temperature", "humidity", "pressure"))
    return (
        campaign.measurements.exclude(temperature_c=None).exists()
        or campaign.measurements.exclude(humidity_percent=None).exists()
        or campaign.measurements.exclude(pressure_hpa=None).exists()
    )


def _clean(value):
    if value == "":
        return None
    if isinstance(value, Decimal):
        return float(value)
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return value


def _context_or_none(campaign):
    try:
        return campaign.research_context
    except ObjectDoesNotExist:
        return None
