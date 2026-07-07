from decimal import Decimal
from datetime import timedelta
from io import BytesIO

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from openpyxl import Workbook, load_workbook

from .models import AnalysisReport, Campaign, Measurement, UploadedFile
from .services.analysis import run_campaign_analysis
from .services.ingestion import parse_decimal, read_uploaded_file
from .services.prediction import evaluate_prediction_models
from .services.regimes import classify_regimes
from .services.reports import build_summary


class CampaignModelTests(TestCase):
    def test_campaign_string_representation(self):
        campaign = Campaign.objects.create(name="Winter Survey")

        self.assertEqual(str(campaign), "Winter Survey")

    def test_measurement_string_representation(self):
        campaign = Campaign.objects.create(name="School Survey")
        measurement = Measurement.objects.create(
            campaign=campaign,
            radon_bq_m3=Decimal("123.45"),
            room_name="Classroom A",
        )

        self.assertIn("123.45 Bq/m3", str(measurement))

    def test_analysis_service_creates_empty_report_without_files(self):
        campaign = Campaign.objects.create(name="Baseline Campaign")

        report = run_campaign_analysis(campaign)

        self.assertEqual(report.status, AnalysisReport.Status.COMPLETE)
        self.assertEqual(report.summary_json["measurement_count"], 0)
        self.assertIn("Research prototype analysis complete", report.summary)


