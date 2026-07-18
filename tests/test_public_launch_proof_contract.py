from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = ROOT / "scripts" / "build_public_launch_proof.py"
ARTIFACT_DIR = ROOT / "docs" / "artifacts" / "public-launch-proof"

spec = importlib.util.spec_from_file_location("public_launch_proof_builder", SCRIPT_PATH)
assert spec and spec.loader
builder = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = builder
spec.loader.exec_module(builder)


def test_failure_demo_exposes_first_failure_and_review_first_boundary() -> None:
    payload = builder.build_failure_demo_payload(
        source_commit="9cc48c2141de15ee2354d0e2aba1435472c2051f",
    )

    assert payload["capability_state"] == "published_in_1.2.0"
    assert payload["diagnosis"] == {
        "ecosystem": "python",
        "tool": "pytest",
        "classification": "test",
        "investigation_classification": "PYTEST_ASSERTION_FAILURE",
        "first_meaningful_failure": (
            "FAILED tests/test_checkout.py::test_total_includes_tax - "
            "AssertionError: total mismatch: expected 110, got 108"
        ),
        "actual_failure": (
            "FAILED tests/test_checkout.py::test_total_includes_tax - "
            "AssertionError: total mismatch: expected 110, got 108"
        ),
        "affected_files": ["tests/test_checkout.py"],
        "proof_command": (
            "PYTHONPATH=src python -m pytest -q "
            "tests/test_checkout.py::test_total_includes_tax -o addopts="
        ),
        "exit_code": 1,
        "confidence": "high",
    }
    assert payload["decision"] == {
        "review_first": True,
        "safe_fix_allowed": False,
        "automation_allowed": False,
        "patch_application_allowed": False,
        "merge_authorized": False,
        "semantic_equivalence_proven": False,
    }


def test_adoption_story_profiles_fixture_without_execution_or_mutation() -> None:
    payload = builder.build_adoption_story_payload(
        source_commit="9cc48c2141de15ee2354d0e2aba1435472c2051f",
    )

    assert payload["capability_state"] == "published_in_1.2.0"
    assert payload["detected_surfaces"] == {
        "languages": ["go", "javascript_typescript", "python"],
        "package_managers": ["go_modules", "npm", "pip"],
        "test_runners": ["node_test_script"],
        "ci_systems": ["gitlab_ci"],
        "security_tools": ["pip_audit"],
    }
    assert payload["recommended_proof_commands"] == ["go test ./...", "npm test"]
    assert payload["review_first_unknowns"] == [
        "Python project detected but test command is not proven"
    ]
    assert payload["safety"] == {
        "read_only": True,
        "dependencies_installed": False,
        "target_code_executed": False,
        "target_repository_mutated": False,
        "automation_allowed": False,
        "patch_application_allowed": False,
        "merge_authorized": False,
        "semantic_equivalence_proven": False,
    }


def test_committed_public_launch_artifacts_are_fresh(tmp_path: Path) -> None:
    committed_failure = json.loads(
        (ARTIFACT_DIR / "failure-diagnosis.json").read_text(encoding="utf-8")
    )
    source_commit = committed_failure["source_commit"]
    out_dir = tmp_path / "public-launch-proof"

    builder.write_public_launch_proof(
        source_commit=source_commit,
        out_dir=out_dir,
    )

    for name in ("failure-diagnosis.json", "adoption-story.json", "walkthrough.md"):
        assert (out_dir / name).read_text(encoding="utf-8") == (ARTIFACT_DIR / name).read_text(
            encoding="utf-8"
        )


def test_public_front_doors_link_the_committed_proof() -> None:
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    docs_home = (ROOT / "docs" / "index.md").read_text(encoding="utf-8")

    assert "docs/public-launch-proof.md" in readme
    assert "public-launch-proof.md" in docs_home
