from __future__ import annotations

import json
from importlib import resources
from pathlib import Path

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover - Python 3.10 compatibility
    import tomli as tomllib

ROOT = Path(__file__).resolve().parents[1]
DOCS_DELTA_PATH = ROOT / "docs" / "contracts" / "current-product-delta.v1.json"


def _delta_text() -> str:
    return (
        resources.files("sdetkit")
        .joinpath("data/current_product_delta.v1.json")
        .read_text(encoding="utf-8")
    )


def _delta() -> dict[str, object]:
    payload = json.loads(_delta_text())
    assert isinstance(payload, dict)
    return payload


def test_current_product_delta_separates_candidate_from_published_version() -> None:
    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    project = pyproject["project"]
    delta = _delta()
    published = delta["published_package_contract"]
    candidate = delta["release_candidate_contract"]

    assert delta["project_version"] == project["version"] == "1.1.0"
    assert delta["release_candidate_version"] == project["version"]
    assert delta["released_version"] == published["version"] == "1.0.3"
    assert delta["release_status"] == "release_candidate_frozen_not_published"
    assert candidate["publication_claimed"] is False
    assert candidate["tag_created"] is False
    assert candidate["public_install_verified"] is False


def test_current_product_delta_preserves_review_first_authority() -> None:
    assert _delta()["authority_boundary"] == {
        "automation_allowed": False,
        "patch_application_allowed": False,
        "merge_authorized": False,
        "semantic_equivalence_proven": False,
    }


def test_current_product_delta_declares_candidate_groups_and_release_blockers() -> None:
    delta = _delta()
    groups = delta["main_only_capability_groups"]
    blockers = delta["release_blockers"]

    assert isinstance(groups, list)
    assert {group["id"] for group in groups} == {
        "diagnostic_failure_model",
        "verification_and_benchmarking",
        "trajectory_and_memory",
        "external_adoption_intelligence",
    }
    assert all(group["capabilities"] for group in groups)
    assert isinstance(blockers, list)
    assert len(blockers) >= 5


def test_docs_and_packaged_delta_match_governing_fields() -> None:
    docs = json.loads(DOCS_DELTA_PATH.read_text(encoding="utf-8"))
    packaged = _delta()

    for field in (
        "schema_version",
        "released_version",
        "project_version",
        "release_candidate_version",
        "release_status",
        "canonical_first_path",
        "published_package_contract",
        "release_candidate_contract",
        "authority_boundary",
    ):
        assert docs[field] == packaged[field]


def test_readme_remains_pinned_to_published_package_until_release() -> None:
    readme = (ROOT / "README.md").read_text(encoding="utf-8")

    assert "docs/current-product-delta.md" in readme
    assert "main-only" in readme
    assert "sdetkit==1.0.3" in readme
    assert "sdetkit==1.1.0" not in readme
