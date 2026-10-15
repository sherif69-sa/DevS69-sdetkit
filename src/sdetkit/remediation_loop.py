"""Local remediation loop: from a saved CI log to an independently verified decision.

The loop chains the existing engines and never edits the caller's working tree:

1. extract the first real failure from each log (shared multi-ecosystem engine)
2. classify the checks, build diagnostic vectors and a remediation plan
3. record the SafetyGate decision for each failure vector
4. with ``--prove``: apply the narrowest mechanical fix in a throwaway copy,
   collect the diff as the proposed patch, score it, run the plan's proof
   profiles in a second isolated copy and hand the evidence to the
   independent verifier
5. record a trajectory, write an operator report, and bind every stage into
   a hash-linked protected proof chain

Every authority flag stays false: the loop proposes and proves, a person decides.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
import tempfile
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from sdetkit import check_intelligence, ci_failure_extractor
from sdetkit.decision_card import write_decision_card
from sdetkit.diagnostic_vector_engine import build_diagnostic_vector
from sdetkit.failure_vector_adapters import build_ecosystem_failure_vector_bundle
from sdetkit.gates.latest_run import LATEST_RUN_PATH, load_latest_run, write_failed_step_logs
from sdetkit.isolated_proof_runner import (
    PROOF_PROFILES,
    _execution_environment,
    _prepare_isolated_workspace,
    run_isolated_proof,
)
from sdetkit.patch_scorer import score_patch
from sdetkit.protected_proof_chain import build_protected_proof_chain
from sdetkit.protected_verifier import STRUCTURALLY_VERIFIED_CANDIDATE, verify_candidate
from sdetkit.remediation_plan_engine import build_remediation_plan
from sdetkit.repo_memory import (
    DEFAULT_MEMORY_PATH,
    append_records,
    build_pattern_insights,
    load_records,
)
from sdetkit.trajectory_store import build_trajectory_records, summarize_trajectory_records
from sdetkit.verdict import build_verdict, git_provenance

SCHEMA_VERSION = "sdetkit.remediation_loop.v1"
JOB_SCHEMA_VERSION = "sdetkit.remediation_loop.job.v1"
DEFAULT_OUT_DIR = Path("build") / "sdetkit" / "remediation-loop"
DEFAULT_TIMEOUT_SECONDS = 600

JsonObject = dict[str, Any]

DECISION_BOUNDARY: dict[str, bool] = {
    "automation_allowed": False,
    "patch_application_allowed": False,
    "merge_authorized": False,
    "semantic_equivalence_proven": False,
    "security_dismissal_allowed": False,
}

# The only fixes the loop will run, keyed by failure class. Each one is
# deterministic, Python-only for now, and limited to the SafetyGate's files.
MECHANICAL_FIXERS: dict[str, tuple[str, ...]] = {
    "formatter_only": ("-m", "ruff", "format"),
    "lint": ("-m", "ruff", "check", "--fix"),
}

DECISION_REVIEW_FIRST = "review_first"
DECISION_PROOF_NOT_RUN = "proof_not_run"
DECISION_NO_CHANGE = "no_change"
DECISION_VERIFIED = "verified_candidate"
DECISION_BLOCKED = "blocked_review_first"

_REMOTE_RE = re.compile(r"[:/](?P<owner>[^/:\s]+)/(?P<name>[^/\s]+?)(?:\.git)?/?$")


def _as_dict(value: Any) -> JsonObject:
    return value if isinstance(value, dict) else {}


def _as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _string(value: Any) -> str:
    return str(value or "").strip()


def _write_json(path: Path, payload: Mapping[str, Any]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def _git(cwd: Path, *args: str, env: Mapping[str, str] | None = None) -> str:
    completed = subprocess.run(
        ["git", *args],
        cwd=cwd,
        env=dict(env) if env is not None else None,
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
        shell=False,
    )
    if completed.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} failed: {completed.stderr.strip()}")
    return completed.stdout


def _repository_identity(repo_root: Path) -> tuple[str, str]:
    """Return (owner/name, HEAD sha); empty strings when not a git checkout."""

    try:
        commit_sha = _git(repo_root, "rev-parse", "HEAD").strip()
    except (RuntimeError, OSError):
        return "", ""
    repository = ""
    try:
        remote = _git(repo_root, "remote", "get-url", "origin").strip()
    except (RuntimeError, OSError):
        remote = ""
    match = _REMOTE_RE.search(remote)
    if match:
        repository = f"{match.group('owner')}/{match.group('name')}"
    else:
        name = re.sub(r"[^\w.-]+", "-", repo_root.resolve().name) or "repository"
        repository = f"local/{name}"
    return repository, commit_sha


def _select_candidate(
    plan_doc: Mapping[str, Any], bundle: Mapping[str, Any]
) -> tuple[JsonObject, JsonObject, list[str]]:
    """Pick the first plan that both the plan engine and the SafetyGate allow.

    Returns (plan, safety_gate_vector, reasons_when_none).
    """

    reasons: list[str] = []
    vectors = [_as_dict(item) for item in _as_list(bundle.get("failure_vectors"))]
    plans = [_as_dict(item) for item in _as_list(plan_doc.get("plans"))]
    if not plans:
        return {}, {}, ["no remediation plan was produced for the supplied logs"]
    for plan in plans:
        diagnosis = _string(plan.get("diagnosis_id")) or "unknown"
        if not plan.get("safe_to_auto_fix"):
            reasons.append(
                f"{diagnosis}: plan is review-first ({_string(plan.get('blocked_reason')) or 'not mechanically eligible'})"
            )
            continue
        scope = set(_as_list(_as_dict(plan.get("exact_fix_scope")).get("allowed_files")))
        for vector in vectors:
            gate = _as_dict(vector.get("safety_gate"))
            adapter = _as_dict(vector.get("adapter"))
            allowed = set(_as_list(gate.get("allowed_files")))
            if not gate.get("safe_fix_allowed"):
                continue
            if adapter.get("ecosystem") != "python":
                continue
            if _string(vector.get("failure_class")) not in MECHANICAL_FIXERS:
                continue
            if scope and not scope <= allowed:
                continue
            return plan, vector, []
        reasons.append(f"{diagnosis}: no SafetyGate decision allows a mechanical fix for its files")
    return {}, {}, reasons


def _proof_profiles(proof_commands: Sequence[str]) -> tuple[list[str], list[str]]:
    by_command = {profile.canonical_command: pid for pid, profile in PROOF_PROFILES.items()}
    profiles: list[str] = []
    unmapped: list[str] = []
    for command in proof_commands:
        profile_id = by_command.get(_string(command))
        if profile_id:
            profiles.append(profile_id)
        else:
            unmapped.append(_string(command))
    return profiles, unmapped


def _apply_fix_in_copy(
    *,
    repo_root: Path,
    workspace: Path,
    failure_class: str,
    allowed_files: Sequence[str],
    timeout_seconds: int,
) -> JsonObject:
    """Run the mechanical fixer in a fresh copy and commit its result there."""

    _prepare_isolated_workspace(repo_root.resolve(), workspace)
    environment = _execution_environment()
    baseline_sha = _git(workspace, "rev-parse", "HEAD", env=environment).strip()
    argv = [sys.executable, *MECHANICAL_FIXERS[failure_class], *allowed_files]
    completed = subprocess.run(
        argv,
        cwd=workspace,
        env=environment,
        capture_output=True,
        text=True,
        timeout=timeout_seconds,
        check=False,
        shell=False,
    )
    _git(workspace, "add", "-A", env=environment)
    status = _git(workspace, "status", "--porcelain", env=environment).strip()
    if status:
        _git(
            workspace,
            "-c",
            "user.name=SDETKit Remediation Loop",
            "-c",
            "user.email=remediation-loop@invalid.local",
            "commit",
            "--quiet",
            "--no-verify",
            "-m",
            "remediation loop candidate",
            env=environment,
        )
    diff = _git(workspace, "diff", "--no-ext-diff", baseline_sha, "HEAD", env=environment)
    changed = [
        line
        for line in _git(
            workspace, "diff", "--name-only", baseline_sha, "HEAD", env=environment
        ).splitlines()
        if line.strip()
    ]
    return {
        "command": " ".join(["python", *MECHANICAL_FIXERS[failure_class], *allowed_files]),
        "exit_code": completed.returncode,
        "baseline_sha": baseline_sha,
        "changed_files": sorted(changed),
        "diff": diff,
    }


def _next_action(decision: str, reasons: Sequence[str], log_args: str) -> str:
    if decision == DECISION_PROOF_NOT_RUN:
        return " ".join(
            part for part in ("python -m sdetkit diagnose run", log_args, "--prove") if part
        )
    if decision == DECISION_VERIFIED:
        return "Review proposed.patch; if you accept it, apply it with `git apply` on a branch."
    if decision == DECISION_NO_CHANGE:
        return "The fix changed nothing in a fresh copy; the failure may be stale or already fixed. Re-collect the CI log."
    if decision == DECISION_BLOCKED:
        return (
            "Read the verifier findings in protected-verifier-result.json before changing anything."
        )
    return reasons[0] if reasons else "Review the diagnosis and choose a fix by hand."


def _memory_line(memory: Mapping[str, Any]) -> str:
    if not memory.get("enabled"):
        return "- RepoMemory: off"
    return (
        f"- RepoMemory: {memory.get('records_before', 0)} earlier records, "
        f"{memory.get('proven_fix_patterns', 0)} proven fix patterns"
    )


def _render_report(summary: Mapping[str, Any]) -> str:
    candidate = _as_dict(summary.get("candidate"))
    lines = [
        "# SDETKit remediation loop",
        "",
        f"- decision: `{summary['decision']}`",
        f"- logs: {len(_as_list(summary.get('logs')))}",
        f"- failures: {summary.get('failure_count', 0)}",
        f"- real working tree modified: `{str(summary['real_tree_modified']).lower()}`",
        _memory_line(_as_dict(summary.get("memory"))),
        "",
        "## Next action",
        "",
        str(summary.get("next_action", "")),
        "",
    ]
    if candidate:
        lines += [
            "## Candidate",
            "",
            f"- diagnosis: `{candidate.get('diagnosis_id', '')}`",
            f"- failure class: `{candidate.get('failure_class', '')}`",
            f"- allowed files: {', '.join(candidate.get('allowed_files', [])) or 'none'}",
            f"- fix command: `{candidate.get('fix_command', 'not run')}`",
            f"- changed files: {', '.join(candidate.get('changed_files', [])) or 'none'}",
            f"- patch score: {candidate.get('patch_score', 'not scored')}",
            f"- proof: `{candidate.get('proof_status', 'not run')}`",
            f"- verifier: `{candidate.get('verifier_status', 'not run')}`",
            "",
        ]
    reasons = _as_list(summary.get("reasons"))
    if reasons:
        lines += ["## Why not automatic", ""] + [f"- {reason}" for reason in reasons] + [""]
    lines += [
        "## Authority",
        "",
        "Every authority flag is false. The loop proposes and proves; a person applies.",
        "",
    ]
    return "\n".join(lines)


def run_remediation_loop(
    *,
    log_paths: Sequence[str | Path],
    repo_root: Path = Path("."),
    out_dir: Path = DEFAULT_OUT_DIR,
    prove: bool = False,
    timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS,
    memory_path: Path | None = DEFAULT_MEMORY_PATH,
    rerun_args: str | None = None,
) -> JsonObject:
    """`rerun_args` replaces the `--log` arguments in the suggested next command."""

    if not log_paths:
        raise ValueError("at least one --log is required")
    out_dir.mkdir(parents=True, exist_ok=True)
    repo_root = repo_root.resolve()
    logs = [Path(path) for path in log_paths]
    artifacts: dict[str, str] = {}

    def record(name: str, path: Path) -> None:
        artifacts[name] = path.as_posix()

    repository, commit_sha = _repository_identity(repo_root)
    log_digests = {path.as_posix(): hashlib.sha256(path.read_bytes()).hexdigest() for path in logs}
    job = {
        "schema_version": JOB_SCHEMA_VERSION,
        "job_id": hashlib.sha256(
            json.dumps([commit_sha, sorted(log_digests.items())]).encode()
        ).hexdigest()[:16],
        "repository": repository or "unknown",
        "commit_sha": commit_sha or "unknown",
        "logs": log_digests,
        "mode": "prove" if prove else "diagnose",
        **DECISION_BOUNDARY,
    }
    record("job", _write_json(out_dir / "job.json", job))

    failed_check_logs = ci_failure_extractor.build_failed_check_logs(logs)
    record("failed_check_logs", _write_json(out_dir / "failed-check-logs.json", failed_check_logs))
    intelligence = check_intelligence.build_check_intelligence(
        checks_json=out_dir / "failed-check-logs.json", current_head_sha=commit_sha
    )
    record("check_intelligence", _write_json(out_dir / "check-intelligence.json", intelligence))
    vector = build_diagnostic_vector(check_intelligence=intelligence)
    record("diagnostic_vector", _write_json(out_dir / "diagnostic-vector.json", vector))
    plan_doc = build_remediation_plan(vector)
    record("remediation_plan", _write_json(out_dir / "remediation-plan.json", plan_doc))
    bundle = build_ecosystem_failure_vector_bundle(logs)
    record("failure_vector", _write_json(out_dir / "failure-vector.json", bundle))

    memory_before = load_records(memory_path) if memory_path is not None else []
    insights = build_pattern_insights(memory_before)
    record("pattern_insights", _write_json(out_dir / "pattern-insights.json", insights))

    plan, safety_vector, reasons = _select_candidate(plan_doc, bundle)
    first_vector = _as_dict(next(iter(_as_list(bundle.get("failure_vectors"))), {}))
    safety_gate = _as_dict(safety_vector.get("safety_gate")) or _as_dict(
        first_vector.get("safety_gate")
    )
    record("safety_gate", _write_json(out_dir / "safety-gate.json", safety_gate))

    candidate: JsonObject = {}
    decision = DECISION_REVIEW_FIRST
    verifier: JsonObject = {}
    evidence: JsonObject = {}
    if plan:
        allowed_files = sorted(_as_list(safety_gate.get("allowed_files")))
        candidate = {
            "diagnosis_id": _string(plan.get("diagnosis_id")),
            "failure_class": _string(safety_vector.get("failure_class")),
            "allowed_files": allowed_files,
        }
        decision = DECISION_PROOF_NOT_RUN
        if prove:
            with tempfile.TemporaryDirectory(prefix="sdetkit-loop-") as temp_dir:
                workspace = Path(temp_dir) / "workspace"
                fix = _apply_fix_in_copy(
                    repo_root=repo_root,
                    workspace=workspace,
                    failure_class=candidate["failure_class"],
                    allowed_files=allowed_files,
                    timeout_seconds=timeout_seconds,
                )
                candidate.update(
                    fix_command=fix["command"],
                    fix_exit_code=fix["exit_code"],
                    changed_files=fix["changed_files"],
                )
                patch_path = out_dir / "proposed.patch"
                patch_path.write_text(fix["diff"], encoding="utf-8")
                record("proposed_patch", patch_path)
                if not fix["changed_files"]:
                    decision = DECISION_NO_CHANGE
                    reasons = ["the mechanical fix produced no change in a fresh copy"]
                else:
                    proposed = {
                        "patch_id": f"loop-{hashlib.sha256(fix['diff'].encode()).hexdigest()[:12]}",
                        "changed_files": fix["changed_files"],
                    }
                    patch_score = score_patch(
                        remediation_plan=plan_doc,
                        proposed_patch=proposed,
                        pattern_insights=insights,
                        diagnosis_id=candidate["diagnosis_id"],
                    )
                    record("patch_score", _write_json(out_dir / "patch-score.json", patch_score))
                    candidate["patch_score"] = patch_score.get("score")
                    profiles, unmapped = _proof_profiles(
                        _as_list(patch_score.get("proof_requirements"))
                        or _as_list(plan.get("proof_commands"))
                    )
                    if unmapped:
                        reasons.append(
                            "no isolated proof profile for: " + ", ".join(sorted(unmapped))
                        )
                    if profiles:
                        evidence = run_isolated_proof(
                            repo_root=workspace,
                            changed_files=fix["changed_files"],
                            profile_ids=profiles,
                            inventory_mode="base_head",
                            base_ref=fix["baseline_sha"],
                            head_ref="HEAD",
                            timeout_seconds=timeout_seconds,
                        )
                    record(
                        "verification_evidence",
                        _write_json(out_dir / "verification-evidence.json", evidence),
                    )
                    candidate["proof_status"] = _string(evidence.get("status")) or "not_run"
                    verifier = verify_candidate(
                        patch_score=patch_score, verification_evidence=evidence
                    )
                    record(
                        "verifier_result",
                        _write_json(out_dir / "protected-verifier-result.json", verifier),
                    )
                    status = _string(_as_dict(verifier.get("decision")).get("status"))
                    candidate["verifier_status"] = status
                    decision = (
                        DECISION_VERIFIED
                        if status == STRUCTURALLY_VERIFIED_CANDIDATE
                        else DECISION_BLOCKED
                    )

    records = build_trajectory_records(
        diagnostic_vector=vector,
        remediation_plan=plan_doc,
        repo=repository,
        commit_sha=commit_sha,
    )
    plans_by_id = {
        _string(item.get("diagnosis_id")): item
        for item in (_as_dict(entry) for entry in _as_list(plan_doc.get("plans")))
    }
    for entry in records:
        source_plan = plans_by_id.get(_string(entry.get("diagnostic_id")), {})
        entry["plan_classification"] = _string(source_plan.get("classification"))
        entry["failure_surface"] = _string(source_plan.get("failure_surface"))
        if candidate and entry.get("diagnostic_id") == candidate.get("diagnosis_id"):
            entry["safety_gate"] = safety_gate
            proof = _as_dict(entry.get("proof"))
            proof["focused_proof"] = candidate.get("proof_status", "not_run")
            proof["verifier_result"] = candidate.get("verifier_status", "not_run")
            entry["proof"] = proof
            entry["loop_decision"] = decision
    trajectory_path = out_dir / "trajectory.jsonl"
    with trajectory_path.open("a", encoding="utf-8") as handle:
        for entry in records:
            handle.write(json.dumps(entry, sort_keys=True) + "\n")
    record("trajectory_jsonl", trajectory_path)
    memory: JsonObject = {"enabled": memory_path is not None}
    if memory_path is not None:
        memory.update(
            path=memory_path.as_posix(),
            records_before=len(memory_before),
            appended=append_records(memory_path, records),
            proven_fix_patterns=len(insights["recurring_safe_fix_patterns"]),
        )
    trajectory_summary = summarize_trajectory_records(records)
    record("trajectory", _write_json(out_dir / "trajectory-summary.json", trajectory_summary))

    log_args = (
        rerun_args
        if rerun_args is not None
        else " ".join(f"--log {path.as_posix()}" for path in logs)
    )
    summary: JsonObject = {
        "schema_version": SCHEMA_VERSION,
        "decision": decision,
        "repository": repository or "unknown",
        "commit_sha": commit_sha or "unknown",
        "logs": [path.as_posix() for path in logs],
        "failure_count": int(failed_check_logs.get("failed_check_count", 0)),
        "candidate": candidate,
        "memory": memory,
        "reasons": reasons,
        "next_action": _next_action(decision, reasons, log_args),
        "real_tree_modified": False,
        "verdict": build_verdict(
            source="diagnose run",
            decision=decision,
            reasons=reasons,
            next_action=_next_action(decision, reasons, log_args),
        ),
        "decision_boundary": dict(DECISION_BOUNDARY),
        "artifacts": artifacts,
    }
    report_path = out_dir / "loop-report.md"
    report_path.write_text(_render_report(summary), encoding="utf-8")
    record("pr_report", report_path)

    chain_stages = (
        "job",
        "failure_vector",
        "safety_gate",
        "verification_evidence",
        "verifier_result",
        "patch_score",
        "pr_report",
        "trajectory",
    )
    if decision in {DECISION_VERIFIED, DECISION_BLOCKED} and repository and commit_sha:
        if all(stage in artifacts for stage in chain_stages):
            chain = build_protected_proof_chain(
                repository=repository,
                commit_sha=commit_sha,
                artifacts={
                    "diagnostic_job": artifacts["job"],
                    "failure_vector": artifacts["failure_vector"],
                    "safety_gate": artifacts["safety_gate"],
                    "proof_result": artifacts["verification_evidence"],
                    "verifier_result": artifacts["verifier_result"],
                    "patch_score": artifacts["patch_score"],
                    "pr_report": artifacts["pr_report"],
                    "trajectory": artifacts["trajectory"],
                },
            )
            record(
                "protected_proof_chain",
                _write_json(out_dir / "protected-proof-chain.json", chain),
            )
    summary["artifacts"] = artifacts
    _write_json(out_dir / "loop.json", summary)
    card_json, card_markdown = write_decision_card(out_dir)
    record("decision_card", card_json)
    record("decision_card_markdown", card_markdown)
    _write_json(out_dir / "loop.json", summary)
    return summary


def logs_from_latest_gate_run(repo_root: Path, out_dir: Path) -> list[Path] | None:
    """Turn the latest gate run's failed steps into log files; None when it passed."""

    run = load_latest_run(repo_root)
    if run is None:
        raise ValueError(
            f"no --log given and no gate run recorded at {LATEST_RUN_PATH.as_posix()}; "
            "run `python -m sdetkit gate fast` first, or pass --log FILE"
        )
    provenance = run.get("provenance")
    recorded = str(provenance.get("head_sha") or "") if isinstance(provenance, dict) else ""
    current = str(git_provenance(repo_root)["head_sha"] or "")
    if recorded and current and recorded != current:
        raise ValueError(
            f"the latest gate run was recorded on commit {recorded[:12]}, but HEAD is "
            f"{current[:12]}; run `python -m sdetkit gate fast` again, or pass --log FILE"
        )
    if run.get("ok"):
        return None
    logs = write_failed_step_logs(run, out_dir / "gate-logs")
    if not logs:
        raise ValueError(
            f"the gate run in {LATEST_RUN_PATH.as_posix()} failed but recorded no step output; "
            "pass --log FILE"
        )
    return logs


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="sdetkit diagnose run",
        description=(
            "Run the local remediation loop on saved CI logs, or with no --log on the "
            "failed steps of the latest `gate fast`/`gate release` run: diagnose, plan, "
            "and with --prove fix in a throwaway copy, score, prove and verify. The real "
            "working tree is never modified."
        ),
    )
    parser.add_argument(
        "--log",
        action="append",
        default=[],
        help="Saved CI log file (default: the failed steps of the latest gate run)",
    )
    parser.add_argument("--repo-root", default=".", help="Repository the logs came from")
    parser.add_argument("--out-dir", default=str(DEFAULT_OUT_DIR))
    parser.add_argument(
        "--prove",
        action="store_true",
        help="Apply the mechanical fix in an isolated copy and run proof and verification",
    )
    parser.add_argument("--timeout-seconds", type=int, default=DEFAULT_TIMEOUT_SECONDS)
    parser.add_argument(
        "--memory",
        default=str(DEFAULT_MEMORY_PATH),
        help="RepoMemory file this run reads proven patterns from and appends to",
    )
    parser.add_argument(
        "--no-memory", action="store_true", help="Neither read nor write RepoMemory"
    )
    parser.add_argument("--format", choices=["text", "json"], default="text")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(list(argv) if argv is not None else None)
    repo_root = Path(args.repo_root)
    out_dir = Path(args.out_dir)
    log_paths: list[str | Path] = list(args.log)
    try:
        if not log_paths:
            gate_logs = logs_from_latest_gate_run(repo_root, out_dir)
            if gate_logs is None:
                message = "the latest gate run passed; nothing to diagnose"
                if args.format == "json":
                    print(
                        json.dumps(
                            {
                                "gate_run": LATEST_RUN_PATH.as_posix(),
                                "ok": True,
                                "message": message,
                            },
                            sort_keys=True,
                        )
                    )
                else:
                    print(message)
                return 0
            log_paths = list(gate_logs)
        summary = run_remediation_loop(
            log_paths=log_paths,
            repo_root=repo_root,
            out_dir=out_dir,
            prove=args.prove,
            timeout_seconds=args.timeout_seconds,
            memory_path=None if args.no_memory else Path(args.memory),
            # Logs taken from the latest gate run are found again the same way.
            rerun_args=None if args.log else "",
        )
    except (OSError, ValueError, RuntimeError, subprocess.TimeoutExpired) as exc:
        print(f"diagnose run error: {exc}", file=sys.stderr)
        return 2
    if args.format == "json":
        print(json.dumps(summary, indent=2, sort_keys=True))
    else:
        print(f"decision={summary['decision']}")
        print(f"failures={summary['failure_count']}")
        candidate = _as_dict(summary.get("candidate"))
        if candidate.get("changed_files"):
            print(f"changed_files={','.join(candidate['changed_files'])}")
        print(f"report={summary['artifacts'].get('pr_report', '')}")
        print(f"decision_card={summary['artifacts'].get('decision_card', '')}")
        print(f"next_action={summary['next_action']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
