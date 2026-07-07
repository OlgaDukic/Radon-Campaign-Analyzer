from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("campaigns", "0001_initial"),
    ]

    operations = [
        migrations.AlterField(
            model_name="measurement",
            name="radon_bq_m3",
            field=models.DecimalField(blank=True, decimal_places=2, max_digits=10, null=True),
        ),
        migrations.AddField(
            model_name="measurement",
            name="temperature_c",
            field=models.DecimalField(blank=True, decimal_places=2, max_digits=7, null=True),
        ),
        migrations.AddField(
            model_name="measurement",
            name="humidity_percent",
            field=models.DecimalField(blank=True, decimal_places=2, max_digits=7, null=True),
        ),
        migrations.AddField(
            model_name="measurement",
            name="pressure_hpa",
            field=models.DecimalField(blank=True, decimal_places=2, max_digits=8, null=True),
        ),
        migrations.AddField(
            model_name="measurement",
            name="segment_id",
            field=models.PositiveIntegerField(default=1),
        ),
        migrations.AddField(
            model_name="analysisreport",
            name="summary_json",
            field=models.JSONField(blank=True, default=dict),
        ),
    ]
