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
