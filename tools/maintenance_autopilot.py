from __future__ import annotations

import argparse
import datetime as _sdetkit_datetime
import json
import os
import shlex
import shutil
import subprocess
import sys
from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from typing import Any

UTC = getattr(_sdetkit_datetime, "UTC", _sdetkit_datetime.timezone.utc)  # noqa: UP017
_ACTIVE_FAILURE_CONTEXT: dict[str, Any] = {
    "out_dir": None,
    "report": None,
    "commit_safe_fixes": False,
    "token_env": "GH_TOKEN",
    "owner": "",
    "repo": "",
}


def _run(
    cmd: list[str], *, allow_fail: bool = False, env: dict[str, str] | None = None
) -> dict[str, Any]:
    proc = subprocess.run(cmd, capture_output=True, text=True, check=False, env=env)
    result = {
        "cmd": cmd,
        "returncode": proc.returncode,
        "stdout": proc.stdout,
        "stderr": proc.stderr,
        "ok": proc.returncode == 0,
    }
    if not allow_fail and proc.returncode != 0:
        _write_adaptive_diagnosis_on_failure(result)
        raise RuntimeError(
            f"command failed ({proc.returncode}): {' '.join(cmd)}\n"
            f"stdout:\n{proc.stdout}\n\nstderr:\n{proc.stderr}"
        )
    return result


def _load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except ValueError:
        return {}
    return data if isinstance(data, dict) else {}


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _append_jsonl(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(payload, sort_keys=True) + "\n")


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        raw = line.strip()
        if not raw:
            continue
        try:
            item = json.loads(raw)
        except ValueError:
            continue
        if isinstance(item, dict):
            rows.append(item)
    return rows


def _failure_key_for_command(cmd: list[str]) -> str:
    joined = " ".join(cmd)
    if "pre_commit" in joined:
        return "baseline_pre_commit"
    if "pytest" in joined and "test_kpi_audit.py" in joined:
        return "baseline_kpi_test"
    if "ruff" in joined:
        return "baseline_ruff"
    if "repo check" in joined:
        return "enterprise_repo_check"
    if "security check" in joined:
        return "security_actionable"
    if "review" in joined:
        return "review_json"
    return "runtime_failure"


def _write_adaptive_diagnosis_on_failure(failure: dict[str, Any]) -> None:
    out_dir = _ACTIVE_FAILURE_CONTEXT.get("out_dir")
    report = _ACTIVE_FAILURE_CONTEXT.get("report")
    if not isinstance(out_dir, Path) or not isinstance(report, dict):
        return

    try:
        from sdetkit import adaptive_diagnosis
    except Exception as exc:
        _write_json(
            out_dir / "adaptive-diagnosis-error.json",
            {
                "schema_version": "sdetkit.maintenance.autopilot.adaptive_diagnosis_error.v1",
                "ok": False,
                "error": str(exc),
            },
        )
        return

    cmd = [str(part) for part in failure.get("cmd", [])]
    failure_key = _failure_key_for_command(cmd)
    steps: list[dict[str, Any]] = []

    for step_name, step_payload in report.get("steps", {}).items():
        if not isinstance(step_payload, dict):
            continue
        if bool(step_payload.get("ok", True)):
            continue
        steps.append(
            {
                "id": str(step_name),
                "status": "failed",
                "rc": step_payload.get("returncode"),
            }
        )

    steps.append(
        {
            "id": failure_key,
            "status": "failed",
            "rc": failure.get("returncode"),
        }
    )

    log_text = "\n".join(
        [
            "command: " + " ".join(cmd),
            str(failure.get("stdout", "")),
            str(failure.get("stderr", "")),
        ]
    )
    payload = adaptive_diagnosis.analyze_evidence(
        log_text=log_text,
        mission_control={
            "decision": "NO_SHIP",
            "failed_step_count": max(1, len(steps)),
            "steps": steps,
            "artifacts": ["adaptive-diagnosis.json", "adaptive-diagnosis.md"],
        },
        ledger_records=[],
    )

    _write_json(out_dir / "adaptive-diagnosis.json", payload)
    (out_dir / "adaptive-diagnosis.md").write_text(
        adaptive_diagnosis.render_markdown(payload),
        encoding="utf-8",
    )
    _write_safe_fix_artifacts_on_failure(out_dir, payload)


def _write_safe_fix_artifacts_on_failure(out_dir: Path, diagnosis_payload: dict[str, Any]) -> None:
    try:
        from sdetkit import adaptive_safe_fix, adaptive_safe_remediation
    except Exception as exc:
        _write_json(
            out_dir / "adaptive-safe-remediation-error.json",
            {
                "schema_version": "sdetkit.maintenance.autopilot.safe_remediation_error.v1",
                "ok": False,
                "error": str(exc),
            },
        )
        return

    try:
        plan = adaptive_safe_fix.build_plan(diagnosis_payload)
        _write_json(out_dir / "safe-fix-plan.json", plan)

        if not (
            plan.get("safe_to_auto_fix") is True
            and plan.get("fix_type") in {"format_only", "ruff_fixable_lint"}
            and plan.get("requires_human_review") is False
        ):
            _write_safe_fix_learning_outcome(out_dir, plan)
            return

        result = adaptive_safe_remediation.run_plan(plan, cwd=Path.cwd())
        result["plan_path"] = (out_dir / "safe-fix-plan.json").as_posix()
        _write_json(out_dir / "adaptive-safe-remediation-result.json", result)
        (out_dir / "adaptive-safe-remediation-result.md").write_text(
            adaptive_safe_remediation.render_markdown(result),
            encoding="utf-8",
        )
        commit_result = _commit_safe_fix_changes(out_dir, plan, result)
        _write_safe_fix_learning_outcome(out_dir, plan, result, commit_result)
    except Exception as exc:
        _write_json(
            out_dir / "adaptive-safe-remediation-error.json",
            {
                "schema_version": "sdetkit.maintenance.autopilot.safe_remediation_error.v1",
                "ok": False,
                "error": str(exc),
            },
        )


GitRunner = Callable[[list[str]], dict[str, Any]]


def _run_git(cmd: list[str]) -> dict[str, Any]:
    proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
    return {
        "cmd": cmd,
        "returncode": proc.returncode,
        "stdout": proc.stdout,
        "stderr": proc.stderr,
        "ok": proc.returncode == 0,
    }


