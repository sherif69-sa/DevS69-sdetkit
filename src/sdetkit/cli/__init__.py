"""CLI package compatibility wrappers."""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
import sys
from collections.abc import Sequence
from contextlib import redirect_stdout
from dataclasses import dataclass
from importlib import import_module
from pathlib import Path
from typing import Any

from ..versioning import tool_version

# Exposed for compatibility: tests and downstream callers monkeypatch these names.
__all__ = [
    "COMMANDS",
    "SUBCOMMANDS",
    "Command",
    "import_module",
    "tool_version",
    "_run_module_main",
    "main",
]


def _split_doctor_report_contract_args(
    argv: list[str],
) -> tuple[bool, str, str | None, str | None, str | None, list[str]]:
    enabled = False
    output_format = "text"
    out_path: str | None = None
    artifact_dir: str | None = None
    failure_vector_bundle_path: str | None = None
    inner: list[str] = []

    index = 0
    while index < len(argv):
        token = argv[index]
        if token == "--report-contract":
            enabled = True
            index += 1
            continue
        if token == "--json":
            output_format = "json"
            index += 1
            continue
        if token == "--format":
            if index + 1 >= len(argv):
                raise SystemExit(2)
            output_format = argv[index + 1]
            index += 2
            continue
        if token.startswith("--format="):
            output_format = token.split("=", 1)[1]
            index += 1
            continue
        if token == "--out":
            if index + 1 >= len(argv):
                raise SystemExit(2)
            out_path = argv[index + 1]
            index += 2
            continue
        if token.startswith("--out="):
            out_path = token.split("=", 1)[1]
            index += 1
            continue
        if token == "--report-artifact-dir":
            if index + 1 >= len(argv):
                raise SystemExit(2)
            artifact_dir = argv[index + 1]
            index += 2
            continue
        if token.startswith("--report-artifact-dir="):
            artifact_dir = token.split("=", 1)[1]
            index += 1
            continue
        if token == "--failure-vector-bundle":
            if index + 1 >= len(argv):
                raise SystemExit(2)
            failure_vector_bundle_path = argv[index + 1]
            index += 2
            continue
        if token.startswith("--failure-vector-bundle="):
            failure_vector_bundle_path = token.split("=", 1)[1]
            index += 1
            continue
        inner.append(token)
        index += 1

    return enabled, output_format, out_path, artifact_dir, failure_vector_bundle_path, inner


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _json_dumps_pretty(value: dict[str, Any]) -> str:
    return json.dumps(value, sort_keys=True, indent=2) + "\n"


def _load_failure_vector_bundle(path: str) -> dict[str, Any]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("FailureVector bundle must be a JSON object")
    return payload


def _write_doctor_report_artifact_bundle(
    artifact_dir: str,
    contract: dict[str, Any],
    json_output: str,
    markdown_output: str,
    failure_vector_bundle: dict[str, Any] | None = None,
) -> None:
    target = Path(artifact_dir)
    target.mkdir(parents=True, exist_ok=True)

    outputs = {
        "json": {
            "path": "doctor-report.json",
            "sha256": _sha256_text(json_output),
        },
        "markdown": {
            "path": "doctor-report.md",
            "sha256": _sha256_text(markdown_output),
        },
    }
    failure_vector_output = None
    if failure_vector_bundle is not None:
        failure_vector_output = _json_dumps_pretty(failure_vector_bundle)
        outputs["failure_vector"] = {
            "path": "failure-vector.json",
            "sha256": _sha256_text(failure_vector_output),
        }

    manifest = {
        "schema_version": "sdetkit.doctor_report_artifact_bundle.v1",
        "report_schema_version": str(contract.get("schema_version", "")),
        "status": str(contract.get("status", "")),
        "outputs": outputs,
    }
    manifest_output = _json_dumps_pretty(manifest)

    (target / "doctor-report.json").write_text(json_output, encoding="utf-8")
    (target / "doctor-report.md").write_text(markdown_output, encoding="utf-8")
    if failure_vector_output is not None:
        (target / "failure-vector.json").write_text(failure_vector_output, encoding="utf-8")
    (target / "doctor-report-manifest.json").write_text(manifest_output, encoding="utf-8")


