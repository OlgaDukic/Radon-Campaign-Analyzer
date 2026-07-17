from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from django.conf import settings
from django.utils import timezone

from campaigns.models import Campaign
from campaigns.services.analysis import run_campaign_analysis
from campaigns.services.analysis_profiles import build_config
from campaigns.services.excel_export import build_campaign_report_workbook
from campaigns.services.paper_outputs import enrich_paper_summary, write_paper_output_package


def run_paper1_analysis(
    campaign_id: int,
    timezone: str = "Europe/Rome",
    resample: str = "1H",
    gap_tolerance: float = 1.5,
    rebuild_canonical: bool = True,
    run_sensitivity: bool = True,
    export_excel: bool = True,
    output_dir: str | None = None,
    profile: str = "default_radon_hourly",
    config_overrides: dict | None = None,
    requested_by: str | None = None,
) -> dict:
    try:
        campaign = Campaign.objects.get(pk=campaign_id)
        _validate_timezone(timezone)
        if not campaign.uploaded_files.exists():
            return _failed(campaign, timezone, resample, gap_tolerance, "Upload at least one monitoring file before running Paper 1 analysis.")

        output_path = _output_dir(campaign_id, output_dir)
        config = build_config(
            profile_name=profile,
            overrides=config_overrides or {},
            timezone_name=timezone,
            resample_interval=resample,
            gap_tolerance_multiplier=float(gap_tolerance),
        )
        report = run_campaign_analysis(campaign, config=config)
        if report.status != report.Status.COMPLETE:
            return _failed(campaign, timezone, resample, gap_tolerance, "Paper 1 analysis did not complete.", report)

        excel_path = None
        if export_excel:
            output_path.mkdir(parents=True, exist_ok=True)
            excel_path = output_path / f"radon_campaign_{campaign.id}_report.xlsx"
            workbook = build_campaign_report_workbook(campaign, report)
            excel_path.write_bytes(workbook.getvalue())

        command_used = _command_used(
            campaign_id,
            timezone,
            resample,
            gap_tolerance,
            rebuild_canonical,
            run_sensitivity,
            export_excel,
            output_path,
            profile,
            config_overrides or {},
        )
        package = write_paper_output_package(
            campaign,
            report,
            output_path,
            excel_path=excel_path,
            command_used=command_used,
        )
        summary = enrich_paper_summary(report.summary_json or {})
        result = _success_result(
            campaign,
            report,
            summary,
            timezone,
            resample,
            gap_tolerance,
            rebuild_canonical,
            run_sensitivity,
            export_excel,
            output_path,
            excel_path,
            package["validation_report"],
        )
        result["requested_by"] = requested_by
        _store_runner_result(report, result, output_path, excel_path, package["validation_report"])
        return result
    except (Campaign.DoesNotExist, ZoneInfoNotFoundError, ValueError) as exc:
        return {
            "status": "failed",
            "campaign_id": campaign_id,
            "campaign_name": "",
            "run_timestamp": timezone_now(),
            "timezone": timezone,
            "resample": resample,
            "gap_tolerance": gap_tolerance,
            "rebuild_canonical": rebuild_canonical,
            "run_sensitivity": run_sensitivity,
            "export_excel": export_excel,
            "output_dir": output_dir or _relative_output_dir(campaign_id),
            "profile": profile,
            "config_overrides": config_overrides or {},
            "warnings": [],
            "error_message": str(exc),
        }


