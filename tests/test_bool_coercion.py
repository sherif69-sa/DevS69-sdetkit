from __future__ import annotations

import json
from pathlib import Path

import pytest

from sdetkit.bools import coerce_bool
from sdetkit.gate import _format_text as format_gate_text
from sdetkit.integration import _evaluate
from sdetkit.ops import run_workflow
from sdetkit.premium_gate_engine import AutoFixResult, _build_script_candidates


@pytest.mark.parametrize(
    ("value", "default", "expected"),
    [
        ("true", False, True),
        ("t", False, True),
        ("y", False, True),
        ("ok", False, True),
        ("passed", False, True),
        ("2", False, True),
        ("2.5", False, True),
        ("active", False, True),
        ("false", True, False),
        ("f", True, False),
        ("n", True, False),
        ("failed", True, False),
        ("error", True, False),
        ("null", True, False),
        ("0.0", True, False),
        ("inactive", True, False),
        ("", True, False),
        ("not-a-bool", False, False),
        ("not-a-bool", True, True),
    ],
)
def test_coerce_bool_handles_string_flags(value: object, default: bool, expected: bool) -> None:
    assert coerce_bool(value, default=default) is expected


def test_ops_policy_string_false_does_not_enable_shell(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    wf = Path("workflow.json")
    wf.write_text(
        json.dumps(
            {
                "workflow": {
                    "name": "bool-policy",
                    "version": "1",
                    "policy": {"allow_shell": "false"},
                    "steps": [
                        {
                            "id": "cmd",
                            "type": "command",
                            "inputs": {"cmd": ["echo", "ok"], "shell": True},
                        }
                    ],
                }
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="policy blocks shell=true"):
        run_workflow(
            wf,
            inputs={},
            artifacts_dir=tmp_path / "artifacts",
            history_dir=tmp_path / "history",
            workers=1,
            dry_run=False,
            fail_fast=False,
        )


def test_script_catalog_false_autofix_flag_is_respected(tmp_path: Path) -> None:
    catalog = tmp_path / "script-catalog.json"
    catalog.write_text(
        json.dumps(
            [
                {
                    "script_id": "noop",
                    "reason": "autofix only",
                    "command": ["echo", "ok"],
                    "trigger_on_autofix": "false",
                }
            ]
        ),
        encoding="utf-8",
    )

    candidates = _build_script_candidates(
        payload={"warnings": [], "checks": []},
        out_dir=tmp_path,
        fix_root=tmp_path,
        auto_fix_results=[AutoFixResult("SEC_1", "a.py", "fixed", "done")],
        script_catalog_path=catalog,
    )

    assert all(item.script_id != "noop" for item in candidates)


def test_integration_required_env_string_false_is_not_treated_as_present(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("FEATURE_READY", "false")
    payload = _evaluate({"required_env": ["FEATURE_READY"], "required_files": [], "services": []})
    assert payload["summary"]["passed"] is False
    assert payload["checks"][0]["passed"] is False


def test_gate_format_respects_string_false() -> None:
    output = format_gate_text({"ok": "false", "steps": [], "failed_steps": []})
    assert "gate fast: FAIL" in output
