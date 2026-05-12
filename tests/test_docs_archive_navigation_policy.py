from __future__ import annotations

import fnmatch
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"
MKDOCS = ROOT / "mkdocs.yml"
POLICY_DOC = DOCS / "archive-navigation-policy.md"


ARCHIVE_EXAMPLES = (
    "continuous-upgrade-big-upgrade-report-1.md",
    "continuous-upgrade-big-upgrade-report-10.md",
    "enterprise-readiness-audit-2026-04.md",
    "investor-readiness-review-2026-04-18.md",
    "plan-execution-followup-2026-04-23.md",
    "powerfuel-execution-plan-2026-05-03.md",
)

ACTIVE_REFERENCE_EXAMPLES = (
    "archive-navigation-policy.md",
    "docs-nav-cleanup-progress.md",
    "environment-compatibility.md",
    "git-workflow.md",
    "ci-legacy-status-bridge.md",
    "core-command-contract.md",
    "ci-cost-telemetry-contract.md",
)


def _mkdocs_text_for_safe_load() -> str:
    text = MKDOCS.read_text(encoding="utf-8")
    return text.replace(
        "!!python/name:pymdownx.superfences.fence_code_format",
        "pymdownx.superfences.fence_code_format",
    )


def _load_mkdocs() -> dict:
    payload = yaml.safe_load(_mkdocs_text_for_safe_load())
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


def test_archive_navigation_policy_is_in_current_reference_nav() -> None:
    nav_paths = _nav_paths()

    assert "archive-navigation-policy.md" in nav_paths


def test_archive_navigation_policy_doc_is_ascii_text() -> None:
    raw = POLICY_DOC.read_bytes()

    raw.decode("ascii")


def test_archive_navigation_policy_names_required_tiers() -> None:
    text = POLICY_DOC.read_text(encoding="utf-8")

    required = [
        "Tier 1: primary journey docs",
        "Tier 2: current supporting references",
        "Tier 3: archive candidates",
        "Tier 4: generated or intentionally excluded material",
    ]
    missing = [marker for marker in required if marker not in text]

    assert missing == []


def test_archive_navigation_policy_records_promotion_and_archive_rules() -> None:
    text = POLICY_DOC.read_text(encoding="utf-8")

    required = [
        "Promotion rules",
        "Archive rules",
        "Current examples of archive candidates",
        "Active-reference examples",
        "Test expectations",
        "Pull request sizing",
        "at least 260 added lines",
    ]
    missing = [marker for marker in required if marker not in text]

    assert missing == []


def test_archive_examples_exist_and_are_built_docs() -> None:
    built_docs = _built_doc_paths()
    missing = [path for path in ARCHIVE_EXAMPLES if path not in built_docs]

    assert missing == []


def test_archive_examples_are_not_primary_nav_promotions() -> None:
    nav_paths = _nav_paths()
    promoted_archive_examples = [path for path in ARCHIVE_EXAMPLES if path in nav_paths]

    assert promoted_archive_examples == []


def test_policy_doc_classifies_known_archive_examples() -> None:
    text = POLICY_DOC.read_text(encoding="utf-8")

    required_markers = [
        "continuous-upgrade-big-upgrade-report-1.md",
        "powerfuel-execution-plan-2026-05-03.md",
        "investor-readiness-review-2026-04-18.md",
        "enterprise-readiness-audit-2026-04.md",
        "roadmap/artifacts/weekly-pack-*",
    ]
    missing = [marker for marker in required_markers if marker not in text]

    assert missing == []


def test_active_reference_examples_are_explicit_nav_paths() -> None:
    nav_paths = _nav_paths()
    missing = [path for path in ACTIVE_REFERENCE_EXAMPLES if path not in nav_paths]

    assert missing == []


def test_policy_uses_safe_yaml_parsing_contract_language() -> None:
    test_source = Path(__file__).read_text(encoding="utf-8")
    policy_text = POLICY_DOC.read_text(encoding="utf-8")

    assert "yaml.safe_load" in test_source
    forbidden_yaml_load_call = "yaml." + "load("
    assert forbidden_yaml_load_call not in test_source
    assert "tests avoid `yaml.load`" in policy_text


def test_archive_policy_keeps_inventory_warning_as_triage_signal() -> None:
    text = POLICY_DOC.read_text(encoding="utf-8")

    required = [
        "triage signal",
        "not a blanket order",
        "separate archive strategy",
        "not historical reports",
        "not accidentally treated as primary navigation",
    ]
    missing = [marker for marker in required if marker not in text]

    assert missing == []
