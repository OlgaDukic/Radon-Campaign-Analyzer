from django.db import models


class Campaign(models.Model):
    name = models.CharField(max_length=200)
    location = models.CharField(max_length=255, blank=True)
    description = models.TextField(blank=True)
    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.name


class UploadedFile(models.Model):
    campaign = models.ForeignKey(
        Campaign,
        on_delete=models.CASCADE,
        related_name="uploaded_files",
    )
    file = models.FileField(upload_to="campaign_uploads/")
    original_name = models.CharField(max_length=255)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-uploaded_at"]

    def __str__(self):
        return self.original_name


class Measurement(models.Model):
    campaign = models.ForeignKey(
        Campaign,
        on_delete=models.CASCADE,
        related_name="measurements",
    )
    uploaded_file = models.ForeignKey(
        UploadedFile,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="measurements",
    )
    measured_at = models.DateTimeField(null=True, blank=True)
    radon_bq_m3 = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    temperature_c = models.DecimalField(max_digits=7, decimal_places=2, null=True, blank=True)
    humidity_percent = models.DecimalField(max_digits=7, decimal_places=2, null=True, blank=True)
    pressure_hpa = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    segment_id = models.PositiveIntegerField(default=1)
    regime = models.CharField(max_length=40, blank=True)
    room_name = models.CharField(max_length=120, blank=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["measured_at", "id"]

    def __str__(self):
        return f"{self.campaign} - {self.radon_bq_m3} Bq/m3"


class AnalysisReport(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        COMPLETE = "complete", "Complete"
        FAILED = "failed", "Failed"

    campaign = models.ForeignKey(
        Campaign,
        on_delete=models.CASCADE,
        related_name="analysis_reports",
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
    )
    summary = models.TextField(blank=True)
    summary_json = models.JSONField(default=dict, blank=True)
    html_report = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.campaign} analysis ({self.status})"
