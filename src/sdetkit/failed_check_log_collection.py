from __future__ import annotations

import argparse
import json
import re
import shlex
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "sdetkit.pr_quality.failed_check_logs.v1"

JsonObject = dict[str, Any]

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
    # GitHub check-runs include both an API URL and one or more human/action URLs.
    # The API URL cannot be parsed by `gh run view`; prefer Actions/job URLs.
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
        log_path = log_dir / f"{index + 1:02d}-{_slug(name)}.log"
        collected = _collect_existing_log(record, log_path)

        logs.append(
            {
                "check_name": name,
                "status": _check_status(record),
                "conclusion": _check_conclusion(record),
                "url": url,
                "run_id": run_id,
                "job_id": job_id,
                "download_supported": bool(run_id),
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
        log_path = _string(item.get("log_path"))
        if not run_id or not log_path:
            continue

        quoted_run = shlex.quote(run_id)
        quoted_log = shlex.quote(log_path)
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
    parser.add_argument("--checks-json", type=Path, required=True)
    parser.add_argument("--out-dir", type=Path, default=Path("build/pr-quality/check-logs"))
    parser.add_argument(
        "--no-script",
        action="store_true",
        help="Do not write the GitHub Actions log download script.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    manifest = write_failed_check_log_artifacts(
        checks_json=args.checks_json,
        out_dir=args.out_dir,
        write_script=not bool(args.no_script),
    )
    print(json.dumps(manifest, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
