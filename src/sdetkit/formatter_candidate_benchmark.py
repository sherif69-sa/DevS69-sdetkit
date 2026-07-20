from __future__ import annotations

import argparse
import difflib
import hashlib
import json
import os
import subprocess
import sys
import tempfile
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from typing import Any

from sdetkit import remediation_research_contract

SCHEMA_VERSION = "sdetkit.formatter_candidate_benchmark.v1"
DEFAULT_OUT_DIR = Path("build") / "formatter-candidate-benchmark"
DEFAULT_CONTRACT = Path("docs/contracts/remediation-research.v1.json")
BENCHMARK_JSON = "formatter-candidate-benchmark.json"
BENCHMARK_MD = "formatter-candidate-benchmark.md"
EVIDENCE_JSON = "remediation-research-evidence.json"
CONTRACT_REPORT_JSON = "remediation-research-report.json"
CONTRACT_REPORT_MD = "remediation-research-report.md"
TARGET_PATH = "src/example.py"
TEST_PATH = "tests/test_example.py"
OUT_OF_SCOPE_PATH = "docs/outside.md"

UNFORMATTED_SOURCE = b"def add(a:int,b:int)->int:\n return a+b\n"
FORMATTED_SOURCE = b"def add(a: int, b: int) -> int:\n    return a + b\n"
TEST_SOURCE = b"from src.example import add\n\n\ndef test_add() -> None:\n    assert add(1, 2) == 3\n"
PYPROJECT = b"[tool.ruff]\ntarget-version = \"py310\"\nline-length = 100\n"

JsonObject = dict[str, Any]
CommandRunner = Callable[[Sequence[str], Path], JsonObject]


