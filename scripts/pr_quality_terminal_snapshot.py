from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
import zipfile
from collections.abc import Mapping, Sequence
from io import BytesIO
from pathlib import Path

from pr_quality_terminal_core import BLOCKING, latest_runs, number, text
from pr_quality_terminal_handoff import verify_handoff
from pr_quality_terminal_model import build_snapshot, render_comment


class GitHubApi:
    def __init__(self, repository: str, token: str):
        self.repository = repository
        self.environment = {**os.environ, "GH_TOKEN": token}

    def request(self, path: str, *, paginate: bool = False):
        command = [
            "gh",
            "api",
            "-H",
            "Accept: application/vnd.github+json",
            "-H",
            "X-GitHub-Api-Version: 2022-11-28",
        ]
        if paginate:
            command.extend(("--paginate", "--slurp"))
        command.append(path)
        completed = subprocess.run(
            command,
            check=True,
            capture_output=True,
            env=self.environment,
        )
        data = completed.stdout
        try:
            return json.loads(data.decode())
        except (UnicodeDecodeError, json.JSONDecodeError):
            return data

    def paginated(self, path: str, key: str | None = None):
        payload = self.request(path, paginate=True)
        if not isinstance(payload, list):
            raise ValueError(f"unexpected paginated payload for {path}")
        rows = []
        for page in payload:
            batch = page.get(key, []) if key and isinstance(page, Mapping) else page
            if not isinstance(batch, list):
                raise ValueError(f"unexpected paginated page for {path}")
            rows.extend(item for item in batch if isinstance(item, dict))
        return rows

    def job_log(self, job_id: int) -> str:
        payload = self.request(f"repos/{self.repository}/actions/jobs/{job_id}/logs")
        if not isinstance(payload, bytes):
            return json.dumps(payload)
        if payload.startswith(b"PK"):
            with zipfile.ZipFile(BytesIO(payload)) as archive:
                return "\n".join(
                    archive.read(name).decode(errors="replace")
                    for name in archive.namelist()
                    if not name.endswith("/")
                )
        return payload.decode(errors="replace")


def collect(api: GitHubApi, pr_number: int, head_sha: str, contexts):
    errors = []
    pr = api.request(f"repos/{api.repository}/pulls/{pr_number}")
    runs = api.paginated(
        f"repos/{api.repository}/actions/runs?head_sha={head_sha}&event=pull_request",
        "workflow_runs",
    )
    checks = api.paginated(
        f"repos/{api.repository}/commits/{head_sha}/check-runs",
        "check_runs",
    )
    statuses = api.request(f"repos/{api.repository}/commits/{head_sha}/status").get("statuses", [])
    try:
        alerts = api.paginated(
            f"repos/{api.repository}/code-scanning/alerts?state=open&pr={pr_number}"
        )
    except (subprocess.CalledProcessError, ValueError) as exc:
        alerts, errors = [], [f"finding collection failed: {exc}"]
    jobs, logs = {}, {}
    for run in latest_runs(runs):
        if run["conclusion"] not in BLOCKING:
            continue
        try:
            run_jobs = api.paginated(
                f"repos/{api.repository}/actions/runs/{run['id']}/jobs",
                "jobs",
            )
            jobs[run["id"]] = run_jobs
            failed_job = next(
                (item for item in run_jobs if text(item.get("conclusion")).lower() in BLOCKING),
                None,
            )
            if failed_job:
                try:
                    job_id = number(failed_job.get("id"))
                    logs[job_id] = api.job_log(job_id)
                except (subprocess.CalledProcessError, zipfile.BadZipFile) as exc:
                    errors.append(f"job log collection failed: {exc}")
        except (subprocess.CalledProcessError, ValueError) as exc:
            errors.append(f"job collection failed for run {run['id']}: {exc}")
    return (
        {
            "current_head_sha": text((pr.get("head") or {}).get("sha")),
            "merge_commit_sha": text(pr.get("merge_commit_sha")),
            "workflow_runs": runs,
            "check_runs": checks,
            "statuses": statuses,
            "security_alerts": alerts,
            "required_contexts": list(contexts),
        },
        jobs,
        logs,
        errors,
    )


