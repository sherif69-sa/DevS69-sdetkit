from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from .adoption_surface import discover_adoption_surface, validate_adoption_surface_payload

SCHEMA_VERSION = "sdetkit.adoption_learning.v1"

AUTHORITY_FIELDS = (
    "automation_allowed",
    "patch_application_allowed",
    "merge_authorized",
    "semantic_equivalence_proven",
)

EXPECTED_FIXTURE_REPOS = frozenset(
    {
        "python_pytest_github",
        "node_no_test_script",
        "node_with_test_script",
        "mixed_python_node",
        "go_module",
        "rust_cargo",
        "java_maven",
        "dotnet_solution",
        "gitlab_python",
        "jenkins_java",
    }
)


def _names(items: object) -> list[str]:
    if not isinstance(items, list):
        return []
    names: list[str] = []
    for item in items:
        if isinstance(item, dict) and isinstance(item.get("name"), str):
            names.append(item["name"])
    return sorted(names)


def _commands(items: object) -> list[str]:
    if not isinstance(items, list):
        return []
    commands: list[str] = []
    for item in items:
        if isinstance(item, dict) and isinstance(item.get("command"), str):
            commands.append(item["command"])
    return sorted(commands)


def _authority_boundary(surface: dict[str, Any]) -> dict[str, bool]:
    return {field: bool(surface.get(field)) for field in AUTHORITY_FIELDS}


def _fixture_repo_matrix_present(repo_root: Path) -> bool:
    fixture_root = repo_root / "tests" / "fixtures" / "adoption_repos"
    if not fixture_root.is_dir():
        return False

    present = {path.name for path in fixture_root.iterdir() if path.is_dir()}
    return EXPECTED_FIXTURE_REPOS <= present


def _local_external_root_smoke_present(repo_root: Path) -> bool:
    return (repo_root / "tests" / "test_adoption_local_external_root.py").is_file()


def _public_repo_eligibility_screen_present(repo_root: Path) -> bool:
    return (repo_root / "tests" / "test_adoption_public_repo_eligibility.py").is_file()


def _first_public_repo_trial_present(repo_root: Path) -> bool:
    return (
        repo_root
        / "tests"
        / "fixtures"
        / "adoption_public_trials"
        / "pallets_markupsafe_readonly_trial.json"
    ).is_file()


def _proof_command_recommendation_levels_present(repo_root: Path) -> bool:
    return (repo_root / "tests" / "test_adoption_proof_recommendations.py").is_file()


def _repo_topology_summary_present(repo_root: Path) -> bool:
    return (repo_root / "tests" / "test_adoption_repo_topology.py").is_file()


def _adoption_evidence_bundle_present(repo_root: Path) -> bool:
    return (repo_root / "tests" / "test_adoption_evidence_bundle.py").is_file()


def _detected_strengths(surface: dict[str, Any]) -> list[str]:
    languages = set(_names(surface.get("detected_languages")))
    package_managers = set(_names(surface.get("package_managers")))
    test_runners = set(_names(surface.get("test_runners")))
    ci_systems = set(_names(surface.get("ci_systems")))
    security_tools = set(_names(surface.get("security_tools")))
    commands = set(_commands(surface.get("recommended_proof_commands")))

    strengths: list[str] = []
    if "python" in languages:
        strengths.append("python project detected")
    if {"pip", "poetry"} & package_managers:
        strengths.append("python package management detected")
    if "pytest" in test_runners:
        strengths.append("pytest proof surface detected")
    if "github_actions" in ci_systems:
        strengths.append("github actions CI detected")
    if security_tools:
        strengths.append("security tooling detected: " + ", ".join(sorted(security_tools)))
    if "NO_MKDOCS_2_WARNING=1 python -m mkdocs build --strict" in commands:
        strengths.append("mkdocs documentation proof detected")
    if "python -m pytest -q -o addopts=" in commands:
        strengths.append("pytest proof command detected")
    if "make proof-after-format" in commands:
        strengths.append("full quality proof command detected")
    return strengths


def _learning_gaps(surface: dict[str, Any], repo_root: Path) -> list[str]:
    languages = set(_names(surface.get("detected_languages")))
    ci_systems = set(_names(surface.get("ci_systems")))
    review_unknowns = surface.get("review_first_unknowns")

    fixture_matrix_present = _fixture_repo_matrix_present(repo_root)
    local_external_root_smoke_present = _local_external_root_smoke_present(repo_root)
    public_repo_eligibility_screen_present = _public_repo_eligibility_screen_present(repo_root)
    first_public_repo_trial_present = _first_public_repo_trial_present(repo_root)
    proof_recommendations_present = _proof_command_recommendation_levels_present(repo_root)
    repo_topology_summary_present = _repo_topology_summary_present(repo_root)
    adoption_evidence_bundle_present = _adoption_evidence_bundle_present(repo_root)

    gaps: list[str] = []
    if languages <= {"python"} and not fixture_matrix_present:
        gaps.append("add fixture repo matrix for non-Python repo shapes")
    if ci_systems <= {"github_actions"} and not fixture_matrix_present:
        gaps.append("add fixture coverage for non-GitHub CI providers")
    if not review_unknowns and not fixture_matrix_present:
        gaps.append("add fixtures that prove review-first unknown handling")
    if not local_external_root_smoke_present:
        gaps.append("add local external-root smoke before public repo trials")
    if not public_repo_eligibility_screen_present:
        gaps.append("add public repo eligibility screen before using third-party repos")
    elif not first_public_repo_trial_present:
        gaps.append("run first permissive public repo read-only trial")
    elif not proof_recommendations_present:
        gaps.append("add proof command recommendation levels")
    elif not repo_topology_summary_present:
        gaps.append("add repo topology summary")
    elif not adoption_evidence_bundle_present:
        gaps.append("add adoption evidence bundle")
    else:
        gaps.append("add public repo trial matrix")
    return gaps


