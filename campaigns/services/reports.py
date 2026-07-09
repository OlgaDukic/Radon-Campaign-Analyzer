from decimal import Decimal
from html import escape

from campaigns.services.regimes import regime_counts


STAT_FIELDS = ("radon_bq_m3", "temperature_c", "humidity_percent", "pressure_hpa")
DYNAMIC_REGIMES = {"rising", "falling", "sudden_rise", "sudden_drop"}


def build_summary(
    rows,
    gaps,
    uploaded_file_count,
    prediction_metrics=None,
    ingestion_debug=None,
    prediction_metrics_by_regime=None,
    prediction_errors=None,
    research_outputs=None,
):
    segments = {}
    for row in rows:
        segments.setdefault(row["segment_id"], []).append(row)

    summary = {
        "uploaded_file_count": uploaded_file_count,
        "measurement_count": len(rows),
        "segment_count": len(segments),
        "gap_count": len(gaps),
        "regime_counts": regime_counts(rows),
        "prediction_metrics": prediction_metrics or {},
        "prediction_metrics_by_regime": prediction_metrics_by_regime or [],
        "prediction_errors": prediction_errors or [],
        "ingestion_debug": ingestion_debug or [],
        "gaps": [_serialize_gap(gap) for gap in gaps],
        "segments": [_segment_summary(segment_id, segment_rows) for segment_id, segment_rows in sorted(segments.items())],
    }
    if research_outputs:
        summary.update(research_outputs)
    return summary


def summary_to_text(summary_json):
    if summary_json["measurement_count"] == 0 and summary_json["uploaded_file_count"]:
        return (
            "Analysis complete, but no measurements were imported. "
            "Review the ingestion diagnostics for each uploaded file."
        )
    return (
        "Research prototype analysis complete. "
        f"Imported {summary_json['measurement_count']} measurement(s) from "
        f"{summary_json['uploaded_file_count']} uploaded file(s). The pipeline identified "
        f"{summary_json['segment_count']} segment(s), and detected "
        f"{summary_json['gap_count']} sampling-aware gap(s). Segment labels summarize exposure level and dynamics; "
        "they do not replace the per-measurement regime classifications."
    )


def build_html_report(campaign, summary_json):
    segment_rows = "\n".join(_segment_interpretation_html(segment) for segment in summary_json["segments"])
    regime_rows = "\n".join(_regime_html(summary_json["regime_counts"]))
    prediction_rows = "\n".join(_prediction_html(summary_json.get("prediction_metrics", {})))
    ingestion_rows = "\n".join(_ingestion_html(summary_json.get("ingestion_debug", [])))
    return f"""
<article>
  <h1>Radon Campaign Research Report: {escape(campaign.name)}</h1>
  <p>{escape(summary_to_text(summary_json))}</p>

  <h2>Segment Interpretation</h2>
  <p>Segment labels combine mean and maximum radon, threshold exceedance, and the share of dynamic measurement regimes.</p>
  <table>
    <thead><tr><th>Segment</th><th>Label</th><th>Mean radon</th><th>Max radon</th><th>Above 100</th><th>Above 200</th><th>Dynamic</th><th>Interpretation</th></tr></thead>
    <tbody>{segment_rows}</tbody>
  </table>

  <h2>Prediction Model Performance</h2>
  <p>Short-term prediction is evaluated against the naive baseline where the future radon value is assumed to equal the current radon value.</p>
  <table>
    <thead><tr><th>Horizon</th><th>Model</th><th>Samples</th><th>MAE</th><th>RMSE</th></tr></thead>
    <tbody>{prediction_rows}</tbody>
  </table>

  <h2>Per-Measurement Regime Counts</h2>
  <p>These counts are retained for auditability; segment interpretation above is usually more informative for campaign-level review.</p>
  <table>
    <thead><tr><th>Regime</th><th>Measurements</th></tr></thead>
    <tbody>{regime_rows}</tbody>
  </table>

  <h2>Ingestion Diagnostics</h2>
  <p>Diagnostics are shown to make file parsing reproducible and to explain skipped or partially parsed exports.</p>
  <table>
    <thead><tr><th>File</th><th>Sheets</th><th>Rows</th><th>Header row</th><th>Detected columns</th><th>Mapped columns</th><th>Parsed rows</th><th>Reason</th></tr></thead>
    <tbody>{ingestion_rows}</tbody>
  </table>
</article>
""".strip()


def _regime_html(regime_count_map):
    regime_rows = "\n".join(
        f"<tr><td>{escape(regime)}</td><td>{count}</td></tr>"
        for regime, count in regime_count_map.items()
    )
    return regime_rows


def _segment_summary(segment_id, rows):
    interpretation = _segment_interpretation(rows)
    summary = {
        "segment_id": segment_id,
        "measurement_count": len(rows),
        "start": rows[0]["measured_at"].isoformat() if rows else None,
        "end": rows[-1]["measured_at"].isoformat() if rows else None,
        "regime_counts": regime_counts(rows),
        "dominant_regime": _dominant_regime(rows),
        "segment_label": interpretation["segment_label"],
        "percent_above_100": interpretation["percent_above_100"],
        "percent_above_200": interpretation["percent_above_200"],
        "dynamic_percent": interpretation["dynamic_percent"],
        "interpretation_text": interpretation["interpretation_text"],
        "statistics": {},
    }
    for field in STAT_FIELDS:
        values = [row[field] for row in rows if row.get(field) is not None]
        summary["statistics"][field] = _stats(values)
    return summary


