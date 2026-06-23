from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
from collections import Counter
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any

from . import (
    adoption_learning_report,
    automation_health,
    maintenance_queue_rollup,
    public_command_surface_report,
    release_anti_hijack_threat_model,
    remediation_readiness_report,
    workflow_governance_report,
)
from .report_provenance import (
    attach_provenance,
    build_input_provenance,
    check_report_path,
    collect_source_run_ids,
    normalize_int_ids,
    render_freshness_text,
    resolve_current_head,
)


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


SCHEMA_VERSION = "sdetkit.product_maturity_radar.v2"

DEFAULT_OUT = "build/sdetkit/product-maturity-radar.json"
GENERATOR_SOURCE = "src/sdetkit/product_maturity_radar.py"
NON_GIT_HEAD_SHA = "0" * 40

REPORT_DEPENDENCY_SPECS: dict[str, dict[str, Any]] = {
    "workflow_governance": {
        "path": "build/sdetkit/workflow-governance-report.json",
        "schema_version": workflow_governance_report.SCHEMA_VERSION,
        "surfaces": ("workflow",),
    },
    "remediation_readiness": {
        "path": "build/sdetkit/remediation-readiness-report.json",
        "schema_version": remediation_readiness_report.SCHEMA_VERSION,
        "surfaces": ("remediation",),
    },
    "public_command_surface": {
        "path": "build/sdetkit/public-command-surface-report.json",
        "schema_version": public_command_surface_report.SCHEMA_VERSION,
        "surfaces": ("docs", "packaging"),
    },
    "adoption_learning": {
        "path": "build/sdetkit/adoption-learning-report.json",
        "schema_version": adoption_learning_report.SCHEMA_VERSION,
        "surfaces": ("adoption", "learning"),
    },
    "release_anti_hijack": {
        "path": "build/sdetkit/release-anti-hijack-threat-model.json",
        "schema_version": release_anti_hijack_threat_model.SCHEMA_VERSION,
        "surfaces": ("security_release",),
    },
    "automation_health": {
        "path": automation_health.DEFAULT_OUT,
        "schema_version": automation_health.SCHEMA_VERSION,
        "surfaces": ("diagnosis",),
    },
    "maintenance_queue_rollup": {
        "path": maintenance_queue_rollup.DEFAULT_OUT,
        "schema_version": maintenance_queue_rollup.SCHEMA_VERSION,
        "surfaces": ("evidence", "diagnosis"),
    },
}

SURFACE_REPORT_DEPENDENCIES: dict[str, tuple[str, ...]] = {
    surface: tuple(
        dependency_id
        for dependency_id, spec in REPORT_DEPENDENCY_SPECS.items()
        if surface in spec["surfaces"]
    )
    for surface in (
        "evidence",
        "diagnosis",
        "adoption",
        "workflow",
        "docs",
        "security_release",
        "packaging",
        "learning",
        "remediation",
    )
}

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
    candidates[0].update(
        {
            "blocked_by": "human_review_evidence_required",
            "blocker_source_report": "sdetkit.workflow_governance_report",
            "blocker_playbook": "docs/ci/workflow-permission-review-playbook.md",
            "next_allowed_action": "collect_human_review_evidence",
            "required_evidence": [
                "workflow path",
                "current granted write scopes",
                "inferred permission reasons from the report",
                "exact scope proposed for removal, if any",
                "exact proof command",
                "rollback plan",
                "reviewer decision",
            ],
            "blocked_actions": [
                "automatic_permission_reduction",
                "broad_workflow_permission_sweep",
                "security_alert_dismissal",
                "merge_authorization",
                "semantic_equivalence_claim",
            ],
        }
    )

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


