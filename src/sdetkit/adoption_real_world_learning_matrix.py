from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .adoption_external_integration import write_external_integration_artifact

SCHEMA_VERSION = "sdetkit.adoption_real_world_learning_matrix.v1"

AUTHORITY_FIELDS = (
    "automation_allowed",
    "patch_application_allowed",
    "merge_authorized",
    "semantic_equivalence_proven",
)

PERMISSIVE_LICENSES = {
    "Apache-2.0",
    "BSD-2-Clause",
    "BSD-3-Clause",
    "ISC",
    "MIT",
    "MPL-2.0",
    "Python-2.0",
    "Unlicense",
    "Zlib",
}


@dataclass(frozen=True)
class MatrixEntry:
    name: str
    target_root: Path
    repo_url: str
    license_id: str
    shape: str


def _authority_boundary() -> dict[str, bool]:
    return {field: False for field in AUTHORITY_FIELDS}


def _load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"expected JSON object: {path}")
    return payload


def _safe_repo_name(name: str) -> str:
    safe = re.sub(r"[^A-Za-z0-9_.-]+", "_", name.strip()).strip("._-")
    return safe or "repo"


def _names(items: object) -> list[str]:
    if not isinstance(items, list):
        return []
    names: list[str] = []
    for item in items:
        if isinstance(item, dict):
            name = str(item.get("name", "")).strip()
            if name:
                names.append(name)
    return sorted(set(names))


