from __future__ import annotations

import json
from pathlib import Path

from sdetkit import check_intelligence


def _write_json(path: Path, payload: dict[str, object]) -> Path:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def test_runtime_traceback_reports_exception_owner_and_exact_proof(tmp_path: Path) -> None:
    log = "\n".join(
        [
            "Run if [ \"pull_request\" = \"pull_request\" ]; then",
            "Traceback (most recent call last):",
            "  File \"/home/runner/work/DevS69-sdetkit/DevS69-sdetkit/tools/maintenance_autopilot.py\", line 1429, in <module>",
            "    raise SystemExit(main())",
            "  File \"/home/runner/work/DevS69-sdetkit/DevS69-sdetkit/tools/maintenance_autopilot.py\", line 1173, in main",
            "    raise RuntimeError(\"dry run returned no bot trackers\")",
            "RuntimeError: dry run returned no bot trackers",
            "Error: Process completed with exit code 1.",
        ]
    )
    checks = _write_json(
        tmp_path / "checks.json",
        {
            "checks": [
                {
                    "name": "maintenance-autopilot / autopilot",
                    "status": "completed",
                    "conclusion": "failure",
                    "url": "https://api.github.com/repos/sherif69-sa/DevS69-sdetkit/check-runs/7712696111377128084464",
                    "log": log,
                }
            ]
        },
    )

    intelligence = check_intelligence.build_check_intelligence(checks_json=checks)
    failed = intelligence["failed_checks"][0]
    first_failure = failed["first_failure"]
    traceback = first_failure["traceback"]

    assert first_failure["kind"] == "runtime_failure"
    assert first_failure["tool"] == "python"
    assert first_failure["line"] == "RuntimeError: dry run returned no bot trackers"
    assert traceback["exception_type"] == "RuntimeError"
    assert traceback["exception_message"] == "dry run returned no bot trackers"
    assert traceback["owner_file"] == "tools/maintenance_autopilot.py"
    assert traceback["owner_line"] == 1173
    assert failed["code"] == "PYTHON_RUNTIME_EXCEPTION"
    assert failed["owner_files"] == ["tools/maintenance_autopilot.py"]

    action_report = check_intelligence.build_action_report(intelligence)
    blocker = action_report["primary_blocker"]

    assert action_report["status"] == "review_required"
    assert blocker["code"] == "PYTHON_RUNTIME_EXCEPTION"
    assert blocker["surface"] == "workflow"
    assert blocker["first_failure_line"] == "RuntimeError: dry run returned no bot trackers"
    assert blocker["owner_files"] == ["tools/maintenance_autopilot.py"]
    assert "tools/maintenance_autopilot.py:1173" in blocker["impact"]
    assert any(
        "tools/maintenance_autopilot.py --owner sherif69-sa" in command
        for command in action_report["proof_commands"]
    )


def test_runtime_traceback_markdown_mentions_exact_exception_and_owner(tmp_path: Path) -> None:
    checks = _write_json(
        tmp_path / "checks.json",
        {
            "checks": [
                {
                    "name": "autopilot",
                    "status": "completed",
                    "conclusion": "failure",
                    "log": "\n".join(
                        [
                            "Traceback (most recent call last):",
                            "  File \"/repo/tools/maintenance_autopilot.py\", line 1173, in main",
                            "    raise RuntimeError(\"dry run returned no bot trackers\")",
                            "RuntimeError: dry run returned no bot trackers",
                        ]
                    ),
                }
            ]
        },
    )

    intelligence = check_intelligence.build_check_intelligence(checks_json=checks)
    report = check_intelligence.build_action_report(intelligence)
    markdown = check_intelligence.render_action_report(report)

    assert "Python runtime exception" in markdown
    assert "RuntimeError: dry run returned no bot trackers" in markdown
    assert "tools/maintenance_autopilot.py:1173" in markdown
    assert "PYTHONPATH=src python tools/maintenance_autopilot.py" in markdown
