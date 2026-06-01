from __future__ import annotations

import argparse
import json
import re
import shlex
import sys
from pathlib import Path
from typing import Any

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

_ACTIONS_URL_PATTERN = re.compile(r"/actions/runs/(?P<run_id>[0-9]+)(?:/job/(?P<job_id>[0-9]+))?")
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
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


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
        target.write_text(source.read_text(encoding="utf-8", errors="ignore"), encoding="utf-8")
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
        if bool(item.get("collected")) and _string(item.get("evidence_source")) == "existing_log"
    )
    github_actions_supported = sum(1 for item in logs if bool(item.get("download_supported")))
    annotation_supported = sum(
        1 for item in logs if bool(item.get("annotation_collection_supported"))
    )
    uncollectible = sum(
        1 for item in logs if _string(item.get("evidence_source")) == "uncollectible"
    )
    run_id_present = sum(1 for item in logs if bool(_string(item.get("run_id"))))
    job_id_present = sum(1 for item in logs if bool(_string(item.get("job_id"))))
    check_run_id_present = sum(1 for item in logs if bool(_string(item.get("check_run_id"))))
    pending_downloads = sum(
        1
        for item in logs
        if not bool(item.get("collected"))
        and (
            bool(item.get("download_supported"))
            or bool(item.get("annotation_collection_supported"))
        )
    )

    gaps: list[str] = []
    if pending_downloads:
        gaps.append("download_script_required")
    if uncollectible:
        gaps.append("uncollectible_failed_checks")

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
        "pending_downloads": pending_downloads,
        "download_script_required": bool(pending_downloads),
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
    log_dir.mkdir(parents=True, exist_ok=True)

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

        logs.append(
            {
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
            }
        )

    return {
        "schema_version": SCHEMA_VERSION,
        "checks_source": checks_json.as_posix(),
        "logs_dir": log_dir.as_posix(),
        "failed_check_count": len(logs),
        "collected_log_count": len([item for item in logs if bool(item.get("collected", False))]),
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
        f"mkdir -p {shlex.quote(_string(manifest.get('logs_dir')))}",
        "",
    ]

    for item in [_as_dict(value) for value in _as_list(manifest.get("logs"))]:
        run_id = _string(item.get("run_id"))
        job_id = _string(item.get("job_id"))
        check_run_id = _string(item.get("check_run_id"))
        log_path = _string(item.get("log_path"))
        annotation_path = _string(item.get("annotation_path"))
        collected = bool(item.get("collected", False))
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
                        "repository="
                        '"${GITHUB_REPOSITORY:-${REPOSITORY_OWNER:-}/${REPOSITORY_NAME:-}}"'
                    ),
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

    manifest_path = out_dir / "check-log-manifest.json"
    manifest["manifest_path"] = manifest_path.as_posix()
    _write_json(manifest_path, manifest)
    return manifest


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m sdetkit.failed_check_log_collection")
    parser.add_argument("--checks-json", type=Path)
    parser.add_argument("--out-dir", type=Path, default=Path("build/pr-quality/check-logs"))
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
            raise SystemExit("annotation log and JSON targets are required for sanitization")
        report = sanitize_check_run_annotations(
            raw_annotations_json=args.sanitize_annotations_json,
            annotation_log_target=args.annotation_log_target,
            annotation_json_target=args.annotation_json_target,
        )
        sys.stdout.write(json.dumps(report, indent=2, sort_keys=True) + "\n")
        return 0

    if args.checks_json is None:
        raise SystemExit("--checks-json is required unless sanitizing annotations")
    manifest = write_failed_check_log_artifacts(
        checks_json=args.checks_json,
        out_dir=args.out_dir,
        write_script=not bool(args.no_script),
    )
    sys.stdout.write(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