def _actionability_summary(ranked: Sequence[dict[str, Any]]) -> dict[str, Any]:
    status_counts = Counter(str(item.get("ranking_status") or "unknown") for item in ranked)
    patch_ready = [
        item
        for item in ranked
        if item.get("accepted_on_main") is not True
        and item.get("safe_to_patch") is True
        and item.get("ranking_status") != "blocked_review_first_candidate"
    ]
    blocked = [
        item for item in ranked if item.get("ranking_status") == "blocked_review_first_candidate"
    ]

    if patch_ready:
        next_allowed_action = "review_patch_ready_candidate"
        status = "patch_ready_candidate_available"
    elif blocked:
        next_allowed_action = str(
            blocked[0].get("next_allowed_action") or "collect_human_review_evidence"
        )
        status = "blocked_review_first_candidate"
    elif ranked:
        next_allowed_action = "review_accepted_candidate_history"
        status = "no_unaccepted_patch_ready_candidates"
    else:
        next_allowed_action = "none"
        status = "no_candidates"

    return {
        "status": status,
        "candidate_count": len(ranked),
        "patch_ready_candidate_count": len(patch_ready),
        "blocked_review_first_candidate_count": len(blocked),
        "accepted_on_main_candidate_count": status_counts.get("accepted_on_main", 0),
        "ranking_status_counts": dict(sorted(status_counts.items())),
        "has_patch_ready_candidate": bool(patch_ready),
        "next_allowed_action": next_allowed_action,
        "review_first": True,
        "safe_to_patch": False,
        "automation_allowed": False,
        "patch_application_allowed": False,
        "merge_authorized": False,
        "semantic_equivalence_proven": False,
    }


def _operator_summary(ranked: Sequence[dict[str, Any]]) -> dict[str, Any]:
    if not ranked:
        return {
            "status": "product_maturity_radar_generated",
            "next_action": "No product maturity candidates found.",
        }

    top = ranked[0]
    summary = {
        "status": "product_maturity_radar_generated",
        "top_candidate": str(top.get("upgrade_candidate_title") or ""),
        "top_candidate_classification": str(top.get("classification") or ""),
        "top_candidate_ranking_status": str(top.get("ranking_status") or "fresh_candidate"),
    }

    if top.get("ranking_status") == "blocked_review_first_candidate":
        summary["next_action"] = str(
            top.get("next_allowed_action") or "collect_human_review_evidence"
        )
        summary["blocked_by"] = str(top.get("blocked_by") or "human_review_evidence_required")
        if top.get("blocker_source_report"):
            summary["blocker_source_report"] = str(top["blocker_source_report"])
        if top.get("blocker_playbook"):
            summary["blocker_playbook"] = str(top["blocker_playbook"])
        return summary

    summary["next_action"] = str(
        top.get("upgrade_candidate_title") or "Review ranked product maturity candidates."
    )
    return summary


def _resolve_radar_head(
    root: Path,
    *,
    current_head_sha: str | None = None,
) -> tuple[str, str]:
    if current_head_sha is not None:
        return resolve_current_head(root, override=current_head_sha), "verified"
    try:
        return resolve_current_head(root), "verified"
    except (OSError, subprocess.CalledProcessError, ValueError):
        return NON_GIT_HEAD_SHA, "unavailable"


def _parse_report_overrides(values: Sequence[str]) -> dict[str, str]:
    overrides: dict[str, str] = {}
    for value in values:
        dependency_id, separator, raw_path = value.partition("=")
        dependency_id = dependency_id.strip()
        raw_path = raw_path.strip()
        if not separator or not dependency_id or not raw_path:
            raise ValueError("--report-json values must use <dependency-id>=<path>")
        if dependency_id not in REPORT_DEPENDENCY_SPECS:
            supported = ", ".join(sorted(REPORT_DEPENDENCY_SPECS))
            raise ValueError(f"unknown report dependency {dependency_id!r}; supported: {supported}")
        overrides[dependency_id] = raw_path
    return overrides


def _resolve_report_paths(
    root: Path,
    report_json: Sequence[str],
) -> dict[str, Path]:
    overrides = _parse_report_overrides(report_json)
    resolved: dict[str, Path] = {}
    for dependency_id, spec in REPORT_DEPENDENCY_SPECS.items():
        raw = overrides.get(dependency_id, str(spec["path"]))
        path = Path(raw)
        resolved[dependency_id] = path if path.is_absolute() else root / path
    return resolved