def _safe_pr_push_target() -> tuple[bool, str, str]:
    if _ACTIVE_FAILURE_CONTEXT.get("commit_safe_fixes") is not True:
        return False, "commit-safe-fixes flag is disabled", ""

    event_name = os.getenv("GITHUB_EVENT_NAME", "")
    if event_name != "pull_request":
        return False, f"event {event_name or '<empty>'} is not pull_request", ""

    head_ref = os.getenv("GITHUB_HEAD_REF", "").strip()
    base_ref = os.getenv("GITHUB_BASE_REF", "").strip()
    if not head_ref:
        return False, "missing GITHUB_HEAD_REF", ""
    if head_ref in {"main", "master"} or head_ref == base_ref:
        return False, "ref is protected or same as base", ""

    token_env = str(_ACTIVE_FAILURE_CONTEXT.get("token_env", "GH_TOKEN"))
    if not os.getenv(token_env, "").strip():
        return False, f"missing token in {token_env}", ""

    event_path = os.getenv("GITHUB_EVENT_PATH", "").strip()
    if not event_path:
        return False, "missing GITHUB_EVENT_PATH", ""

    payload = _load_json(Path(event_path))
    pull_request = payload.get("pull_request", {})
    if not isinstance(pull_request, dict):
        return False, "event payload has no pull_request object", ""

    head = pull_request.get("head", {})
    base = pull_request.get("base", {})
    head_repo = head.get("repo", {}) if isinstance(head, dict) else {}
    base_repo = base.get("repo", {}) if isinstance(base, dict) else {}
    head_full_name = str(head_repo.get("full_name", "")) if isinstance(head_repo, dict) else ""
    base_full_name = str(base_repo.get("full_name", "")) if isinstance(base_repo, dict) else ""
    expected = f"{_ACTIVE_FAILURE_CONTEXT.get('owner')}/{_ACTIVE_FAILURE_CONTEXT.get('repo')}"

    if head_full_name != expected or base_full_name != expected:
        return False, "pull request is not a same-repository branch", ""

    return True, "ok", head_ref


def _allowed_safe_changed_files(plan: dict[str, Any]) -> set[str]:
    values = plan.get("affected_files", [])
    if not isinstance(values, list):
        return set()
    return {
        str(value).strip()
        for value in values
        if str(value).strip() and "<" not in str(value) and ">" not in str(value)
    }


def _git_stdout_lines(result: dict[str, Any]) -> list[str]:
    return [line.strip() for line in str(result.get("stdout", "")).splitlines() if line.strip()]


def _write_safe_fix_commit_result(out_dir: Path, payload: dict[str, Any]) -> None:
    _write_json(out_dir / "adaptive-safe-commit-result.json", payload)


REMEDIATION_EXECUTION_SCHEMA = "sdetkit.maintenance.autopilot.remediation_execution.v1"
REMEDIATION_ALLOWED_STRATEGIES = {
    "run_pre_commit",
    "ruff_format",
    "eof_fixer",
    "trim_trailing_whitespace",
}
REMEDIATION_BLOCKED_CLASSIFICATIONS = {
    "type_contract",
    "runtime_exception",
    "release_artifact",
    "dependency_drift",
    "security",
    "docs_structural_change",
    "workflow_contract",
    "test_contract",
    "quality_contract",
    "unknown",
}
REMEDIATION_SAFE_PATH_PREFIXES = ("src/", "tests/", "tools/")


def _remediation_string(value: Any) -> str:
    return str(value or "").strip()


def _remediation_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes"}


def _remediation_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _remediation_string_list(value: Any) -> list[str]:
    return sorted(
        {
            _remediation_string(item)
            for item in _remediation_list(value)
            if _remediation_string(item)
        }
    )


def _is_safe_repo_owned_path(path: str) -> bool:
    clean = path.strip().replace("\\", "/")
    if not clean or clean.startswith("/") or clean.startswith("~"):
        return False
    if clean in {".", ".."} or "/../" in f"/{clean}/":
        return False
    if "<" in clean or ">" in clean:
        return False
    return clean.startswith(REMEDIATION_SAFE_PATH_PREFIXES)


def _remediation_commands_for_strategy(strategy: str, plan: dict[str, Any]) -> list[str]:
    commands = _remediation_string_list(plan.get("commands_to_run"))
    if commands:
        return commands
    if strategy == "run_pre_commit":
        return ["python -m pre_commit run -a"]
    if strategy == "ruff_format":
        return ["python -m ruff format ."]
    if strategy == "eof_fixer":
        return ["python -m pre_commit run end-of-file-fixer -a"]
    if strategy == "trim_trailing_whitespace":
        return ["python -m pre_commit run trailing-whitespace -a"]
    return []


def _remediation_refusal_reason(plans: list[dict[str, Any]]) -> str:
    if not plans:
        return "remediation plan has no plans"

    blocked = [
        _remediation_string(plan.get("classification") or plan.get("failure_surface") or "unknown")
        for plan in plans
        if _remediation_string(
            plan.get("classification") or plan.get("failure_surface") or "unknown"
        )
        in REMEDIATION_BLOCKED_CLASSIFICATIONS
    ]
    if blocked:
        return "review-first remediation plans are not executable: " + ", ".join(
            sorted(set(blocked))
        )

    non_executable = [
        _remediation_string(plan.get("diagnosis_id") or plan.get("failure_surface") or "unknown")
        for plan in plans
        if plan.get("safe_to_auto_fix") is not True
    ]
    if non_executable:
        return "one or more remediation plans are review-first or not executable"

    strategies = {
        _remediation_string(plan.get("allowed_strategy"))
        for plan in plans
        if _remediation_string(plan.get("allowed_strategy"))
    }
    disallowed = sorted(
        strategy for strategy in strategies if strategy not in REMEDIATION_ALLOWED_STRATEGIES
    )
    if disallowed:
        return "remediation strategy is not allowlisted: " + ", ".join(disallowed)

    affected_files: list[str] = []
    for plan in plans:
        affected_files.extend(_remediation_string_list(plan.get("affected_files")))
    if not affected_files:
        return "remediation plan has no affected files"

    unsafe = sorted(path for path in set(affected_files) if not _is_safe_repo_owned_path(path))
    if unsafe:
        return "remediation plan contains unsafe affected files: " + ", ".join(unsafe)

    return ""


