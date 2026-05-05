from pathlib import Path

from sdetkit.maintenance.checks import github_actions_annotation_hygiene_check as check
from sdetkit.maintenance.registry import discover_checks
from sdetkit.maintenance.types import MaintenanceContext

ANNOTATIONS = """submit-pypi
Node.js 20 actions are deprecated. The following actions are running on Node.js 20 and may not work as expected: actions/component-detection-dependency-submission-action@374343effede691df3a5ffaf36b4e7acab919590.
submit-pypi
The `python-version` input is not set. The version of Python currently in `PATH` will be used.
"""


def _ctx(tmp_path: Path, env: dict[str, str] | None = None) -> MaintenanceContext:
    return MaintenanceContext(
        repo_root=tmp_path,
        python_exe="python",
        mode="quick",
        fix=False,
        env=env or {},
        logger=object(),
    )


def test_annotation_hygiene_check_is_discovered():
    names = {name for name, _runner, _modes in discover_checks()}

    assert "github_actions_annotation_hygiene" in names


def test_annotation_hygiene_check_is_ok_when_log_is_not_configured(tmp_path):
    result = check.run(_ctx(tmp_path))

    assert result.ok is True
    assert "not configured" in result.summary
    assert result.details["env_var"] == "SDETKIT_GITHUB_ACTIONS_ANNOTATION_LOG"
    assert result.actions[0].id == "annotation-hygiene-configure"


def test_annotation_hygiene_check_flags_missing_configured_log(tmp_path):
    result = check.run(
        _ctx(tmp_path, {"SDETKIT_GITHUB_ACTIONS_ANNOTATION_LOG": "missing-annotations.txt"})
    )

    assert result.ok is False
    assert "not found" in result.summary
    assert result.details["configured"] is True
    assert result.actions[0].id == "annotation-hygiene-missing-log"


def test_annotation_hygiene_check_reports_warning_findings(tmp_path):
    log_path = tmp_path / "annotations.txt"
    log_path.write_text(ANNOTATIONS, encoding="utf-8")

    result = check.run(_ctx(tmp_path, {"SDETKIT_GITHUB_ACTIONS_ANNOTATION_LOG": "annotations.txt"}))

    assert result.ok is False
    assert "1 warning" in result.summary
    payload = result.details["annotation_hygiene"]
    assert payload["warning_count"] == 1
    assert payload["notice_count"] == 1
    assert any(action.id == "github_actions_node20_deprecation" for action in result.actions)


def test_annotation_hygiene_check_passes_clean_log(tmp_path):
    log_path = tmp_path / "annotations.txt"
    log_path.write_text("all green\n", encoding="utf-8")

    result = check.run(_ctx(tmp_path, {"SDETKIT_GITHUB_ACTIONS_ANNOTATION_LOG": str(log_path)}))

    assert result.ok is True
    assert "0 finding" in result.summary
    assert result.details["annotation_hygiene"]["findings"] == []
