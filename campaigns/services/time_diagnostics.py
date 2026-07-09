from datetime import timedelta
from zoneinfo import ZoneInfo


def build_dst_diagnostics(rows, config):
    timezone_info = ZoneInfo(config.timezone_name)
    diagnostics = []
    for row in rows:
        measured_at = row.get("measured_at")
        if not measured_at:
            diagnostics.append(
                {
                    "timestamp": None,
                    "timezone": config.timezone_name,
                    "flags": ["TIMESTAMP_PARSE_WARNING", "TIMEZONE_ASSUMED"],
                    "note": "Missing parsed timestamp.",
                }
            )
            continue
        local = measured_at.astimezone(timezone_info)
        flags = ["TIMEZONE_ASSUMED"]
        if _is_ambiguous(local, timezone_info):
            flags.append("DST_AMBIGUOUS")
        diagnostics.append(
            {
                "timestamp": measured_at.isoformat(),
                "local_timestamp": local.isoformat(),
                "utc_timestamp": measured_at.astimezone(ZoneInfo("UTC")).isoformat(),
                "timezone": config.timezone_name,
                "flags": flags,
                "note": "Timezone applied for reproducible UTC ordering.",
            }
        )

    missing = _dst_missing_intervals(rows, timezone_info, config.timezone_name)
    diagnostics.extend(missing)
    return diagnostics


def _is_ambiguous(local, timezone_info):
    naive = local.replace(tzinfo=None)
    first = naive.replace(tzinfo=timezone_info, fold=0)
    second = naive.replace(tzinfo=timezone_info, fold=1)
    return first.utcoffset() != second.utcoffset()


def _dst_missing_intervals(rows, timezone_info, timezone_name):
    ordered = sorted([row for row in rows if row.get("measured_at")], key=lambda row: row["measured_at"])
    diagnostics = []
    for previous, current in zip(ordered, ordered[1:]):
        previous_local = previous["measured_at"].astimezone(timezone_info)
        current_local = current["measured_at"].astimezone(timezone_info)
        utc_minutes = (current["measured_at"] - previous["measured_at"]).total_seconds() / 60
        local_minutes = (current_local.replace(tzinfo=None) - previous_local.replace(tzinfo=None)).total_seconds() / 60
        if local_minutes - utc_minutes >= 59:
            diagnostics.append(
                {
                    "timestamp": previous["measured_at"].isoformat(),
                    "local_timestamp": previous_local.isoformat(),
                    "utc_timestamp": previous["measured_at"].astimezone(ZoneInfo("UTC")).isoformat(),
                    "timezone": timezone_name,
                    "flags": ["DST_MISSING"],
                    "note": f"Local clock advanced by about {round(local_minutes - utc_minutes)} minutes between adjacent records.",
                }
            )
    return diagnostics