def _safe_fix_plan_from_remediation_plans(plans: list[dict[str, Any]]) -> dict[str, Any]:
    affected_files: set[str] = set()
    commands: list[str] = []
    proof_commands: set[str] = set()
    strategies: set[str] = set()

    for plan in plans:
        strategy = _remediation_string(plan.get("allowed_strategy"))
        strategies.add(strategy)
        affected_files.update(_remediation_string_list(plan.get("affected_files")))
        commands.extend(_remediation_commands_for_strategy(strategy, plan))
        proof_commands.update(_remediation_string_list(plan.get("proof_commands")))

    return {
        "schema_version": "sdetkit.maintenance.autopilot.remediation_plan_bridge.v1",
        "source": "remediation-plan",
        "source_code": "REMEDIATION_PLAN_APPROVED_FORMATTING",
        "title": "Approved remediation-plan formatting-only execution",
        "safe_to_auto_fix": True,
        "fix_type": "format_only",
        "requires_human_review": False,
        "commands": sorted(set(commands)) or ["python -m pre_commit run -a"],
        "proof_commands": sorted(proof_commands),
        "affected_files": sorted(affected_files),
        "allowed_strategy": sorted(strategies),
        "reason": "All remediation plans are approved formatting-only strategies.",
    }


def _render_remediation_execution_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# Remediation execution",
        "",
        f"- Attempted: `{str(bool(payload.get('attempted', False))).lower()}`",
        f"- Allowed: `{str(bool(payload.get('allowed', False))).lower()}`",
        f"- Refused reason: `{payload.get('refused_reason', '')}`",
        f"- Executed strategy: `{payload.get('executed_strategy', 'none')}`",
        f"- Committed: `{str(bool(payload.get('committed', False))).lower()}`",
        f"- Pushed: `{str(bool(payload.get('pushed', False))).lower()}`",
        f"- Commit SHA: `{payload.get('commit_sha', 'none')}`",
        "",
        "## Affected files",
    ]
    files = _remediation_string_list(payload.get("affected_files"))
    if not files:
        lines.append("- None")
    else:
        for file in files:
            lines.append(f"- `{file}`")
    blockers = _remediation_string_list(payload.get("remaining_review_first_blockers"))
    lines.extend(["", "## Remaining review-first blockers"])
    if not blockers:
        lines.append("- None")
    else:
        for blocker in blockers:
            lines.append(f"- `{blocker}`")
    return "\n".join(lines).strip() + "\n"


def _write_remediation_execution_artifacts(out_dir: Path, payload: dict[str, Any]) -> None:
    _write_json(out_dir / "remediation-execution.json", payload)
    (out_dir / "remediation-execution.md").write_text(
        _render_remediation_execution_markdown(payload),
        encoding="utf-8",
    )


def _write_remediation_execution_from_plan(
    out_dir: Path,
    remediation_plan_path: Path,
) -> dict[str, Any]:
    out_dir.mkdir(parents=True, exist_ok=True)
    payload: dict[str, Any] = {
        "schema_version": REMEDIATION_EXECUTION_SCHEMA,
        "ok": False,
        "attempted": False,
        "allowed": False,
        "refused_reason": "",
        "executed_strategy": "none",
        "affected_files": [],
        "command_results": [],
        "committed": False,
        "pushed": False,
        "commit_sha": "none",
        "proof_after_fix_commands": [],
        "remaining_review_first_blockers": [],
        "remediation_plan_path": remediation_plan_path.as_posix(),
    }

    if not remediation_plan_path.exists():
        payload["refused_reason"] = "remediation plan file not found"
        _write_remediation_execution_artifacts(out_dir, payload)
        _write_json(
            out_dir / "remediation-commit-result.json",
            {"ok": False, "reason": payload["refused_reason"]},
        )
        return payload

    remediation_payload = _load_json(remediation_plan_path)
    plans = [
        _bridge_as_dict(item)
        for item in _bridge_as_list(remediation_payload.get("plans"))
        if isinstance(item, dict)
    ]
    payload["plan_count"] = len(plans)
    payload["remaining_review_first_blockers"] = [
        _remediation_string(plan.get("diagnosis_id") or plan.get("failure_surface") or "unknown")
        for plan in plans
        if plan.get("safe_to_auto_fix") is not True
        or _remediation_string(plan.get("classification")) in REMEDIATION_BLOCKED_CLASSIFICATIONS
    ]

    refusal = _remediation_refusal_reason(plans)
    if refusal:
        payload["refused_reason"] = refusal
        payload["affected_files"] = sorted(
            {
                file
                for plan in plans
                for file in _remediation_string_list(plan.get("affected_files"))
            }
        )
        _write_remediation_execution_artifacts(out_dir, payload)
        _write_json(out_dir / "remediation-commit-result.json", {"ok": False, "reason": refusal})
        return payload

    merged_plan = _safe_fix_plan_from_remediation_plans(plans)
    payload["allowed"] = True
    payload["affected_files"] = _remediation_string_list(merged_plan.get("affected_files"))
    payload["executed_strategy"] = ",".join(
        _remediation_string_list(merged_plan.get("allowed_strategy"))
    )
    payload["proof_after_fix_commands"] = _remediation_string_list(
        merged_plan.get("proof_commands")
    )
    _write_json(out_dir / "safe-fix-plan.json", merged_plan)

    from sdetkit import adaptive_safe_remediation

    remediation_result = adaptive_safe_remediation.run_plan(merged_plan, cwd=Path.cwd())
    remediation_result["plan_path"] = (out_dir / "safe-fix-plan.json").as_posix()
    _write_json(out_dir / "adaptive-safe-remediation-result.json", remediation_result)
    (out_dir / "adaptive-safe-remediation-result.md").write_text(
        adaptive_safe_remediation.render_markdown(remediation_result),
        encoding="utf-8",
    )

    commit_result = _commit_safe_fix_changes(out_dir, merged_plan, remediation_result)
    _write_json(out_dir / "remediation-commit-result.json", commit_result)

    payload.update(
        {
            "ok": bool(remediation_result.get("ok", False)),
            "attempted": True,
            "remediation_ok": bool(remediation_result.get("ok", False)),
            "command_results": _bridge_as_list(remediation_result.get("commands")),
            "committed": bool(commit_result.get("committed", False)),
            "pushed": bool(commit_result.get("pushed", False)),
            "commit_sha": str(
                commit_result.get("commit_sha") or commit_result.get("sha") or "none"
            ),
            "commit_ok": bool(commit_result.get("ok", False)),
            "refused_reason": ""
            if bool(remediation_result.get("ok", False))
            else "safe remediation did not succeed",
        }
    )
    _write_remediation_execution_artifacts(out_dir, payload)
    _write_safe_fix_learning_outcome(out_dir, merged_plan, remediation_result, commit_result)
    _write_safe_fix_outcome_artifacts(out_dir)
    return payload


