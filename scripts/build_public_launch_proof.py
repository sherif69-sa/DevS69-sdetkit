from __future__ import annotations

import argparse
import json
import re
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from sdetkit import investigate
from sdetkit.adoption_surface import discover_adoption_surface
from sdetkit.failure_vector_adapters import extract_ecosystem_failure_vector
from sdetkit.safety_gate import evaluate_failure_vector

SCHEMA_VERSION = "sdetkit.public_launch_proof.v1"
ROOT = Path(__file__).resolve().parents[1]
DEFAULT_FAILURE_LOG = ROOT / "tests" / "fixtures" / "public_failure_demo" / "ci_log.txt"
DEFAULT_ADOPTION_TARGET = ROOT / "tests" / "fixtures" / "public_adoption_target"
DEFAULT_OUT_DIR = ROOT / "docs" / "artifacts" / "public-launch-proof"
SOURCE_COMMIT_RE = re.compile(r"[0-9a-f]{40}")


def _relative(path: Path) -> str:
    try:
        return path.resolve().relative_to(ROOT.resolve()).as_posix()
    except ValueError:
        return path.resolve().as_posix()


def _named(items: object) -> list[str]:
    if not isinstance(items, list):
        return []
    names = [str(item.get("name", "")) for item in items if isinstance(item, dict)]
    return sorted(name for name in names if name)


def _proof_commands(items: object) -> list[str]:
    if not isinstance(items, list):
        return []
    commands = [str(item.get("command", "")) for item in items if isinstance(item, dict)]
    return sorted(command for command in commands if command)


def _validate_source_commit(source_commit: str) -> str:
    normalized = source_commit.strip().lower()
    if not SOURCE_COMMIT_RE.fullmatch(normalized):
        raise ValueError("source_commit must be a full 40-character lowercase Git SHA")
    return normalized


def build_failure_demo_payload(
    *,
    failure_log: Path = DEFAULT_FAILURE_LOG,
    source_commit: str,
) -> dict[str, Any]:
    commit = _validate_source_commit(source_commit)
    log_text = failure_log.read_text(encoding="utf-8")
    adapter = extract_ecosystem_failure_vector(
        log_text,
        ecosystem="python",
        check="pytest-ci",
        environment="github_actions",
    )
    vector = adapter.vector
    decision = evaluate_failure_vector(vector)
    investigation = investigate._payload_for_failure(log_text)

    return {
        "schema_version": SCHEMA_VERSION,
        "proof_type": "failure_diagnosis",
        "source_commit": commit,
        "capability_state": "main_only_until_1.1.0",
        "input": {
            "path": _relative(failure_log),
            "visible_log": log_text.rstrip().splitlines(),
        },
        "commands": {
            "public_cli": (
                "python -m sdetkit investigate failure "
                "--log tests/fixtures/public_failure_demo/ci_log.txt "
                "--format json --out build/public-launch-proof/investigation.json"
            ),
            "rebuild_committed_proof": (
                "python scripts/build_public_launch_proof.py "
                f"--source-commit {commit}"
            ),
        },
        "diagnosis": {
            "ecosystem": adapter.ecosystem,
            "tool": adapter.tool,
            "classification": vector.failure_class,
            "investigation_classification": investigation["classification"],
            "first_meaningful_failure": vector.first_failing_line,
            "actual_failure": vector.actual_failure,
            "affected_files": list(vector.affected_files),
            "proof_command": vector.local_repro_command,
            "exit_code": vector.exit_code,
            "confidence": adapter.confidence,
        },
        "decision": {
            "review_first": decision.review_first,
            "safe_fix_allowed": decision.safe_fix_allowed,
            "automation_allowed": decision.automation_allowed,
            "patch_application_allowed": decision.patch_application_allowed,
            "merge_authorized": decision.merge_authorized,
            "semantic_equivalence_proven": False,
        },
    }


def build_adoption_story_payload(
    *,
    target_root: Path = DEFAULT_ADOPTION_TARGET,
    source_commit: str,
) -> dict[str, Any]:
    commit = _validate_source_commit(source_commit)
    surface = discover_adoption_surface(target_root)

    return {
        "schema_version": SCHEMA_VERSION,
        "proof_type": "fixture_based_external_adoption",
        "source_commit": commit,
        "capability_state": "main_only_until_1.1.0",
        "target": {
            "path": _relative(target_root),
            "fixture_based": True,
            "git_detected": bool(surface["repo_identity"]["git_detected"]),
        },
        "detected_surfaces": {
            "languages": _named(surface["detected_languages"]),
            "package_managers": _named(surface["package_managers"]),
            "test_runners": _named(surface["test_runners"]),
            "ci_systems": _named(surface["ci_systems"]),
            "security_tools": _named(surface["security_tools"]),
        },
        "recommended_proof_commands": _proof_commands(surface["recommended_proof_commands"]),
        "review_first_unknowns": list(surface["review_first_unknowns"]),
        "generated_artifacts": [
            "docs/artifacts/public-launch-proof/failure-diagnosis.json",
            "docs/artifacts/public-launch-proof/adoption-story.json",
            "docs/artifacts/public-launch-proof/walkthrough.md",
        ],
        "safety": {
            "read_only": True,
            "dependencies_installed": False,
            "target_code_executed": False,
            "target_repository_mutated": False,
            "automation_allowed": bool(surface["automation_allowed"]),
            "patch_application_allowed": bool(surface["patch_application_allowed"]),
            "merge_authorized": bool(surface["merge_authorized"]),
            "semantic_equivalence_proven": bool(surface["semantic_equivalence_proven"]),
        },
    }