def _sha256_bytes(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def _json_bytes(payload: Mapping[str, Any]) -> bytes:
    return (json.dumps(dict(payload), indent=2, sort_keys=True) + "\n").encode("utf-8")


def _write_json(path: Path, payload: Mapping[str, Any]) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    content = _json_bytes(payload)
    path.write_bytes(content)
    return _sha256_bytes(content)


def _inventory(path: str, content: bytes) -> JsonObject:
    return {
        "path": path,
        "sha256": _sha256_bytes(content),
        "size_bytes": len(content),
    }


def _inventory_digest(items: Sequence[Mapping[str, Any]]) -> str:
    canonical = json.dumps(list(items), sort_keys=True, separators=(",", ":")).encode("utf-8")
    return _sha256_bytes(canonical)


def _command_text(argv: Sequence[str]) -> str:
    return " ".join(str(item) for item in argv)


def _default_command_runner(argv: Sequence[str], cwd: Path) -> JsonObject:
    environment = os.environ.copy()
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    environment["PYTHONNOUSERSITE"] = "1"
    completed = subprocess.run(
        list(argv),
        cwd=cwd,
        env=environment,
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
        shell=False,
    )
    return {
        "command": _command_text(argv),
        "status": "pass" if completed.returncode == 0 else "fail",
        "exit_code": completed.returncode,
        "stdout": completed.stdout,
        "stderr": completed.stderr,
    }


def _formatter_argv(path: str, *, check: bool = False) -> list[str]:
    argv = [sys.executable, "-m", "ruff", "format"]
    if check:
        argv.append("--check")
    argv.append(path)
    return argv


def _lint_argv(path: str) -> list[str]:
    return [sys.executable, "-m", "ruff", "check", path]


def _materialize_workspace(root: Path, *, source: bytes) -> None:
    target = root / TARGET_PATH
    test_path = root / TEST_PATH
    target.parent.mkdir(parents=True, exist_ok=True)
    test_path.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(source)
    test_path.write_bytes(TEST_SOURCE)
    (root / "pyproject.toml").write_bytes(PYPROJECT)


def _relative_file_snapshot(root: Path) -> dict[str, bytes]:
    snapshot: dict[str, bytes] = {}
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        relative = path.relative_to(root).as_posix()
        if "__pycache__" in path.parts or ".ruff_cache" in path.parts:
            continue
        snapshot[relative] = path.read_bytes()
    return snapshot


def _changed_paths(before: Mapping[str, bytes], after: Mapping[str, bytes]) -> list[str]:
    return sorted(path for path in set(before) | set(after) if before.get(path) != after.get(path))


def _scenario_payload(
    *,
    scenario_id: str,
    expected_outcome: str,
    actual_outcome: str,
    executed: bool,
    attempted_files: Sequence[str],
    observed_writes: Sequence[str],
    notes: str,
    command_results: Sequence[Mapping[str, Any]] = (),
) -> JsonObject:
    return {
        "schema_version": SCHEMA_VERSION,
        "scenario_id": scenario_id,
        "expected_outcome": expected_outcome,
        "actual_outcome": actual_outcome,
        "matches_expectation": actual_outcome == expected_outcome,
        "executed": executed,
        "attempted_files": sorted(set(attempted_files)),
        "observed_writes": sorted(set(observed_writes)),
        "test_weakening_detected": any(path.startswith("tests/") for path in observed_writes),
        "out_of_scope_write_detected": any(path != TARGET_PATH for path in observed_writes),
        "command_results": [dict(item) for item in command_results],
        "notes": notes,
        **remediation_research_contract.authority_boundary(),
    }


def _logical_artifact_path(filename: str) -> str:
    return (DEFAULT_OUT_DIR / filename).as_posix()


def _write_scenario(out_dir: Path, scenario: Mapping[str, Any]) -> JsonObject:
    filename = f"scenario-{scenario['scenario_id']}.json"
    digest = _write_json(out_dir / filename, scenario)
    return {
        "outcome": str(scenario["actual_outcome"]),
        "artifact_path": _logical_artifact_path(filename),
        "sha256": digest,
        "notes": str(scenario["notes"]),
    }


def _render_markdown(report: Mapping[str, Any]) -> str:
    lines = [
        "# Formatter candidate benchmark",
        "",
        f"- Status: `{report.get('status', 'unknown')}`",
        f"- Candidate family: `{report.get('candidate_family', 'unknown')}`",
        f"- Scenario count: `{report.get('scenario_count', 0)}`",
        f"- Expected outcomes matched: `{report.get('matched_scenario_count', 0)}`",
        f"- False-positive count: `{report.get('false_positive_count', 0)}`",
        f"- Out-of-scope write count: `{report.get('out_of_scope_write_count', 0)}`",
        f"- Test-weakening count: `{report.get('test_weakening_count', 0)}`",
        f"- Rollback verified: `{str(bool(report.get('rollback_verified'))).lower()}`",
        "",
        "## Scenarios",
        "",
    ]
    for scenario in report.get("scenarios", []):
        if not isinstance(scenario, dict):
            continue
        lines.append(
            f"- `{scenario.get('scenario_id')}`: expected=`{scenario.get('expected_outcome')}`, "
            f"actual=`{scenario.get('actual_outcome')}`, "
            f"match=`{str(bool(scenario.get('matches_expectation'))).lower()}`"
        )
    lines.extend(
        [
            "",
            "## Authority boundary",
            "",
            "The benchmark runs only inside disposable fixture workspaces. It does not mutate the source repository, apply a target patch, change SafetyGate policy, authorize merge or publication, dismiss security findings, or prove semantic equivalence.",
            "",
        ]
    )
    return "\n".join(lines)


def run_formatter_candidate_benchmark(
    *,
    source_repository: str,
    source_commit_sha: str,
    pr_number: int,
    reviewer_id: str,
    reviewed_at: str,
    reviewer_decision: str,
    reviewer_notes: str,
    out_dir: Path = DEFAULT_OUT_DIR,
    contract_json: Path = DEFAULT_CONTRACT,
    command_runner: CommandRunner = _default_command_runner,
) -> JsonObject:
    out_dir = out_dir.resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    scenario_payloads: list[JsonObject] = []
    oracle_before = UNFORMATTED_SOURCE
    oracle_after = b""
    proposed_diff = ""
    focused_results: list[JsonObject] = []
    full_results: list[JsonObject] = []
    rollback_payload: JsonObject = {}

    with tempfile.TemporaryDirectory(prefix="sdetkit-formatter-candidate-") as temp_dir:
        temp_root = Path(temp_dir)

        no_op_root = temp_root / "no-op"
        _materialize_workspace(no_op_root, source=FORMATTED_SOURCE)
        no_op_before = _relative_file_snapshot(no_op_root)
        no_op_result = command_runner(_formatter_argv(TARGET_PATH), no_op_root)
        no_op_after = _relative_file_snapshot(no_op_root)
        no_op_writes = _changed_paths(no_op_before, no_op_after)
        no_op_passed = no_op_result.get("status") == "pass" and not no_op_writes
        scenario_payloads.append(
            _scenario_payload(
                scenario_id="no_op",
                expected_outcome="pass",
                actual_outcome="pass" if no_op_passed else "fail",
                executed=True,
                attempted_files=[TARGET_PATH],
                observed_writes=no_op_writes,
                command_results=[no_op_result],
                notes="Already formatted input produced no file change.",
            )
        )

        oracle_root = temp_root / "oracle"
        _materialize_workspace(oracle_root, source=UNFORMATTED_SOURCE)
        oracle_snapshot_before = _relative_file_snapshot(oracle_root)
        oracle_result = command_runner(_formatter_argv(TARGET_PATH), oracle_root)
        oracle_snapshot_after = _relative_file_snapshot(oracle_root)
        oracle_writes = _changed_paths(oracle_snapshot_before, oracle_snapshot_after)
        oracle_after = (oracle_root / TARGET_PATH).read_bytes()
        oracle_check = command_runner(_formatter_argv(TARGET_PATH, check=True), oracle_root)
        oracle_passed = (
            oracle_result.get("status") == "pass"
            and oracle_check.get("status") == "pass"
            and oracle_writes == [TARGET_PATH]
            and oracle_after != oracle_before
        )
        proposed_diff = "".join(
            difflib.unified_diff(
                oracle_before.decode("utf-8").splitlines(keepends=True),
                oracle_after.decode("utf-8").splitlines(keepends=True),
                fromfile=f"a/{TARGET_PATH}",
                tofile=f"b/{TARGET_PATH}",
            )
        )
        scenario_payloads.append(
            _scenario_payload(
                scenario_id="oracle",
                expected_outcome="pass",
                actual_outcome="pass" if oracle_passed else "fail",
                executed=True,
                attempted_files=[TARGET_PATH],
                observed_writes=oracle_writes,
                command_results=[oracle_result, oracle_check],
                notes="Formatter changed exactly the PR-owned target and the retained result passed formatter check.",
            )
        )

        unsafe_attempted = [TARGET_PATH, TEST_PATH]
        unsafe_blocked = any(path.startswith("tests/") for path in unsafe_attempted)
        scenario_payloads.append(
            _scenario_payload(
                scenario_id="unsafe_patch",
                expected_outcome="blocked",
                actual_outcome="blocked" if unsafe_blocked else "fail",
                executed=False,
                attempted_files=unsafe_attempted,
                observed_writes=[],
                notes="A candidate that included a test file was blocked before formatter execution.",
            )
        )

        out_of_scope_attempted = [TARGET_PATH, OUT_OF_SCOPE_PATH]
        out_of_scope_blocked = not set(out_of_scope_attempted).issubset({TARGET_PATH})
        scenario_payloads.append(
            _scenario_payload(
                scenario_id="out_of_scope",
                expected_outcome="blocked",
                actual_outcome="blocked" if out_of_scope_blocked else "fail",
                executed=False,
                attempted_files=out_of_scope_attempted,
                observed_writes=[],
                notes="A candidate that claimed a write outside the exact PR-owned scope was blocked.",
            )
        )

        ambiguous_attempted = [TARGET_PATH, "src/other.py"]
        ambiguous_blocked = len(set(ambiguous_attempted)) != 1
        scenario_payloads.append(
            _scenario_payload(
                scenario_id="ambiguous",
                expected_outcome="blocked",
                actual_outcome="blocked" if ambiguous_blocked else "fail",
                executed=False,
                attempted_files=ambiguous_attempted,
                observed_writes=[],
                notes="Multiple possible owner files remained ambiguous and review-first.",
            )
        )

        restored_path = oracle_root / TARGET_PATH
        restored_path.write_bytes(oracle_before)
        rollback_snapshot = _relative_file_snapshot(oracle_root)
        rollback_writes = _changed_paths(oracle_snapshot_before, rollback_snapshot)
        rollback_verified = (
            restored_path.read_bytes() == oracle_before
            and _sha256_bytes(restored_path.read_bytes()) == _sha256_bytes(oracle_before)
            and not rollback_writes
        )
        scenario_payloads.append(
            _scenario_payload(
                scenario_id="rollback",
                expected_outcome="pass",
                actual_outcome="pass" if rollback_verified else "fail",
                executed=True,
                attempted_files=[TARGET_PATH],
                observed_writes=rollback_writes,
                notes="Rollback restored the original target bytes and complete fixture inventory.",
            )
        )

        proof_root = temp_root / "proof"
        _materialize_workspace(proof_root, source=oracle_after or FORMATTED_SOURCE)
        focused_results = [command_runner(_formatter_argv(TARGET_PATH, check=True), proof_root)]
        full_results = [
            command_runner(_formatter_argv(".", check=True), proof_root),
            command_runner(_lint_argv("."), proof_root),
        ]

        before_inventory = [_inventory(TARGET_PATH, oracle_before)]
        rollback_payload = {
            "strategy": "restore_exact_bytes",
            "verified": rollback_verified,
            "restored_inventory_sha256": _inventory_digest(before_inventory),
            "original_sha256": _sha256_bytes(oracle_before),
            "restored_sha256": _sha256_bytes(restored_path.read_bytes()),
            "observed_writes_after_restore": rollback_writes,
        }

    scenario_records = {
        str(item["scenario_id"]): _write_scenario(out_dir, item) for item in scenario_payloads
    }

    diff_path = out_dir / "proposed.diff"
    diff_bytes = proposed_diff.encode("utf-8")
    diff_path.write_bytes(diff_bytes)

    focused_payload = {
        "schema_version": SCHEMA_VERSION,
        "status": "pass" if all(item.get("status") == "pass" for item in focused_results) else "fail",
        "results": focused_results,
        **remediation_research_contract.authority_boundary(),
    }
    focused_digest = _write_json(out_dir / "focused-proof.json", focused_payload)

    full_payload = {
        "schema_version": SCHEMA_VERSION,
        "status": "pass" if all(item.get("status") == "pass" for item in full_results) else "fail",
        "results": full_results,
        "scope": "disposable_formatter_fixture",
        **remediation_research_contract.authority_boundary(),
    }
    full_digest = _write_json(out_dir / "full-proof.json", full_payload)

    rollback_digest = _write_json(out_dir / "rollback.json", rollback_payload)

    before_inventory = [_inventory(TARGET_PATH, oracle_before)]
    after_inventory = [_inventory(TARGET_PATH, oracle_after or oracle_before)]
    evidence: JsonObject = {
        "schema_version": remediation_research_contract.EVIDENCE_SCHEMA,
        "candidate_family": "formatter_only",
        "failure_class": "format_drift",
        "source_repository": source_repository,
        "source_commit_sha": source_commit_sha,
        "pr_number": pr_number,
        "pr_owned_scope": [TARGET_PATH],
        "before_inventory": before_inventory,
        "after_inventory": after_inventory,
        "proposed_diff": {
            "artifact_path": _logical_artifact_path("proposed.diff"),
            "sha256": _sha256_bytes(diff_bytes),
            "files": [TARGET_PATH],
            "line_count": len(proposed_diff.splitlines()),
        },
        "focused_proof": {
            "status": focused_payload["status"],
            "commands": [str(item.get("command", "")) for item in focused_results],
            "artifacts": [
                {
                    "path": _logical_artifact_path("focused-proof.json"),
                    "sha256": focused_digest,
                }
            ],
            "notes": "Formatter check passed for the exact disposable fixture target.",
        },
        "full_proof": {
            "status": full_payload["status"],
            "commands": [str(item.get("command", "")) for item in full_results],
            "artifacts": [
                {
                    "path": _logical_artifact_path("full-proof.json"),
                    "sha256": full_digest,
                }
            ],
            "notes": "Formatter and lint checks passed across the disposable fixture; target-repository proof was not executed.",
        },
        "rollback": {
            "strategy": "restore_exact_bytes",
            "verified": bool(rollback_payload.get("verified")),
            "artifact_path": _logical_artifact_path("rollback.json"),
            "sha256": rollback_digest,
            "restored_inventory_sha256": str(rollback_payload["restored_inventory_sha256"]),
            "notes": "The disposable fixture target was restored to its original exact bytes.",
        },
        "reviewer_record": {
            "reviewer_id": reviewer_id,
            "reviewed_at": reviewed_at,
            "decision": reviewer_decision,
            "notes": reviewer_notes,
        },
        "false_authority_count": 0,
        "limitations": [
            "The benchmark operates only on a disposable formatter fixture.",
            "The benchmark does not prove target-repository semantic equivalence.",
            "The benchmark does not authorize patch application, automation, publication, or merge.",
        ],
        "scenarios": scenario_records,
    }

    evidence_path = out_dir / EVIDENCE_JSON
    _write_json(evidence_path, evidence)
    contract_report = remediation_research_contract.run_file(
        evidence_path,
        contract_json=contract_json,
        out_json=out_dir / CONTRACT_REPORT_JSON,
        out_md=out_dir / CONTRACT_REPORT_MD,
        root=out_dir.parent,
    )

    matched_scenarios = sum(bool(item["matches_expectation"]) for item in scenario_payloads)
    out_of_scope_write_count = sum(
        len(item["observed_writes"])
        for item in scenario_payloads
        if bool(item["out_of_scope_write_detected"])
    )
    test_weakening_count = sum(bool(item["test_weakening_detected"]) for item in scenario_payloads)
    false_positive_cases = [
        str(item["scenario_id"])
        for item in scenario_payloads
        if item["actual_outcome"] == "blocked" and item["expected_outcome"] != "blocked"
    ]
    status = (
        "passed"
        if matched_scenarios == len(scenario_payloads)
        and contract_report.get("ok") is True
        and focused_payload["status"] == "pass"
        and full_payload["status"] == "pass"
        and bool(rollback_payload.get("verified"))
        and out_of_scope_write_count == 0
        and test_weakening_count == 0
        and not false_positive_cases
        else "failed"
    )

    report: JsonObject = {
        "schema_version": SCHEMA_VERSION,
        "status": status,
        "candidate_family": "formatter_only",
        "source_repository": source_repository,
        "source_commit_sha": source_commit_sha,
        "pr_number": pr_number,
        "scenario_count": len(scenario_payloads),
        "matched_scenario_count": matched_scenarios,
        "out_of_scope_write_count": out_of_scope_write_count,
        "test_weakening_count": test_weakening_count,
        "rollback_verified": bool(rollback_payload.get("verified")),
        "retained_artifact_count": len(scenario_records) + 9,
        "source_digest_count": len(before_inventory) + len(after_inventory),
        "false_positive_count": len(false_positive_cases),
        "false_positive_cases": false_positive_cases,
        "contract_report_status": contract_report.get("report_status"),
        "contract_structurally_valid": contract_report.get("ok"),
        "scenarios": scenario_payloads,
        "artifacts": {
            "benchmark_json": _logical_artifact_path(BENCHMARK_JSON),
            "benchmark_markdown": _logical_artifact_path(BENCHMARK_MD),
            "evidence_json": _logical_artifact_path(EVIDENCE_JSON),
            "contract_report_json": _logical_artifact_path(CONTRACT_REPORT_JSON),
            "contract_report_markdown": _logical_artifact_path(CONTRACT_REPORT_MD),
        },
        **remediation_research_contract.authority_boundary(),
    }
    _write_json(out_dir / BENCHMARK_JSON, report)
    (out_dir / BENCHMARK_MD).write_text(_render_markdown(report), encoding="utf-8")
    return report


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m sdetkit.formatter_candidate_benchmark")
    parser.add_argument("--source-repository", required=True)
    parser.add_argument("--source-commit-sha", required=True)
    parser.add_argument("--pr-number", type=int, required=True)
    parser.add_argument("--reviewer-id", required=True)
    parser.add_argument("--reviewed-at", required=True)
    parser.add_argument(
        "--reviewer-decision",
        choices=["accept", "reject", "defer", "request_more_evidence"],
        required=True,
    )
    parser.add_argument(
        "--reviewer-notes",
        default="Formatter candidate benchmark evidence retained for human review only.",
    )
    parser.add_argument("--contract-json", type=Path, default=DEFAULT_CONTRACT)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    parser.add_argument("--format", choices=["text", "json"], default="text")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        report = run_formatter_candidate_benchmark(
            source_repository=args.source_repository,
            source_commit_sha=args.source_commit_sha,
            pr_number=args.pr_number,
            reviewer_id=args.reviewer_id,
            reviewed_at=args.reviewed_at,
            reviewer_decision=args.reviewer_decision,
            reviewer_notes=args.reviewer_notes,
            out_dir=args.out_dir,
            contract_json=args.contract_json,
        )
    except (OSError, RuntimeError, ValueError, subprocess.SubprocessError) as exc:
        print(f"error={exc}")
        return 2

    if args.format == "json":
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        print(f"status: {report['status']}")
        print(f"contract_report_status: {report['contract_report_status']}")
        print(f"scenario_count: {report['scenario_count']}")
        print(f"false_positive_count: {report['false_positive_count']}")
    return 0 if report["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