def _write_safe_fix_outcome_artifacts(
    out_dir: Path,
    check_intelligence_path: Path | None = None,
) -> dict[str, Any]:
    from sdetkit import safe_fix_outcome

    outcome = safe_fix_outcome.write_outcome(out_dir)
    if check_intelligence_path is not None and check_intelligence_path.exists():
        check_intelligence = _load_json(check_intelligence_path)
        check_intelligence["safe_fix_outcome"] = outcome
        _write_json(check_intelligence_path, check_intelligence)
    return outcome


def _write_safe_fix_learning_outcome(
    out_dir: Path,
    plan: dict[str, Any],
    remediation_result: dict[str, Any] | None = None,
    commit_result: dict[str, Any] | None = None,
) -> None:
    try:
        from sdetkit import adaptive_diagnosis_memory
    except Exception as exc:
        _write_json(
            out_dir / "adaptive-safe-fix-learning-error.json",
            {
                "schema_version": "sdetkit.maintenance.autopilot.safe_fix_learning_error.v1",
                "ok": False,
                "error": str(exc),
            },
        )
        return

    try:
        record = adaptive_diagnosis_memory.build_safe_fix_learning_record(
            plan=plan,
            remediation_result=remediation_result,
            commit_result=commit_result,
        )
        memory_path = Path(".sdetkit/maintenance/adaptive-safe-fix-memory.jsonl")
        summary = adaptive_diagnosis_memory.append_learning_records(memory_path, [record])
        rollup = adaptive_diagnosis_memory.build_safe_fix_memory_rollup(_read_jsonl(memory_path))
        summary["record_id"] = record.get("record_id", "")
        summary["fix_type"] = record.get("fix_type", "unknown")
        summary["remediation_status"] = record.get("remediation_status", "unknown")
        summary["commit_pushed"] = record.get("commit_pushed", False)
        _write_json(out_dir / "adaptive-safe-fix-learning-result.json", summary)
        _write_json(out_dir / "adaptive-safe-fix-learning-rollup.json", rollup)
    except Exception as exc:
        _write_json(
            out_dir / "adaptive-safe-fix-learning-error.json",
            {
                "schema_version": "sdetkit.maintenance.autopilot.safe_fix_learning_error.v1",
                "ok": False,
                "error": str(exc),
            },
        )


def _commit_safe_fix_changes(
    out_dir: Path,
    plan: dict[str, Any],
    remediation_result: dict[str, Any],
    *,
    git_runner: GitRunner = _run_git,
) -> dict[str, Any]:
    result: dict[str, Any] = {
        "schema_version": "sdetkit.maintenance.autopilot.safe_fix_commit.v1",
        "ok": False,
        "attempted": False,
        "pushed": False,
        "reason": "",
        "changed_files": [],
        "head_ref": "",
    }

    if not bool(remediation_result.get("ok", False)):
        result["reason"] = "safe remediation did not succeed"
        _write_safe_fix_commit_result(out_dir, result)
        return result

    if not (
        plan.get("safe_to_auto_fix") is True
        and plan.get("fix_type") in {"format_only", "ruff_fixable_lint"}
        and plan.get("requires_human_review") is False
    ):
        result["reason"] = "plan is not an approved safe mechanical fix"
        _write_safe_fix_commit_result(out_dir, result)
        return result

    ok, reason, head_ref = _safe_pr_push_target()
    result["head_ref"] = head_ref
    if not ok:
        result["reason"] = reason
        _write_safe_fix_commit_result(out_dir, result)
        return result

    diff = git_runner(["git", "diff", "--name-only"])
    if not bool(diff.get("ok", False)):
        result["reason"] = "git diff failed"
        result["stderr"] = str(diff.get("stderr", ""))[-2000:]
        _write_safe_fix_commit_result(out_dir, result)
        return result

    changed_files = _git_stdout_lines(diff)
    result["changed_files"] = changed_files
    if not changed_files:
        result["reason"] = "safe remediation produced no tracked file changes"
        _write_safe_fix_commit_result(out_dir, result)
        return result

    allowed_files = _allowed_safe_changed_files(plan)
    outside = [item for item in changed_files if item not in allowed_files]
    if outside:
        result["reason"] = "changed files are outside the safe fix plan"
        result["outside_plan"] = outside
        _write_safe_fix_commit_result(out_dir, result)
        return result

    result["attempted"] = True
    commands = [
        ["git", "config", "user.name", "github-actions[bot]"],
        ["git", "config", "user.email", "41898282+github-actions[bot]@users.noreply.github.com"],
        ["git", "add", "--", *changed_files],
        ["git", "commit", "-m", "chore: apply safe mechanical fixes"],
        ["git", "push", "origin", f"HEAD:{head_ref}"],
    ]

    command_results: list[dict[str, Any]] = []
    for cmd in commands:
        item = git_runner(cmd)
        command_results.append(
            {
                "cmd": cmd,
                "ok": bool(item.get("ok", False)),
                "returncode": item.get("returncode"),
                "stdout": str(item.get("stdout", ""))[-2000:],
                "stderr": str(item.get("stderr", ""))[-2000:],
            }
        )
        if not bool(item.get("ok", False)):
            result["reason"] = f"command failed: {' '.join(cmd[:2])}"
            result["commands"] = command_results
            _write_safe_fix_commit_result(out_dir, result)
            return result

    result["ok"] = True
    result["pushed"] = True
    result["reason"] = "safe mechanical fix committed and pushed"
    result["commands"] = command_results
    _write_safe_fix_commit_result(out_dir, result)
    return result


