from __future__ import annotations

import argparse
import json
import subprocess
import sys
from collections import Counter
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any


def _accepted_candidate_history(root: Path) -> set[str]:
    """Return normalized commit subjects already accepted on the local history."""

    try:
        completed = subprocess.run(
            ["git", "log", "--format=%s", "--max-count=300"],
            cwd=root,
            check=False,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
        )
    except OSError:
        return set()

    if completed.returncode != 0:
        return set()

    subjects: set[str] = set()
    for line in completed.stdout.splitlines():
        subject = line.strip()
        if not subject:
            continue
        if " (#" in subject and subject.endswith(")"):
            subject = subject.rsplit(" (#", 1)[0].strip()
        subjects.add(subject.lower())

    return subjects


def _normalized_history_subject(value: str) -> str:
    return " ".join(value.strip().lower().replace("-", " ").split())


def _history_title_tokens(value: str) -> set[str]:
    cleaned = value.lower().replace("-", " ")
    for char in "()[]{}:,_/.":
        cleaned = cleaned.replace(char, " ")

    return {token for token in cleaned.split() if len(token) >= 3}


def _accepted_title_drift_match(candidate_title: str, accepted_subject: str) -> bool:
    candidate_tokens = _history_title_tokens(candidate_title)
    subject_tokens = _history_title_tokens(accepted_subject)

    if not candidate_tokens or not subject_tokens:
        return False

    overlap = candidate_tokens & subject_tokens

    # Conservative title-drift rule:
    # - catches wording drift like "refresh README and docs map" vs "refresh docs lanes"
    # - avoids overmatching broad workflow/ci subjects where only 1-3 generic tokens overlap
    return len(overlap) >= 4


def _candidate_accepted_on_main(candidate_title: str, accepted_subjects: set[str]) -> bool:
    normalized_candidate = _normalized_history_subject(candidate_title)
    if not normalized_candidate:
        return False

    if normalized_candidate in accepted_subjects:
        return True

    for subject in accepted_subjects:
        normalized_subject = _normalized_history_subject(subject)
        if not normalized_subject:
            continue
        if normalized_candidate == normalized_subject:
            return True
        if SequenceMatcher(None, normalized_candidate, normalized_subject).ratio() >= 0.82:
            return True
        if _accepted_title_drift_match(candidate_title, subject):
            return True

    return False


SCHEMA_VERSION = "sdetkit.product_maturity_radar.v1"

AUTHORITY_FIELDS = (
    "automation_allowed",
    "patch_application_allowed",
    "merge_authorized",
    "semantic_equivalence_proven",
)

EXCLUDED_PARTS = {
    ".git",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".venv",
    "__pycache__",
    "build",
    "dist",
    "htmlcov",
    "mutants",
    "site",
}

SOURCE_SUFFIXES = {".py", ".md", ".toml", ".yml", ".yaml", ".txt", ".sh"}


@dataclass(frozen=True)
class Surface:
    name: str
    title: str
    owner_files: tuple[str, ...]
    indicators: tuple[str, ...]


def _authority_boundary() -> dict[str, bool]:
    return {field: False for field in AUTHORITY_FIELDS}


def _iter_files(root: Path) -> Iterable[Path]:
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        if any(part in EXCLUDED_PARTS for part in path.parts):
            continue
        if path.suffix.lower() not in SOURCE_SUFFIXES and path.name not in {
            "README.md",
            "LICENSE",
            "CHANGELOG.md",
            "SECURITY.md",
            "CONTRIBUTING.md",
            "Makefile",
        }:
            continue
        yield path


def _rel(root: Path, path: Path) -> str:
    return path.relative_to(root).as_posix()


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="ignore")


def _exists(root: Path, *paths: str) -> bool:
    return any((root / item).exists() for item in paths)


def _count_files(root: Path, pattern: str) -> int:
    return sum(1 for path in root.glob(pattern) if path.is_file())


def _files_matching(root: Path, pattern: str) -> list[str]:
    return sorted(_rel(root, path) for path in root.glob(pattern) if path.is_file())


