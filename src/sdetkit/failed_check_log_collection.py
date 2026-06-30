from __future__ import annotations

import argparse
import json
import re
import shlex
import sys
from pathlib import Path
from typing import Any

from sdetkit.pr_quality_terminal_workflows import (
    collect_and_merge_terminal_snapshot_from_environment,
)

SCHEMA_VERSION = "sdetkit.pr_quality.failed_check_logs.v1"
ANNOTATION_SCHEMA_VERSION = "sdetkit.pr_quality.failed_check_annotations.v1"

JsonObject = dict[str, Any]

WORKFLOW_JOB_EVIDENCE_QUALITY_KEY = "_".join(("workflow", "job", "evidence", "quality"))
WORKFLOW_JOB_EVIDENCE_QUALITY_SCHEMA_VERSION = ".".join(
    ("sdetkit", WORKFLOW_JOB_EVIDENCE_QUALITY_KEY, "v1")
)

_FAILURE_CONCLUSIONS = {
    "action_required",
    "cancelled",
    "failure",
    "startup_failure",
    "timed_out",
}

_SUCCESS_CONCLUSIONS = {
    "neutral",
    "skipped",
    "success",
}

_ACTIONS_URL_PATTERN = re.compile(
    r"/actions/runs/(?P<run_id>[0-9]+)(?:/job/(?P<job_id>[0-9]+))?"
)
_CHECK_RUN_URL_PATTERN = re.compile(r"/(?:check-runs|runs)/(?P<check_run_id>[0-9]+)")


def _as_dict(value: Any) -> JsonObject:
    return value if isinstance(value, dict) else {}


def _as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _string(value: Any) -> str:
    return str(value).strip() if value is not None else ""


def _read_json(path: Path) -> JsonObject:
    if not path.exists():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    return _as_dict(payload)


def _write_json(path: Path, payload: JsonObject) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


