from __future__ import annotations

import re

from pr_quality_terminal_core import BLOCKING, inline, number, text


def first_failure_line(log_text: str) -> str:
    for pattern in (
        r"^FAILED\s+[^\n]+",
        r"^ERROR\s+[^\n]+",
        r"^[^\n]+\.py:\d+:\s+(?:AssertionError|Error|Exception)[^\n]*",
        r"^E\s+[^\n]+",
    ):
        match = re.search(pattern, log_text, re.MULTILINE)
        if match:
            return inline(match.group(0))[:500]
    return ""


def failed_workflows(runs, jobs_by_run=None, logs_by_job=None):
    jobs_by_run, logs_by_job = jobs_by_run or {}, logs_by_job or {}
    result = []
    for run in runs:
        if run["conclusion"] not in BLOCKING:
            continue
        jobs = list(jobs_by_run.get(run["id"], []))
        job = next(
            (item for item in jobs if text(item.get("conclusion")).lower() in BLOCKING),
            jobs[0] if jobs else {},
        )
        step = next(
            (
                item
                for item in job.get("steps") or []
                if text(item.get("conclusion")).lower() in BLOCKING
            ),
            {},
        )
        job_id = number(job.get("id"))
        result.append(
            {
                "workflow_name": run["name"],
                "workflow_url": run["url"],
                "workflow_conclusion": run["conclusion"],
                "job_name": text(job.get("name")) or "Not captured",
                "job_url": text(job.get("html_url")),
                "step_name": text(step.get("name")) or "Not captured",
                "step_number": number(step.get("number")),
                "first_failure": first_failure_line(logs_by_job.get(job_id, "")),
            }
        )
    return result
