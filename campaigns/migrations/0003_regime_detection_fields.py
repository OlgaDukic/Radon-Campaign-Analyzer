from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("campaigns", "0002_analysis_pipeline_fields"),
    ]

    operations = [
        migrations.AddField(
            model_name="measurement",
            name="regime",
            field=models.CharField(blank=True, max_length=40),
        ),
        migrations.AddField(
            model_name="analysisreport",
            name="html_report",
            field=models.TextField(blank=True),
        ),
    ]