def _load_dependency_payload(path: Path) -> tuple[dict[str, Any] | None, str]:
    if not path.is_file():
        return None, "missing"
    try:
        loaded = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None, "invalid_json"
    if not isinstance(loaded, dict):
        return None, "invalid_type"
    return loaded, "loaded"


def _dependency_record(
    *,
    dependency_id: str,
    path: Path,
    expected_schema: str,
    current_head_sha: str,
) -> tuple[dict[str, Any], dict[str, Any] | None]:
    payload, load_status = _load_dependency_payload(path)
    record: dict[str, Any] = {
        "id": dependency_id,
        "path": path.as_posix(),
        "expected_schema_version": expected_schema,
        "observed_schema_version": "",
        "status": "missing",
        "reasons": [],
        "current_head_sha": "",
        "input_digest": "",
        "reporting_only": True,
        "automation_allowed": False,
        "patch_application_allowed": False,
        "security_dismissal_allowed": False,
        "merge_authorized": False,
        "semantic_equivalence_proven": False,
    }

    if load_status == "missing":
        record["reasons"] = ["dependency_report_missing"]
        return record, None
    if load_status != "loaded" or payload is None:
        record["status"] = "invalid"
        record["reasons"] = [f"dependency_report_{load_status}"]
        return record, None

    observed_schema = str(payload.get("schema_version") or "")
    record["observed_schema_version"] = observed_schema
    provenance = payload.get("input_provenance")
    provenance = provenance if isinstance(provenance, dict) else {}
    observed_head = str(
        payload.get("current_head_sha") or provenance.get("generated_from_head_sha") or ""
    )
    input_digest = str(provenance.get("input_digest") or "")
    record["current_head_sha"] = observed_head
    record["input_digest"] = input_digest

    invalid_reasons: list[str] = []
    stale_reasons: list[str] = []
    if observed_schema != expected_schema:
        invalid_reasons.append("dependency_schema_version_mismatch")
    if any(
        payload.get(field) is True
        for field in (
            "automation_allowed",
            "patch_application_allowed",
            "security_dismissal_allowed",
            "merge_authorized",
            "semantic_equivalence_proven",
        )
    ):
        invalid_reasons.append("dependency_authority_expansion")
    if not provenance:
        stale_reasons.append("dependency_input_provenance_missing")
    if observed_head != current_head_sha:
        stale_reasons.append("dependency_head_mismatch")
    if re.fullmatch(r"[0-9a-f]{64}", input_digest) is None:
        stale_reasons.append("dependency_input_digest_invalid")
    if provenance.get("generator_schema_version") != expected_schema:
        stale_reasons.append("dependency_generator_schema_mismatch")

    reasons = sorted(set([*invalid_reasons, *stale_reasons]))
    record["reasons"] = reasons
    if invalid_reasons:
        record["status"] = "invalid"
    elif stale_reasons:
        record["status"] = "stale"
    else:
        record["status"] = "fresh"
    return record, payload


def _evaluate_report_dependencies(
    root: Path,
    *,
    report_json: Sequence[str],
    current_head_sha: str,
) -> tuple[list[dict[str, Any]], dict[str, dict[str, Any]], dict[str, Path]]:
    paths = _resolve_report_paths(root, report_json)
    records: list[dict[str, Any]] = []
    payloads: dict[str, dict[str, Any]] = {}
    for dependency_id, spec in REPORT_DEPENDENCY_SPECS.items():
        record, payload = _dependency_record(
            dependency_id=dependency_id,
            path=paths[dependency_id],
            expected_schema=str(spec["schema_version"]),
            current_head_sha=current_head_sha,
        )
        records.append(record)
        if payload is not None:
            payloads[dependency_id] = payload
    return records, payloads, paths