def _run_doctor_report_contract(argv: list[str]) -> int | None:
    if not argv or argv[0] != "doctor":
        return None

    (
        enabled,
        output_format,
        out_path,
        artifact_dir,
        failure_vector_bundle_path,
        inner,
    ) = _split_doctor_report_contract_args(argv[1:])
    if not enabled:
        return None

    if output_format == "markdown":
        output_format = "md"
    if output_format not in {"text", "json", "md"}:
        print(
            "doctor: error: --report-contract supports --format text, json, md, or markdown",
            file=sys.stderr,
        )
        raise SystemExit(2)

    from .. import doctor as doctor_module
    from ..doctor_report import build_doctor_report_contract, render_doctor_report_markdown

    doctor_args = [*inner, "--format", "json"]
    if "--no-workspace" not in inner:
        doctor_args.append("--no-workspace")

    captured = io.StringIO()
    with redirect_stdout(captured):
        rc = int(doctor_module.main(doctor_args))

    raw = captured.getvalue()
    try:
        doctor_payload = json.loads(raw)
    except json.JSONDecodeError:
        print("doctor: error: could not build report contract from doctor JSON", file=sys.stderr)
        return rc if rc else 2

    failure_vector_bundle = None
    if failure_vector_bundle_path:
        try:
            failure_vector_bundle = _load_failure_vector_bundle(failure_vector_bundle_path)
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            print(f"doctor: error: could not load FailureVector bundle: {exc}", file=sys.stderr)
            return 2

    contract = build_doctor_report_contract(
        doctor_payload,
        failure_vector_bundle=failure_vector_bundle,
    )
    json_output = json.dumps(contract, sort_keys=True) + "\n"
    markdown_output = render_doctor_report_markdown(contract)
    output = json_output if output_format == "json" else markdown_output

    if artifact_dir:
        _write_doctor_report_artifact_bundle(
            artifact_dir,
            contract,
            json_output,
            markdown_output,
            failure_vector_bundle=failure_vector_bundle,
        )
    if out_path:
        Path(out_path).write_text(output, encoding="utf-8")
    sys.stdout.write(output)
    return rc


@dataclass(frozen=True)
class Command:
    """One ``sdetkit`` subcommand: the module whose ``main(argv)`` it runs."""

    module: str
    help: str
    group: str
    prefix: tuple[str, ...] = ()


_CORE = "Release confidence"
_DIAGNOSE = "Diagnose and adopt"
_TOOLS = "SDET utilities"
_ADVANCED = "Advanced"

