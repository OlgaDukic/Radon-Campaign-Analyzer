from django.core.management.base import BaseCommand

from campaigns.services.campaign_comparison import compare_campaigns


class Command(BaseCommand):
    help = "Export a read-only standardized comparison table for completed radon campaign reports."

    def add_arguments(self, parser):
        parser.add_argument("--campaign-ids", nargs="+", type=int, required=True)
        parser.add_argument("--profile", default="")
        parser.add_argument("--output", default="")

    def handle(self, *args, **options):
        rows = compare_campaigns(
            options["campaign_ids"],
            output_path=options["output"] or None,
            profile=options["profile"] or None,
        )
        self.stdout.write(f"Compared campaigns: {len(rows)}")
        if options["output"]:
            self.stdout.write(f"Comparison CSV: {options['output']}")
