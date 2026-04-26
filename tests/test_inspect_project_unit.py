from __future__ import annotations

import json
from pathlib import Path

import pytest

from sdetkit import inspect_project


def test_inspect_project_policy_validation_and_rules(tmp_path: Path) -> None:
    valid = {
        "inputs": {"scopes": [{"name": "scope-a", "include": ["data/*.json"]}]},
        "rules": {"inline": {"files": {}}},
        "compare": {"baseline": "none", "thresholds": {"id_drift_files": 1}},
        "precedence": {"weights": {"compare_threshold": 5}},
        "outputs": {"project_subdir": "proj", "scope_dir": "scopes"},
    }
    assert inspect_project._validate_policy(valid) is None
    assert "unknown policy section" in inspect_project._validate_policy({"bogus": 1})
    assert "inputs.scopes must be a non-empty array" in inspect_project._validate_policy(
        {"inputs": {"scopes": []}}
    )
    assert "compare.baseline" in inspect_project._validate_policy(
        {"inputs": {"scopes": [{"name": "x", "include": ["*.json"]}]}, "compare": {"baseline": "x"}}
    )

    project = tmp_path / "p"
    project.mkdir()
    rules_file = project / "rules.json"
    rules_file.write_text(json.dumps({"files": {"orders.csv": {}}}), encoding="utf-8")

    from_inline = inspect_project._resolve_rules_payload(project, {"rules": {"inline": {"a": 1}}})
    assert from_inline == {"a": 1}
    from_file = inspect_project._resolve_rules_payload(
        project, {"rules": {"rules_file": "rules.json"}}
    )
    assert from_file["files"]["orders.csv"] == {}


def test_inspect_project_materialize_threshold_render_and_main_errors(
    tmp_path: Path, capsys
) -> None:
    project = tmp_path / "project"
    project.mkdir()
    (project / "data").mkdir()
    (project / "data" / "a.csv").write_text("id\n1\n", encoding="utf-8")
    (project / "data" / "b.json").write_text(json.dumps({"x": 1}), encoding="utf-8")
    run_root = tmp_path / "out"

    files, scope_dir = inspect_project._materialize_scope(
        project,
        {
            "name": "Core Data",
            "include": ["data/*.csv", "data/*.json"],
            "_scope_dir_name": "scopes",
        },
        run_root,
    )
    assert len(files) == 2
    assert scope_dir.exists()
    manifest = json.loads((scope_dir / "scope-input-manifest.json").read_text(encoding="utf-8"))
    assert manifest["scope"] == "Core Data"

    failures = inspect_project._threshold_failures({"id_drift_files": 3}, {"id_drift_files": 1})
    assert failures[0]["metric"] == "id_drift_files"

    rendered = inspect_project._render_text(
        {
            "ok": False,
            "project_dir": "/tmp/project",
            "summary": {"scopes": 1, "inspect_fail_scopes": 1, "compare_fail_scopes": 0},
            "findings": [
                {"scope": "core", "kind": "inspect_findings", "priority": 25, "message": "m"}
            ],
            "judgment": {"status": "fail", "severity": "medium", "confidence": {"score": 0.7}},
        }
    )
    assert "SDETKit inspect-project: FAIL" in rendered
    assert "top_findings:" in rendered

    rc = inspect_project.main([str(tmp_path / "missing-project")])
    assert rc == inspect_project.EXIT_FINDINGS
    assert "project_dir does not exist" in capsys.readouterr().err

    empty_project = tmp_path / "empty"
    empty_project.mkdir()
    rc = inspect_project.main([str(empty_project)])
    assert rc == inspect_project.EXIT_FINDINGS
    assert "policy file not found" in capsys.readouterr().err


