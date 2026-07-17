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


class NullableChoice(models.TextChoices):
    YES = "YES", "Yes"
    NO = "NO", "No"
    UNKNOWN = "UNKNOWN", "Unknown"


class EvidenceStatus(models.TextChoices):
    UNKNOWN = "UNKNOWN", "Unknown"
    ASSUMED = "ASSUMED", "Assumed"
    ESTIMATED = "ESTIMATED", "Estimated"
    PROVIDED = "PROVIDED", "Provided"
    VERIFIED = "VERIFIED", "Verified"


class RoomVolumeSource(models.TextChoices):
    CALCULATED = "CALCULATED", "Calculated"
    REPORTED = "REPORTED", "Reported"
    ESTIMATED = "ESTIMATED", "Estimated"
    USER_SELECTED = "USER_SELECTED", "User selected"
    UNKNOWN = "UNKNOWN", "Unknown"


class EventLogAvailability(models.TextChoices):
    DOCUMENTED = "DOCUMENTED", "Documented"
    PARTIAL = "PARTIAL", "Partial"
    UNAVAILABLE = "UNAVAILABLE", "Unavailable"
    NATURALISTIC_FREQUENT_INTERVENTIONS = "NATURALISTIC_FREQUENT_INTERVENTIONS", "Naturalistic frequent interventions"


class CampaignResearchContext(models.Model):
    campaign = models.OneToOneField(Campaign, on_delete=models.CASCADE, related_name="research_context")
    floor_level = models.IntegerField(null=True, blank=True)
    height_above_ground_m = models.DecimalField(max_digits=7, decimal_places=2, null=True, blank=True)
    direct_connection_to_soil = models.CharField(max_length=20, choices=NullableChoice.choices, blank=True)
    room_volume_m3 = models.DecimalField(max_digits=10, decimal_places=3, null=True, blank=True)
    room_volume_source = models.CharField(max_length=30, choices=RoomVolumeSource.choices, blank=True)
    dominant_material = models.CharField(max_length=160, blank=True)
    sensor_height_m = models.DecimalField(max_digits=7, decimal_places=3, null=True, blank=True)
    distance_from_nearest_opening_m = models.DecimalField(max_digits=7, decimal_places=3, null=True, blank=True)
    sensor_moved_during_campaign = models.CharField(max_length=20, choices=NullableChoice.choices, blank=True)
    event_log_availability = models.CharField(max_length=60, choices=EventLogAvailability.choices, blank=True)
    notes = models.TextField(blank=True)
    evidence_status = models.CharField(max_length=20, choices=EvidenceStatus.choices, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "campaign research context"
        verbose_name_plural = "campaign research contexts"

    def __str__(self):
        return f"{self.campaign} research context"


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