def _list_strings(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return sorted({str(item) for item in value if str(item).strip()})


def _classification_for_surface(
    *,
    integration: dict[str, Any],
    surface: dict[str, Any],
) -> list[str]:
    observations: set[str] = set()

    languages = _names(surface.get("detected_languages"))
    package_managers = _names(surface.get("package_managers"))
    test_runners = _names(surface.get("test_runners"))
    ci_systems = _names(surface.get("ci_systems"))
    security_tools = _names(surface.get("security_tools"))
    docs_tools = _names(surface.get("docs_tools"))
    release_surfaces = _names(surface.get("release_surfaces"))
    artifact_surfaces = _names(surface.get("artifact_surfaces"))
    proof_commands = surface.get("recommended_proof_commands")
    review_first_unknowns = _list_strings(surface.get("review_first_unknowns"))

    if integration.get("integration_status") != "passed":
        observations.add("integration_runner_bug")
    if (
        languages
        or package_managers
        or ci_systems
        or docs_tools
        or release_surfaces
        or proof_commands
    ):
        observations.add("supported_surface")
    if not languages and not docs_tools:
        observations.add("unsupported_language")
    if languages and not package_managers:
        observations.add("unsupported_package_manager")
    if languages and not test_runners:
        observations.add("unsupported_test_runner")
    if not ci_systems:
        observations.add("unsupported_ci_provider")
    if not isinstance(proof_commands, list) or not proof_commands or review_first_unknowns:
        observations.add("weak_proof_command_mapping")
    if review_first_unknowns:
        observations.add("review_first_unknown")
    if ci_systems and not security_tools:
        observations.add("missed_security_surface")
    if package_managers and not release_surfaces:
        observations.add("missed_release_surface")
    if not artifact_surfaces:
        observations.add("artifact_path_gap")
    if len(languages) > 1 or len(package_managers) > 1:
        observations.add("monorepo_shape_gap")

    return sorted(observations)


def _upgrade_title(classification: str) -> str:
    titles = {
        "unsupported_language": "feat(adoption): expand language detection from real-world matrix gaps",
        "unsupported_package_manager": "feat(adoption): expand package-manager detection from real-world matrix gaps",
        "unsupported_test_runner": "feat(adoption): improve test-runner detection from real-world matrix gaps",
        "unsupported_ci_provider": "feat(adoption): improve CI provider detection from real-world matrix gaps",
        "weak_proof_command_mapping": "feat(adoption): strengthen proof-command mapping from real-world matrix evidence",
        "review_first_unknown": "feat(adoption): prioritize review-first unknown explanations from real-world matrix evidence",
        "missed_security_surface": "feat(adoption): improve security-surface detection from real-world matrix evidence",
        "missed_release_surface": "feat(adoption): improve release-surface detection from real-world matrix evidence",
        "monorepo_shape_gap": "feat(adoption): improve monorepo shape detection from real-world matrix evidence",
        "artifact_path_gap": "feat(adoption): improve artifact path detection from real-world matrix evidence",
        "docs_site_gap": "feat(adoption): improve docs-site detection from real-world matrix evidence",
        "workflow_detection_gap": "feat(adoption): improve workflow detection from real-world matrix evidence",
        "integration_runner_bug": "fix(adoption): harden external integration runner from real-world matrix evidence",
        "performance_or_timeout_issue": "perf(adoption): harden real-world matrix runtime behavior",
    }
    return titles.get(
        classification,
        f"feat(adoption): investigate {classification} from real-world matrix evidence",
    )


def _owner_files(classification: str) -> list[str]:
    common = ["src/sdetkit/adoption_surface.py", "tests/test_adoption_surface.py"]
    if classification == "integration_runner_bug":
        return [
            "src/sdetkit/adoption_external_integration.py",
            "tests/test_adoption_external_integration.py",
        ]
    if classification in {"monorepo_shape_gap", "artifact_path_gap"}:
        return [
            "src/sdetkit/adoption_repo_topology.py",
            "src/sdetkit/adoption_surface.py",
            "tests/test_adoption_repo_topology.py",
        ]
    if classification == "weak_proof_command_mapping":
        return [
            "src/sdetkit/adoption_proof_recommendations.py",
            "src/sdetkit/adoption_surface.py",
            "tests/test_adoption_proof_recommendations.py",
        ]
    return common


def _upgrade_candidates(repos: list[dict[str, Any]]) -> list[dict[str, Any]]:
    counts: Counter[str] = Counter()
    seen_repos: dict[str, list[str]] = {}

    for repo in repos:
        repo_name = str(repo.get("name", "unknown"))
        for classification in _list_strings(repo.get("learning_observations")):
            if classification == "supported_surface":
                continue
            counts[classification] += 1
            seen_repos.setdefault(classification, []).append(repo_name)

    candidates: list[dict[str, Any]] = []
    for classification, count in sorted(counts.items(), key=lambda item: (-item[1], item[0])):
        candidates.append(
            {
                "upgrade_candidate_title": _upgrade_title(classification),
                "classification": classification,
                "observed_in_repos": sorted(seen_repos[classification]),
                "owner_files": _owner_files(classification),
                "reason_from_real_repo": (
                    f"{classification} appeared in {count} repo(s) in the learning matrix."
                ),
                "frequency_across_matrix": count,
                "proof_needed": [
                    "python -m pytest -q tests/test_adoption_real_world_learning_matrix.py -o addopts=",
                    "python -m pytest -q tests/test_adoption_surface.py tests/test_adoption_proof_recommendations.py tests/test_adoption_repo_topology.py -o addopts=",
                    "make proof-after-format",
                ],
                "priority": "P1" if count >= 3 else "P2",
                "review_first": True,
                "safe_to_patch": False,
            }
        )

    return candidates


def _load_matrix_entries(matrix_json: Path) -> list[MatrixEntry]:
    raw = json.loads(matrix_json.read_text(encoding="utf-8"))
    if isinstance(raw, dict):
        raw_entries = raw.get("repos")
    else:
        raw_entries = raw

    if not isinstance(raw_entries, list):
        raise ValueError("matrix JSON must be a list or an object with a repos list")

    matrix_dir = matrix_json.parent.resolve()
    entries: list[MatrixEntry] = []
    for index, item in enumerate(raw_entries, 1):
        if not isinstance(item, dict):
            raise ValueError(f"matrix entry {index} must be an object")

        raw_target = str(item.get("target_root", "")).strip()
        if not raw_target:
            raise ValueError(f"matrix entry {index} is missing target_root")

        target = Path(raw_target)
        if not target.is_absolute():
            target = (matrix_dir / target).resolve()
        else:
            target = target.resolve()

        license_id = str(item.get("license", item.get("license_id", ""))).strip()
        if license_id not in PERMISSIVE_LICENSES:
            raise ValueError(
                f"matrix entry {index} license must be permissive and verified: {license_id!r}"
            )

        name = str(item.get("name", "")).strip() or target.name
        entries.append(
            MatrixEntry(
                name=name,
                target_root=target,
                repo_url=str(item.get("repo_url", "")).strip(),
                license_id=license_id,
                shape=str(item.get("shape", "")).strip(),
            )
        )

    return entries


def run_real_world_learning_matrix(
    *,
    matrix_json: str | Path,
    artifact_root: str | Path,
    minimum_repos: int = 10,
) -> dict[str, Any]:
    matrix_path = Path(matrix_json).resolve()
    artifact_root_path = Path(artifact_root).resolve()
    entries = _load_matrix_entries(matrix_path)

    if len(entries) < minimum_repos:
        raise ValueError(f"real-world learning matrix requires at least {minimum_repos} repos")

    artifact_root_path.mkdir(parents=True, exist_ok=True)

    repos: list[dict[str, Any]] = []
    observation_counts: Counter[str] = Counter()

    for index, entry in enumerate(entries, 1):
        if not entry.target_root.is_dir():
            raise ValueError(
                f"target_root does not exist or is not a directory: {entry.target_root}"
            )

        safe_name = f"{index:02d}_{_safe_repo_name(entry.name)}"
        per_repo_dir = artifact_root_path / "per_repo_artifacts" / safe_name
        integration_path = per_repo_dir / "adoption-external-integration.json"

        integration = write_external_integration_artifact(
            target_root=entry.target_root,
            artifact_dir=per_repo_dir,
            out=integration_path,
        )
        surface_path = Path(str(integration["artifact_paths"]["surface_json"]))
        surface = _load_json(surface_path)

        learning_observations = _classification_for_surface(
            integration=integration,
            surface=surface,
        )
        observation_counts.update(learning_observations)

        repos.append(
            {
                "name": entry.name,
                "safe_name": safe_name,
                "repo_url": entry.repo_url,
                "license": entry.license_id,
                "shape": entry.shape,
                "target_root": entry.target_root.as_posix(),
                "artifact_dir": per_repo_dir.as_posix(),
                "integration_status": integration["integration_status"],
                "target_tree_unchanged": integration["target_tree_unchanged"],
                "detected_languages": _names(surface.get("detected_languages")),
                "package_managers": _names(surface.get("package_managers")),
                "test_runners": _names(surface.get("test_runners")),
                "ci_systems": _names(surface.get("ci_systems")),
                "security_tools": _names(surface.get("security_tools")),
                "docs_tools": _names(surface.get("docs_tools")),
                "release_surfaces": _names(surface.get("release_surfaces")),
                "review_first_unknowns": _list_strings(surface.get("review_first_unknowns")),
                "learning_observations": learning_observations,
                "artifact_paths": {
                    **dict(integration["artifact_paths"]),
                    "external_integration_json": integration_path.as_posix(),
                },
            }
        )

    matrix_status = (
        "passed"
        if all(repo["integration_status"] == "passed" for repo in repos)
        and all(repo["target_tree_unchanged"] is True for repo in repos)
        else "review_required"
    )

    return {
        "schema_version": SCHEMA_VERSION,
        "matrix_status": matrix_status,
        "repo_count": len(repos),
        "minimum_repos": minimum_repos,
        "repos": repos,
        "observation_counts": dict(sorted(observation_counts.items())),
        "upgrade_candidates": _upgrade_candidates(repos),
        "rules": {
            "permissive_license_verified_before_use": True,
            "clone_or_fetch_only": True,
            "artifacts_outside_target_root": True,
            "install_dependencies": False,
            "target_tests_executed": False,
            "target_repo_mutation": False,
            "target_pr_or_issue_opened": False,
            "endorsement_claim": False,
        },
        "automation_allowed": False,
        "patch_application_allowed": False,
        "merge_authorized": False,
        "semantic_equivalence_proven": False,
        "authority_boundary": _authority_boundary(),
    }


def render_real_world_learning_matrix_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# SDETKit real-world adoption learning matrix",
        "",
        f"- status: {payload['matrix_status']}",
        f"- repo_count: {payload['repo_count']}",
        f"- minimum_repos: {payload['minimum_repos']}",
        "- install_dependencies: false",
        "- target_tests_executed: false",
        "- target_repo_mutation: false",
        "- endorsement_claim: false",
        "",
        "## Repositories",
        "",
        "| Repo | License | Shape | Status | Observations |",
        "| --- | --- | --- | --- | --- |",
    ]

    for repo in payload["repos"]:
        observations = ", ".join(repo["learning_observations"]) or "none"
        lines.append(
            "| {name} | {license} | {shape} | {status} | {observations} |".format(
                name=repo["name"],
                license=repo["license"],
                shape=repo["shape"] or "unknown",
                status=repo["integration_status"],
                observations=observations,
            )
        )

    lines.extend(["", "## Observation counts", ""])
    for name, count in payload["observation_counts"].items():
        lines.append(f"- {name}: {count}")

    lines.extend(["", "## Upgrade candidates", ""])
    if payload["upgrade_candidates"]:
        for candidate in payload["upgrade_candidates"]:
            lines.append(f"- {candidate['upgrade_candidate_title']}")
            lines.append(f"  - classification: {candidate['classification']}")
            lines.append(f"  - frequency: {candidate['frequency_across_matrix']}")
            lines.append("  - review_first: true")
            lines.append("  - safe_to_patch: false")
    else:
        lines.append("- none")

    lines.extend(
        [
            "",
            "## Authority boundary",
            "",
            "- automation_allowed: false",
            "- patch_application_allowed: false",
            "- merge_authorized: false",
            "- semantic_equivalence_proven: false",
            "",
        ]
    )
    return "\n".join(lines)