class CampaignViewTests(TestCase):
    def test_campaign_list_view(self):
        Campaign.objects.create(name="Residential Pilot")

        response = self.client.get(reverse("campaigns:campaign_list"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Residential Pilot")

    def test_create_campaign_view(self):
        response = self.client.post(
            reverse("campaigns:campaign_create"),
            {"name": "Office Pilot", "location": "Nis"},
        )

        campaign = Campaign.objects.get(name="Office Pilot")
        self.assertRedirects(response, reverse("campaigns:campaign_detail", args=[campaign.pk]))

    def test_campaign_detail_view(self):
        campaign = Campaign.objects.create(name="Lab Pilot")

        response = self.client.get(reverse("campaigns:campaign_detail", args=[campaign.pk]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Lab Pilot")
        self.assertContains(response, "Run analysis")

    def test_upload_csv_file_to_campaign(self):
        campaign = Campaign.objects.create(name="CSV Campaign")
        upload = SimpleUploadedFile(
            "measurements.csv",
            b"measured_at,radon_bq_m3\n2026-01-01,100\n",
            content_type="text/csv",
        )

        response = self.client.post(
            reverse("campaigns:upload_file", args=[campaign.pk]),
            {"file": upload},
        )

        self.assertRedirects(response, reverse("campaigns:campaign_detail", args=[campaign.pk]))
        uploaded_file = UploadedFile.objects.get(campaign=campaign)
        self.assertEqual(uploaded_file.original_name, "measurements.csv")

    def test_run_analysis_view(self):
        campaign = Campaign.objects.create(name="Analysis Campaign")

        response = self.client.post(reverse("campaigns:run_analysis", args=[campaign.pk]))

        self.assertRedirects(response, reverse("campaigns:campaign_detail", args=[campaign.pk]))
        self.assertEqual(campaign.analysis_reports.count(), 1)

    def test_campaign_detail_renders_research_dashboard(self):
        campaign = Campaign.objects.create(name="Dashboard Campaign")
        report = AnalysisReport.objects.create(
            campaign=campaign,
            status=AnalysisReport.Status.COMPLETE,
            summary="Research prototype analysis complete.",
            summary_json={
                "measurement_count": 3,
                "segment_count": 1,
                "gap_count": 1,
                "regime_counts": {"stable_low": 1, "rising": 2},
                "prediction_metrics": {
                    "1h": {
                        "naive_baseline": {"samples": 2, "mae": 8.0, "rmse": 9.0},
                        "ridge": {"samples": 2, "mae": 4.0, "rmse": 5.0},
                    }
                },
                "gaps": [{"from": "2026-01-01T01:00:00+00:00", "to": "2026-01-01T03:00:00+00:00", "minutes": 120.0}],
                "segments": [
                    {
                        "segment_id": 1,
                        "measurement_count": 3,
                        "segment_label": "elevated_dynamic",
                        "percent_above_100": 66.7,
                        "percent_above_200": 0.0,
                        "dynamic_percent": 66.7,
                        "interpretation_text": "Radon is frequently above 100 Bq/m3.",
                        "statistics": {"radon_bq_m3": {"mean": 120.0, "max": 150.0}},
                    }
                ],
                "ingestion_debug": [
                    {
                        "filename": "dashboard.xlsx",
                        "detected_sheets": ["Measurements"],
                        "raw_rows_read": 5,
                        "detected_header_row": 2,
                        "detected_columns": ["Date and time", "Radon"],
                        "mapped_columns": {
                            "timestamp": "Date and time",
                            "radon": "Radon",
                            "temperature": None,
                            "humidity": None,
                            "pressure": None,
                        },
                        "parsed_measurement_rows": 3,
                        "skipped_reason": "",
                    }
                ],
            },
            html_report="<article>Generated report</article>",
        )
        start = timezone.datetime(2026, 1, 1, 0, 0, tzinfo=timezone.get_current_timezone())
        for index, value in enumerate([90, 120, 150]):
            Measurement.objects.create(
                campaign=campaign,
                measured_at=start + timedelta(hours=index),
                radon_bq_m3=Decimal(str(value)),
                segment_id=1,
                regime="rising" if index else "stable_low",
            )

        response = self.client.get(reverse("campaigns:campaign_detail", args=[campaign.pk]))

        self.assertEqual(report, response.context["latest_report"])
        self.assertContains(response, "Dashboard Summary")
        self.assertContains(response, "Uploaded files")
        self.assertContains(response, "Imported measurements")
        self.assertContains(response, "Mean radon")
        self.assertContains(response, "Max radon")
        self.assertContains(response, "Data Quality Summary")
        self.assertContains(response, "Segment Interpretation")
        self.assertContains(response, "elevated_dynamic")
        self.assertContains(response, "Regime Counts")
        self.assertContains(response, "Prediction Metrics")
        self.assertContains(response, "naive baseline")
        self.assertContains(response, "Detected Gaps")
        self.assertContains(response, "Ingestion Diagnostics")
        self.assertContains(response, "dashboard.xlsx")
        self.assertContains(response, "Radon Time Series")
        self.assertContains(response, "<svg", html=False)

    def test_campaign_detail_dashboard_handles_missing_summary_fields(self):
        campaign = Campaign.objects.create(name="Sparse Dashboard")
        AnalysisReport.objects.create(
            campaign=campaign,
            status=AnalysisReport.Status.COMPLETE,
            summary="Sparse report.",
            summary_json={"regime_counts": {}, "segments": []},
        )

        response = self.client.get(reverse("campaigns:campaign_detail", args=[campaign.pk]))

        self.assertContains(response, "Dashboard Summary")
        self.assertContains(response, "N/A")
        self.assertContains(response, "Radon Time Series")

    def test_campaign_detail_links_to_excel_report(self):
        campaign = Campaign.objects.create(name="Excel Link Campaign")
        AnalysisReport.objects.create(
            campaign=campaign,
            status=AnalysisReport.Status.COMPLETE,
            summary="Report ready.",
            summary_json={},
        )

        response = self.client.get(reverse("campaigns:campaign_detail", args=[campaign.pk]))

        self.assertContains(response, "Download Excel Report")
        self.assertContains(response, reverse("campaigns:export_excel_report", args=[campaign.pk]))


class AnalysisPipelineTests(TestCase):
    def test_parse_decimal_accepts_decimal_commas(self):
        self.assertEqual(parse_decimal("123,45"), Decimal("123.45"))

    def test_csv_pipeline_merges_duplicates_segments_and_stores_measurements(self):
        campaign = Campaign.objects.create(name="Aranet CSV")
        UploadedFile.objects.create(
            campaign=campaign,
            original_name="aranet.csv",
            file=SimpleUploadedFile(
                "aranet.csv",
                (
                    "Time;Radon (Bq/m3);Temperature (C);Humidity (%);Pressure (hPa)\n"
                    "2026-01-01 00:00;100,5;20,1;45,2;1001,5\n"
                    "2026-01-01 00:00;;20,3;;\n"
                    "2026-01-01 00:30;110;20,4;46;1002\n"
                    "2026-01-01 02:00;130;21;48;1004\n"
                ).encode("utf-8"),
                content_type="text/csv",
            ),
        )

        report = run_campaign_analysis(campaign)

        self.assertEqual(report.status, AnalysisReport.Status.COMPLETE)
        self.assertEqual(report.summary_json["measurement_count"], 3)
        self.assertEqual(report.summary_json["segment_count"], 2)
        self.assertEqual(report.summary_json["gap_count"], 1)

        measurements = list(campaign.measurements.order_by("measured_at"))
        self.assertEqual(len(measurements), 3)
        self.assertEqual(measurements[0].radon_bq_m3, Decimal("100.50"))
        self.assertEqual(measurements[0].temperature_c, Decimal("20.10"))
        self.assertEqual([measurement.segment_id for measurement in measurements], [1, 1, 2])

        first_segment = report.summary_json["segments"][0]
        self.assertEqual(first_segment["statistics"]["radon_bq_m3"]["count"], 2)
        self.assertEqual(first_segment["statistics"]["radon_bq_m3"]["mean"], 105.25)

    def test_xlsx_pipeline_detects_aranet_columns(self):
        campaign = Campaign.objects.create(name="Aranet XLSX")
        workbook = Workbook()
        worksheet = workbook.active
        worksheet.append(["Date time", "Radon", "Temp", "Humidity", "Pressure"])
        worksheet.append(["2026-02-01 10:00", "90", "19,5", "44", "998"])
        worksheet.append(["2026-02-01 10:30", "95", "19,7", "45", "999"])
        buffer = BytesIO()
        workbook.save(buffer)

        UploadedFile.objects.create(
            campaign=campaign,
            original_name="aranet.xlsx",
            file=SimpleUploadedFile(
                "aranet.xlsx",
                buffer.getvalue(),
                content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            ),
        )

        report = run_campaign_analysis(campaign)

        self.assertEqual(report.status, AnalysisReport.Status.COMPLETE)
        self.assertEqual(report.summary_json["measurement_count"], 2)
        self.assertEqual(campaign.measurements.count(), 2)
        self.assertEqual(campaign.measurements.first().temperature_c, Decimal("19.50"))

    def test_xlsx_pipeline_skips_metadata_rows_before_aranet_header(self):
        campaign = Campaign.objects.create(name="Aranet Metadata XLSX")
        workbook = Workbook()
        metadata = workbook.active
        metadata.title = "About"
        metadata.append(["Aranet export"])
        metadata.append(["Device", "Airthings-like metadata"])
        data = workbook.create_sheet("Measurements")
        data.append(["Aranet4 data export"])
        data.append(["Sensor name", "Living room"])
        data.append(["Serial number", "12345"])
        data.append([])
        data.append(["Date and time", "Radon concentration (Bq/m³)", "Temperature (°C)", "Humidity (%)", "Pressure (hPa)"])
        data.append(["2026-05-01 08:00", "101,5", "20,2", "44,1", "1000,5"])
        data.append(["2026-05-01 09:00", "110,0", "20,3", "44,5", "1001,0"])
        buffer = BytesIO()
        workbook.save(buffer)

        uploaded = UploadedFile.objects.create(
            campaign=campaign,
            original_name="aranet-metadata.xlsx",
            file=SimpleUploadedFile(
                "aranet-metadata.xlsx",
                buffer.getvalue(),
                content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            ),
        )

        rows, column_map, debug = read_uploaded_file(uploaded)
        report = run_campaign_analysis(campaign)

        self.assertEqual(len(rows), 2)
        self.assertEqual(column_map.timestamp, "Date and time")
        self.assertEqual(debug["detected_sheets"], ["About", "Measurements"])
        self.assertEqual(debug["selected_sheet"], "Measurements")
        self.assertEqual(debug["detected_header_row"], 5)
        self.assertEqual(debug["mapped_columns"]["radon"], "Radon concentration (Bq/m³)")
        self.assertEqual(debug["parsed_measurement_rows"], 2)
        self.assertEqual(report.summary_json["measurement_count"], 2)
        self.assertEqual(report.summary_json["ingestion_debug"][0]["selected_sheet"], "Measurements")
        self.assertEqual(campaign.measurements.count(), 2)

    def test_no_measurements_report_shows_file_failure_reason(self):
        campaign = Campaign.objects.create(name="Bad Aranet XLSX")
        workbook = Workbook()
        worksheet = workbook.active
        worksheet.title = "Export"
        worksheet.append(["Aranet metadata only"])
        worksheet.append(["No table here"])
        buffer = BytesIO()
        workbook.save(buffer)
        UploadedFile.objects.create(
            campaign=campaign,
            original_name="bad-aranet.xlsx",
            file=SimpleUploadedFile(
                "bad-aranet.xlsx",
                buffer.getvalue(),
                content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            ),
        )

        report = run_campaign_analysis(campaign)

        self.assertEqual(report.summary_json["measurement_count"], 0)
        self.assertIn("no measurements were imported", report.summary.lower())
        self.assertEqual(report.summary_json["ingestion_debug"][0]["filename"], "bad-aranet.xlsx")
        self.assertIn("Could not find a header row", report.summary_json["ingestion_debug"][0]["skipped_reason"])
        self.assertIn("Ingestion Diagnostics", report.html_report)


class RegimeClassificationTests(TestCase):
    def test_classify_regimes_uses_one_hour_radon_change(self):
        start = timezone.datetime(2026, 3, 1, 0, 0, tzinfo=timezone.get_current_timezone())
        values = [
            Decimal("80"),
            Decimal("90"),
            Decimal("130"),
            Decimal("260"),
            Decimal("310"),
            Decimal("170"),
            Decimal("130"),
            Decimal("150"),
        ]
        rows = [
            {
                "measured_at": start + timedelta(hours=index),
                "radon_bq_m3": value,
                "temperature_c": None,
                "humidity_percent": None,
                "pressure_hpa": None,
                "segment_id": 1,
            }
            for index, value in enumerate(values)
        ]

        classified = classify_regimes(rows)

        self.assertEqual(
            [row["regime"] for row in classified],
            [
                "stable_low",
                "stable_low",
                "rising",
                "sudden_rise",
                "high_episode",
                "sudden_drop",
                "falling",
                "stable_elevated",
            ],
        )

    def test_pipeline_stores_regimes_and_report_statistics(self):
        campaign = Campaign.objects.create(name="Regime Campaign")
        UploadedFile.objects.create(
            campaign=campaign,
            original_name="regimes.csv",
            file=SimpleUploadedFile(
                "regimes.csv",
                (
                    "Time,Radon,Temperature,Humidity,Pressure\n"
                    "2026-03-01 00:00,80,20,45,1000\n"
                    "2026-03-01 01:00,90,20,45,1000\n"
                    "2026-03-01 02:00,130,20,45,1000\n"
                    "2026-03-01 03:00,260,20,45,1000\n"
                    "2026-03-01 04:00,310,20,45,1000\n"
                    "2026-03-01 05:00,170,20,45,1000\n"
                    "2026-03-01 06:00,130,20,45,1000\n"
                    "2026-03-01 07:00,150,20,45,1000\n"
                ).encode("utf-8"),
                content_type="text/csv",
            ),
        )

        report = run_campaign_analysis(campaign)

        self.assertEqual(report.summary_json["regime_counts"]["stable_low"], 2)
        self.assertEqual(report.summary_json["regime_counts"]["high_episode"], 1)
        self.assertEqual(report.summary_json["segments"][0]["dominant_regime"], "stable_low")
        self.assertIn("Per-Measurement Regime Counts", report.html_report)
        self.assertIn("high_episode", report.html_report)
        self.assertEqual(
            list(campaign.measurements.order_by("measured_at").values_list("regime", flat=True)),
            [
                "stable_low",
                "stable_low",
                "rising",
                "sudden_rise",
                "high_episode",
                "sudden_drop",
                "falling",
                "stable_elevated",
            ],
        )

    def test_campaign_detail_exposes_regime_statistics(self):
        campaign = Campaign.objects.create(name="Visible Regimes")
        AnalysisReport.objects.create(
            campaign=campaign,
            status=AnalysisReport.Status.COMPLETE,
            summary="Analysis complete.",
            summary_json={"regime_counts": {"stable_low": 1}, "segments": []},
            html_report="<article><h1>Regime Statistics</h1></article>",
        )

        response = self.client.get(reverse("campaigns:campaign_detail", args=[campaign.pk]))

        self.assertContains(response, "Regime Counts")
        self.assertContains(response, "stable_low")
        self.assertContains(response, "Generated HTML Report")


class SegmentInterpretationTests(TestCase):
    def test_segment_interpretation_labels_exposure_and_dynamics(self):
        start = timezone.datetime(2026, 6, 1, 0, 0, tzinfo=timezone.get_current_timezone())
        rows = []
        rows.extend(_segment_rows(start, 1, [70, 75, 80, 78], ["stable_low"] * 4))
        rows.extend(_segment_rows(start, 2, [70, 82, 95, 105, 90], ["stable_low", "rising", "falling", "stable_elevated", "stable_low"]))
        rows.extend(_segment_rows(start, 3, [105, 125, 135, 145], ["stable_elevated", "rising", "stable_elevated", "falling"]))
        rows.extend(_segment_rows(start, 4, [120, 220, 330, 180], ["stable_elevated", "rising", "high_episode", "falling"]))
        rows.extend(_segment_rows(start, 5, [90, 95], ["stable_low", "stable_low"]))

        summary = build_summary(rows, gaps=[], uploaded_file_count=1)
        segments = {segment["segment_id"]: segment for segment in summary["segments"]}

        self.assertEqual(segments[1]["segment_label"], "low_stable")
        self.assertEqual(segments[1]["percent_above_100"], 0.0)
        self.assertEqual(segments[1]["dynamic_percent"], 0.0)
        self.assertEqual(segments[2]["segment_label"], "low_dynamic")
        self.assertEqual(segments[2]["percent_above_100"], 20.0)
        self.assertEqual(segments[2]["dynamic_percent"], 40.0)
        self.assertEqual(segments[3]["segment_label"], "elevated_dynamic")
        self.assertEqual(segments[3]["percent_above_100"], 100.0)
        self.assertEqual(segments[4]["segment_label"], "high_episode")
        self.assertEqual(segments[4]["percent_above_200"], 50.0)
        self.assertEqual(segments[5]["segment_label"], "insufficient_data")
        self.assertIn("Fewer than three", segments[5]["interpretation_text"])

    def test_pipeline_report_includes_segment_interpretation(self):
        campaign = Campaign.objects.create(name="Segment Interpretation Campaign")
        UploadedFile.objects.create(
            campaign=campaign,
            original_name="segments.csv",
            file=SimpleUploadedFile(
                "segments.csv",
                (
                    "Time,Radon,Temperature,Humidity,Pressure\n"
                    "2026-06-01 00:00,90,20,45,1000\n"
                    "2026-06-01 01:00,115,20,45,1000\n"
                    "2026-06-01 02:00,140,20,45,1000\n"
                    "2026-06-01 03:00,165,20,45,1000\n"
                ).encode("utf-8"),
                content_type="text/csv",
            ),
        )

        report = run_campaign_analysis(campaign)
        segment = report.summary_json["segments"][0]

        self.assertEqual(segment["segment_label"], "elevated_dynamic")
        self.assertIn("percent_above_100", segment)
        self.assertIn("dynamic_percent", segment)
        self.assertIn("Segment Interpretation", report.html_report)
        self.assertIn("naive baseline", report.html_report)


class PredictionModelTests(TestCase):
    def test_prediction_models_compute_metrics_for_1h_and_6h_horizons(self):
        start = timezone.datetime(2026, 4, 1, 0, 0, tzinfo=timezone.get_current_timezone())
        rows = [
            {
                "measured_at": start + timedelta(hours=index),
                "radon_bq_m3": Decimal(str(100 + index * 10)),
                "segment_id": 1,
            }
            for index in range(10)
        ]

        metrics = evaluate_prediction_models(rows)

        self.assertEqual(metrics["1h"]["naive_baseline"]["samples"], 7)
        self.assertEqual(metrics["1h"]["naive_baseline"]["mae"], 10.0)
        self.assertEqual(metrics["1h"]["ridge"]["samples"], 7)
        self.assertLess(metrics["1h"]["ridge"]["mae"], metrics["1h"]["naive_baseline"]["mae"])
        self.assertEqual(metrics["6h"]["naive_baseline"]["samples"], 2)
        self.assertEqual(metrics["6h"]["naive_baseline"]["mae"], 60.0)

    def test_prediction_samples_do_not_cross_segment_boundaries(self):
        start = timezone.datetime(2026, 4, 1, 0, 0, tzinfo=timezone.get_current_timezone())
        rows = [
            {
                "measured_at": start + timedelta(hours=index),
                "radon_bq_m3": Decimal(str(100 + index * 5)),
                "segment_id": 1,
            }
            for index in range(3)
        ]
        rows.extend(
            {
                "measured_at": start + timedelta(hours=10 + index),
                "radon_bq_m3": Decimal(str(200 + index * 5)),
                "segment_id": 2,
            }
            for index in range(3)
        )

        metrics = evaluate_prediction_models(rows)

        self.assertEqual(metrics["1h"]["naive_baseline"]["samples"], 0)
        self.assertEqual(metrics["6h"]["naive_baseline"]["samples"], 0)

    def test_pipeline_stores_prediction_metrics_and_report_output(self):
        campaign = Campaign.objects.create(name="Prediction Campaign")
        csv_lines = ["Time,Radon,Temperature,Humidity,Pressure"]
        for index in range(10):
            csv_lines.append(
                f"2026-04-01 {index:02d}:00,{100 + index * 10},20,45,1000"
            )
        UploadedFile.objects.create(
            campaign=campaign,
            original_name="prediction.csv",
            file=SimpleUploadedFile(
                "prediction.csv",
                "\n".join(csv_lines).encode("utf-8"),
                content_type="text/csv",
            ),
        )

        report = run_campaign_analysis(campaign)

        self.assertEqual(report.summary_json["prediction_metrics"]["1h"]["naive_baseline"]["samples"], 7)
        self.assertEqual(report.summary_json["prediction_metrics"]["6h"]["naive_baseline"]["samples"], 2)
        self.assertIn("Model Performance", report.html_report)
        self.assertIn("ridge", report.html_report)

    def test_campaign_detail_exposes_model_performance(self):
        campaign = Campaign.objects.create(name="Visible Models")
        AnalysisReport.objects.create(
            campaign=campaign,
            status=AnalysisReport.Status.COMPLETE,
            summary="Analysis complete.",
            summary_json={
                "regime_counts": {},
                "prediction_metrics": {
                    "1h": {
                        "naive_baseline": {"samples": 3, "mae": 5.0, "rmse": 6.0},
                        "ridge": {"samples": 3, "mae": 2.0, "rmse": 3.0},
                    }
                },
                "segments": [],
            },
            html_report="<article><h1>Model Performance</h1></article>",
        )

        response = self.client.get(reverse("campaigns:campaign_detail", args=[campaign.pk]))

        self.assertContains(response, "Model Performance")
        self.assertContains(response, "naive_baseline")
        self.assertContains(response, "ridge")


class ExcelExportTests(TestCase):
    def test_excel_report_export_returns_workbook(self):
        campaign = Campaign.objects.create(name="Export Campaign", location="Lab A")
        UploadedFile.objects.create(
            campaign=campaign,
            original_name="export.csv",
            file=SimpleUploadedFile("export.csv", b"Time,Radon\n2026-01-01 00:00,100\n"),
        )
        report = AnalysisReport.objects.create(
            campaign=campaign,
            status=AnalysisReport.Status.COMPLETE,
            summary="Research prototype analysis complete.",
            summary_json={
                "measurement_count": 2,
                "segment_count": 1,
                "gap_count": 1,
                "regime_counts": {"stable_low": 1, "rising": 1},
                "prediction_metrics": {
                    "1h": {
                        "naive_baseline": {"samples": 1, "mae": 10.0, "rmse": 10.0},
                        "ridge": {"samples": 1, "mae": 5.0, "rmse": 6.0},
                    }
                },
                "gaps": [{"from": "2026-01-01T00:00:00+00:00", "to": "2026-01-01T02:00:00+00:00", "minutes": 120}],
                "segments": [
                    {
                        "segment_id": 1,
                        "start": "2026-01-01T00:00:00+00:00",
                        "end": "2026-01-01T01:00:00+00:00",
                        "segment_label": "low_dynamic",
                        "dominant_regime": "rising",
                        "interpretation_text": "Low but dynamic.",
                        "statistics": {"radon_bq_m3": {"mean": 105.0, "max": 110.0}},
                    }
                ],
                "ingestion_debug": [
                    {
                        "filename": "export.csv",
                        "parsed_measurement_rows": 2,
                        "skipped_rows": 0,
                        "skipped_reason": "",
                        "detected_sheets": ["CSV"],
                        "detected_header_row": 1,
                        "mapped_columns": {"timestamp": "Time", "radon": "Radon"},
                    }
                ],
            },
        )
        start = timezone.datetime(2026, 1, 1, 0, 0, tzinfo=timezone.get_current_timezone())
        Measurement.objects.create(
            campaign=campaign,
            measured_at=start,
            radon_bq_m3=Decimal("100"),
            temperature_c=Decimal("20.1"),
            humidity_percent=Decimal("45.0"),
            pressure_hpa=Decimal("1001.0"),
            segment_id=1,
            regime="stable_low",
        )
        Measurement.objects.create(
            campaign=campaign,
            measured_at=start + timedelta(hours=1),
            radon_bq_m3=Decimal("110"),
            segment_id=1,
            regime="rising",
        )

        response = self.client.get(reverse("campaigns:export_excel_report", args=[campaign.pk]))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response["Content-Type"],
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        self.assertIn(f"radon_campaign_{campaign.pk}_report.xlsx", response["Content-Disposition"])

        workbook = load_workbook(BytesIO(response.content))
        self.assertEqual(
            workbook.sheetnames,
            [
                "Summary",
                "Segments",
                "Regime Counts",
                "Prediction Metrics",
                "Gaps",
                "Ingestion Diagnostics",
                "Measurements",
            ],
        )
        self.assertEqual(workbook["Summary"]["B2"].value, "Export Campaign")
        self.assertEqual(workbook["Summary"]["B3"].value, "Lab A")
        self.assertEqual(workbook["Summary"]["B6"].value, 2)
        self.assertEqual(workbook["Summary"]["B7"].value, 1)
        self.assertEqual(workbook["Segments"]["A2"].value, 1)
        self.assertEqual(workbook["Segments"]["G2"].value, "low_dynamic")
        self.assertEqual(workbook["Regime Counts"]["A2"].value, "stable_low")
        self.assertEqual(workbook["Prediction Metrics"]["A2"].value, "1h")
        self.assertEqual(workbook["Gaps"]["C2"].value, 120)
        self.assertEqual(workbook["Ingestion Diagnostics"]["A2"].value, "export.csv")
        self.assertEqual(workbook["Measurements"]["B2"].value, 100.0)
        for sheet_name in workbook.sheetnames:
            self.assertEqual(workbook[sheet_name].freeze_panes, "A2")
            self.assertTrue(workbook[sheet_name].auto_filter.ref)
            self.assertTrue(workbook[sheet_name]["A1"].font.bold)
            self.assertEqual(workbook[sheet_name]["A1"].alignment.vertical, "center")
        self.assertEqual(workbook["Measurements"]["A2"].number_format, "yyyy-mm-dd hh:mm")
        self.assertEqual(workbook["Measurements"]["B2"].number_format, "0.0")
        self.assertEqual(workbook["Measurements"]["C2"].number_format, "0.0")
        self.assertEqual(workbook["Prediction Metrics"]["D2"].number_format, "0.000")
        self.assertTrue(workbook["Ingestion Diagnostics"]["H2"].alignment.wrap_text)
        self.assertEqual(report, campaign.analysis_reports.first())

    def test_excel_report_export_handles_missing_optional_fields(self):
        campaign = Campaign.objects.create(name="Sparse Export")
        AnalysisReport.objects.create(
            campaign=campaign,
            status=AnalysisReport.Status.COMPLETE,
            summary="Sparse report.",
            summary_json={"segments": [{}], "prediction_metrics": {"6h": {"ridge": {"samples": 0}}}},
        )

        response = self.client.get(reverse("campaigns:export_excel_report", args=[campaign.pk]))

        self.assertEqual(response.status_code, 200)
        workbook = load_workbook(BytesIO(response.content))
        self.assertEqual(workbook["Summary"]["B2"].value, "Sparse Export")
        self.assertEqual(workbook["Summary"]["B3"].value, "N/A")
        self.assertEqual(workbook["Segments"]["A2"].value, "N/A")
        self.assertEqual(workbook["Prediction Metrics"]["A2"].value, "6h")


def _segment_rows(start, segment_id, radon_values, regimes):
    return [
        {
            "measured_at": start + timedelta(hours=segment_id * 24 + index),
            "radon_bq_m3": Decimal(str(value)),
            "temperature_c": None,
            "humidity_percent": None,
            "pressure_hpa": None,
            "segment_id": segment_id,
            "regime": regime,
        }
        for index, (value, regime) in enumerate(zip(radon_values, regimes))
    ]