BRIDGE_ONLY_MODE = "_".join(("pr", "quality", "safe", "bridge", "only"))


def _bridge_as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _bridge_as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _safe_plan_from_pr_quality_check(check: dict[str, Any]) -> dict[str, Any]:
    from sdetkit import adaptive_safe_fix

    safe_remediation = _bridge_as_dict(check.get("safe_remediation"))
    diagnosis = _bridge_as_dict(check.get("diagnosis"))
    if check.get("safe_to_auto_fix") is not True:
        return {}
    if safe_remediation.get("safe_to_auto_fix") is not True:
        return {}
    if str(safe_remediation.get("strategy", "")) != "run_pre_commit":
        return {}
    if str(safe_remediation.get("category", "")) != "formatting_only":
        return {}

    affected_files = [
        str(value).strip()
        for value in _bridge_as_list(safe_remediation.get("affected_files"))
        if str(value).strip() and "<" not in str(value) and ">" not in str(value)
    ]
    if not affected_files:
        return {}

    proof_commands = [
        str(value).strip()
        for value in _bridge_as_list(safe_remediation.get("proof_commands"))
        if str(value).strip()
    ] or [
        "python -m pre_commit run -a",
        "python -m ruff check src tests",
        "python -m mypy src",
    ]

    return {
        "schema_version": adaptive_safe_fix.SCHEMA_VERSION,
        "source_schema_version": str(safe_remediation.get("schema_version", "")),
        "source_code": str(
            diagnosis.get("code")
            or _bridge_as_dict(check.get("first_failure")).get("kind")
            or "PRE_COMMIT_FORMAT_DRIFT"
        ).upper(),
        "title": "PR Quality approved formatting-only remediation",
        "safe_to_auto_fix": True,
        "fix_type": "format_only",
        "requires_human_review": False,
        "affected_files": sorted(set(affected_files)),
        "reason": str(
            safe_remediation.get("reason")
            or "PR Quality classified this failure as formatting-only safe remediation."
        ),
        "commands": ["python -m pre_commit run -a"],
        "proof_commands": proof_commands[:3],
    }


def _write_safe_fix_artifacts_from_check_intelligence(
    out_dir: Path,
    check_intelligence_path: Path,
) -> dict[str, Any]:
    out_dir.mkdir(parents=True, exist_ok=True)
    payload: dict[str, Any] = {
        "schema_version": "sdetkit.maintenance.autopilot.pr_quality_safe_remediation_bridge.v1",
        "ok": False,
        "attempted": False,
        "reason": "",
        "check_intelligence_path": check_intelligence_path.as_posix(),
    }

    if not check_intelligence_path.exists():
        payload["reason"] = "check intelligence file not found"
        _write_json(out_dir / "pr-quality-safe-remediation-bridge.json", payload)
        _write_safe_fix_outcome_artifacts(out_dir, check_intelligence_path)
        return payload

    intelligence = _load_json(check_intelligence_path)
    failed_checks = [
        _bridge_as_dict(item)
        for item in _bridge_as_list(intelligence.get("failed_checks"))
        if isinstance(item, dict)
    ]

    if not failed_checks:
        payload["ok"] = True
        payload["reason"] = "no failed checks to remediate"
        _write_json(out_dir / "pr-quality-safe-remediation-bridge.json", payload)
        _write_safe_fix_outcome_artifacts(out_dir, check_intelligence_path)
        return payload

    plans = [_safe_plan_from_pr_quality_check(check) for check in failed_checks]
    eligible_plans = [plan for plan in plans if plan]

    if len(eligible_plans) != len(failed_checks):
        payload["reason"] = "one or more failed checks are review-first or lack affected files"
        payload["failed_check_count"] = len(failed_checks)
        payload["eligible_plan_count"] = len(eligible_plans)
        _write_json(out_dir / "pr-quality-safe-remediation-bridge.json", payload)
        _write_safe_fix_outcome_artifacts(out_dir, check_intelligence_path)
        return payload

    affected_files: set[str] = set()
    for plan in eligible_plans:
        affected_files.update(str(value) for value in _bridge_as_list(plan.get("affected_files")))

    merged_plan = dict(eligible_plans[0])
    merged_plan["affected_files"] = sorted(affected_files)
    merged_plan["reason"] = "All failed checks are PR Quality approved formatting-only remediation."
    _write_json(out_dir / "safe-fix-plan.json", merged_plan)

    from sdetkit import adaptive_safe_remediation

    remediation_result = adaptive_safe_remediation.run_plan(merged_plan, cwd=Path.cwd())
    remediation_result["plan_path"] = (out_dir / "safe-fix-plan.json").as_posix()
    _write_json(out_dir / "adaptive-safe-remediation-result.json", remediation_result)
    (out_dir / "adaptive-safe-remediation-result.md").write_text(
        adaptive_safe_remediation.render_markdown(remediation_result),
        encoding="utf-8",
    )

    commit_result = _commit_safe_fix_changes(out_dir, merged_plan, remediation_result)
    payload.update(
        {
            "ok": bool(remediation_result.get("ok", False)),
            "attempted": True,
            "reason": "PR Quality safe-remediation bridge executed",
            "remediation_ok": bool(remediation_result.get("ok", False)),
            "commit_ok": bool(commit_result.get("ok", False)),
            "commit_pushed": bool(commit_result.get("pushed", False)),
            "commit_sha": str(commit_result.get("commit_sha") or commit_result.get("sha") or ""),
            "affected_files": sorted(affected_files),
        }
    )
    _write_json(out_dir / "pr-quality-safe-remediation-bridge.json", payload)
    _write_safe_fix_learning_outcome(out_dir, merged_plan, remediation_result, commit_result)
    _write_safe_fix_outcome_artifacts(out_dir, check_intelligence_path)
    return payload