def write_real_world_learning_matrix_artifacts(
    *,
    matrix_json: str | Path,
    artifact_root: str | Path,
    out: str | Path | None = None,
    markdown_out: str | Path | None = None,
    minimum_repos: int = 10,
) -> dict[str, Any]:
    artifact_root_path = Path(artifact_root)
    payload = run_real_world_learning_matrix(
        matrix_json=matrix_json,
        artifact_root=artifact_root_path,
        minimum_repos=minimum_repos,
    )
    out_path = Path(out) if out else artifact_root_path / "adoption-real-world-matrix.json"
    markdown_path = (
        Path(markdown_out) if markdown_out else artifact_root_path / "adoption-real-world-matrix.md"
    )

    out_path.parent.mkdir(parents=True, exist_ok=True)
    markdown_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    markdown_path.write_text(
        render_real_world_learning_matrix_markdown(payload) + "\n",
        encoding="utf-8",
    )
    return payload


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="sdetkit adoption-real-world-learning-matrix",
        description=(
            "Run the read-only external adoption integration stack across a verified "
            "real-world target-root matrix."
        ),
    )
    parser.add_argument("--matrix-json", required=True)
    parser.add_argument(
        "--artifact-root",
        default="build/sdetkit/adoption-real-world-learning",
    )
    parser.add_argument("--out", default="")
    parser.add_argument("--markdown-out", default="")
    parser.add_argument("--minimum-repos", type=int, default=10)
    parser.add_argument("--format", choices=["json", "text"], default="json")
    ns = parser.parse_args(list(argv) if argv is not None else None)

    payload = write_real_world_learning_matrix_artifacts(
        matrix_json=ns.matrix_json,
        artifact_root=ns.artifact_root,
        out=ns.out or None,
        markdown_out=ns.markdown_out or None,
        minimum_repos=ns.minimum_repos,
    )

    if ns.format == "json":
        sys.stdout.write(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    else:
        sys.stdout.write(render_real_world_learning_matrix_markdown(payload) + "\n")
    return 0 if payload["matrix_status"] == "passed" else 2


if __name__ == "__main__":
    raise SystemExit(main())