def _dependency_summary(records: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    counts = Counter(str(record.get("status") or "unknown") for record in records)
    invalid_count = counts.get("invalid", 0) + counts.get("stale", 0)
    missing_count = counts.get("missing", 0)
    if invalid_count:
        projection_status = "invalid"
    elif missing_count:
        projection_status = "partial"
    else:
        projection_status = "current"
    return {
        "projection_status": projection_status,
        "dependency_count": len(records),
        "fresh_dependency_count": counts.get("fresh", 0),
        "missing_dependency_count": missing_count,
        "stale_dependency_count": counts.get("stale", 0),
        "invalid_dependency_count": counts.get("invalid", 0),
        "status_counts": dict(sorted(counts.items())),
        "valid_for_projection": invalid_count == 0,
        "complete_projection": projection_status == "current",
        "reporting_only": True,
        "automation_allowed": False,
        "patch_application_allowed": False,
        "security_dismissal_allowed": False,
        "merge_authorized": False,
        "semantic_equivalence_proven": False,
    }


def _claim_source(record: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "report_id": str(record.get("id") or ""),
        "path": str(record.get("path") or ""),
        "status": str(record.get("status") or "missing"),
        "schema_version": str(record.get("observed_schema_version") or ""),
        "expected_schema_version": str(record.get("expected_schema_version") or ""),
        "current_head_sha": str(record.get("current_head_sha") or ""),
        "input_digest": str(record.get("input_digest") or ""),
        "reporting_only": True,
        "source_authority": False,
    }


def _attach_claim_sources(
    surfaces: Sequence[dict[str, Any]],
    records: Sequence[dict[str, Any]],
) -> tuple[list[dict[str, Any]], dict[str, list[dict[str, Any]]]]:
    by_id = {str(record["id"]): record for record in records}
    claim_sources: dict[str, list[dict[str, Any]]] = {}
    enriched: list[dict[str, Any]] = []
    for surface in surfaces:
        surface_name = str(surface["name"])
        sources = [
            _claim_source(by_id[dependency_id])
            for dependency_id in SURFACE_REPORT_DEPENDENCIES.get(surface_name, ())
        ]
        claim_sources[surface_name] = sources
        candidates = [
            {**candidate, "claim_sources": list(sources)}
            for candidate in surface["upgrade_candidates"]
        ]
        enriched.append(
            {
                **surface,
                "claim_sources": list(sources),
                "upgrade_candidates": candidates,
            }
        )
    return enriched, claim_sources


def _repository_snapshot_bytes(
    root: Path,
    *,
    exclude_paths: Sequence[str | Path] = (),
) -> bytes:
    excluded = {
        (Path(path) if Path(path).is_absolute() else root / Path(path)).resolve()
        for path in exclude_paths
    }
    manifest = [
        {
            "path": _rel(root, path),
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        }
        for path in _iter_files(root)
        if path.resolve() not in excluded
    ]
    return json.dumps(
        manifest,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def product_maturity_radar_input_provenance(
    *,
    repo_root: str | Path = ".",
    report_json: Sequence[str] = (),
    exclude_paths: Sequence[str | Path] = (),
    generator_path: str | Path | None = None,
    current_head_sha: str | None = None,
    generated_at: str | None = None,
) -> tuple[
    dict[str, Any],
    list[dict[str, Any]],
    dict[str, dict[str, Any]],
    str,
    str,
]:
    root = Path(repo_root).resolve()
    head, head_status = _resolve_radar_head(
        root,
        current_head_sha=current_head_sha,
    )
    records, payloads, paths = _evaluate_report_dependencies(
        root,
        report_json=report_json,
        current_head_sha=head,
    )
    generator = (
        Path(generator_path).resolve() if generator_path is not None else Path(__file__).resolve()
    )
    data_inputs: dict[str, bytes] = {
        "repository_snapshot": _repository_snapshot_bytes(
            root,
            exclude_paths=exclude_paths,
        ),
    }
    for dependency_id, path in sorted(paths.items()):
        data_inputs[f"dependency:{dependency_id}"] = (
            path.read_bytes() if path.is_file() else b"<missing>"
        )

    source_issue_numbers: list[object] = []
    for payload in payloads.values():
        raw = payload.get("source_issue_numbers", [])
        if isinstance(raw, list):
            source_issue_numbers.extend(raw)

    artifact_schemas = {
        dependency_id: str(
            next(
                record["observed_schema_version"] or record["status"]
                for record in records
                if record["id"] == dependency_id
            )
        )
        for dependency_id in sorted(REPORT_DEPENDENCY_SPECS)
    }

    provenance = build_input_provenance(
        schema_version=SCHEMA_VERSION,
        generator_source=GENERATOR_SOURCE,
        generator_bytes=generator.read_bytes(),
        data_inputs=data_inputs,
        root=root,
        source_issue_numbers=normalize_int_ids(source_issue_numbers),
        source_run_ids=collect_source_run_ids(payloads=tuple(payloads.values())),
        input_artifact_schemas=artifact_schemas,
        current_head_sha=head,
        generated_at=generated_at,
    )
    return provenance, records, payloads, head, head_status


def check_product_maturity_radar_freshness(
    *,
    repo_root: str | Path = ".",
    report_path: str | Path = DEFAULT_OUT,
    markdown_path: str | Path | None = None,
    report_json: Sequence[str] = (),
    generator_path: str | Path | None = None,
    current_head_sha: str | None = None,
) -> dict[str, Any]:
    report = Path(report_path)
    markdown = Path(markdown_path) if markdown_path is not None else report.with_suffix(".md")
    provenance, records, _, _, head_status = product_maturity_radar_input_provenance(
        repo_root=repo_root,
        report_json=report_json,
        exclude_paths=(report, markdown),
        generator_path=generator_path,
        current_head_sha=current_head_sha,
    )
    result = check_report_path(
        report,
        provenance,
        expected_schema_version=SCHEMA_VERSION,
    )
    current_summary = _dependency_summary(records)
    result["projection_status"] = current_summary["projection_status"]
    result["dependency_status"] = current_summary
    result["head_binding_status"] = head_status

    if report.is_file():
        try:
            loaded = json.loads(report.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            loaded = {}
        if isinstance(loaded, dict):
            if loaded.get("dependency_status") != current_summary:
                result["reasons"] = sorted(set([*result["reasons"], "dependency_status_mismatch"]))
            if loaded.get("projection_status") != current_summary["projection_status"]:
                result["reasons"] = sorted(set([*result["reasons"], "projection_status_mismatch"]))

    if current_summary["projection_status"] == "invalid":
        result["reasons"] = sorted(set([*result["reasons"], "stale_or_invalid_dependency"]))

    if result["reasons"]:
        result["status"] = "stale"
        result["fresh"] = False
    return result


def build_product_maturity_radar(
    repo_root: str | Path = ".",
    *,
    report_json: Sequence[str] = (),
    exclude_paths: Sequence[str | Path] = (),
    generated_at: str | None = None,
    current_head_sha: str | None = None,
) -> dict[str, Any]:
    root = Path(repo_root).resolve()
    text_index = _repo_text_index(root)
    provenance, dependency_records, _, _, head_status = product_maturity_radar_input_provenance(
        repo_root=root,
        report_json=report_json,
        exclude_paths=exclude_paths,
        current_head_sha=current_head_sha,
        generated_at=generated_at,
    )
    dependency_status = _dependency_summary(dependency_records)

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
    surfaces, claim_sources = _attach_claim_sources(
        surfaces,
        dependency_records,
    )
    ranked = _rank_candidates(surfaces, root)
    status_counts = Counter(str(surface["status"]) for surface in surfaces)
    total_score = sum(int(surface["score"]) for surface in surfaces)
    total_max_score = sum(int(surface["max_score"]) for surface in surfaces)

    if dependency_status["projection_status"] == "invalid":
        report_status = "invalid_dependency"
    else:
        report_status = "review_required" if ranked else "passed"

    payload = {
        "schema_version": SCHEMA_VERSION,
        "report_status": report_status,
        "projection_status": dependency_status["projection_status"],
        "projection_only": True,
        "source_authority": False,
        "head_binding_status": head_status,
        "repo_root": root.as_posix(),
        "surface_count": len(surfaces),
        "candidate_count": len(ranked),
        "total_score": total_score,
        "total_max_score": total_max_score,
        "status_counts": dict(sorted(status_counts.items())),
        "surfaces": surfaces,
        "ranked_upgrade_candidates": ranked,
        "claim_sources": claim_sources,
        "report_dependencies": dependency_records,
        "dependency_status": dependency_status,
        "actionability_summary": _actionability_summary(ranked),
        "operator_summary": _operator_summary(ranked),
        "rules": {
            "advisory_only": True,
            "projection_only": True,
            "source_reports_authoritative": False,
            "repo_mutation": False,
            "workflow_mutation": False,
            "target_repo_mutation": False,
            "review_first": True,
        },
        "automation_allowed": False,
        "patch_application_allowed": False,
        "security_dismissal_allowed": False,
        "merge_authorized": False,
        "semantic_equivalence_proven": False,
        "authority_boundary": _authority_boundary(),
    }
    return attach_provenance(payload, provenance)


def render_product_maturity_radar_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# SDETKit product maturity radar",
        "",
        f"- report_status: {payload['report_status']}",
        f"- projection_status: {payload.get('projection_status', 'unknown')}",
        f"- current_head_sha: {payload.get('current_head_sha', '')}",
        f"- generated_at: {payload.get('generated_at', '')}",
        f"- surface_count: {payload['surface_count']}",
        f"- candidate_count: {payload['candidate_count']}",
        f"- total_score: {payload['total_score']}/{payload['total_max_score']}",
        "- projection_only: true",
        "- source_authority: false",
        "- advisory_only: true",
        "- repo_mutation: false",
        "- review_first: true",
        "",
        "## Dependency status",
        "",
        f"- status: `{payload.get('dependency_status', {}).get('projection_status', 'unknown')}`",
        f"- fresh_dependency_count: `{payload.get('dependency_status', {}).get('fresh_dependency_count', 0)}`",
        f"- missing_dependency_count: `{payload.get('dependency_status', {}).get('missing_dependency_count', 0)}`",
        f"- stale_dependency_count: `{payload.get('dependency_status', {}).get('stale_dependency_count', 0)}`",
        f"- invalid_dependency_count: `{payload.get('dependency_status', {}).get('invalid_dependency_count', 0)}`",
        "",
        "| Report dependency | Status | Schema | Head |",
        "| --- | --- | --- | --- |",
    ]

    for dependency in payload.get("report_dependencies", []):
        lines.append(
            "| {id} | `{status}` | `{schema}` | `{head}` |".format(
                id=dependency.get("id", ""),
                status=dependency.get("status", ""),
                schema=dependency.get("observed_schema_version", ""),
                head=dependency.get("current_head_sha", ""),
            )
        )

    lines.extend(
        [
            "",
            "## Actionability summary",
            "",
            f"- status: `{payload['actionability_summary']['status']}`",
            f"- patch_ready_candidate_count: `{payload['actionability_summary']['patch_ready_candidate_count']}`",
            f"- blocked_review_first_candidate_count: `{payload['actionability_summary']['blocked_review_first_candidate_count']}`",
            f"- accepted_on_main_candidate_count: `{payload['actionability_summary']['accepted_on_main_candidate_count']}`",
            f"- next_allowed_action: `{payload['actionability_summary']['next_allowed_action']}`",
            "- safe_to_patch: false",
            "",
            "## Surfaces",
            "",
            "| Surface | Status | Score | Candidates | Claim sources |",
            "| --- | --- | ---: | ---: | --- |",
        ]
    )

    for surface in payload["surfaces"]:
        source_text = ", ".join(
            f"{source['report_id']}:{source['status']}"
            for source in surface.get("claim_sources", [])
        )
        lines.append(
            "| {title} | `{status}` | {score}/{max_score} | {candidate_count} | {sources} |".format(
                title=surface["title"],
                status=surface["status"],
                score=surface["score"],
                max_score=surface["max_score"],
                candidate_count=surface["candidate_count"],
                sources=source_text or "none",
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
            for source in candidate.get("claim_sources", []):
                lines.append(
                    f"   - claim_source: `{source.get('report_id')}:{source.get('status')}`"
                )
            if candidate.get("ranking_status") == "blocked_review_first_candidate":
                lines.append(
                    f"   - blocked_by: `{candidate.get('blocked_by', 'human_review_evidence_required')}`"
                )
                if candidate.get("next_allowed_action"):
                    lines.append(f"   - next_allowed_action: `{candidate['next_allowed_action']}`")
                if candidate.get("blocker_source_report"):
                    lines.append(
                        f"   - blocker_source_report: `{candidate['blocker_source_report']}`"
                    )
                if candidate.get("blocker_playbook"):
                    lines.append(f"   - blocker_playbook: `{candidate['blocker_playbook']}`")
            lines.append("   - review_first: true")
            lines.append("   - safe_to_patch: false")

    lines.extend(
        [
            "",
            "## Authority boundary",
            "",
            "- automation_allowed: false",
            "- patch_application_allowed: false",
            "- security_dismissal_allowed: false",
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
    report_json: Sequence[str] = (),
    generated_at: str | None = None,
    current_head_sha: str | None = None,
) -> dict[str, Any]:
    out_path = Path(out)
    markdown_path = Path(markdown_out) if markdown_out is not None else out_path.with_suffix(".md")
    payload = build_product_maturity_radar(
        repo_root=repo_root,
        report_json=report_json,
        exclude_paths=(out_path, markdown_path),
        generated_at=generated_at,
        current_head_sha=current_head_sha,
    )

    out_path.parent.mkdir(parents=True, exist_ok=True)
    markdown_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    markdown_path.write_text(
        render_product_maturity_radar_markdown(payload) + "\n",
        encoding="utf-8",
    )
    return payload


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="sdetkit product-maturity-radar",
        description="Build a report-backed advisory product maturity projection.",
    )
    parser.add_argument("--root", default=".")
    parser.add_argument("--out", default=DEFAULT_OUT)
    parser.add_argument("--markdown-out", default="")
    parser.add_argument(
        "--report-json",
        action="append",
        default=[],
        metavar="DEPENDENCY=PATH",
        help="Override a known report dependency path; repeatable.",
    )
    parser.add_argument("--format", choices=["json", "text"], default="json")
    parser.add_argument(
        "--check-freshness",
        action="store_true",
        help="Check the existing radar against current repository and report inputs.",
    )
    ns = parser.parse_args(list(argv) if argv is not None else None)

    if ns.check_freshness:
        freshness = check_product_maturity_radar_freshness(
            repo_root=ns.root,
            report_path=ns.out,
            markdown_path=ns.markdown_out or None,
            report_json=ns.report_json,
        )
        if ns.format == "json":
            sys.stdout.write(json.dumps(freshness, indent=2, sort_keys=True) + "\n")
        else:
            sys.stdout.write(render_freshness_text(freshness) + "\n")
            sys.stdout.write(f"projection_status={freshness.get('projection_status', 'unknown')}\n")
        return 0 if freshness["fresh"] else 1

    payload = write_product_maturity_radar(
        repo_root=ns.root,
        out=ns.out,
        markdown_out=ns.markdown_out or None,
        report_json=ns.report_json,
    )

    if ns.format == "json":
        sys.stdout.write(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    else:
        sys.stdout.write(render_product_maturity_radar_markdown(payload) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