def _segment_interpretation_html(segment):
    radon_stats = segment["statistics"]["radon_bq_m3"]
    return (
        "<tr>"
        f"<td>{segment['segment_id']}</td>"
        f"<td>{escape(str(segment['segment_label']))}</td>"
        f"<td>{'' if radon_stats['mean'] is None else radon_stats['mean']}</td>"
        f"<td>{'' if radon_stats['max'] is None else radon_stats['max']}</td>"
        f"<td>{segment['percent_above_100']}%</td>"
        f"<td>{segment['percent_above_200']}%</td>"
        f"<td>{segment['dynamic_percent']}%</td>"
        f"<td>{escape(segment['interpretation_text'])}</td>"
        "</tr>"
    )


def _prediction_html(prediction_metrics):
    for horizon, model_results in prediction_metrics.items():
        for model_name, metrics in model_results.items():
            yield (
                "<tr>"
                f"<td>{escape(horizon)}</td>"
                f"<td>{escape(model_name)}</td>"
                f"<td>{metrics['samples']}</td>"
                f"<td>{'' if metrics['mae'] is None else metrics['mae']}</td>"
                f"<td>{'' if metrics['rmse'] is None else metrics['rmse']}</td>"
                "</tr>"
            )


def _ingestion_html(ingestion_debug):
    for file_debug in ingestion_debug:
        mapped_columns = ", ".join(
            f"{key}: {value or ''}"
            for key, value in file_debug.get("mapped_columns", {}).items()
        )
        yield (
            "<tr>"
            f"<td>{escape(str(file_debug.get('filename', '')))}</td>"
            f"<td>{escape(', '.join(file_debug.get('detected_sheets', [])))}</td>"
            f"<td>{file_debug.get('raw_rows_read', 0)}</td>"
            f"<td>{file_debug.get('detected_header_row') or ''}</td>"
            f"<td>{escape(', '.join(file_debug.get('detected_columns', [])))}</td>"
            f"<td>{escape(mapped_columns)}</td>"
            f"<td>{file_debug.get('parsed_measurement_rows', 0)}</td>"
            f"<td>{escape(str(file_debug.get('skipped_reason', '')))}</td>"
            "</tr>"
        )


def _dominant_regime(rows):
    counts = regime_counts(rows)
    if not counts:
        return None
    return max(counts.items(), key=lambda item: (item[1], item[0]))[0]


def _segment_interpretation(rows):
    radon_values = [row["radon_bq_m3"] for row in rows if row.get("radon_bq_m3") is not None]
    if len(radon_values) < 3:
        return {
            "segment_label": "insufficient_data",
            "percent_above_100": _percent(0, len(radon_values)),
            "percent_above_200": _percent(0, len(radon_values)),
            "dynamic_percent": _dynamic_percent(rows),
            "interpretation_text": "Fewer than three valid radon measurements are available, so segment-level behavior is not interpreted.",
        }

    mean_radon = sum(radon_values, Decimal("0")) / len(radon_values)
    max_radon = max(radon_values)
    percent_above_100 = _percent(sum(1 for value in radon_values if value > Decimal("100")), len(radon_values))
    percent_above_200 = _percent(sum(1 for value in radon_values if value > Decimal("200")), len(radon_values))
    dynamic_percent = _dynamic_percent(rows)

    if max_radon >= Decimal("300") or percent_above_200 >= 20:
        label = "high_episode"
        text = (
            "The segment contains a high-radon episode, indicated by maximum radon or repeated values above 200 Bq/m3."
        )
    elif mean_radon >= Decimal("100") or percent_above_100 >= 50:
        label = "elevated_dynamic"
        text = (
            "Radon is frequently above 100 Bq/m3, with dynamics assessed from rising, falling, or sudden-change labels."
        )
    elif dynamic_percent >= 20 or percent_above_100 > 0:
        label = "low_dynamic"
        text = (
            "Average radon remains low, but the segment shows dynamic behavior or intermittent values above 100 Bq/m3."
        )
    else:
        label = "low_stable"
        text = "Radon is mostly below 100 Bq/m3 with little dynamic behavior in the classified measurements."

    return {
        "segment_label": label,
        "percent_above_100": percent_above_100,
        "percent_above_200": percent_above_200,
        "dynamic_percent": dynamic_percent,
        "interpretation_text": text,
    }


def _dynamic_percent(rows):
    if not rows:
        return 0.0
    dynamic_count = sum(1 for row in rows if row.get("regime") in DYNAMIC_REGIMES)
    return _percent(dynamic_count, len(rows))


def _percent(numerator, denominator):
    if not denominator:
        return 0.0
    return round((numerator / denominator) * 100, 1)


def _stats(values):
    if not values:
        return {"count": 0, "min": None, "max": None, "mean": None}
    total = sum(values, Decimal("0"))
    return {
        "count": len(values),
        "min": _serialize_decimal(min(values)),
        "max": _serialize_decimal(max(values)),
        "mean": _serialize_decimal(total / len(values)),
    }


def _serialize_gap(gap):
    return {
        "from": gap["from"].isoformat(),
        "to": gap["to"].isoformat(),
        "minutes": gap["minutes"],
        "expected_interval_minutes": gap.get("expected_interval_minutes"),
        "threshold_minutes": gap.get("threshold_minutes"),
        "gap_class": gap.get("gap_class"),
        "reason": gap.get("reason"),
    }


def _serialize_decimal(value):
    return float(round(value, 2))
