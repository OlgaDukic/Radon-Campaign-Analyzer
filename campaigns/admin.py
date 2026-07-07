from django.contrib import admin

from .models import AnalysisReport, Campaign, Measurement, UploadedFile


@admin.register(Campaign)
class CampaignAdmin(admin.ModelAdmin):
    list_display = ("name", "location", "start_date", "end_date", "created_at")
    search_fields = ("name", "location")


@admin.register(UploadedFile)
class UploadedFileAdmin(admin.ModelAdmin):
    list_display = ("campaign", "original_name", "uploaded_at")
    list_filter = ("uploaded_at",)


@admin.register(Measurement)
class MeasurementAdmin(admin.ModelAdmin):
    list_display = ("campaign", "measured_at", "radon_bq_m3", "room_name")
    list_filter = ("campaign", "measured_at")


@admin.register(AnalysisReport)
class AnalysisReportAdmin(admin.ModelAdmin):
    list_display = ("campaign", "status", "created_at")
    list_filter = ("status", "created_at")
