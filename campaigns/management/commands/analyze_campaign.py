from django.core.management.base import BaseCommand, CommandError

from campaigns.services.paper1_analysis_runner import run_paper1_analysis


class Command(BaseCommand):
    help = "Run a reproducible local research analysis for a radon campaign."

    def add_arguments(self, parser):
        parser.add_argument("campaign_id", type=int)
        parser.add_argument("--timezone", default="Europe/Rome")
        parser.add_argument("--resample", default="1H")
        parser.add_argument("--gap-tolerance", type=float, default=1.5)
        parser.add_argument("--rebuild-canonical", action="store_true")
        parser.add_argument("--run-sensitivity", action="store_true")
        parser.add_argument("--export-excel", action="store_true")
        parser.add_argument("--output-dir", default=".")

    def handle(self, *args, **options):
        result = run_paper1_analysis(
            campaign_id=options["campaign_id"],
            timezone=options["timezone"],
            resample=options["resample"],
            gap_tolerance=options["gap_tolerance"],
            rebuild_canonical=options["rebuild_canonical"],
            run_sensitivity=options["run_sensitivity"],
            export_excel=options["export_excel"],
            output_dir=options["output_dir"],
            requested_by="management_command",
        )
        if result["status"] != "success":
            raise CommandError(result.get("error_message") or "Paper 1 analysis failed.")

        self.stdout.write(f"Campaign id: {result['campaign_id']}")
        self.stdout.write(f"Source files: {result.get('source_file_count', 'N/A')}")
        self.stdout.write(f"Raw records: {result['raw_imported_rows']}")
        self.stdout.write(f"Canonical records: {result['canonical_valid_rows']}")
        self.stdout.write(f"Major quality warnings: {result['warnings'] or 'none'}")
        self.stdout.write(f"Output report id: {result['analysis_report_id']}")
        if result.get("excel_report_path"):
            self.stdout.write(f"Excel export path: {result['excel_report_path']}")
        if result.get("validation_report_path"):
            self.stdout.write(f"Validation report path: {result['validation_report_path']}")
