from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "dependency-auto-merge.yml"


def test_dependency_auto_merge_helper_is_best_effort() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")

    action = (
        "uses: peter-evans/enable-pull-request-automerge@a660677d5469627102a1c1e11409dd063606628d"
    )

    assert action in text
    assert "continue-on-error: true" in text
    assert "repository auto-merge may be disabled" in text


def test_auto_merge_is_limited_to_dependabot_and_small_updates() -> None:
    import yaml

    workflow = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
    job = workflow["jobs"]["auto-merge"]
    assert "github.event.pull_request.user.login == 'dependabot[bot]'" in job["if"]
    assert "github.actor == github.repository_owner" in job["if"]
    step = next(s for s in job["steps"] if s.get("name") == "Enable auto-merge for safe updates")
    assert "semver-patch" in step["if"] and "semver-minor" in step["if"]
    assert "semver-major" not in step["if"]


def test_dependabot_groups_exclude_major_updates() -> None:
    import yaml

    config = yaml.safe_load((ROOT / ".github/dependabot.yml").read_text(encoding="utf-8"))
    for update in config["updates"]:
        for group in update["groups"].values():
            assert set(group["update-types"]) == {"minor", "patch"}