COMMANDS: dict[str, Command] = {
    "gate": Command("sdetkit.gate", "Run the fast or release quality gate (SHIP / NO-SHIP)", _CORE),
    "doctor": Command("sdetkit.doctor", "Check repository and release readiness", _CORE),
    "release": Command("", "Release kit: release gate|doctor|security|evidence|repo", _CORE),
    "security": Command(
        "sdetkit.security_gate", "Scan for secrets and risky code, with a baseline", _CORE
    ),
    "evidence": Command("sdetkit.evidence", "Pack, validate and compare release evidence", _CORE),
    "report": Command("sdetkit.report", "Ingest, diff and build run report artifacts", _CORE),
    "diagnose": Command(
        "", "Diagnosis engine: check intelligence, failure vectors, remediation plans", _DIAGNOSE
    ),
    "verify": Command(
        "", "Fix-safety checks: protected verifier, patch scoring, benchmarks, merge", _DIAGNOSE
    ),
    "investigate": Command(
        "sdetkit.investigate", "Diagnose a failure and print the next action", _DIAGNOSE
    ),
    "triage-ci": Command("sdetkit.ci_failure_triage", "Diagnose a saved CI job log", _DIAGNOSE),
    "mission-control": Command(
        "sdetkit.mission_control", "Build a release-confidence evidence bundle", _DIAGNOSE
    ),
    "adoption-surface": Command(
        "sdetkit.adoption_surface",
        "Map a repository's languages, CI and proof commands (read-only)",
        _DIAGNOSE,
    ),
    "adoption-proof-recommendations": Command(
        "sdetkit.adoption_proof_recommendations",
        "Recommend proof commands from an adoption-surface artifact",
        _DIAGNOSE,
    ),
    "adoption-repo-topology": Command(
        "sdetkit.adoption_repo_topology",
        "Map workspace topology from an adoption-surface artifact",
        _DIAGNOSE,
    ),
    "fit": Command("sdetkit.fit", "Recommend an adoption depth for a repository", _DIAGNOSE),
    "adoption": Command(
        "sdetkit.adoption", "Plan follow-up actions from fit and gate results", _DIAGNOSE
    ),
    "repo": Command("sdetkit.repo", "Check, fix and audit repository hygiene", _DIAGNOSE),
    "init": Command(
        "sdetkit.repo", "Scaffold SDETKit config in a repository", _DIAGNOSE, ("init",)
    ),
    "dev": Command(
        "sdetkit.repo", "Developer setup: pre-commit and IDE integration", _DIAGNOSE, ("dev",)
    ),
    "maintenance": Command("sdetkit.maintenance", "Run repository maintenance checks", _DIAGNOSE),
    "apiget": Command(
        "sdetkit.apiget",
        "HTTP GET JSON with retries, pagination and cassette record/replay",
        _TOOLS,
    ),
    "cassette-get": Command(
        "sdetkit.cassette_get", "Record or replay a single HTTP GET cassette", _TOOLS
    ),
    "kv": Command("sdetkit.kvcli", "Parse key=value input into JSON", _TOOLS),
    "patch": Command("sdetkit.patch", "Apply a JSON patch spec to files, with size limits", _TOOLS),
    "serve": Command("sdetkit.serve", "Run SDETKit as a local review API service", _TOOLS),
    "inspect": Command(
        "sdetkit.inspect_data", "Inspect CSV/JSON evidence and emit diagnostics", _TOOLS
    ),
    "inspect-compare": Command(
        "sdetkit.inspect_compare", "Compare inspect snapshots for baseline drift", _TOOLS
    ),
    "inspect-project": Command(
        "sdetkit.inspect_project", "Run inspection policy packs over dataset families", _TOOLS
    ),
    "readiness": Command("sdetkit.readiness", "Score repository release readiness", _ADVANCED),
    "release-room": Command(
        "sdetkit.release_room", "Build a release-room operator plan", _ADVANCED
    ),
    "adaptive": Command(
        "sdetkit.adaptive", "Local adaptive memory: init, ingest, history, explain", _ADVANCED
    ),
    "ci": Command("sdetkit.ci", "Validate CI workflow templates", _ADVANCED),
    "policy": Command("sdetkit.policy", "Snapshot, check and diff repository policy", _ADVANCED),
    "review": Command("sdetkit.review", "Run the review workflow over a repository", _ADVANCED),
    "boost": Command("sdetkit.boost", "Scan a repository and rank local risk signals", _ADVANCED),
    "index": Command("sdetkit.index", "Build or inspect a local repository index", _ADVANCED),
    "kits": Command("sdetkit.kits", "List, search and describe the umbrella kits", _ADVANCED),
    "intelligence": Command(
        "sdetkit.intelligence", "Flake detection, change impact and failure fingerprints", _ADVANCED
    ),
    "integration": Command(
        "sdetkit.integration",
        "Integration checks, environment matrix and cassette validation",
        _ADVANCED,
    ),
    "forensics": Command("sdetkit.forensics", "Failure forensics kit", _ADVANCED),
    "contract": Command(
        "sdetkit.contract", "Print SDETKit runtime and integration contracts", _ADVANCED
    ),
    "example": Command("sdetkit.example", "Run the guided example flow", _ADVANCED),
    "notify": Command("sdetkit.notify", "Send a message through a notification adapter", _ADVANCED),
    "ops": Command("sdetkit.ops", "Run, replay and diff operations workflows", _ADVANCED),
    "workflow-governance-report": Command(
        "sdetkit.workflow_governance_report",
        "Report on GitHub Actions workflow permissions (read-only)",
        _ADVANCED,
    ),
}

# Commands that take a subcommand: {command: {subcommand: (module, help)}}.
SUBCOMMANDS: dict[str, dict[str, tuple[str, str]]] = {
    "release": {
        "gate": ("sdetkit.gate", "Run the gate"),
        "doctor": ("sdetkit.doctor", "Run doctor"),
        "security": ("sdetkit.security_gate", "Run the security gate"),
        "evidence": ("sdetkit.evidence", "Build or check evidence"),
        "repo": ("sdetkit.repo", "Run repository checks"),
    },
    "diagnose": {
        "run": (
            "sdetkit.remediation_loop",
            "Run the full loop on saved CI logs: diagnose, plan, prove in a copy, verify",
        ),
        "card": ("sdetkit.decision_card", "Build the decision card and PR comment for a run"),
        "decide": ("sdetkit.human_decision", "Record a person's approve/reject on a decision card"),
        "checks": ("sdetkit.check_intelligence", "Classify failed checks and their provenance"),
        "ci-log": ("sdetkit.ci_failure_extractor", "Extract the first failure from a CI log"),
        "vector": ("sdetkit.diagnostic_vector_engine", "Build a diagnostic vector for a failure"),
        "plan": ("sdetkit.diagnostic_execution_plan", "Plan which proofs to run for a failure"),
        "job": ("sdetkit.diagnostic_job", "Run a full diagnostic job from saved evidence"),
        "remediation": ("sdetkit.remediation_plan_engine", "Build a review-first remediation plan"),
        "trajectory": (
            "sdetkit.diagnostic_worker_trajectory",
            "Record a diagnostic worker trajectory",
        ),
        "history": ("sdetkit.trajectory_store", "Record diagnostic trajectories"),
        "memory": (
            "sdetkit.repo_memory",
            "Show what the repository's remediation history has proven",
        ),
        "security": ("sdetkit.security_review_evidence", "Summarise security review evidence"),
    },
    "verify": {
        "patch": ("sdetkit.protected_verifier", "Verify a candidate patch against protections"),
        "score": ("sdetkit.patch_scorer", "Score a candidate patch"),
        "benchmark": ("sdetkit.replayable_benchmark_harness", "Replay a fix benchmark"),
        "merge": ("sdetkit.merge_readiness", "Decide merge readiness from evidence"),
        "isolated": ("sdetkit.isolated_proof_runner", "Run a proof command in isolation"),
        "network": ("sdetkit.network_boundary", "Check a proof run's network boundary"),
        "inventory": ("sdetkit.git_inventory_collector", "Collect a git file inventory"),
    },
}