def _contains_any(text: str, needles: Sequence[str]) -> bool:
    lower = text.lower()
    return any(needle.lower() in lower for needle in needles)


def _repo_text_index(root: Path) -> dict[str, str]:
    return {_rel(root, path): _read(path) for path in _iter_files(root)}


def _candidate(
    *,
    title: str,
    classification: str,
    surface: str,
    owner_files: Sequence[str],
    reason: str,
    proof_commands: Sequence[str],
    priority: str,
) -> dict[str, Any]:
    return {
        "upgrade_candidate_title": title,
        "classification": classification,
        "surface": surface,
        "owner_files": sorted(set(owner_files)),
        "reason_from_repo": reason,
        "proof_needed": list(proof_commands),
        "priority": priority,
        "review_first": True,
        "safe_to_patch": False,
    }


def _surface_payload(
    *,
    name: str,
    title: str,
    status: str,
    score: int,
    max_score: int,
    indicators: dict[str, str],
    owner_files: Sequence[str],
    candidates: Sequence[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "name": name,
        "title": title,
        "status": status,
        "score": score,
        "max_score": max_score,
        "indicators": dict(sorted(indicators.items())),
        "owner_files": sorted(set(owner_files)),
        "candidate_count": len(candidates),
        "upgrade_candidates": list(candidates),
        "review_first": True,
        "safe_to_patch": False,
    }


def _yes_no(value: bool) -> str:
    return "yes" if value else "no"


def _status(score: int, max_score: int) -> str:
    if max_score == 0:
        return "unknown"
    ratio = score / max_score
    if ratio >= 0.8:
        return "strong"
    if ratio >= 0.5:
        return "developing"
    return "needs_attention"


def _evidence_surface(root: Path, text_index: dict[str, str]) -> dict[str, Any]:
    evidence_modules = _files_matching(root, "src/sdetkit/*evidence*.py")
    artifact_docs = _files_matching(root, "docs/*artifact*.md")
    has_stable_json = any("stable-json" in text for text in text_index.values())
    has_product_proof = _exists(root, "docs/live-adoption-product-proof.md")
    has_artifact_reference = _exists(root, "docs/artifact-reference.md")

    indicators = {
        "evidence_modules": _yes_no(bool(evidence_modules)),
        "artifact_reference": _yes_no(has_artifact_reference),
        "stable_json_contract": _yes_no(has_stable_json),
        "product_proof_page": _yes_no(has_product_proof),
    }
    score = sum(value == "yes" for value in indicators.values())
    candidates: list[dict[str, Any]] = []
    if not has_artifact_reference or not has_stable_json:
        candidates.append(
            _candidate(
                title="feat(evidence): strengthen artifact contract map",
                classification="artifact_contract_gap",
                surface="evidence",
                owner_files=[
                    "docs/artifact-reference.md",
                    "src/sdetkit",
                    "tests",
                ],
                reason="The radar found missing or weak artifact/stable JSON contract signals.",
                proof_commands=[
                    "python -m pytest -q tests/test_artifact_reference.py -o addopts=",
                    "make proof-after-format",
                ],
                priority="P1",
            )
        )

    return _surface_payload(
        name="evidence",
        title="Evidence and artifact contracts",
        status=_status(score, len(indicators)),
        score=score,
        max_score=len(indicators),
        indicators=indicators,
        owner_files=[*evidence_modules, *artifact_docs],
        candidates=candidates,
    )


def _diagnosis_surface(root: Path, text_index: dict[str, str]) -> dict[str, Any]:
    files = [
        "src/sdetkit/check_intelligence.py",
        "src/sdetkit/current_head_failure_bundle.py",
        "src/sdetkit/diagnostic_vector_engine.py",
        "src/sdetkit/reliability_spine_alignment.py",
    ]
    tests = [
        "tests/test_check_intelligence.py",
        "tests/test_current_head_failure_bundle.py",
        "tests/test_pr_quality_current_head_failure_bundle.py",
    ]
    has_failure_taxonomy = any(
        _contains_any(text, ["diagnosis", "failure", "primary_blocker"])
        for text in text_index.values()
    )
    existing_files = [_rel(root, root / item) for item in files if (root / item).is_file()]
    existing_tests = [_rel(root, root / item) for item in tests if (root / item).is_file()]
    indicators = {
        "check_intelligence": _yes_no((root / "src/sdetkit/check_intelligence.py").is_file()),
        "failure_bundle": _yes_no((root / "src/sdetkit/current_head_failure_bundle.py").is_file()),
        "diagnostic_vector_engine": _yes_no(
            (root / "src/sdetkit/diagnostic_vector_engine.py").is_file()
        ),
        "diagnosis_tests": _yes_no(bool(existing_tests)),
        "failure_taxonomy_signal": _yes_no(has_failure_taxonomy),
    }
    score = sum(value == "yes" for value in indicators.values())
    candidates: list[dict[str, Any]] = []
    if score < len(indicators):
        candidates.append(
            _candidate(
                title="feat(diagnosis): consolidate failure taxonomy and owner mapping",
                classification="diagnosis_taxonomy_gap",
                surface="diagnosis",
                owner_files=[*existing_files, *existing_tests],
                reason="Diagnosis surfaces exist but the radar found incomplete taxonomy coverage.",
                proof_commands=[
                    "python -m pytest -q tests/test_check_intelligence.py tests/test_current_head_failure_bundle.py -o addopts=",
                    "make proof-after-format",
                ],
                priority="P1",
            )
        )

    return _surface_payload(
        name="diagnosis",
        title="Failure diagnosis and vector intelligence",
        status=_status(score, len(indicators)),
        score=score,
        max_score=len(indicators),
        indicators=indicators,
        owner_files=[*existing_files, *existing_tests],
        candidates=candidates,
    )


def _adoption_surface(root: Path) -> dict[str, Any]:
    modules = _files_matching(root, "src/sdetkit/adoption_*.py")
    tests = _files_matching(root, "tests/test_adoption_*.py")
    indicators = {
        "adoption_modules": _yes_no(bool(modules)),
        "adoption_tests": _yes_no(bool(tests)),
        "real_world_matrix": _yes_no(
            (root / "src/sdetkit/adoption_real_world_learning_matrix.py").is_file()
        ),
        "learning_report": _yes_no((root / "src/sdetkit/adoption_learning_report.py").is_file()),
        "external_integration": _yes_no(
            (root / "src/sdetkit/adoption_external_integration.py").is_file()
        ),
    }
    score = sum(value == "yes" for value in indicators.values())
    candidates = [
        _candidate(
            title="feat(adoption): turn real-world learning gaps into detector upgrades",
            classification="adoption_learning_next",
            surface="adoption",
            owner_files=[*modules, *tests],
            reason="The repo now has real-world matrix/report contracts; next work should consume their candidate output.",
            proof_commands=[
                "python -m pytest -q tests/test_adoption_learning_report.py tests/test_adoption_real_world_learning_matrix.py -o addopts=",
                "make proof-after-format",
            ],
            priority="P1",
        )
    ]

    return _surface_payload(
        name="adoption",
        title="External repo adoption and learning",
        status=_status(score, len(indicators)),
        score=score,
        max_score=len(indicators),
        indicators=indicators,
        owner_files=[*modules, *tests],
        candidates=candidates,
    )


def _workflow_surface(root: Path) -> dict[str, Any]:
    workflows = _files_matching(root, ".github/workflows/*.yml") + _files_matching(
        root, ".github/workflows/*.yaml"
    )
    has_governance = (root / "src/sdetkit/workflow_governance_report.py").is_file()
    has_tests = (root / "tests/test_workflow_governance_report.py").is_file()
    indicators = {
        "workflow_files": _yes_no(bool(workflows)),
        "workflow_governance_report": _yes_no(has_governance),
        "workflow_governance_tests": _yes_no(has_tests),
        "workflow_count_reasonable": _yes_no(len(workflows) <= 60),
    }
    score = sum(value == "yes" for value in indicators.values())
    candidates = [
        _candidate(
            title="ci: continue workflow hardening from governance report findings",
            classification="workflow_governance_followup",
            surface="workflow",
            owner_files=[
                "src/sdetkit/workflow_governance_report.py",
                "tests/test_workflow_governance_report.py",
                ".github/workflows",
            ],
            reason="Workflow governance evidence exists; follow-up hardening should remain small and report-driven.",
            proof_commands=[
                "python -m pytest -q tests/test_workflow_governance_report.py tests/test_workflow_external_tool_pin_contract.py -o addopts=",
                "python -m sdetkit workflow-governance-report --root . --out build/sdetkit/workflow-governance-report.json --format text",
                "make proof-after-format",
            ],
            priority="P2",
        )
    ]

    return _surface_payload(
        name="workflow",
        title="CI workflow governance and hardening",
        status=_status(score, len(indicators)),
        score=score,
        max_score=len(indicators),
        indicators=indicators,
        owner_files=[*workflows, "src/sdetkit/workflow_governance_report.py"],
        candidates=candidates,
    )


def _docs_surface(root: Path) -> dict[str, Any]:
    docs = _files_matching(root, "docs/*.md")
    has_readme = (root / "README.md").is_file()
    has_mkdocs = (root / "mkdocs.yml").is_file()
    has_start_here = (root / "docs/start-here-5-minutes.md").is_file()
    has_cli_docs = (root / "docs/cli.md").is_file()
    indicators = {
        "readme": _yes_no(has_readme),
        "mkdocs": _yes_no(has_mkdocs),
        "start_here": _yes_no(has_start_here),
        "cli_docs": _yes_no(has_cli_docs),
        "docs_count": _yes_no(len(docs) >= 10),
    }
    score = sum(value == "yes" for value in indicators.values())
    candidates = [
        _candidate(
            title="docs(product): refresh README and docs map for real-world learning lanes",
            classification="product_docs_refresh",
            surface="docs",
            owner_files=["README.md", "docs/index.md", "docs/start-here-5-minutes.md"],
            reason="Recent adoption, learning, and governance commands should be reflected in public docs.",
            proof_commands=[
                "python -m pytest -q tests/test_docs_navigation.py -o addopts=",
                "make proof-after-format",
            ],
            priority="P1",
        )
    ]

    return _surface_payload(
        name="docs",
        title="Docs, README, and product positioning",
        status=_status(score, len(indicators)),
        score=score,
        max_score=len(indicators),
        indicators=indicators,
        owner_files=["README.md", "mkdocs.yml", *docs[:20]],
        candidates=candidates,
    )


def _security_release_surface(root: Path) -> dict[str, Any]:
    indicators = {
        "security_policy": _yes_no(_exists(root, "SECURITY.md", "docs/security.md")),
        "changelog": _yes_no(_exists(root, "CHANGELOG.md")),
        "release_process": _yes_no(_exists(root, "docs/project/release-process.md")),
        "supply_chain_docs": _yes_no(
            _exists(root, "docs/project/release-process.md", "docs/policy-and-baselines.md")
        ),
    }
    score = sum(value == "yes" for value in indicators.values())
    candidates = [
        _candidate(
            title="security: refresh anti-hijack and release threat model",
            classification="security_release_hardening",
            surface="security_release",
            owner_files=[
                "SECURITY.md",
                "docs/security.md",
                "docs/project/release-process.md",
                "docs/policy-and-baselines.md",
            ],
            reason="Security/release files exist; roadmap calls for explicit anti-hijack and release threat-model hardening.",
            proof_commands=[
                "python -m pytest -q tests/test_docs_security.py -o addopts=",
                "make proof-after-format",
            ],
            priority="P1",
        )
    ]

    return _surface_payload(
        name="security_release",
        title="Security, release, and supply chain",
        status=_status(score, len(indicators)),
        score=score,
        max_score=len(indicators),
        indicators=indicators,
        owner_files=[
            "SECURITY.md",
            "docs/security.md",
            "docs/project/release-process.md",
            "CHANGELOG.md",
        ],
        candidates=candidates,
    )


def _packaging_surface(root: Path) -> dict[str, Any]:
    pyproject = root / "pyproject.toml"
    text = _read(pyproject) if pyproject.is_file() else ""
    indicators = {
        "pyproject": _yes_no(pyproject.is_file()),
        "console_scripts": _yes_no("[project.scripts]" in text),
        "package_data": _yes_no("[tool.setuptools.package-data]" in text),
        "optional_dependencies": _yes_no("[project.optional-dependencies]" in text),
        "python_310_plus": _yes_no('requires-python = ">=3.10"' in text),
    }
    score = sum(value == "yes" for value in indicators.values())
    candidates = [
        _candidate(
            title="feat(packaging): publish stable versus hidden command surface report",
            classification="public_command_surface_gap",
            surface="packaging",
            owner_files=["pyproject.toml", "src/sdetkit/_legacy_cli.py", "docs/cli.md"],
            reason="The package has public entrypoints and many hidden/internal commands; roadmap needs stable surface clarity.",
            proof_commands=[
                "python -m pytest -q tests/test_public_command_surface.py -o addopts=",
                "make proof-after-format",
            ],
            priority="P2",
        )
    ]

    return _surface_payload(
        name="packaging",
        title="Packaging and public command surface",
        status=_status(score, len(indicators)),
        score=score,
        max_score=len(indicators),
        indicators=indicators,
        owner_files=["pyproject.toml", "src/sdetkit/_legacy_cli.py", "docs/cli.md"],
        candidates=candidates,
    )


def _learning_surface(root: Path) -> dict[str, Any]:
    indicators = {
        "repo_memory": _yes_no((root / "src/sdetkit/repo_memory.py").is_file()),
        "trajectory_tests": _yes_no((root / "tests/test_trajectory_store.py").is_file()),
        "learning_report": _yes_no((root / "src/sdetkit/adoption_learning_report.py").is_file()),
        "benchmark_harness": _yes_no(
            (root / "src/sdetkit/replayable_benchmark_harness.py").is_file()
        ),
    }
    score = sum(value == "yes" for value in indicators.values())
    candidates = [
        _candidate(
            title="feat(learning): connect repo memory to adoption and diagnosis reports",
            classification="learning_loop_integration",
            surface="learning",
            owner_files=[
                "src/sdetkit/repo_memory.py",
                "src/sdetkit/adoption_learning_report.py",
                "src/sdetkit/replayable_benchmark_harness.py",
                "tests/test_repo_memory.py",
            ],
            reason="Learning primitives exist but should be connected into a stronger repo-wide control loop.",
            proof_commands=[
                "python -m pytest -q tests/test_repo_memory.py tests/test_adoption_learning_report.py -o addopts=",
                "make proof-after-format",
            ],
            priority="P1",
        )
    ]

    return _surface_payload(
        name="learning",
        title="Repo memory, learning loop, and benchmark replay",
        status=_status(score, len(indicators)),
        score=score,
        max_score=len(indicators),
        indicators=indicators,
        owner_files=[
            "src/sdetkit/repo_memory.py",
            "src/sdetkit/replayable_benchmark_harness.py",
            "tests/test_repo_memory.py",
        ],
        candidates=candidates,
    )


def _remediation_surface(root: Path, text_index: dict[str, str]) -> dict[str, Any]:
    has_safe_boundary = any("safe_to_patch" in text for text in text_index.values())
    has_patch_boundary = any("patch_application_allowed" in text for text in text_index.values())
    has_cookbook = (root / "docs/remediation-cookbook.md").is_file()
    has_examples = (root / "examples/kits/intelligence/failure-fix-playbook.md").is_file()
    indicators = {
        "safe_to_patch_boundary": _yes_no(has_safe_boundary),
        "patch_application_boundary": _yes_no(has_patch_boundary),
        "remediation_cookbook": _yes_no(has_cookbook),
        "failure_fix_playbook": _yes_no(has_examples),
    }
    score = sum(value == "yes" for value in indicators.values())
    candidates = [
        _candidate(
            title="feat(remediation): add verifier-backed dry-run remediation readiness report",
            classification="remediation_readiness_gap",
            surface="remediation",
            owner_files=[
                "docs/remediation-cookbook.md",
                "examples/kits/intelligence/failure-fix-playbook.md",
                "src/sdetkit",
                "tests",
            ],
            reason="The repo has safety boundaries; next remediation work should stay dry-run and verifier-backed.",
            proof_commands=[
                "python -m pytest -q tests/test_patch_scorer.py tests/test_pr_quality_action_report.py -o addopts=",
                "make proof-after-format",
            ],
            priority="P2",
        )
    ]

    return _surface_payload(
        name="remediation",
        title="Controlled remediation readiness",
        status=_status(score, len(indicators)),
        score=score,
        max_score=len(indicators),
        indicators=indicators,
        owner_files=[
            "docs/remediation-cookbook.md",
            "examples/kits/intelligence/failure-fix-playbook.md",
            "src/sdetkit/pr_quality_action_report.py",
        ],
        candidates=candidates,
    )


def _rank_candidates(surfaces: Sequence[dict[str, Any]], root: Path) -> list[dict[str, Any]]:
    priority_weight = {"P0": 400, "P1": 300, "P2": 200, "P3": 100}
    accepted_subjects = _accepted_candidate_history(root)
    ranked: list[dict[str, Any]] = []
    for surface in surfaces:
        surface_score = int(surface["score"])
        surface_max = int(surface["max_score"])
        maturity_gap = surface_max - surface_score
        for candidate in surface["upgrade_candidates"]:
            priority = str(candidate.get("priority", "P3"))
            candidate_title = str(
                candidate.get("upgrade_candidate_title") or candidate.get("title") or ""
            )
            accepted_on_main = _candidate_accepted_on_main(
                candidate_title,
                accepted_subjects,
            )
            if accepted_on_main:
                ranking_status = "accepted_on_main"
            elif candidate.get("review_first") is True and candidate.get("safe_to_patch") is False:
                ranking_status = "blocked_review_first_candidate"
            else:
                ranking_status = "fresh_candidate"
            accepted_penalty = 1000 if accepted_on_main else 0

            ranked.append(
                {
                    **candidate,
                    "surface_score": surface_score,
                    "surface_max_score": surface_max,
                    "ranking_score": priority_weight.get(priority, 0)
                    + maturity_gap * 10
                    - accepted_penalty,
                    "accepted_on_main": accepted_on_main,
                    "ranking_status": ranking_status,
                }
            )

    return sorted(
        ranked,
        key=lambda item: (
            -int(item["ranking_score"]),
            str(item["surface"]),
            str(item["upgrade_candidate_title"]),
        ),
    )


def build_product_maturity_radar(repo_root: str | Path = ".") -> dict[str, Any]:
    root = Path(repo_root).resolve()
    text_index = _repo_text_index(root)

    surfaces = [
        _evidence_surface(root, text_index),
        _diagnosis_surface(root, text_index),
        _adoption_surface(root),
        _workflow_surface(root),
        _docs_surface(root),
        _security_release_surface(root),
        _packaging_surface(root),
        _learning_surface(root),
        _remediation_surface(root, text_index),
    ]
    ranked = _rank_candidates(surfaces, root)
    status_counts = Counter(str(surface["status"]) for surface in surfaces)
    total_score = sum(int(surface["score"]) for surface in surfaces)
    total_max_score = sum(int(surface["max_score"]) for surface in surfaces)

    return {
        "schema_version": SCHEMA_VERSION,
        "report_status": "review_required" if ranked else "passed",
        "repo_root": root.as_posix(),
        "surface_count": len(surfaces),
        "candidate_count": len(ranked),
        "total_score": total_score,
        "total_max_score": total_max_score,
        "status_counts": dict(sorted(status_counts.items())),
        "surfaces": surfaces,
        "ranked_upgrade_candidates": ranked,
        "operator_summary": {
            "status": "product_maturity_radar_generated",
            "next_action": ranked[0]["upgrade_candidate_title"]
            if ranked
            else "No product maturity candidates found.",
        },
        "rules": {
            "advisory_only": True,
            "repo_mutation": False,
            "workflow_mutation": False,
            "target_repo_mutation": False,
            "review_first": True,
        },
        "automation_allowed": False,
        "patch_application_allowed": False,
        "merge_authorized": False,
        "semantic_equivalence_proven": False,
        "authority_boundary": _authority_boundary(),
    }


def render_product_maturity_radar_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# SDETKit product maturity radar",
        "",
        f"- report_status: {payload['report_status']}",
        f"- surface_count: {payload['surface_count']}",
        f"- candidate_count: {payload['candidate_count']}",
        f"- total_score: {payload['total_score']}/{payload['total_max_score']}",
        "- advisory_only: true",
        "- repo_mutation: false",
        "- review_first: true",
        "",
        "## Surfaces",
        "",
        "| Surface | Status | Score | Candidates |",
        "| --- | --- | ---: | ---: |",
    ]

    for surface in payload["surfaces"]:
        lines.append(
            "| {title} | `{status}` | {score}/{max_score} | {candidate_count} |".format(
                title=surface["title"],
                status=surface["status"],
                score=surface["score"],
                max_score=surface["max_score"],
                candidate_count=surface["candidate_count"],
            )
        )

    lines.extend(["", "## Ranked upgrade candidates", ""])
    candidates = payload.get("ranked_upgrade_candidates")
    if not isinstance(candidates, list) or not candidates:
        lines.append("- none")
    else:
        for index, candidate in enumerate(candidates, 1):
            lines.append(f"{index}. {candidate['upgrade_candidate_title']}")
            lines.append(f"   - surface: `{candidate['surface']}`")
            lines.append(f"   - classification: `{candidate['classification']}`")
            lines.append(f"   - priority: `{candidate['priority']}`")
            lines.append(f"   - ranking_score: `{candidate['ranking_score']}`")
            if candidate.get("accepted_on_main"):
                lines.append("   - accepted_on_main: true")
            lines.append(
                f"   - ranking_status: `{candidate.get('ranking_status', 'fresh_candidate')}`"
            )
            if candidate.get("ranking_status") == "blocked_review_first_candidate":
                lines.append("   - blocked_by: `human_review_evidence_required`")
            lines.append("   - review_first: true")
            lines.append("   - safe_to_patch: false")

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