def test_inspect_project_main_happy_path_and_findings(tmp_path: Path, monkeypatch, capsys) -> None:
    project = tmp_path / "project"
    project.mkdir()
    (project / "data").mkdir()
    (project / "data" / "a.csv").write_text("id\n1\n", encoding="utf-8")
    (project / "inspect-project.json").write_text(
        json.dumps(
            {
                "inputs": {"scopes": [{"name": "core", "include": ["data/*.csv"]}]},
                "rules": {"inline": {"files": {}}},
                "compare": {"baseline": "none"},
            }
        ),
        encoding="utf-8",
    )

    monkeypatch.setattr(
        inspect_project,
        "run_inspect",
        lambda **_kwargs: (
            inspect_project.EXIT_OK,
            {"ok": True, "workspace": {}},
            _kwargs["out_dir"] / "inspect.json",
            _kwargs["out_dir"] / "inspect.txt",
        ),
    )
    monkeypatch.setattr(inspect_project, "build_contradiction_graph", lambda **_k: [])
    monkeypatch.setattr(
        inspect_project,
        "build_judgment",
        lambda **_k: {
            "status": "pass",
            "severity": "none",
            "confidence": {"score": 1.0},
            "contradictions": [],
        },
    )
    monkeypatch.setattr(inspect_project, "investigation_confidence", lambda **_k: 1.0)
    monkeypatch.setattr(
        inspect_project,
        "decide_escalation",
        lambda **_k: type("Esc", (), {"as_dict": lambda self: {"escalate": False}})(),
    )
    monkeypatch.setattr(
        inspect_project,
        "decide_stop",
        lambda **_k: type("Stop", (), {"as_dict": lambda self: {"stop": True}})(),
    )
    monkeypatch.setattr(inspect_project, "rank_likely_issue_tracks", lambda **_k: [])

    rc = inspect_project.main([str(project), "--out-dir", str(tmp_path / "out"), "--no-workspace"])
    assert rc == inspect_project.EXIT_OK
    out_text = capsys.readouterr().out
    assert "inspect-project: PASS" in out_text

    monkeypatch.setattr(
        inspect_project,
        "run_inspect",
        lambda **_kwargs: (
            inspect_project.EXIT_FINDINGS,
            {"ok": False, "workspace": {}},
            _kwargs["out_dir"] / "inspect.json",
            _kwargs["out_dir"] / "inspect.txt",
        ),
    )
    rc = inspect_project.main([str(project), "--out-dir", str(tmp_path / "out2"), "--no-workspace"])
    assert rc == inspect_project.EXIT_FINDINGS


def test_safe_slug_and_load_json_non_object_error(tmp_path: Path) -> None:
    assert inspect_project._safe_slug("@@@").startswith("inspect-project")

    bad = tmp_path / "list.json"
    bad.write_text(json.dumps([1, 2, 3]), encoding="utf-8")
    with pytest.raises(ValueError, match="expected JSON object"):
        inspect_project._load_json(bad)


def test_resolve_rules_payload_invalid_inline_and_missing_file(tmp_path: Path) -> None:
    project = tmp_path / "project"
    project.mkdir()

    with pytest.raises(ValueError, match="rules.inline must be an object"):
        inspect_project._resolve_rules_payload(project, {"rules": {"inline": ["bad"]}})

    with pytest.raises(ValueError, match="rules file not found"):
        inspect_project._resolve_rules_payload(project, {"rules": {"rules_file": "missing.json"}})


def test_main_handles_security_errors_for_project_and_out_dir(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys
) -> None:
    project = tmp_path / "project"
    project.mkdir()
    (project / "inspect-project.json").write_text(
        json.dumps(
            {
                "inputs": {"scopes": [{"name": "core", "include": ["*.csv"]}]},
                "rules": {"inline": {}},
                "compare": {"baseline": "none"},
            }
        ),
        encoding="utf-8",
    )

    def _deny_all(*_args, **_kwargs):
        raise inspect_project.SecurityError("blocked")

    monkeypatch.setattr(inspect_project, "safe_path", _deny_all)
    rc = inspect_project.main([str(project)])
    assert rc == inspect_project.EXIT_FINDINGS
    assert "path rejected" in capsys.readouterr().err

    calls = {"n": 0}

    def _safe_path_then_reject_out_dir(
        root: Path, user_path: str, *, allow_absolute: bool = False
    ) -> Path:
        _ = (root, user_path, allow_absolute)
        calls["n"] += 1
        if calls["n"] == 1:
            return project
        if calls["n"] == 2:
            return Path.cwd()
        raise inspect_project.SecurityError("bad out")

    monkeypatch.setattr(inspect_project, "safe_path", _safe_path_then_reject_out_dir)
    rc = inspect_project.main([str(project), "--out-dir", "../bad-out"])
    assert rc == inspect_project.EXIT_FINDINGS
    assert "out-dir rejected" in capsys.readouterr().err
