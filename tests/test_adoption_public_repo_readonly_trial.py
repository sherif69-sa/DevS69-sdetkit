from __future__ import annotations

import json
from pathlib import Path

from sdetkit.adoption_learning import build_adoption_learning_payload

TRIAL_PATH = Path("tests/fixtures/adoption_public_trials/pallets_markupsafe_readonly_trial.json")


def test_first_public_readonly_trial_record_is_safe_and_non_vendored() -> None:
    payload = json.loads(TRIAL_PATH.read_text(encoding="utf-8"))

    assert payload["schema_version"] == "sdetkit.public_repo_readonly_trial.v1"
    assert payload["repo_full_name"] == "pallets/markupsafe"
    assert payload["license_id"] == "BSD-3-Clause"
    assert payload["eligibility_allowed_for_read_only_trial"] is True
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


def test_first_public_readonly_trial_fixture_contains_no_source_tree() -> None:
    fixture_root = TRIAL_PATH.parent
    files = sorted(
        path.relative_to(fixture_root).as_posix()
        for path in fixture_root.rglob("*")
        if path.is_file()
    )

    assert "pallets_markupsafe_readonly_trial.json" in files
    assert all(file_name.endswith(".json") for file_name in files)
    assert all(not file_name.endswith(".py") for file_name in files)


def test_self_learning_advances_after_first_public_readonly_trial() -> None:
    payload = build_adoption_learning_payload(Path("."))

    assert payload["recommended_next_upgrade"] == "public repo trial matrix report"
    assert "run first permissive public repo read-only trial" not in payload["learning_gaps"]
    assert "add proof command recommendation levels" not in payload["learning_gaps"]
    assert "add repo topology summary" not in payload["learning_gaps"]
    assert "add adoption evidence bundle" not in payload["learning_gaps"]
    assert "add public repo trial matrix" not in payload["learning_gaps"]
    assert "add public repo trial matrix report" in payload["learning_gaps"]
    assert payload["authority_boundary"]["automation_allowed"] is False
    assert payload["authority_boundary"]["patch_application_allowed"] is False