def _success_result(campaign, report, summary, timezone_name, resample, gap_tolerance, rebuild_canonical, run_sensitivity, export_excel, output_path, excel_path, validation_path):
    reconciliation = summary.get("row_reconciliation_summary", {})
    dst = summary.get("dst_diagnostics_compact_summary", {})
    sampling = summary.get("sampling_gaps_compact_summary", {})
    prediction_metrics = summary.get("prediction_metrics") or {}
    prediction_skill = summary.get("prediction_skill_by_regime") or []
    quality = summary.get("quality_flag_counts") or {}
    return {
        "status": "success",
        "campaign_id": campaign.id,
        "campaign_name": campaign.name,
        "source_file_count": campaign.uploaded_files.count(),
        "analysis_report_id": report.id,
        "run_timestamp": report.created_at.isoformat(),
        "timezone": timezone_name,
        "resample": resample,
        "gap_tolerance": gap_tolerance,
        "rebuild_canonical": rebuild_canonical,
        "run_sensitivity": run_sensitivity,
        "export_excel": export_excel,
        "output_dir": _relative_path(output_path),
        "raw_imported_rows": reconciliation.get("raw_imported_rows", 0),
        "exact_duplicate_rows_removed": reconciliation.get("exact_duplicate_rows_removed", 0),
        "duplicate_conflict_rows": reconciliation.get("duplicate_conflict_rows", 0),
        "canonical_valid_rows": reconciliation.get("canonical_valid_rows", 0),
        "canonical_hourly_rows": reconciliation.get("canonical_hourly_rows", 0),
        "timezone_audit_rows": dst.get("timezone_audit_rows", 0),
        "dst_ambiguous_count": dst.get("dst_ambiguous_count", 0),
        "dst_nonexistent_count": dst.get("dst_nonexistent_count", 0),
        "total_sampling_irregularities": sampling.get("total_sampling_irregularities", 0),
        "short_gaps": sampling.get("short_gaps", 0),
        "long_gaps": sampling.get("long_gaps", 0),
        "regime_labels_found": list((summary.get("regime_counts") or {}).keys()),
        "prediction_horizons_evaluated": sorted(prediction_metrics.keys()),
        "models_evaluated": sorted({model for results in prediction_metrics.values() for model in results.keys()}),
        "small_sample_warning_count": sum(1 for row in prediction_skill if row.get("small_sample_warning")),
        "excel_report_path": _relative_path(excel_path) if excel_path else None,
        "validation_report_path": _relative_path(validation_path),
        "warnings": _warnings(quality),
        "error_message": "",
    }


def _failed(campaign, timezone_name, resample, gap_tolerance, message, report=None):
    return {
        "status": "failed",
        "campaign_id": campaign.id,
        "campaign_name": campaign.name,
        "analysis_report_id": report.id if report else None,
        "run_timestamp": timezone_now(),
        "timezone": timezone_name,
        "resample": resample,
        "gap_tolerance": gap_tolerance,
        "warnings": [],
        "error_message": message,
    }


def _store_runner_result(report, result, output_path, excel_path, validation_path):
    summary = dict(report.summary_json or {})
    summary["paper1_run_summary"] = result
    summary["paper1_artifacts"] = {
        "output_dir": _relative_path(output_path),
        "excel_report": _relative_path(excel_path) if excel_path else None,
        "validation_report": _relative_path(validation_path),
    }
    report.summary_json = summary
    report.save(update_fields=["summary_json"])


def _output_dir(campaign_id, output_dir):
    if output_dir:
        return Path(output_dir)
    return settings.BASE_DIR / "paper_outputs" / f"campaign_{campaign_id}"


def _relative_output_dir(campaign_id):
    return f"paper_outputs/campaign_{campaign_id}"


def _relative_path(path):
    if not path:
        return None
    try:
        return str(Path(path).resolve().relative_to(settings.BASE_DIR.resolve()))
    except ValueError:
        return str(path)


def _validate_timezone(timezone_name):
    if not timezone_name:
        raise ValueError("Timezone cannot be empty.")
    ZoneInfo(timezone_name)


def _warnings(quality):
    return [
        f"{key}: {value}"
        for key, value in quality.items()
        if key in {"DUPLICATE_CONFLICT", "GAP_LONG", "DST_AMBIGUOUS"} and value
    ]


def _command_used(campaign_id, timezone_name, resample, gap_tolerance, rebuild_canonical, run_sensitivity, export_excel, output_path, profile, config_overrides):
    parts = [
        "python manage.py analyze_campaign",
        str(campaign_id),
        "--timezone",
        timezone_name,
        "--resample",
        resample,
        "--gap-tolerance",
        str(gap_tolerance),
    ]
    if rebuild_canonical:
        parts.append("--rebuild-canonical")
    if run_sensitivity:
        parts.append("--run-sensitivity")
    if export_excel:
        parts.append("--export-excel")
    parts.extend(["--profile", profile])
    for key, value in sorted((config_overrides or {}).items()):
        parts.extend(["--config-override", f"{key}={value}"])
    parts.extend(["--output-dir", _relative_path(output_path)])
    return " ".join(parts)


def timezone_now():
    return timezone.now().isoformat()