def _recommended_next_upgrade(gaps: list[str]) -> str:
    if any("fixture repo matrix" in gap for gap in gaps):
        return "fixture repo matrix"
    if any("local external-root smoke" in gap for gap in gaps):
        return "local external root smoke"
    if any("public repo eligibility screen" in gap for gap in gaps):
        return "public repo eligibility screen"
    if any("first permissive public repo read-only trial" in gap for gap in gaps):
        return "first permissive public repo read-only trial"
    if any("proof command recommendation levels" in gap for gap in gaps):
        return "proof command recommendation levels"
    if any("repo topology summary" in gap for gap in gaps):
        return "repo topology summary"
    if any("adoption evidence bundle" in gap for gap in gaps):
        return "adoption evidence bundle"
    if any("public repo trial matrix" in gap for gap in gaps):
        return "public repo trial matrix"
    return "review learning gaps"


def _upgrade_candidates() -> list[str]:
    return [
        "fixture repo matrix",
        "local external root smoke",
        "public repo eligibility screen",
        "proof command recommendation levels",
        "multi-CI fixture coverage",
        "repo topology summary",
    ]


def build_adoption_learning_payload(
    repo_root: str | Path = ".",
    *,
    trial_name: str = "self_adoption_baseline",
    surface_payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    surface = (
        surface_payload if surface_payload is not None else discover_adoption_surface(repo_root)
    )
    errors = validate_adoption_surface_payload(surface)
    if errors:
        raise ValueError("invalid adoption surface payload: " + "; ".join(errors))

    repo_identity = surface.get("repo_identity")
    identity = repo_identity if isinstance(repo_identity, dict) else {}
    is_current_repo = bool(identity.get("is_current_sdetkit_repo"))

    root_path = Path(repo_root)
    learning_gaps = _learning_gaps(surface, root_path)

    return {
        "schema_version": SCHEMA_VERSION,
        "trial_name": trial_name,
        "target": "current_sdetkit_repo" if is_current_repo else "external_repo",
        "adoption_surface_schema_version": surface.get("schema_version"),
        "repo_identity": identity,
        "detected_strengths": _detected_strengths(surface),
        "observed_surfaces": {
            "detected_languages": _names(surface.get("detected_languages")),
            "package_managers": _names(surface.get("package_managers")),
            "test_runners": _names(surface.get("test_runners")),
            "ci_systems": _names(surface.get("ci_systems")),
            "security_tools": _names(surface.get("security_tools")),
            "recommended_proof_commands": _commands(surface.get("recommended_proof_commands")),
            "review_first_unknowns": sorted(
                str(item) for item in surface.get("review_first_unknowns", [])
            ),
        },
        "learning_gaps": learning_gaps,
        "upgrade_candidates": _upgrade_candidates(),
        "recommended_next_upgrade": _recommended_next_upgrade(learning_gaps),
        "authority_boundary": _authority_boundary(surface),
        "automation_allowed": False,
        "patch_application_allowed": False,
        "merge_authorized": False,
        "semantic_equivalence_proven": False,
    }


def write_adoption_learning_artifact(
    *,
    repo_root: str | Path = ".",
    surface_json: str | Path | None = None,
    out: str | Path = "build/sdetkit/adoption-learning.json",
    trial_name: str = "self_adoption_baseline",
) -> dict[str, Any]:
    surface_payload: dict[str, Any] | None = None
    if surface_json:
        loaded = json.loads(Path(surface_json).read_text(encoding="utf-8"))
        if not isinstance(loaded, dict):
            raise ValueError("surface_json must contain a JSON object")
        surface_payload = loaded

    payload = build_adoption_learning_payload(
        repo_root,
        trial_name=trial_name,
        surface_payload=surface_payload,
    )
    out_path = Path(out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return payload


def render_adoption_learning_text(payload: dict[str, Any]) -> str:
    lines = [
        "adoption_learning_status=recorded",
        f"trial_name={payload['trial_name']}",
        f"target={payload['target']}",
        f"recommended_next_upgrade={payload['recommended_next_upgrade']}",
        "detected_strengths:",
        *[f"- {item}" for item in payload["detected_strengths"]],
        "learning_gaps:",
        *[f"- {item}" for item in payload["learning_gaps"]],
        "authority_boundary:",
    ]
    authority = payload["authority_boundary"]
    lines.extend(f"- {field}={str(authority[field]).lower()}" for field in AUTHORITY_FIELDS)
    return "\n".join(lines)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="sdetkit adoption-learning",
        description="Record a read-only adoption learning baseline.",
    )
    parser.add_argument("--root", default=".")
    parser.add_argument("--surface-json", default="")
    parser.add_argument("--out", default="build/sdetkit/adoption-learning.json")
    parser.add_argument("--trial-name", default="self_adoption_baseline")
    parser.add_argument("--format", choices=["json", "text"], default="json")
    ns = parser.parse_args(list(argv) if argv is not None else None)

    payload = write_adoption_learning_artifact(
        repo_root=ns.root,
        surface_json=ns.surface_json or None,
        out=ns.out,
        trial_name=ns.trial_name,
    )

    if ns.format == "json":
        sys.stdout.write(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    else:
        sys.stdout.write(render_adoption_learning_text(payload) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