POLICY_RULES: dict[str, dict[str, Any]] = {
    "baseline_pre_commit": {
        "actions": ["python -m pre_commit run -a"],
        "route": "auto",
        "min_success_rate_for_auto": 0.5,
    },
    "baseline_kpi_test": {
        "actions": ["PYTHONPATH=src python -m pytest -q tests/test_kpi_audit.py"],
        "route": "review",
        "min_success_rate_for_auto": 1.0,
    },
    "baseline_ruff": {
        "actions": ["ruff check src/sdetkit/kpi_audit.py tools/maintenance_command_center.py"],
        "route": "auto",
        "min_success_rate_for_auto": 0.5,
    },
    "enterprise_repo_check": {
        "actions": [
            "PYTHONPATH=src python -m sdetkit repo check . --profile enterprise --format json --force"
        ],
        "route": "review",
        "min_success_rate_for_auto": 1.0,
    },
    "security_actionable": {
        "actions": ["PYTHONPATH=src python -m sdetkit security check --root . --format json"],
        "route": "review",
        "min_success_rate_for_auto": 1.0,
    },
    "review_json": {
        "actions": ["PYTHONPATH=src python -m sdetkit review . --no-workspace --format json"],
        "route": "review",
        "min_success_rate_for_auto": 1.0,
    },
}


def _policy_actions(key: str) -> list[str]:
    rule = POLICY_RULES.get(key, {})
    actions = rule.get("actions", [])
    return actions if isinstance(actions, list) else []


def _policy_route(key: str) -> str:
    route = str(POLICY_RULES.get(key, {}).get("route", "review")).strip()
    return route if route in {"auto", "review"} else "review"


def _policy_min_success_rate(key: str) -> float:
    raw = POLICY_RULES.get(key, {}).get("min_success_rate_for_auto", 1.0)
    try:
        value = float(raw)
    except (TypeError, ValueError):
        value = 1.0
    return min(max(value, 0.0), 1.0)


def _attempts_in_history(history: list[dict[str, Any]], failure_key: str) -> int:
    return sum(
        1
        for item in history
        if str(item.get("kind", "")) == "remediation_attempt"
        and str(item.get("failure_key", "")) == failure_key
    )


def _runs_since_last_attempt(history: list[dict[str, Any]], failure_key: str) -> int:
    seen_runs: set[str] = set()
    for item in reversed(history):
        run_id = str(item.get("run_id", "")).strip()
        if run_id:
            seen_runs.add(run_id)
        if (
            str(item.get("kind", "")) == "remediation_attempt"
            and str(item.get("failure_key", "")) == failure_key
        ):
            return len(seen_runs)
    return 10**9


def _remediation_success_rate(history: list[dict[str, Any]], failure_key: str) -> float:
    attempts = [
        item
        for item in history
        if str(item.get("kind", "")) == "remediation_attempt"
        and str(item.get("failure_key", "")) == failure_key
    ]
    if not attempts:
        return 1.0
    successes = sum(1 for item in attempts if bool(item.get("ok", False)))
    return successes / len(attempts)