def _integer(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _normalized_workflow_run(payload: JsonObject) -> JsonObject:
    if not payload:
        return {}
    return {
        "id": _integer(payload.get("id")),
        "name": _string(payload.get("name")),
        "run_number": _integer(payload.get("run_number")),
        "run_attempt": _integer(payload.get("run_attempt")),
        "status": _string(payload.get("status")),
        "conclusion": _string(payload.get("conclusion")),
        "head_sha": _string(payload.get("head_sha")),
        "html_url": _string(payload.get("html_url")),
        "event": _string(payload.get("event")),
    }


def _normalized_workflow_job(payload: JsonObject) -> JsonObject:
    if not payload:
        return {}
    steps: list[JsonObject] = []
    for raw_step in _as_list(payload.get("steps")):
        step = _as_dict(raw_step)
        name = _string(step.get("name"))
        if not name:
            continue
        steps.append(
            {
                "name": name,
                "number": _integer(step.get("number")),
                "status": _string(step.get("status")),
                "conclusion": _string(step.get("conclusion")),
            }
        )
    return {
        "id": _integer(payload.get("id")),
        "run_id": _integer(payload.get("run_id")),
        "name": _string(payload.get("name")),
        "status": _string(payload.get("status")),
        "conclusion": _string(payload.get("conclusion")),
        "head_sha": _string(payload.get("head_sha")),
        "html_url": _string(payload.get("html_url")),
        "steps": steps,
    }


def _hydrate_checks_payload(*, checks_json: Path, manifest: JsonObject) -> JsonObject:
    payload = _read_json(checks_json)
    if isinstance(payload.get("check_runs"), list):
        records_key = "check_runs"
    elif isinstance(payload.get("checks"), list):
        records_key = "checks"
    else:
        return payload

    records = [dict(_as_dict(item)) for item in _as_list(payload.get(records_key))]
    for raw_item in _as_list(manifest.get("logs")):
        item = _as_dict(raw_item)
        index = _integer(item.get("record_index"))
        if index < 0 or index >= len(records):
            continue
        record = dict(records[index])
        workflow_run = _as_dict(item.get("workflow_run"))
        workflow_job = _as_dict(item.get("workflow_job"))
        if workflow_run:
            record["workflow_run"] = workflow_run
            record["workflow_name"] = _string(workflow_run.get("name"))
            record["workflow_run_id"] = _integer(workflow_run.get("id"))
        if workflow_job:
            record["workflow_job"] = workflow_job
            record["workflow_job_id"] = _integer(workflow_job.get("id"))
            record["workflow_job_name"] = _string(workflow_job.get("name"))
            record["steps"] = _as_list(workflow_job.get("steps"))
            if _string(workflow_job.get("html_url")):
                record["details_url"] = _string(workflow_job.get("html_url"))
        record["failure_provenance_collection"] = {
            "status": _string(item.get("workflow_metadata_status") or "unavailable"),
            "reporting_only": True,
            "patch_application_allowed": False,
            "automation_allowed": False,
            "security_dismissal_allowed": False,
            "merge_authorized": False,
            "semantic_equivalence_proven": False,
        }
        records[index] = record

    hydrated = dict(payload)
    hydrated[records_key] = records
    return hydrated


def _slug(value: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", value.strip().lower()).strip("-")
    return slug or "check"


def _iter_check_records(payload: JsonObject) -> list[JsonObject]:
    if isinstance(payload.get("checks"), list):
        return [_as_dict(item) for item in _as_list(payload.get("checks"))]

    records: list[JsonObject] = []
    for key in (
        "check_runs",
        "jobs",
        "workflow_runs",
        "statuses",
        "check_suites",
    ):
        records.extend(_as_dict(item) for item in _as_list(payload.get(key)))

    if not records and payload:
        records.append(payload)

    return records


def _check_name(record: JsonObject, index: int) -> str:
    for key in ("name", "displayName", "workflowName", "context", "check_name"):
        value = _string(record.get(key))
        if value:
            return value
    return f"check-{index + 1}"


def _check_status(record: JsonObject) -> str:
    return _string(record.get("status")).lower()


def _check_conclusion(record: JsonObject) -> str:
    return _string(record.get("conclusion") or record.get("state")).lower()


def _is_failed(record: JsonObject) -> bool:
    conclusion = _check_conclusion(record)
    status = _check_status(record)
    if conclusion in _FAILURE_CONCLUSIONS:
        return True
    return status == "completed" and conclusion not in _SUCCESS_CONCLUSIONS


def _record_url(record: JsonObject) -> str:
    # Prefer human/action URLs in operator artifacts; retain API URL separately
    # when resolving Check Run annotations.
    for key in ("details_url", "html_url", "target_url", "url"):
        value = _string(record.get(key))
        if value:
            return value
    return ""


def _inline_log_text(record: JsonObject) -> str:
    for key in ("log", "logs", "stdout", "stderr", "output", "text"):
        value = record.get(key)
        if isinstance(value, str) and value.strip():
            return value
    return ""


def _source_log_path(record: JsonObject) -> Path | None:
    value = _string(record.get("log_path") or record.get("logPath"))
    if not value:
        return None
    path = Path(value)
    return path if path.exists() else None


def _actions_run_job(url: str) -> tuple[str, str]:
    match = _ACTIONS_URL_PATTERN.search(url)
    if not match:
        return "", ""
    return match.group("run_id") or "", match.group("job_id") or ""


def _check_run_id(record: JsonObject, url: str) -> str:
    for candidate in (
        _string(record.get("url")),
        _string(record.get("details_url")),
        _string(record.get("html_url")),
        url,
    ):
        if "/actions/runs/" in candidate:
            continue
        match = _CHECK_RUN_URL_PATTERN.search(candidate)
        if match:
            return match.group("check_run_id") or ""
    return ""


def _collect_existing_log(record: JsonObject, target: Path) -> bool:
    if target.exists() and target.stat().st_size > 0:
        return True

    inline = _inline_log_text(record)
    if inline.strip():
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(inline.rstrip() + "\n", encoding="utf-8")
        return True

    source = _source_log_path(record)
    if source is not None:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(
            source.read_text(encoding="utf-8", errors="ignore"), encoding="utf-8"
        )
        return target.exists() and target.stat().st_size > 0

    return False


def _safe_annotation_title(value: Any) -> str:
    text = _string(value).replace("\r", " ").replace("\n", " ")
    text = re.sub(r"\s+", " ", text)
    text = re.sub(r"[A-Za-z0-9_=-]{24,}", "<redacted-long-token-like-text>", text)
    return text[:160]


def sanitize_check_run_annotations(
    *,
    raw_annotations_json: Path,
    annotation_log_target: Path,
    annotation_json_target: Path,
) -> JsonObject:
    payload = json.loads(raw_annotations_json.read_text(encoding="utf-8"))
    annotations = payload if isinstance(payload, list) else []

    sanitized: list[JsonObject] = []
    lines: list[str] = []
    for raw_item in annotations:
        item = _as_dict(raw_item)
        level = _string(item.get("annotation_level") or "notice").lower()
        path = _string(item.get("path"))
        line = int(item.get("start_line") or 0)
        title = _safe_annotation_title(item.get("title") or "Check annotation")
        if not path or line <= 0 or not title:
            continue
        sanitized.append(
            {
                "annotation_level": level,
                "path": path,
                "start_line": line,
                "end_line": int(item.get("end_line") or line),
                "title": title,
                "message_present": bool(_string(item.get("message"))),
                "raw_details_present": bool(_string(item.get("raw_details"))),
            }
        )
        lines.append(f"GitHub check annotation {level}: {title} at {path}:{line}")

    report = {
        "schema_version": ANNOTATION_SCHEMA_VERSION,
        "source": "github_check_run_annotations",
        "annotation_count": len(sanitized),
        "raw_message_text_persisted": False,
        "raw_details_text_persisted": False,
        "annotations": sanitized,
    }
    _write_json(annotation_json_target, report)

    if lines:
        annotation_log_target.parent.mkdir(parents=True, exist_ok=True)
        annotation_log_target.write_text("\n".join(lines) + "\n", encoding="utf-8")
    elif annotation_log_target.exists():
        annotation_log_target.unlink()

    return report


def _workflow_job_evidence_quality(logs: list[JsonObject]) -> JsonObject:
    failed_checks = len(logs)
    existing_logs_collected = sum(
        1
        for item in logs
        if bool(item.get("collected"))
        and _string(item.get("evidence_source")) == "existing_log"
    )
    github_actions_supported = sum(
        1 for item in logs if bool(item.get("download_supported"))
    )
    annotation_supported = sum(
        1 for item in logs if bool(item.get("annotation_collection_supported"))
    )
    uncollectible = sum(
        1 for item in logs if _string(item.get("evidence_source")) == "uncollectible"
    )
    run_id_present = sum(1 for item in logs if bool(_string(item.get("run_id"))))
    job_id_present = sum(1 for item in logs if bool(_string(item.get("job_id"))))
    check_run_id_present = sum(
        1 for item in logs if bool(_string(item.get("check_run_id")))
    )
    workflow_run_metadata_present = sum(
        1 for item in logs if bool(_as_dict(item.get("workflow_run")))
    )
    workflow_job_metadata_present = sum(
        1 for item in logs if bool(_as_dict(item.get("workflow_job")))
    )
    workflow_job_steps_present = sum(
        1
        for item in logs
        if bool(_as_list(_as_dict(item.get("workflow_job")).get("steps")))
    )
    pending_downloads = sum(
        1
        for item in logs
        if not bool(item.get("collected"))
        and (
            bool(item.get("download_supported"))
            or bool(item.get("annotation_collection_supported"))
        )
    )
    metadata_downloads_pending = max(
        run_id_present - workflow_run_metadata_present,
        0,
    ) + max(job_id_present - workflow_job_metadata_present, 0)

    gaps: list[str] = []
    if pending_downloads or metadata_downloads_pending:
        gaps.append("download_script_required")
    if uncollectible:
        gaps.append("uncollectible_failed_checks")
    if run_id_present > workflow_run_metadata_present:
        gaps.append("workflow_run_metadata_missing")
    if job_id_present > workflow_job_metadata_present:
        gaps.append("workflow_job_metadata_missing")
    if job_id_present > workflow_job_steps_present:
        gaps.append("workflow_job_steps_missing")

    return {
        "schema_version": WORKFLOW_JOB_EVIDENCE_QUALITY_SCHEMA_VERSION,
        "failed_checks": failed_checks,
        "existing_logs_collected": existing_logs_collected,
        "github_actions_log_download_supported": github_actions_supported,
        "check_run_annotation_collection_supported": annotation_supported,
        "uncollectible_failed_checks": uncollectible,
        "run_id_present": run_id_present,
        "job_id_present": job_id_present,
        "check_run_id_present": check_run_id_present,
        "workflow_run_metadata_present": workflow_run_metadata_present,
        "workflow_job_metadata_present": workflow_job_metadata_present,
        "workflow_job_steps_present": workflow_job_steps_present,
        "pending_downloads": pending_downloads,
        "metadata_downloads_pending": metadata_downloads_pending,
        "download_script_required": bool(pending_downloads or metadata_downloads_pending),
        "evidence_gaps": gaps,
        "reporting_only": True,
        "patch_application_allowed": False,
        "automation_allowed": False,
        "merge_authorized": False,
        "semantic_equivalence_proven": False,
    }


def build_failed_check_log_manifest(
    *,
    checks_json: Path,
    out_dir: Path,
) -> JsonObject:
    payload = _read_json(checks_json)
    records = _iter_check_records(payload)
    log_dir = out_dir / "failed-check-logs"
    metadata_dir = out_dir / "workflow-job-metadata"
    log_dir.mkdir(parents=True, exist_ok=True)
    metadata_dir.mkdir(parents=True, exist_ok=True)

    logs: list[JsonObject] = []
    for index, record in enumerate(records):
        if not _is_failed(record):
            continue

        name = _check_name(record, index)
        url = _record_url(record)
        run_id, job_id = _actions_run_job(url)
        check_run_id = _check_run_id(record, url)
        log_path = log_dir / f"{index + 1:02d}-{_slug(name)}.log"
        annotation_path = log_dir / f"{index + 1:02d}-{_slug(name)}.annotations.json"
        workflow_run_path = metadata_dir / f"run-{run_id}.json" if run_id else None
        workflow_job_path = metadata_dir / f"job-{job_id}.json" if job_id else None
        workflow_run = _normalized_workflow_run(
            _read_json(workflow_run_path) if workflow_run_path is not None else {}
        )
        workflow_job = _normalized_workflow_job(
            _read_json(workflow_job_path) if workflow_job_path is not None else {}
        )
        collected = _collect_existing_log(record, log_path)
        annotation_collected = annotation_path.exists() and collected

        if annotation_collected:
            evidence_source = "github_check_run_annotations"
        elif collected:
            evidence_source = "existing_log"
        elif run_id:
            evidence_source = "github_actions_log"
        elif check_run_id:
            evidence_source = "github_check_run_annotations"
        else:
            evidence_source = "uncollectible"

        if workflow_run and workflow_job and _as_list(workflow_job.get("steps")):
            metadata_status = "confirmed"
        elif workflow_run or workflow_job:
            metadata_status = "partial"
        else:
            metadata_status = "unavailable"

        logs.append(
            {
                "record_index": index,
                "check_name": name,
                "status": _check_status(record),
                "conclusion": _check_conclusion(record),
                "url": url,
                "run_id": run_id,
                "job_id": job_id,
                "check_run_id": check_run_id,
                "download_supported": bool(run_id),
                "annotation_collection_supported": bool(check_run_id and not run_id),
                "annotation_collected": annotation_collected,
                "annotation_path": annotation_path.as_posix(),
                "evidence_source": evidence_source,
                "log_path": log_path.as_posix(),
                "collected": collected,
                "workflow_run_path": (
                    workflow_run_path.as_posix()
                    if workflow_run_path is not None
                    else ""
                ),
                "workflow_job_path": (
                    workflow_job_path.as_posix()
                    if workflow_job_path is not None
                    else ""
                ),
                "workflow_run": workflow_run,
                "workflow_job": workflow_job,
                "workflow_metadata_status": metadata_status,
            }
        )

    return {
        "schema_version": SCHEMA_VERSION,
        "checks_source": checks_json.as_posix(),
        "logs_dir": log_dir.as_posix(),
        "workflow_metadata_dir": metadata_dir.as_posix(),
        "failed_check_count": len(logs),
        "collected_log_count": len(
            [item for item in logs if bool(item.get("collected", False))]
        ),
        "annotation_collected_count": len(
            [item for item in logs if bool(item.get("annotation_collected", False))]
        ),
        WORKFLOW_JOB_EVIDENCE_QUALITY_KEY: _workflow_job_evidence_quality(logs),
        "logs": logs,
    }


def render_download_script(manifest: JsonObject) -> str:
    lines = [
        "#!/usr/bin/env bash",
        "set -u",
        'repository="${GITHUB_REPOSITORY:-${REPOSITORY_OWNER:-}/${REPOSITORY_NAME:-}}"',
        f"mkdir -p {shlex.quote(_string(manifest.get('logs_dir')))}",
        f"mkdir -p {shlex.quote(_string(manifest.get('workflow_metadata_dir')))}",
        "",
    ]

    for item in [_as_dict(value) for value in _as_list(manifest.get("logs"))]:
        run_id = _string(item.get("run_id"))
        job_id = _string(item.get("job_id"))
        check_run_id = _string(item.get("check_run_id"))
        log_path = _string(item.get("log_path"))
        annotation_path = _string(item.get("annotation_path"))
        workflow_run_path = _string(item.get("workflow_run_path"))
        workflow_job_path = _string(item.get("workflow_job_path"))
        collected = bool(item.get("collected", False))

        if run_id and workflow_run_path:
            quoted_target = shlex.quote(workflow_run_path)
            quoted_tmp = shlex.quote(f"{workflow_run_path}.tmp")
            lines.extend(
                [
                    f'if [ ! -s {quoted_target} ] && [ -n "$repository" ] && [ "$repository" != "/" ]; then',
                    (
                        f'  if gh api -H "Accept: application/vnd.github+json" '
                        f'"repos/${{repository}}/actions/runs/{run_id}" > {quoted_tmp}; then'
                    ),
                    f"    mv {quoted_tmp} {quoted_target}",
                    "  else",
                    f"    rm -f {quoted_tmp}",
                    "  fi",
                    "fi",
                    "",
                ]
            )

        if job_id and workflow_job_path:
            quoted_target = shlex.quote(workflow_job_path)
            quoted_tmp = shlex.quote(f"{workflow_job_path}.tmp")
            lines.extend(
                [
                    f'if [ ! -s {quoted_target} ] && [ -n "$repository" ] && [ "$repository" != "/" ]; then',
                    (
                        f'  if gh api -H "Accept: application/vnd.github+json" '
                        f'"repos/${{repository}}/actions/jobs/{job_id}" > {quoted_tmp}; then'
                    ),
                    f"    mv {quoted_tmp} {quoted_target}",
                    "  else",
                    f"    rm -f {quoted_tmp}",
                    "  fi",
                    "fi",
                    "",
                ]
            )

        if not log_path or collected:
            continue

        quoted_log = shlex.quote(log_path)
        if run_id:
            quoted_run = shlex.quote(run_id)
            quoted_err = shlex.quote(f"{log_path}.stderr")
            job_args = f" --job {shlex.quote(job_id)}" if job_id else ""
            lines.extend(
                [
                    f"echo collecting_failed_check_log={shlex.quote(_string(item.get('check_name')))}",
                    (
                        f"gh run view {quoted_run}{job_args} --log-failed > {quoted_log} "
                        f"2> {quoted_err} || "
                        f"gh run view {quoted_run}{job_args} --log > {quoted_log} "
                        f"2>> {quoted_err} || true"
                    ),
                    f"if [ ! -s {quoted_log} ]; then rm -f {quoted_log}; fi",
                    "",
                ]
            )
            continue

        if check_run_id and annotation_path:
            quoted_annotations = shlex.quote(annotation_path)
            lines.extend(
                [
                    (
                        f'raw_annotations="${{RUNNER_TEMP:-/tmp}}/'
                        f"sdetkit-check-run-{check_run_id}-"
                        'annotations.json"'
                    ),
                    (
                        f"echo collecting_failed_check_annotations="
                        f"{shlex.quote(_string(item.get('check_name')))}"
                    ),
                    (
                        f'if gh api -H "Accept: application/vnd.github+json" '
                        f'"repos/${{repository}}/check-runs/{check_run_id}/annotations?per_page=100" '
                        f'> "$raw_annotations"; then'
                    ),
                    (
                        "  PYTHONPATH=src python -m sdetkit.failed_check_log_collection "
                        '--sanitize-annotations-json "$raw_annotations" '
                        f"--annotation-log-target {quoted_log} "
                        f"--annotation-json-target {quoted_annotations} || true"
                    ),
                    "fi",
                    'rm -f "$raw_annotations"',
                    "",
                ]
            )

    return "\n".join(lines).rstrip() + "\n"


def write_failed_check_log_artifacts(
    *,
    checks_json: Path,
    out_dir: Path,
    write_script: bool = True,
) -> JsonObject:
    out_dir.mkdir(parents=True, exist_ok=True)
    manifest = build_failed_check_log_manifest(checks_json=checks_json, out_dir=out_dir)

    script_path = out_dir / "download-failed-check-logs.sh"
    if write_script:
        script_path.write_text(render_download_script(manifest), encoding="utf-8")
        script_path.chmod(0o755)
        manifest["download_script"] = script_path.as_posix()

    hydrated_checks_path = out_dir / "checks-with-workflow-metadata.json"
    hydrated = _hydrate_checks_payload(checks_json=checks_json, manifest=manifest)
    _write_json(hydrated_checks_path, hydrated)
    manifest["hydrated_checks_json"] = hydrated_checks_path.as_posix()

    manifest_path = out_dir / "check-log-manifest.json"
    manifest["manifest_path"] = manifest_path.as_posix()
    _write_json(manifest_path, manifest)
    return manifest


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m sdetkit.failed_check_log_collection"
    )
    parser.add_argument("--checks-json", type=Path)
    parser.add_argument(
        "--out-dir", type=Path, default=Path("build/pr-quality/check-logs")
    )
    parser.add_argument(
        "--no-script",
        action="store_true",
        help="Do not write the GitHub evidence download script.",
    )
    parser.add_argument("--sanitize-annotations-json", type=Path)
    parser.add_argument("--annotation-log-target", type=Path)
    parser.add_argument("--annotation-json-target", type=Path)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.sanitize_annotations_json is not None:
        if args.annotation_log_target is None or args.annotation_json_target is None:
            raise SystemExit(
                "annotation log and JSON targets are required for sanitization"
            )
        report = sanitize_check_run_annotations(
            raw_annotations_json=args.sanitize_annotations_json,
            annotation_log_target=args.annotation_log_target,
            annotation_json_target=args.annotation_json_target,
        )
        sys.stdout.write(json.dumps(report, indent=2, sort_keys=True) + "\n")
        return 0

    if args.checks_json is None:
        raise SystemExit(
            "--checks-json is required unless sanitizing annotations"
        )
    collect_and_merge_terminal_snapshot_from_environment(
        checks_json=args.checks_json,
        out_dir=args.out_dir,
    )
    manifest = write_failed_check_log_artifacts(
        checks_json=args.checks_json,
        out_dir=args.out_dir,
        write_script=not bool(args.no_script),
    )
    sys.stdout.write(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