def poll(api, pr_number, head_sha, contexts, timeout, interval, stable_polls):
    start, previous, stable = time.monotonic(), "", 0
    while True:
        try:
            sample, jobs, logs, errors = collect(api, pr_number, head_sha, contexts)
        except (subprocess.CalledProcessError, ValueError, json.JSONDecodeError) as exc:
            sample = {
                "current_head_sha": head_sha,
                "merge_commit_sha": "",
                "workflow_runs": [],
                "check_runs": [],
                "statuses": [],
                "security_alerts": [],
                "required_contexts": list(contexts),
            }
            jobs, logs = {}, {}
            errors = [f"terminal snapshot collection failed: {exc}"]
        common = {
            "repository": api.repository,
            "pr_number": pr_number,
            "head_sha": head_sha,
            "current_head_sha": sample["current_head_sha"],
            "merge_commit_sha": sample["merge_commit_sha"],
            "workflow_runs": sample["workflow_runs"],
            "check_runs": sample["check_runs"],
            "statuses": sample["statuses"],
            "required_contexts": sample["required_contexts"],
            "jobs_by_run": jobs,
            "logs_by_job": logs,
            "security_alerts": sample["security_alerts"],
            "required_stable_polls": stable_polls,
            "collection_errors": errors,
        }
        provisional = build_snapshot(stable_poll_count=0, **common)
        current = provisional["workflow_signature"]
        waiting = provisional["pending_workflows"] or provisional["unknown_workflows"]
        waiting = waiting or provisional["pending_required_contexts"]
        waiting = waiting or provisional["unknown_required_contexts"]
        stable = stable + 1 if not waiting and current == previous else (1 if not waiting else 0)
        previous = current
        result = build_snapshot(stable_poll_count=stable, **common)
        if result["review_state"] == "stale" or stable >= stable_polls:
            return result
        if time.monotonic() - start >= timeout:
            return build_snapshot(stable_poll_count=stable, timed_out=True, **common)
        time.sleep(max(interval, 1))


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    for name in (
        "repository",
        "head-sha",
        "handoff-manifest",
        "review-model",
        "required-checks-contract",
        "snapshot-output",
        "comment-output",
    ):
        parser.add_argument(f"--{name}", required=True)
    parser.add_argument("--pr-number", type=int, required=True)
    parser.add_argument("--source-run-id", type=int, required=True)
    parser.add_argument("--source-run-attempt", type=int, required=True)
    parser.add_argument("--timeout-seconds", type=int, default=600)
    parser.add_argument("--poll-interval-seconds", type=int, default=15)
    parser.add_argument("--stable-polls", type=int, default=2)
    args = parser.parse_args(argv or sys.argv[1:])
    token = os.environ.get("GH_TOKEN", "")
    if not token:
        raise SystemExit("trusted workflow token is unavailable")
    verify_handoff(
        Path(args.handoff_manifest),
        args.repository,
        args.pr_number,
        args.head_sha,
        args.source_run_id,
        args.source_run_attempt,
    )
    contract = json.loads(Path(args.required_checks_contract).read_text())
    contexts = contract.get("contexts", [])
    if not isinstance(contexts, list) or not all(isinstance(item, str) for item in contexts):
        raise ValueError("required-check contexts must be strings")
    model = json.loads(Path(args.review_model).read_text())
    result = poll(
        GitHubApi(args.repository, token),
        args.pr_number,
        args.head_sha,
        contexts,
        max(args.timeout_seconds, 1),
        max(args.poll_interval_seconds, 1),
        max(args.stable_polls, 2),
    )
    snapshot_path = Path(args.snapshot_output)
    comment_path = Path(args.comment_output)
    snapshot_path.parent.mkdir(parents=True, exist_ok=True)
    comment_path.parent.mkdir(parents=True, exist_ok=True)
    snapshot_path.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    comment_path.write_text(render_comment(result, model))
    print(f"terminal_snapshot_status={result['snapshot_status']}")
    print(f"terminal_review_state={result['review_state']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
