from __future__ import annotations

import json
from pathlib import Path

from sdetkit.adoption_learning import build_adoption_learning_payload

MATRIX_PATH = Path("tests/fixtures/adoption_public_trials/public_repo_trial_matrix.json")


def _matrix() -> dict:
    return json.loads(MATRIX_PATH.read_text(encoding="utf-8"))


def test_public_repo_trial_matrix_records_safe_readonly_boundaries() -> None:
    payload = _matrix()

    assert payload["schema_version"] == "sdetkit.public_repo_trial_matrix.v1"
    assert payload["trial_mode"] == "manual_read_only_public_repo_matrix"
    assert payload["source_code_vendored"] is False
    assert payload["dependency_install_performed"] is False
    assert payload["target_tests_executed"] is False
    assert payload["target_repo_mutated"] is False
    assert payload["target_pr_or_issue_opened"] is False
    assert payload["endorsement_claimed"] is False
    assert payload["authority_boundary"] == {
        "automation_allowed": False,
        "patch_application_allowed": False,
        "merge_authorized": False,
        "semantic_equivalence_proven": False,
    }


def test_public_repo_trial_matrix_contains_expected_permissive_candidates() -> None:
    payload = _matrix()
    trials = {trial["repo_full_name"]: trial for trial in payload["trials"]}

    assert set(trials) == {
        "pallets/markupsafe",
        "pallets/click",
        "pallets/itsdangerous",
    }

    for trial in trials.values():
        assert trial["repo_url"].startswith("https://github.com/pallets/")
        assert trial["license_id"] == "BSD-3-Clause"
        assert trial["expected_primary_language"] == "python"
        assert trial["eligibility_allowed_for_read_only_trial"] is True

    assert trials["pallets/markupsafe"]["prior_single_repo_trial"] is True
    assert trials["pallets/click"]["prior_single_repo_trial"] is False
    assert trials["pallets/itsdangerous"]["prior_single_repo_trial"] is False


def test_public_repo_trial_matrix_fixture_contains_no_source_tree() -> None:
    fixture_root = MATRIX_PATH.parent
    files = sorted(
        path.relative_to(fixture_root).as_posix()
        for path in fixture_root.rglob("*")
        if path.is_file()
    )

    assert "public_repo_trial_matrix.json" in files
    assert "pallets_markupsafe_readonly_trial.json" in files
    assert all(not file_name.endswith(".py") for file_name in files)


def test_self_learning_advances_after_public_repo_trial_matrix_exists() -> None:
    payload = build_adoption_learning_payload(Path("."))

    assert payload["recommended_next_upgrade"] == "public repo trial matrix report"
    assert "add public repo trial matrix" not in payload["learning_gaps"]
    assert "add public repo trial matrix report" in payload["learning_gaps"]
    assert payload["authority_boundary"]["automation_allowed"] is False
    assert payload["authority_boundary"]["patch_application_allowed"] is False