def _summary_from_plan(path: Path) -> dict[str, Any]:
    payload = _load_json(path)
    keep_open = payload.get("keep_open", [])
    defer = payload.get("defer", [])
    return {
        "command_center_issue": payload.get("command_center_issue"),
        "total_bot_trackers": payload.get("total_bot_trackers", 0),
        "keep_open_count": len(keep_open) if isinstance(keep_open, list) else 0,
        "defer_count": len(defer) if isinstance(defer, list) else 0,
        "keep_open_numbers": [
            item.get("number") for item in keep_open if isinstance(item, dict) and "number" in item
        ],
        "defer_numbers": [
            item.get("number") for item in defer if isinstance(item, dict) and "number" in item
        ],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Fully automated maintenance command-center autopilot: baseline checks, enterprise gate, "
            "dry-run validation, and optional live execution."
        )
    )
    parser.add_argument("--owner", required=True)
    parser.add_argument("--repo", required=True)
    parser.add_argument("--out-dir", default="build/maintenance/autopilot")
    parser.add_argument("--run-live-if-token", action="store_true")
    parser.add_argument("--token-env", default="GH_TOKEN")
    parser.add_argument("--memory-db", default=".sdetkit/maintenance/failure-memory.jsonl")
    parser.add_argument("--auto-remediate-safe", action="store_true")
    parser.add_argument("--commit-safe-fixes", action="store_true")
    parser.add_argument("--check-intelligence-json", default="")
    parser.add_argument("--remediation-plan-json", default="")
    parser.add_argument("--pr-quality-safe-bridge-only", action="store_true")
    parser.add_argument("--max-remediation-attempts", type=int, default=3)
    parser.add_argument("--remediation-cooldown-runs", type=int, default=2)
    args = parser.parse_args(argv)

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    report: dict[str, Any] = {
        "schema_version": "sdetkit.maintenance.autopilot.v1",
        "owner": args.owner,
        "repo": args.repo,
        "steps": {},
    }

    _ACTIVE_FAILURE_CONTEXT["out_dir"] = out_dir
    _ACTIVE_FAILURE_CONTEXT["report"] = report
    _ACTIVE_FAILURE_CONTEXT["commit_safe_fixes"] = bool(args.commit_safe_fixes)
    _ACTIVE_FAILURE_CONTEXT["token_env"] = args.token_env
    _ACTIVE_FAILURE_CONTEXT["owner"] = args.owner
    _ACTIVE_FAILURE_CONTEXT["repo"] = args.repo

    if str(args.check_intelligence_json).strip():
        report["steps"]["pr_quality_safe_remediation_bridge"] = (
            _write_safe_fix_artifacts_from_check_intelligence(
                out_dir,
                Path(str(args.check_intelligence_json)),
            )
        )

    if str(args.remediation_plan_json).strip():
        report["steps"]["remediation_plan_execution"] = _write_remediation_execution_from_plan(
            out_dir,
            Path(str(args.remediation_plan_json)),
        )

    if bool(args.pr_quality_safe_bridge_only):
        report["mode"] = BRIDGE_ONLY_MODE
        bridge = report["steps"].get("pr_quality_safe_remediation_bridge", {})
        report["live_run"] = {
            "attempted": False,
            "executed": False,
            "reason": "safe bridge only; skip the full maintenance baseline",
        }
        _write_json(out_dir / "autopilot-report.json", report)
        (out_dir / "autopilot-report.md").write_text(
            "\n".join(
                [
                    "# Maintenance autopilot report",
                    "",
                    f"- mode: `{BRIDGE_ONLY_MODE}`",
                    f"- bridge attempted: `{bool(bridge.get('attempted', False))}`",
                    f"- bridge reason: `{bridge.get('reason', 'n/a')}`",
                    f"- remediation execution attempted: `{bool(report['steps'].get('remediation_plan_execution', {}).get('attempted', False))}`",
                    f"- remediation execution reason: `{report['steps'].get('remediation_plan_execution', {}).get('refused_reason', 'n/a')}`",
                ]
            ).strip()
            + "\n",
            encoding="utf-8",
        )
        print(f"json: {out_dir / 'autopilot-report.json'}")
        print(f"markdown: {out_dir / 'autopilot-report.md'}")
        return 0
    # 1) Baseline checks
    report["steps"]["baseline_pre_commit"] = _run([sys.executable, "-m", "pre_commit", "run", "-a"])
    report["steps"]["baseline_kpi_test"] = _run(
        [sys.executable, "-m", "pytest", "-q", "tests/test_kpi_audit.py"],
        env={**os.environ, "PYTHONPATH": "src"},
    )
    report["steps"]["baseline_ruff"] = _run(
        ["ruff", "check", "src/sdetkit/kpi_audit.py", "tools/maintenance_command_center.py"]
    )
    report["steps"]["baseline_security_check"] = _run(
        [
            sys.executable,
            "-m",
            "sdetkit",
            "security",
            "check",
            "--root",
            ".",
            "--format",
            "json",
            "--out",
            str(out_dir / "security-check.json"),
        ],
        allow_fail=True,
        env={**os.environ, "PYTHONPATH": "src"},
    )

    # 2) Enterprise gate
    shutil.rmtree(".sdetkit/cache", ignore_errors=True)
    shutil.rmtree(".sdetkit/ops-artifacts", ignore_errors=True)
    report["steps"]["enterprise_repo_check"] = _run(
        [
            sys.executable,
            "-m",
            "sdetkit",
            "repo",
            "check",
            ".",
            "--profile",
            "enterprise",
            "--format",
            "json",
            "--out",
            str(out_dir / "sdet_check.json"),
            "--force",
        ],
        env={**os.environ, "PYTHONPATH": "src"},
    )
    sdet_payload = _load_json(out_dir / "sdet_check.json")
    findings = int(sdet_payload.get("summary", {}).get("findings", -1))
    if findings != 0:
        raise RuntimeError(f"enterprise repo check findings expected 0, got {findings}")

    # 3) Build inputs + dry run
    doctor_json = out_dir / "doctor.json"
    review_json = out_dir / "review.json"
    report["steps"]["doctor_json"] = _run(
        [sys.executable, "-m", "sdetkit", "doctor", "--format", "json", "--out", str(doctor_json)],
        allow_fail=True,
        env={**os.environ, "PYTHONPATH": "src"},
    )
    review_run = _run(
        [sys.executable, "-m", "sdetkit", "review", ".", "--no-workspace", "--format", "json"],
        allow_fail=True,
        env={**os.environ, "PYTHONPATH": "src"},
    )
    review_json.write_text(review_run.get("stdout", ""), encoding="utf-8")
    report["steps"]["review_json"] = review_run

    dry_plan = out_dir / "command-center-dry-run-plan.json"
    report["steps"]["command_center_dry_run"] = _run(
        [
            sys.executable,
            "tools/maintenance_command_center.py",
            "--owner",
            args.owner,
            "--repo",
            args.repo,
            "--dry-run",
            "--doctor-json",
            str(doctor_json),
            "--review-json",
            str(review_json),
            "--plan-out",
            str(dry_plan),
            "--db-path",
            str(out_dir / "issue-learning-db.jsonl"),
            "--rollup-path",
            str(out_dir / "issue-learning-rollup.json"),
        ]
    )
    dry_summary = _summary_from_plan(dry_plan)
    report["dry_run_summary"] = dry_summary

    total_bot_trackers = int(dry_summary["total_bot_trackers"])
    if total_bot_trackers < 0:
        raise RuntimeError("dry run returned negative bot tracker count")
    if total_bot_trackers == 0:
        report["dry_run_empty"] = {
            "ok": True,
            "reason": "dry run returned no bot trackers; no maintenance action required",
        }
    elif dry_summary["keep_open_count"] + dry_summary["defer_count"] != total_bot_trackers:
        raise RuntimeError("dry run keep/defer counts do not match total_bot_trackers")

    # 4) Optional live run
    token = os.getenv(args.token_env, "")
    report["live_run"] = {"attempted": False, "executed": False, "token_env": args.token_env}
    if args.run_live_if_token:
        report["live_run"]["attempted"] = True
        if token:
            live_plan = out_dir / "command-center-live-plan.json"
            report["steps"]["command_center_live_run"] = _run(
                [
                    sys.executable,
                    "tools/maintenance_command_center.py",
                    "--owner",
                    args.owner,
                    "--repo",
                    args.repo,
                    "--doctor-json",
                    str(doctor_json),
                    "--review-json",
                    str(review_json),
                    "--plan-out",
                    str(live_plan),
                    "--db-path",
                    ".sdetkit/maintenance/issue-learning-db.jsonl",
                    "--rollup-path",
                    ".sdetkit/maintenance/issue-learning-rollup.json",
                    "--token",
                    token,
                ]
            )
            report["live_run"]["executed"] = True
            report["live_run"]["summary"] = _summary_from_plan(live_plan)
        else:
            report["live_run"]["reason"] = f"missing token in env var {args.token_env}"

    security_payload = _load_json(out_dir / "security-check.json")
    security_counts = (
        security_payload.get("counts", {}) if isinstance(security_payload, dict) else {}
    )
    warn_count = int(security_counts.get("warn", 0) or 0)
    error_count = int(security_counts.get("error", 0) or 0)
    report["security"] = {
        "warn": warn_count,
        "error": error_count,
        "actionable_findings": warn_count + error_count,
        "follow_up_required": (warn_count + error_count) > 0,
    }

    observed_failures: list[dict[str, Any]] = []
    for step_name, step_payload in report.get("steps", {}).items():
        if not isinstance(step_payload, dict):
            continue
        if bool(step_payload.get("ok", True)):
            continue
        observed_failures.append(
            {
                "failure_key": step_name,
                "returncode": step_payload.get("returncode"),
                "policy_actions": _policy_actions(step_name),
            }
        )
    if report["security"]["follow_up_required"]:
        observed_failures.append(
            {
                "failure_key": "security_actionable",
                "returncode": 1,
                "policy_actions": _policy_actions("security_actionable"),
            }
        )

    memory_db = Path(args.memory_db)
    run_id = datetime.now(UTC).isoformat()
    history_before = _read_jsonl(memory_db)
    for item in observed_failures:
        _append_jsonl(
            memory_db,
            {
                "run_id": run_id,
                "owner": args.owner,
                "repo": args.repo,
                "kind": "observed_failure",
                **item,
            },
        )

    history = _read_jsonl(memory_db)
    score: dict[str, int] = {}
    for item in history[-500:]:
        key = str(item.get("failure_key", "")).strip()
        if not key:
            continue
        score[key] = score.get(key, 0) + 1
    top_now = sorted(score.items(), key=lambda pair: (-pair[1], pair[0]))[:5]
    report["follow_up"] = {
        "observed_failures_this_run": observed_failures,
        "memory_db": str(memory_db),
        "top_now": [
            {
                "failure_key": key,
                "seen_runs": count,
                "policy_actions": _policy_actions(key),
                "policy_route": _policy_route(key),
                "success_rate": _remediation_success_rate(history_before, key),
            }
            for key, count in top_now
        ],
        "auto_remediation": [],
    }

    if args.auto_remediate_safe and observed_failures:
        remediation_results: list[dict[str, Any]] = []
        for item in observed_failures:
            key = str(item.get("failure_key", "")).strip()
            if _policy_route(key) != "auto":
                remediation_results.append(
                    {
                        "failure_key": key,
                        "attempted": False,
                        "reason": "policy route is review",
                    }
                )
                continue
            success_rate = _remediation_success_rate(history_before, key)
            min_rate = _policy_min_success_rate(key)
            if success_rate < min_rate:
                remediation_results.append(
                    {
                        "failure_key": key,
                        "attempted": False,
                        "reason": f"success rate below threshold ({success_rate:.2f} < {min_rate:.2f})",
                    }
                )
                continue
            attempts = _attempts_in_history(history_before, key)
            if attempts >= args.max_remediation_attempts:
                remediation_results.append(
                    {
                        "failure_key": key,
                        "attempted": False,
                        "reason": f"max attempts reached ({args.max_remediation_attempts})",
                    }
                )
                continue
            runs_since_last = _runs_since_last_attempt(history_before, key)
            if runs_since_last <= args.remediation_cooldown_runs:
                remediation_results.append(
                    {
                        "failure_key": key,
                        "attempted": False,
                        "reason": f"cooldown active ({runs_since_last} run(s) since last attempt)",
                    }
                )
                continue
            actions = _policy_actions(key)
            if not actions:
                remediation_results.append(
                    {
                        "failure_key": key,
                        "attempted": False,
                        "reason": "no policy actions configured",
                    }
                )
                continue
            cmd = actions[0]
            env = {**os.environ, "PYTHONPATH": "src"}
            result = _run(shlex.split(cmd), allow_fail=True, env=env)
            remediation_results.append(
                {
                    "failure_key": key,
                    "kind": "remediation_attempt",
                    "attempted": True,
                    "command": cmd,
                    "ok": bool(result.get("ok", False)),
                    "returncode": result.get("returncode"),
                }
            )
            _append_jsonl(
                memory_db,
                {
                    "run_id": run_id,
                    "owner": args.owner,
                    "repo": args.repo,
                    "kind": "remediation_attempt",
                    "failure_key": key,
                    "command": cmd,
                    "ok": bool(result.get("ok", False)),
                    "returncode": result.get("returncode"),
                },
            )
        report["follow_up"]["auto_remediation"] = remediation_results

    _write_json(out_dir / "autopilot-report.json", report)

    md = [
        "# Maintenance autopilot report",
        "",
        f"- owner/repo: `{args.owner}/{args.repo}`",
        f"- dry-run total trackers: **{dry_summary['total_bot_trackers']}**",
        f"- dry-run keep_open: **{dry_summary['keep_open_count']}**",
        f"- dry-run defer: **{dry_summary['defer_count']}**",
        f"- dry-run keep_open numbers: `{dry_summary['keep_open_numbers']}`",
        f"- dry-run defer numbers: `{dry_summary['defer_numbers']}`",
        "",
        "## Security",
        f"- warn: **{warn_count}**",
        f"- error: **{error_count}**",
        f"- actionable findings: **{warn_count + error_count}**",
        f"- follow-up required: **{(warn_count + error_count) > 0}**",
        "",
        "## Failure memory + policy follow-up",
        f"- memory db: `{memory_db}`",
        f"- observed failures this run: **{len(observed_failures)}**",
        "- top recurring failure keys:",
    ]
    for item in report["follow_up"]["top_now"]:
        md.append(f"  - `{item['failure_key']}` seen {item['seen_runs']} run(s)")
        md.append(
            f"    - route: `{item.get('policy_route', 'review')}`"
            f" | success_rate: {float(item.get('success_rate', 1.0)):.2f}"
        )
        for action in item.get("policy_actions", []):
            md.append(f"    - auto-policy: `{action}`")
    md.append("- auto-remediation attempts:")
    for item in report["follow_up"].get("auto_remediation", []):
        if not item.get("attempted"):
            md.append(
                f"  - `{item.get('failure_key', 'unknown')}` skipped ({item.get('reason', 'n/a')})"
            )
            continue
        md.append(
            f"  - `{item.get('failure_key', 'unknown')}` attempted: ok={item.get('ok')} rc={item.get('returncode')}"
        )
    md.extend(
        [
            "",
            "## Live run",
            f"- attempted: **{report['live_run']['attempted']}**",
            f"- executed: **{report['live_run']['executed']}**",
        ]
    )
    if not report["live_run"]["executed"] and "reason" in report["live_run"]:
        md.append(f"- reason: `{report['live_run']['reason']}`")
    (out_dir / "autopilot-report.md").write_text("\n".join(md).strip() + "\n", encoding="utf-8")

    print(f"json: {out_dir / 'autopilot-report.json'}")
    print(f"markdown: {out_dir / 'autopilot-report.md'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
