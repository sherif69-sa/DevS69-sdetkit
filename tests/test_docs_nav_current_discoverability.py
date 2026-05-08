from __future__ import annotations

import fnmatch
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"
MKDOCS = ROOT / "mkdocs.yml"


CURRENT_NAV_GROUPS = {
    "canonical_first_proof": (
        "day1-proof-starter.md",
        "first-failure-triage.md",
        "first-proof-troubleshooting.md",
        "first-proof-learning-db.md",
        "first-proof-benchmark-narrative.md",
    ),
    "team_adoption": (
        "role-based-quickstarts.md",
        "quickstart-role-platform-engineer.md",
        "quickstart-role-qa-governance.md",
        "quickstart-role-release-owner.md",
        "operator-onboarding-7-day.md",
        "onboarding-optimization.md",
        "adoption-examples.md",
        "adoption-scorecard.md",
        "adoption-troubleshooting.md",
        "adoption-walkthrough-small-team.md",
        "adoption-walkthrough-enterprise.md",
        "example-adoption-flow.md",
        "pilot-to-rollout-guide.md",
        "proof-sprint-checklist.md",
    ),
    "operator_evidence": (
        "adaptive-review.md",
        "doctor-cortex.md",
        "doctor-diagnosis.md",
        "doctor-prescriptions.md",
        "golden-path-health.md",
        "proof-log.md",
    ),
    "current_reference": (
        "docs-nav-cleanup-progress.md",
        "environment-compatibility.md",
        "git-workflow.md",
        "ci-legacy-status-bridge.md",
        "core-command-contract.md",
        "ci-cost-telemetry-contract.md",
        "integrations/github-actions-reference-pack.md",
        "integrations/gitlab-reference-pack.md",
        "integrations/jenkins-reference-pack.md",
        "integrations/rollback-remediation-examples.md",
    ),
}


def _load_mkdocs() -> dict:
    text = MKDOCS.read_text(encoding="utf-8")
    text = text.replace(
        "!!python/name:pymdownx.superfences.fence_code_format",
        "pymdownx.superfences.fence_code_format",
    )
    payload = yaml.safe_load(text)
    assert isinstance(payload, dict)
    return payload


def _walk_nav(node: object) -> list[str]:
    if isinstance(node, str):
        return [node]
    if isinstance(node, list):
        paths: list[str] = []
        for item in node:
            paths.extend(_walk_nav(item))
        return paths
    if isinstance(node, dict):
        paths = []
        for value in node.values():
            paths.extend(_walk_nav(value))
        return paths
    return []


def _nav_paths() -> set[str]:
    config = _load_mkdocs()
    return {
        item
        for item in _walk_nav(config.get("nav", []))
        if isinstance(item, str) and item.endswith(".md")
    }


def _exclude_patterns() -> list[str]:
    config = _load_mkdocs()
    exclude_raw = config.get("exclude_docs", "") or ""
    return [
        line.strip().lstrip("/")
        for line in exclude_raw.splitlines()
        if line.strip() and not line.strip().startswith("!")
    ]


def _is_excluded(path: str, patterns: list[str]) -> bool:
    return any(fnmatch.fnmatch(path, pattern) for pattern in patterns)


def _built_doc_paths() -> set[str]:
    patterns = _exclude_patterns()
    return {
        str(path.relative_to(DOCS))
        for path in DOCS.rglob("*.md")
        if not _is_excluded(str(path.relative_to(DOCS)), patterns)
    }


def _required_current_docs() -> tuple[str, ...]:
    docs: list[str] = []
    for group in CURRENT_NAV_GROUPS.values():
        docs.extend(group)
    return tuple(docs)


def test_current_docs_nav_groups_have_unique_paths() -> None:
    docs = _required_current_docs()

    assert len(docs) == len(set(docs))


def test_current_docs_nav_groups_reference_existing_docs() -> None:
    missing = [doc_path for doc_path in _required_current_docs() if not (DOCS / doc_path).is_file()]

    assert missing == []


def test_current_docs_nav_groups_are_not_excluded_from_mkdocs_build() -> None:
    built_docs = _built_doc_paths()
    excluded_required_docs = [
        doc_path for doc_path in _required_current_docs() if doc_path not in built_docs
    ]

    assert excluded_required_docs == []


def test_current_docs_nav_groups_are_in_mkdocs_nav() -> None:
    nav_paths = _nav_paths()
    missing_from_nav = [
        doc_path for doc_path in _required_current_docs() if doc_path not in nav_paths
    ]

    assert missing_from_nav == []


def test_current_docs_slice_no_longer_contributes_to_mkdocs_nav_inventory() -> None:
    built_docs = _built_doc_paths()
    nav_paths = _nav_paths()
    not_in_nav = built_docs - nav_paths

    current_docs_still_missing = [
        doc_path for doc_path in _required_current_docs() if doc_path in not_in_nav
    ]

    assert current_docs_still_missing == []


def test_docs_nav_cleanup_progress_records_current_slice_policy() -> None:
    progress_doc = DOCS / "docs-nav-cleanup-progress.md"
    text = progress_doc.read_text(encoding="utf-8")

    required_markers = [
        "Current-docs navigation slice",
        "first-proof",
        "team adoption",
        "operator evidence",
        "current reference",
        "not historical reports",
    ]
    missing_markers = [marker for marker in required_markers if marker not in text]

    assert missing_markers == []


def test_nav_inventory_keeps_current_docs_explicit_not_implicit() -> None:
    nav_paths = _nav_paths()

    for group_name, group_docs in CURRENT_NAV_GROUPS.items():
        missing = [doc_path for doc_path in group_docs if doc_path not in nav_paths]
        assert missing == [], f"{group_name} missing nav docs: {missing}"
