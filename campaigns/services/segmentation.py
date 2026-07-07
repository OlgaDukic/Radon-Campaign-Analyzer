from datetime import timedelta


def assign_segment_ids(rows, gap_threshold_minutes=60):
    ordered = sorted(rows, key=lambda row: row["measured_at"])
    current_segment = 1
    previous_timestamp = None
    threshold = timedelta(minutes=gap_threshold_minutes)

    segmented = []
    for row in ordered:
        if previous_timestamp and row["measured_at"] - previous_timestamp > threshold:
            current_segment += 1
        updated = row.copy()
        updated["segment_id"] = current_segment
        segmented.append(updated)
        previous_timestamp = row["measured_at"]
    return segmented
