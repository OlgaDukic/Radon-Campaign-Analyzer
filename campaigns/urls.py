from django.urls import path

from . import views

app_name = "campaigns"

urlpatterns = [
    path("", views.campaign_list, name="campaign_list"),
    path("campaigns/new/", views.campaign_create, name="campaign_create"),
    path("campaigns/<int:pk>/", views.campaign_detail, name="campaign_detail"),
    path("campaigns/<int:pk>/upload/", views.upload_file, name="upload_file"),
    path("campaigns/<int:pk>/analyze/", views.run_analysis, name="run_analysis"),
    path("campaigns/<int:pk>/export.xlsx", views.export_excel_report, name="export_excel_report"),
]