def render_walkthrough(failure: dict[str, Any], adoption: dict[str, Any]) -> str:
    diagnosis = failure["diagnosis"]
    decision = failure["decision"]
    surfaces = adoption["detected_surfaces"]
    safety = adoption["safety"]
    unknowns = adoption["review_first_unknowns"]
    unknown_lines = [f"- {item}" for item in unknowns] or ["- none"]

    return "\n".join(
        [
            "# Public launch proof walkthrough",
            "",
            (
                "Accessible static walkthrough: a saved pytest CI log is reduced to the "
                "first failing node, its owning file, a focused proof command, and an "
                "explicit review-first decision. A separate fixture repository is then "
                "profiled without installing dependencies, executing target code, or "
                "modifying the target."
            ),
            "",
            "## Failure diagnosis",
            "",
            f"- source commit: `{failure['source_commit']}`",
            f"- input log: `{failure['input']['path']}`",
            f"- classification: `{diagnosis['classification']}`",
            f"- first failure: `{diagnosis['first_meaningful_failure']}`",
            f"- affected file: `{diagnosis['affected_files'][0]}`",
            f"- proof command: `{diagnosis['proof_command']}`",
            f"- review first: `{str(decision['review_first']).lower()}`",
            f"- merge authorized: `{str(decision['merge_authorized']).lower()}`",
            "",
            "## Fixture-based adoption story",
            "",
            f"- target: `{adoption['target']['path']}`",
            f"- languages: `{', '.join(surfaces['languages'])}`",
            f"- package managers: `{', '.join(surfaces['package_managers'])}`",
            f"- CI systems: `{', '.join(surfaces['ci_systems'])}`",
            f"- security tools: `{', '.join(surfaces['security_tools'])}`",
            "",
            "### Review-first unknowns",
            "",
            *unknown_lines,
            "",
            "### Safety proof",
            "",
            f"- dependencies installed: `{str(safety['dependencies_installed']).lower()}`",
            f"- target code executed: `{str(safety['target_code_executed']).lower()}`",
            (
                "- target repository mutated: "
                f"`{str(safety['target_repository_mutated']).lower()}`"
            ),
            f"- automation allowed: `{str(safety['automation_allowed']).lower()}`",
            f"- merge authorized: `{str(safety['merge_authorized']).lower()}`",
            "",
        ]
    )


def write_public_launch_proof(
    *,
    source_commit: str,
    failure_log: Path = DEFAULT_FAILURE_LOG,
    target_root: Path = DEFAULT_ADOPTION_TARGET,
    out_dir: Path = DEFAULT_OUT_DIR,
) -> dict[str, str]:
    failure = build_failure_demo_payload(
        failure_log=failure_log,
        source_commit=source_commit,
    )
    adoption = build_adoption_story_payload(
        target_root=target_root,
        source_commit=source_commit,
    )
    out_dir.mkdir(parents=True, exist_ok=True)
    failure_path = out_dir / "failure-diagnosis.json"
    adoption_path = out_dir / "adoption-story.json"
    walkthrough_path = out_dir / "walkthrough.md"
    failure_path.write_text(
        json.dumps(failure, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    adoption_path.write_text(
        json.dumps(adoption, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    walkthrough_path.write_text(
        render_walkthrough(failure, adoption) + "\n",
        encoding="utf-8",
    )
    return {
        "failure_diagnosis": _relative(failure_path),
        "adoption_story": _relative(adoption_path),
        "walkthrough": _relative(walkthrough_path),
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Build deterministic public failure-diagnosis and adoption proof.",
    )
    parser.add_argument("--source-commit", required=True)
    parser.add_argument("--failure-log", type=Path, default=DEFAULT_FAILURE_LOG)
    parser.add_argument("--target-root", type=Path, default=DEFAULT_ADOPTION_TARGET)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    ns = parser.parse_args(list(argv) if argv is not None else None)
    outputs = write_public_launch_proof(
        source_commit=ns.source_commit,
        failure_log=ns.failure_log,
        target_root=ns.target_root,
        out_dir=ns.out_dir,
    )
    print(json.dumps(outputs, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