def write_product_maturity_radar(
    *,
    repo_root: str | Path,
    out: str | Path,
    markdown_out: str | Path | None = None,
) -> dict[str, Any]:
    payload = build_product_maturity_radar(repo_root=repo_root)
    out_path = Path(out)
    markdown_path = Path(markdown_out) if markdown_out else out_path.with_suffix(".md")

    out_path.parent.mkdir(parents=True, exist_ok=True)
    markdown_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    markdown_path.write_text(
        render_product_maturity_radar_markdown(payload) + "\n", encoding="utf-8"
    )
    return payload


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="sdetkit product-maturity-radar",
        description="Build a repo-wide advisory product maturity radar for roadmap planning.",
    )
    parser.add_argument("--root", default=".")
    parser.add_argument("--out", default="build/sdetkit/product-maturity-radar.json")
    parser.add_argument("--markdown-out", default="")
    parser.add_argument("--format", choices=["json", "text"], default="json")
    ns = parser.parse_args(list(argv) if argv is not None else None)

    payload = write_product_maturity_radar(
        repo_root=ns.root,
        out=ns.out,
        markdown_out=ns.markdown_out or None,
    )

    if ns.format == "json":
        sys.stdout.write(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    else:
        sys.stdout.write(render_product_maturity_radar_markdown(payload) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