_DESCRIPTION = """\
SDETKit decides whether a change is ready to ship and explains why.

Start here:
  python -m sdetkit gate fast      fast quality gate for the current change
  python -m sdetkit gate release   release gate (doctor --release, security scan, gate fast)
  python -m sdetkit doctor         repository and release readiness checks
"""


def _build_root_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="sdetkit",
        description=_DESCRIPTION,
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="Run `sdetkit <command> --help` for command options.",
    )
    parser.add_argument("--version", action="version", version=tool_version())
    groups: dict[str, list[tuple[str, Command]]] = {}
    for name, command in COMMANDS.items():
        groups.setdefault(command.group, []).append((name, command))
    sub = parser.add_subparsers(dest="cmd", required=True, metavar="command")
    for group in (_CORE, _DIAGNOSE, _TOOLS, _ADVANCED):
        for name, command in groups.get(group, []):
            sub.add_parser(name, help=f"[{group}] {command.help}", add_help=False)
    return parser


def _run_module_main(module_name: str, args: Sequence[str]) -> int:
    module = import_module(module_name)
    return int(module.main(list(args)))


def _run_subcommand(name: str, args: list[str]) -> int:
    table = SUBCOMMANDS[name]
    if args and args[0] in {"-h", "--help"}:
        print(f"usage: sdetkit {name} <subcommand> [options]\n\nsubcommands:")
        for sub, (_, text) in table.items():
            print(f"  {sub:<12} {text}")
        print(f"\nRun `sdetkit {name} <subcommand> --help` for its options.")
        return 0
    if not args or args[0] not in table:
        choices = "|".join(table)
        sys.stderr.write(f"{name} error: expected a subcommand ({choices})\n")
        return 2
    return _run_module_main(table[args[0]][0], args[1:])


def _split_cassette_args(args: list[str]) -> tuple[str | None, str, list[str]]:
    cassette: str | None = None
    mode = "auto"
    rest: list[str] = []
    index = 0
    while index < len(args):
        token = args[index]
        for flag in ("--cassette", "--cassette-mode"):
            if token == flag and index + 1 < len(args):
                value = args[index + 1]
                index += 2
                break
            if token.startswith(f"{flag}="):
                value = token.split("=", 1)[1]
                index += 1
                break
        else:
            rest.append(token)
            index += 1
            continue
        if flag == "--cassette":
            cassette = value
        else:
            mode = value
    return cassette, mode, rest


def _run_apiget(args: list[str]) -> int:
    cassette, mode, rest = _split_cassette_args(args)
    if not cassette:
        return _run_module_main("sdetkit.apiget", rest)
    saved = {key: os.environ.get(key) for key in ("SDETKIT_CASSETTE", "SDETKIT_CASSETTE_MODE")}
    os.environ["SDETKIT_CASSETTE"] = cassette
    os.environ["SDETKIT_CASSETTE_MODE"] = mode
    try:
        return _run_module_main("sdetkit.apiget", rest)
    finally:
        for key, value in saved.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


def _run_cassette_get(args: list[str]) -> int:
    from ..cassette_get import cassette_get

    try:
        return int(cassette_get(args))
    except Exception as exc:
        print(str(exc), file=sys.stderr)
        return 2


def main(argv: Sequence[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    report_contract_rc = _run_doctor_report_contract(argv)
    if report_contract_rc is not None:
        return report_contract_rc
    if not argv or argv[0] not in COMMANDS:
        # argparse prints help, the version, or a usage error and exits.
        _build_root_parser().parse_args(argv)
        return 2
    name, args = argv[0], argv[1:]
    if name in SUBCOMMANDS:
        return _run_subcommand(name, args)
    if name == "apiget":
        return _run_apiget(args)
    if name == "cassette-get":
        return _run_cassette_get(args)
    command = COMMANDS[name]
    return _run_module_main(command.module, [*command.prefix, *args])
