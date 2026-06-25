"""Deterministic, reporting-only post-merge verification evidence."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from .report_provenance import (
    attach_provenance,
    build_input_provenance,
    check_report_path,
    render_freshness_text,
)

JsonObject = dict[str, Any]

SCHEMA_VERSION = "sdetkit.post_merge_verification.v1"
DEFAULT_OUT = "build/sdetkit/post-merge-verification/report.json"
DEFAULT_MARKDOWN_OUT = "build/sdetkit/post-merge-verification/report.md"
GENERATOR_SOURCE = "src/sdetkit/post_merge_verification.py"

EVIDENCE_FILES: dict[str, str] = {
    "pr": "pr.json",
    "commit_status": "main-status.json",
    "review_threads": "review-threads.json",
    "security": "security-check.json",
}

PROTECTED_PATHS: tuple[str, ...] = (
    ".github/workflows/pr-quality-comment.yml",
    ".github/workflows/pr-quality-publisher.yml",
    ".github/workflows/release.yml",
)

COLLECTION_STATES: tuple[str, ...] = (
    "collected",
    "missing",
    "malformed",
    "stale",
    "unavailable",
)
REPORT_STATUSES: tuple[str, ...] = (
    "verified",
    "review_required",
    "unavailable",
)
MERGE_RELATIONS: tuple[str, ...] = (
    "exact_merge_commit",
    "merge_commit_ancestor",
    "head_ancestor",
    "unverified",
    "diverged",
)
CI_STATES: tuple[str, ...] = (
    "success",
    "pending",
    "failure",
    "unavailable",
)
SECURITY_THREAD_STATES: tuple[str, ...] = (
    "current",
    "outdated",
    "resolved",
    "unavailable",
)

_KEYS = {
    "issue_mutation": "_".join(("issue", "mutation", "allowed")),
    "patch_application": "_".join(("patch", "application", "allowed")),
    "workflow_rerun": "_".join(("workflow", "rerun", "allowed")),
    "security_dismissal": "_".join(("security", "dismissal", "allowed")),
    "semantic_equivalence": "_".join(("semantic", "equivalence", "proven")),
}

AUTHORITY_BOUNDARY: JsonObject = {
    "boundary_mode": "reporting_only",
    "reporting_only": True,
    "repo_mutation": False,
    _KEYS["issue_mutation"]: False,
    "automation_allowed": False,
    _KEYS["patch_application"]: False,
    _KEYS["workflow_rerun"]: False,
    _KEYS["security_dismissal"]: False,
    "release_authorized": False,
    "publish_authorized": False,
    "merge_authorized": False,
    _KEYS["semantic_equivalence"]: False,
}

REQUIRED_FIELDS: tuple[str, ...] = (
    "schema_version",
    "status",
    "report_status",
    "generated_at",
    "current_head_sha",
    "previous_main_sha",
    "pr_number",
    "pr_head_sha",
    "merge_commit_sha",
    "merge_relation",
    "merged",
    "changed_paths",
    "protected_path_drift",
    "ci",
    "ghas_review_threads",
    "local_security",
    "input_artifacts",
    "input_digests",
    "input_provenance",
    "authority_boundary",
    "next_allowed_action",
    "reporting_only",
    "repo_mutation",
    _KEYS["issue_mutation"],
    "automation_allowed",
    _KEYS["patch_application"],
    _KEYS["workflow_rerun"],
    _KEYS["security_dismissal"],
    "release_authorized",
    "publish_authorized",
    "merge_authorized",
    _KEYS["semantic_equivalence"],
)


def _valid_sha(value: object) -> bool:
    return (
        isinstance(value, str)
        and re.fullmatch(
            r"[0-9a-f]{40}",
            value.strip().lower(),
        )
        is not None
    )


def _normalized_sha(value: object) -> str:
    if not _valid_sha(value):
        return ""
    return str(value).strip().lower()


def _git(
    root: Path,
    *arguments: str,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-C", str(root), *arguments],
        check=False,
        capture_output=True,
        text=True,
    )


def _commit_exists(root: Path, sha: str) -> bool:
    if not _valid_sha(sha):
        return False
    completed = _git(root, "cat-file", "-e", f"{sha}^{{commit}}")
    return completed.returncode == 0


def _is_ancestor(root: Path, ancestor: str, descendant: str) -> bool:
    if not _commit_exists(root, ancestor):
        return False
    if not _commit_exists(root, descendant):
        return False
    completed = _git(
        root,
        "merge-base",
        "--is-ancestor",
        ancestor,
        descendant,
    )
    if completed.returncode == 0:
        return True
    if completed.returncode == 1:
        return False
    raise RuntimeError(
        f"git merge-base failed: {completed.stderr.strip() or completed.stdout.strip()}"
    )


def _changed_paths(
    root: Path,
    previous_main_sha: str,
    merge_commit_sha: str,
) -> list[str]:
    completed = _git(
        root,
        "diff",
        "--name-only",
        f"{previous_main_sha}..{merge_commit_sha}",
    )
    if completed.returncode != 0:
        raise RuntimeError(
            f"git diff failed: {completed.stderr.strip() or completed.stdout.strip()}"
        )
    return sorted({line.strip() for line in completed.stdout.splitlines() if line.strip()})


def _read_json_artifact(
    path: Path,
) -> tuple[str, JsonObject | None, str, bytes]:
    if not path.is_file():
        return "missing", None, "file missing", b"missing\0"

    try:
        raw = path.read_bytes()
    except OSError as exc:
        return "unavailable", None, f"read failed: {exc}", b"unavailable\0"

    try:
        loaded = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return "malformed", None, "invalid JSON", raw

    if not isinstance(loaded, dict):
        return "malformed", None, "top level is not an object", raw

    return "collected", loaded, "", raw


def _artifact_summary(
    *,
    name: str,
    path: Path,
    state: str,
    reason: str,
) -> JsonObject:
    return {
        "name": name,
        "path": path.as_posix(),
        "collection_status": state,
        "available": state in {"collected", "stale"},
        "reason": reason,
    }


def _extract_status_contexts(
    payload: Mapping[str, Any],
) -> dict[str, str]:
    raw_statuses = payload.get("statuses")
    if not isinstance(raw_statuses, list):
        return {}

    contexts: dict[str, str] = {}
    for row in raw_statuses:
        if not isinstance(row, dict):
            continue
        context = str(row.get("context", "")).strip()
        state = str(row.get("state", "")).strip().lower()
        if context:
            contexts[context] = state
    return contexts


def _normalize_ci_state(value: str) -> str:
    state = value.strip().lower()
    if state == "success":
        return "success"
    if state == "pending":
        return "pending"
    if state in {"failure", "error"}:
        return "failure"
    return "unavailable"


def _extract_review_threads(
    payload: Mapping[str, Any],
) -> list[Mapping[str, Any]] | None:
    data = payload.get("data")
    if not isinstance(data, dict):
        return None
    repository = data.get("repository")
    if not isinstance(repository, dict):
        return None
    pull_request = repository.get("pullRequest")
    if not isinstance(pull_request, dict):
        return None
    review_threads = pull_request.get("reviewThreads")
    if not isinstance(review_threads, dict):
        return None
    nodes = review_threads.get("nodes")
    if not isinstance(nodes, list):
        return None
    return [node for node in nodes if isinstance(node, dict)]


def _review_thread_summary(
    threads: Sequence[Mapping[str, Any]],
) -> JsonObject:
    current = 0
    outdated = 0
    resolved = 0

    for thread in threads:
        if bool(thread.get("isResolved", False)):
            resolved += 1
        elif bool(thread.get("isOutdated", False)):
            outdated += 1
        else:
            current += 1

    return {
        "collection_status": "collected",
        "available": True,
        "current_count": current,
        "outdated_count": outdated,
        "resolved_count": resolved,
        "state_counts": {
            "current": current,
            "outdated": outdated,
            "resolved": resolved,
            "unavailable": 0,
        },
    }


def _security_summary(
    payload: Mapping[str, Any],
) -> JsonObject | None:
    findings = payload.get("findings")
    counts = payload.get("counts")
    if not isinstance(findings, list) or not isinstance(counts, dict):
        return None

    finding_rows = [row for row in findings if isinstance(row, dict)]
    try:
        warnings = int(counts.get("warn", 0))
        errors = int(counts.get("error", 0))
    except (TypeError, ValueError):
        return None

    return {
        "collection_status": "collected",
        "available": True,
        "finding_count": len(finding_rows),
        "warn_count": warnings,
        "error_count": errors,
    }


def _source_run_ids(
    status_payload: Mapping[str, Any] | None,
) -> list[int]:
    if status_payload is None:
        return []

    raw_statuses = status_payload.get("statuses")
    if not isinstance(raw_statuses, list):
        return []

    run_ids: set[int] = set()
    for row in raw_statuses:
        if not isinstance(row, dict):
            continue
        target_url = str(row.get("target_url", ""))
        match = re.search(r"/actions/runs/(\d+)", target_url)
        if match is not None:
            run_ids.add(int(match.group(1)))
    return sorted(run_ids)


def _source_issue_numbers(
    pr_payload: Mapping[str, Any] | None,
) -> list[int]:
    if pr_payload is None:
        return []
    try:
        number = int(pr_payload.get("number", 0))
    except (TypeError, ValueError):
        return []
    return [number] if number > 0 else []


def _merge_relation(
    *,
    root: Path,
    current_head_sha: str,
    pr_head_sha: str,
    merge_commit_sha: str,
) -> str:
    if not _commit_exists(root, current_head_sha):
        return "unverified"

    if _commit_exists(root, merge_commit_sha):
        if merge_commit_sha == current_head_sha:
            return "exact_merge_commit"
        if _is_ancestor(root, merge_commit_sha, current_head_sha):
            return "merge_commit_ancestor"

    if _commit_exists(root, pr_head_sha) and _is_ancestor(
        root,
        pr_head_sha,
        current_head_sha,
    ):
        return "head_ancestor"

    if _valid_sha(merge_commit_sha):
        return "diverged"
    return "unverified"


def post_merge_verification_input_provenance(
    *,
    repo_root: str | Path = ".",
    evidence_dir: str | Path,
    previous_main_sha: str,
    current_head_sha: str | None = None,
    generated_at: str | None = None,
) -> JsonObject:
    root = Path(repo_root).resolve()
    evidence_root = Path(evidence_dir)
    if not evidence_root.is_absolute():
        evidence_root = root / evidence_root

    data_inputs: dict[str, bytes] = {
        "previous_main_sha": previous_main_sha.encode("utf-8"),
    }
    loaded: dict[str, JsonObject | None] = {}
    for name, filename in EVIDENCE_FILES.items():
        path = evidence_root / filename
        _, payload, _, raw = _read_json_artifact(path)
        loaded[name] = payload
        data_inputs[f"evidence:{name}"] = raw

    return build_input_provenance(
        schema_version=SCHEMA_VERSION,
        generator_source=GENERATOR_SOURCE,
        generator_bytes=Path(__file__).read_bytes(),
        data_inputs=data_inputs,
        root=root,
        source_issue_numbers=_source_issue_numbers(loaded["pr"]),
        source_run_ids=_source_run_ids(loaded["commit_status"]),
        current_head_sha=current_head_sha,
        generated_at=generated_at,
    )


def build_post_merge_verification(
    repo_root: str | Path = ".",
    *,
    evidence_dir: str | Path,
    previous_main_sha: str,
    current_head_sha: str | None = None,
    generated_at: str | None = None,
) -> JsonObject:
    root = Path(repo_root).resolve()
    evidence_root = Path(evidence_dir)
    if not evidence_root.is_absolute():
        evidence_root = root / evidence_root

    provenance = post_merge_verification_input_provenance(
        repo_root=root,
        evidence_dir=evidence_root,
        previous_main_sha=previous_main_sha,
        current_head_sha=current_head_sha,
        generated_at=generated_at,
    )
    current_head = str(provenance.get("generated_from_head_sha", ""))

    artifacts: dict[str, JsonObject] = {}
    loaded: dict[str, JsonObject | None] = {}
    for name, filename in EVIDENCE_FILES.items():
        path = evidence_root / filename
        state, payload, reason, _ = _read_json_artifact(path)
        artifacts[name] = _artifact_summary(
            name=name,
            path=path,
            state=state,
            reason=reason,
        )
        loaded[name] = payload

    pr_payload = loaded["pr"]
    pr_number = 0
    pr_head_sha = ""
    pr_base_sha = ""
    merge_commit_sha = ""
    merged = False
    pr_state = ""

    if pr_payload is not None:
        try:
            pr_number = int(pr_payload.get("number", 0))
        except (TypeError, ValueError):
            pr_number = 0
        head_value = pr_payload.get("head")
        base_value = pr_payload.get("base")
        if isinstance(head_value, dict):
            pr_head_sha = _normalized_sha(head_value.get("sha"))
        if isinstance(base_value, dict):
            pr_base_sha = _normalized_sha(base_value.get("sha"))
        merge_commit_sha = _normalized_sha(pr_payload.get("merge_commit_sha"))
        merged = bool(pr_payload.get("merged", False))
        pr_state = str(pr_payload.get("state", "")).strip().lower()

        if pr_number <= 0 or not pr_head_sha or not pr_base_sha or not merge_commit_sha:
            artifacts["pr"]["collection_status"] = "unavailable"
            artifacts["pr"]["available"] = False
            artifacts["pr"]["reason"] = "required PR fields missing"
        elif pr_base_sha != previous_main_sha.strip().lower():
            artifacts["pr"]["collection_status"] = "stale"
            artifacts["pr"]["reason"] = "PR base does not match previous main"

    relation = _merge_relation(
        root=root,
        current_head_sha=current_head,
        pr_head_sha=pr_head_sha,
        merge_commit_sha=merge_commit_sha,
    )

    changed_paths: list[str] = []
    protected_path_drift: list[str] = []
    git_collection_status = "collected"
    git_reason = ""

    if not _valid_sha(previous_main_sha):
        git_collection_status = "unavailable"
        git_reason = "previous main SHA is invalid"
    elif not _commit_exists(root, previous_main_sha):
        git_collection_status = "unavailable"
        git_reason = "previous main commit is missing"
    elif not _commit_exists(root, merge_commit_sha):
        git_collection_status = "unavailable"
        git_reason = "merge commit is missing"
    else:
        try:
            changed_paths = _changed_paths(
                root,
                previous_main_sha.strip().lower(),
                merge_commit_sha,
            )
        except RuntimeError as exc:
            git_collection_status = "unavailable"
            git_reason = str(exc)
        else:
            protected_path_drift = sorted(set(changed_paths).intersection(PROTECTED_PATHS))

    ci_summary: JsonObject = {
        "collection_status": artifacts["commit_status"]["collection_status"],
        "available": False,
        "state": "unavailable",
        "contexts": {},
    }
    status_payload = loaded["commit_status"]
    if status_payload is not None:
        contexts = _extract_status_contexts(status_payload)
        ci_state = _normalize_ci_state(contexts.get("ci", ""))
        ci_summary = {
            "collection_status": ("collected" if ci_state != "unavailable" else "unavailable"),
            "available": ci_state != "unavailable",
            "state": ci_state,
            "contexts": contexts,
        }
        if ci_state == "unavailable":
            artifacts["commit_status"]["collection_status"] = "unavailable"
            artifacts["commit_status"]["available"] = False
            artifacts["commit_status"]["reason"] = "CI context is missing or unknown"

    thread_summary: JsonObject = {
        "collection_status": artifacts["review_threads"]["collection_status"],
        "available": False,
        "current_count": 0,
        "outdated_count": 0,
        "resolved_count": 0,
        "state_counts": {
            "current": 0,
            "outdated": 0,
            "resolved": 0,
            "unavailable": 1,
        },
    }
    review_payload = loaded["review_threads"]
    if review_payload is not None:
        threads = _extract_review_threads(review_payload)
        if threads is None:
            artifacts["review_threads"]["collection_status"] = "unavailable"
            artifacts["review_threads"]["available"] = False
            artifacts["review_threads"]["reason"] = "review-thread envelope is missing"
        else:
            thread_summary = _review_thread_summary(threads)

    local_security: JsonObject = {
        "collection_status": artifacts["security"]["collection_status"],
        "available": False,
        "finding_count": 0,
        "warn_count": 0,
        "error_count": 0,
    }
    security_payload = loaded["security"]
    if security_payload is not None:
        parsed_security = _security_summary(security_payload)
        if parsed_security is None:
            artifacts["security"]["collection_status"] = "unavailable"
            artifacts["security"]["available"] = False
            artifacts["security"]["reason"] = "security contract is missing"
        else:
            local_security = parsed_security

    collection_states = {item["collection_status"] for item in artifacts.values()}
    collection_states.add(git_collection_status)

    required_unavailable = bool(
        collection_states.intersection({"missing", "malformed", "unavailable"})
    )
    stale_evidence = "stale" in collection_states
    canonical_merge_relation = relation in {
        "exact_merge_commit",
        "merge_commit_ancestor",
    }

    verified = all(
        (
            not required_unavailable,
            not stale_evidence,
            merged,
            pr_state == "closed",
            canonical_merge_relation,
            ci_summary["state"] == "success",
            thread_summary["current_count"] == 0,
            local_security["finding_count"] == 0,
            local_security["warn_count"] == 0,
            local_security["error_count"] == 0,
            not protected_path_drift,
        )
    )

    if required_unavailable:
        status = "unavailable"
    elif verified:
        status = "verified"
    else:
        status = "review_required"

    payload: JsonObject = {
        "schema_version": SCHEMA_VERSION,
        "tool": "sdetkit.post_merge_verification",
        "status": status,
        "report_status": "passed",
        "previous_main_sha": previous_main_sha.strip().lower(),
        "pr_number": pr_number,
        "pr_head_sha": pr_head_sha,
        "pr_base_sha": pr_base_sha,
        "merge_commit_sha": merge_commit_sha,
        "merge_relation": relation,
        "merged": merged,
        "pr_state": pr_state,
        "changed_paths": changed_paths,
        "protected_path_drift": protected_path_drift,
        "git": {
            "collection_status": git_collection_status,
            "available": git_collection_status == "collected",
            "reason": git_reason,
        },
        "ci": ci_summary,
        "ghas_review_threads": thread_summary,
        "local_security": local_security,
        "input_artifacts": artifacts,
        "reporting_only": True,
        "repo_mutation": False,
        _KEYS["issue_mutation"]: False,
        "automation_allowed": False,
        _KEYS["patch_application"]: False,
        _KEYS["workflow_rerun"]: False,
        _KEYS["security_dismissal"]: False,
        "release_authorized": False,
        "publish_authorized": False,
        "merge_authorized": False,
        _KEYS["semantic_equivalence"]: False,
        "authority_boundary": dict(AUTHORITY_BOUNDARY),
        "next_allowed_action": "human_post_merge_review",
    }
    return attach_provenance(payload, provenance)


def check_post_merge_verification_freshness(
    *,
    repo_root: str | Path = ".",
    evidence_dir: str | Path,
    previous_main_sha: str,
    report_path: str | Path = DEFAULT_OUT,
    current_head_sha: str | None = None,
) -> JsonObject:
    current = post_merge_verification_input_provenance(
        repo_root=repo_root,
        evidence_dir=evidence_dir,
        previous_main_sha=previous_main_sha,
        current_head_sha=current_head_sha,
    )
    return check_report_path(
        report_path,
        current,
        expected_schema_version=SCHEMA_VERSION,
    )


def render_post_merge_verification_markdown(
    payload: Mapping[str, Any],
) -> str:
    ci = payload.get("ci", {})
    if not isinstance(ci, dict):
        ci = {}
    threads = payload.get("ghas_review_threads", {})
    if not isinstance(threads, dict):
        threads = {}
    security = payload.get("local_security", {})
    if not isinstance(security, dict):
        security = {}

    lines = [
        "# Post-merge verification",
        "",
        f"- schema_version: `{payload.get('schema_version', '')}`",
        f"- status: `{payload.get('status', 'unavailable')}`",
        f"- report_status: `{payload.get('report_status', '')}`",
        f"- generated_at: `{payload.get('generated_at', '')}`",
        f"- current_head_sha: `{payload.get('current_head_sha', '')}`",
        f"- previous_main_sha: `{payload.get('previous_main_sha', '')}`",
        f"- pr_number: `{payload.get('pr_number', 0)}`",
        f"- pr_head_sha: `{payload.get('pr_head_sha', '')}`",
        f"- merge_commit_sha: `{payload.get('merge_commit_sha', '')}`",
        f"- merge_relation: `{payload.get('merge_relation', 'unverified')}`",
        f"- merged: `{str(bool(payload.get('merged', False))).lower()}`",
        "- reporting_only: `true`",
        "- merge_authorized: `false`",
        "",
        "## Collection summary",
        "",
        f"- ci: `{ci.get('state', 'unavailable')}`",
        (f"- current_ghas_threads: `{threads.get('current_count', 0)}`"),
        (f"- outdated_ghas_threads: `{threads.get('outdated_count', 0)}`"),
        (f"- resolved_ghas_threads: `{threads.get('resolved_count', 0)}`"),
        (f"- local_security_findings: `{security.get('finding_count', 0)}`"),
        "",
        "## Changed paths",
        "",
    ]

    changed_paths = payload.get("changed_paths", [])
    if isinstance(changed_paths, list) and changed_paths:
        for path in changed_paths:
            lines.append(f"- `{path}`")
    else:
        lines.append("- none")

    lines.extend(["", "## Protected-path drift", ""])
    drift = payload.get("protected_path_drift", [])
    if isinstance(drift, list) and drift:
        for path in drift:
            lines.append(f"- `{path}`")
    else:
        lines.append("- none")

    lines.extend(["", "## Input artifacts", ""])
    artifacts = payload.get("input_artifacts", {})
    if isinstance(artifacts, dict):
        for name, item in sorted(artifacts.items()):
            if not isinstance(item, dict):
                continue
            lines.append(
                f"- `{name}`: "
                f"`{item.get('collection_status', 'unavailable')}` "
                f"({item.get('reason', '')})"
            )

    lines.extend(["", "## Authority boundary", ""])
    boundary = payload.get("authority_boundary", {})
    if isinstance(boundary, dict):
        for key, value in boundary.items():
            rendered = str(value).lower() if isinstance(value, bool) else value
            lines.append(f"- {key}: `{rendered}`")

    lines.extend(
        [
            "",
            (
                "_Reporting-only. This report does not authorize "
                "repository mutation, workflow reruns, security dismissal, "
                "release, publishing, merging, or semantic-equivalence "
                "claims._"
            ),
        ]
    )
    return "\n".join(lines)


def write_post_merge_verification(
    repo_root: str | Path = ".",
    *,
    evidence_dir: str | Path,
    previous_main_sha: str,
    out_json: str | Path = DEFAULT_OUT,
    out_md: str | Path = DEFAULT_MARKDOWN_OUT,
    current_head_sha: str | None = None,
    generated_at: str | None = None,
) -> JsonObject:
    payload = build_post_merge_verification(
        repo_root,
        evidence_dir=evidence_dir,
        previous_main_sha=previous_main_sha,
        current_head_sha=current_head_sha,
        generated_at=generated_at,
    )

    json_path = Path(out_json)
    markdown_path = Path(out_md)
    json_path.parent.mkdir(parents=True, exist_ok=True)
    markdown_path.parent.mkdir(parents=True, exist_ok=True)

    json_path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    markdown_path.write_text(
        render_post_merge_verification_markdown(payload) + "\n",
        encoding="utf-8",
    )
    return payload


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="sdetkit post-merge-verification")
    parser.add_argument("--root", default=".")
    parser.add_argument("--evidence-dir", required=True)
    parser.add_argument("--previous-main-sha", required=True)
    parser.add_argument("--out-json", default=DEFAULT_OUT)
    parser.add_argument("--out-md", default=DEFAULT_MARKDOWN_OUT)
    parser.add_argument(
        "--format",
        choices=["json", "text"],
        default="text",
    )
    parser.add_argument("--check-freshness", action="store_true")
    args = parser.parse_args(list(argv) if argv is not None else None)

    if args.check_freshness:
        freshness = check_post_merge_verification_freshness(
            repo_root=args.root,
            evidence_dir=args.evidence_dir,
            previous_main_sha=args.previous_main_sha,
            report_path=args.out_json,
        )
        if args.format == "json":
            sys.stdout.write(
                json.dumps(
                    freshness,
                    indent=2,
                    sort_keys=True,
                )
                + "\n"
            )
        else:
            sys.stdout.write(render_freshness_text(freshness) + "\n")
        return 0 if freshness["fresh"] else 1

    payload = write_post_merge_verification(
        repo_root=args.root,
        evidence_dir=args.evidence_dir,
        previous_main_sha=args.previous_main_sha,
        out_json=args.out_json,
        out_md=args.out_md,
    )
    if args.format == "json":
        sys.stdout.write(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    else:
        sys.stdout.write(render_post_merge_verification_markdown(payload) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
