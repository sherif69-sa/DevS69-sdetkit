from __future__ import annotations

from typing import Any


def render_markdown(payload: dict[str, Any]) -> str:
    provenance = payload.get("input_provenance")
    if not isinstance(provenance, dict):
        provenance = {}
    lines = [
        "# SDETKit reviewed product KPI report",
        "",
        f"- report_status: {payload.get('report_status', 'review_required')}",
        f"- reviewed_observation_count: {payload.get('reviewed_observation_count', 0)}",
        f"- metric_count: {payload.get('metric_count', 0)}",
        f"- input_digest: `{provenance.get('input_digest', '')}`",
        f"- current_head_sha: `{provenance.get('current_head_sha', '')}`",
        "- reporting_only: true",
        "- review_first: true",
        "",
        "## Metrics",
        "",
        "| Metric | Status | Pass | Fail | Applicable | Precision | Unavailable | Malformed | Unsupported | N/A |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    raw_metrics = payload.get("metrics")
    metrics = raw_metrics if isinstance(raw_metrics, list) else []
    for metric in metrics:
        if not isinstance(metric, dict):
            continue
        raw_counts = metric.get("outcome_counts")
        counts = raw_counts if isinstance(raw_counts, dict) else {}
        precision = metric.get("precision")
        precision_text = "unavailable" if precision is None else f"{float(precision) * 100:.2f}%"
        lines.append(
            "| {metric_id} | {status} | {passed} | {failed} | {denominator} | {precision} | "
            "{unavailable} | {malformed} | {unsupported} | {not_applicable} |".format(
                metric_id=metric.get("metric_id", "unknown"),
                status=metric.get("status", "unavailable"),
                passed=counts.get("pass", 0),
                failed=counts.get("fail", 0),
                denominator=metric.get("reviewed_applicable_observations", 0),
                precision=precision_text,
                unavailable=counts.get("unavailable", 0),
                malformed=counts.get("malformed", 0),
                unsupported=counts.get("unsupported", 0),
                not_applicable=counts.get("not_applicable", 0),
            )
        )

    lines.extend(["", "## Reviewed observation provenance", ""])
    raw_observations = payload.get("reviewed_observation_index")
    observations = raw_observations if isinstance(raw_observations, list) else []
    if not observations:
        lines.append("- none")
    for observation in observations:
        if not isinstance(observation, dict):
            continue
        lines.append(
            "- `{observation_id}` — {repository_name} @ `{source_commit_sha}`; "
            "reviewer `{reviewer_id}`; evidence `{evidence_sha256}`".format(
                observation_id=observation.get("observation_id", ""),
                repository_name=observation.get("repository_name", ""),
                source_commit_sha=observation.get("source_commit_sha", ""),
                reviewer_id=observation.get("reviewer_id", ""),
                evidence_sha256=observation.get("evidence_sha256", ""),
            )
        )

    lines.extend(["", "## Authority boundary", ""])
    raw_boundary = payload.get("authority_boundary")
    boundary = raw_boundary if isinstance(raw_boundary, dict) else {}
    for field, value in sorted(boundary.items()):
        lines.append(f"- {field}: {str(bool(value)).lower()}")
    lines.append("")
    return "\n".join(lines)
