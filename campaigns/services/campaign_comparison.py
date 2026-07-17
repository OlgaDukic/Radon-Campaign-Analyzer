import csv
from pathlib import Path

from campaigns.models import Campaign


def compare_campaigns(campaign_ids, output_path=None, profile=None):
    rows = []
    for campaign in Campaign.objects.filter(id__in=campaign_ids).order_by("id"):
        report = campaign.analysis_reports.order_by("-created_at").first()
        summary = report.summary_json if report and report.summary_json else {}
        standardized = summary.get("standardized_campaign_summary") or {}
        applicability = summary.get("profile_applicability") or {}
        rows.append(
            {
                "campaign_id": campaign.id,
                "campaign_name": campaign.name,
                "analysis_report_id": report.id if report else None,
                "requested_profile": profile or "N/A",
                "profile_name": standardized.get("profile_name") or applicability.get("profile_name"),
                "profile_version": standardized.get("profile_version") or applicability.get("profile_version"),
                "algorithm_version": standardized.get("algorithm_version"),
                "profile_compatibility": applicability.get("status"),
                "warnings": applicability.get("reason_codes"),
                "sampling_interval_minutes": standardized.get("sampling_interval_minutes"),
                "campaign_duration_hours": standardized.get("campaign_duration_hours"),
                "valid_row_count": standardized.get("valid_row_count"),
                "gap_rate_per_1000_hours": standardized.get("gap_rate_per_1000_hours"),
                "concentration_level_percentages": standardized.get("concentration_level_percentages"),
                "dynamic_state_percentages": standardized.get("dynamic_state_percentages"),
                "episode_counts_per_1000_hours": standardized.get("episode_counts_per_1000_hours"),
                "maximum_radon": standardized.get("maximum_radon"),
                "median_absolute_slope": standardized.get("median_absolute_slope"),
                "p90_absolute_slope": standardized.get("p90_absolute_slope"),
                "median_confidence": standardized.get("median_confidence"),
                "low_confidence_percent": standardized.get("low_confidence_percent"),
            }
        )
    if output_path:
        _write_csv(Path(output_path), rows)
    return rows


def _write_csv(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    headers = list(rows[0].keys()) if rows else ["note"]
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=headers)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)
