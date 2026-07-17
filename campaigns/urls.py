from django.urls import path

from . import views

app_name = "campaigns"

urlpatterns = [
    path("", views.campaign_list, name="campaign_list"),
    path("campaigns/new/", views.campaign_create, name="campaign_create"),
    path("campaigns/<int:pk>/", views.campaign_detail, name="campaign_detail"),
    path("campaigns/<int:pk>/quality/", views.campaign_quality, name="campaign_quality"),
    path("campaigns/<int:pk>/regimes/", views.campaign_regimes, name="campaign_regimes"),
    path("campaigns/<int:pk>/prediction/", views.campaign_prediction, name="campaign_prediction"),
    path("campaigns/<int:pk>/prediction/baseline-experiment/", views.baseline_prediction_experiment, name="baseline_prediction_experiment"),
    path("campaigns/<int:pk>/prediction/baseline-experiment.json", views.baseline_prediction_experiment_json, name="baseline_prediction_experiment_json"),
    path("campaigns/<int:pk>/prediction/baseline-experiment.csv", views.baseline_prediction_experiment_csv, name="baseline_prediction_experiment_csv"),
    path("campaigns/<int:pk>/prediction/baseline-experiment.xlsx", views.baseline_prediction_experiment_excel, name="baseline_prediction_experiment_excel"),
    path("campaigns/<int:pk>/prediction/apparent-dynamics-audit/", views.apparent_dynamics_audit, name="apparent_dynamics_audit"),
    path("campaigns/<int:pk>/prediction/apparent-dynamics-audit.json", views.apparent_dynamics_audit_json, name="apparent_dynamics_audit_json"),
    path("campaigns/<int:pk>/prediction/apparent-dynamics-audit.csv", views.apparent_dynamics_audit_csv, name="apparent_dynamics_audit_csv"),
    path("campaigns/<int:pk>/prediction/apparent-dynamics-audit.xlsx", views.apparent_dynamics_audit_excel, name="apparent_dynamics_audit_excel"),
    path("campaigns/<int:pk>/prediction/reduced-state-space-experiment/", views.reduced_state_space_experiment, name="reduced_state_space_experiment"),
    path("campaigns/<int:pk>/prediction/reduced-state-space-experiment.json", views.reduced_state_space_experiment_json, name="reduced_state_space_experiment_json"),
    path("campaigns/<int:pk>/prediction/reduced-state-space-experiment.csv", views.reduced_state_space_experiment_csv, name="reduced_state_space_experiment_csv"),
    path("campaigns/<int:pk>/prediction/reduced-state-space-experiment.xlsx", views.reduced_state_space_experiment_excel, name="reduced_state_space_experiment_excel"),
    path("campaigns/<int:pk>/sensitivity/", views.campaign_sensitivity, name="campaign_sensitivity"),
    path("campaigns/<int:pk>/research-context/", views.campaign_research_context, name="campaign_research_context"),
    path("campaigns/<int:pk>/research-context.json", views.research_context_json, name="research_context_json"),
    path("campaigns/<int:pk>/documented-events/", views.documented_events, name="documented_events"),
    path("campaigns/<int:pk>/documented-events.json", views.documented_events_json, name="documented_events_json"),
    path("campaigns/<int:pk>/documented-events.csv", views.documented_events_csv, name="documented_events_csv"),
    path("campaigns/<int:pk>/documented-events.xlsx", views.documented_events_excel, name="documented_events_excel"),
    path("campaigns/<int:pk>/provenance/", views.campaign_provenance, name="campaign_provenance"),
    path("campaigns/<int:pk>/reports/", views.campaign_reports, name="campaign_reports"),
    path("campaigns/<int:pk>/upload/", views.upload_file, name="upload_file"),
    path("campaigns/<int:pk>/analyze/", views.run_analysis, name="run_analysis"),
    path("campaigns/<int:campaign_id>/run-analysis/", views.run_campaign_analysis, name="run_campaign_analysis"),
    path("campaigns/<int:campaign_id>/paper-output/<str:filename>/", views.download_paper_output, name="download_paper_output"),
    path("campaigns/<int:pk>/chart-data/", views.campaign_chart_data, name="campaign_chart_data"),
    path("campaigns/<int:pk>/measurements/", views.campaign_measurements, name="campaign_measurements"),
    path("campaigns/<int:pk>/gaps/", views.campaign_gaps, name="campaign_gaps"),
    path("campaigns/<int:pk>/episodes/", views.campaign_episodes, name="campaign_episodes"),
    path("campaigns/<int:pk>/export.xlsx", views.export_excel_report, name="export_excel_report"),
]
