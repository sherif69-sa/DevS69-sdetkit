from __future__ import annotations

import json
from pathlib import Path

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover - Python 3.10 compatibility
    import tomli as tomllib

ROOT = Path(__file__).resolve().parents[1]
DELTA_PATH = ROOT / "docs" / "contracts" / "current-product-delta.v1.json"


def _delta() -> dict[str, object]:
    payload = json.loads(DELTA_PATH.read_text(encoding="utf-8"))
    assert isinstance(payload, dict)
    return payload


def test_current_product_delta_matches_published_project_version() -> None:
    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    project = pyproject["project"]
    delta = _delta()

    assert delta["released_version"] == project["version"]
    assert delta["release_status"] == "main_ahead_of_published_package"
    assert delta["release_candidate_version"] != delta["released_version"]


def test_current_product_delta_preserves_review_first_authority() -> None:
    authority = _delta()["authority_boundary"]

    assert authority == {
        "automation_allowed": False,
        "patch_application_allowed": False,
        "merge_authorized": False,
        "semantic_equivalence_proven": False,
    }


def test_current_product_delta_declares_main_only_groups_and_release_blockers() -> None:
    delta = _delta()
    groups = delta["main_only_capability_groups"]
    blockers = delta["release_blockers"]

    assert isinstance(groups, list)
    assert all(isinstance(group, dict) for group in groups)
    assert {group["id"] for group in groups} == {
        "diagnostic_failure_model",
        "verification_and_benchmarking",
        "trajectory_and_memory",
        "external_adoption_intelligence",
    }
    assert all(group["capabilities"] for group in groups)
    assert isinstance(blockers, list)
    assert len(blockers) >= 5


def test_readme_links_release_delta_and_avoids_unqualified_main_claims() -> None:
    readme = (ROOT / "README.md").read_text(encoding="utf-8")

    assert "docs/current-product-delta.md" in readme
    assert "main-only" in readme
    assert "sdetkit==1.0.3" in readme
