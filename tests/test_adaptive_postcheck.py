from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

_SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "adaptive_postcheck.py"
_SPEC = importlib.util.spec_from_file_location("adaptive_postcheck_script", _SCRIPT_PATH)
assert _SPEC is not None and _SPEC.loader is not None
adaptive_postcheck = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(adaptive_postcheck)


def test_parse_json_stdout_accepts_clean_json_object() -> None:
    payload = adaptive_postcheck._parse_json_stdout('{"ok": true, "score": 95}')
    assert payload == {"ok": True, "score": 95}


def test_parse_json_stdout_recovers_json_after_log_lines() -> None:
    payload = adaptive_postcheck._parse_json_stdout(
        'warning: bootstrapping lane\ninfo: continuing\n{"ok": false, "failed_required": 1}\n'
    )
    assert payload == {"ok": False, "failed_required": 1}


def test_local_python_env_targets_repo_root_src(monkeypatch) -> None:
    monkeypatch.setenv("PYTHONPATH", "existing-path")
    env = adaptive_postcheck._local_python_env("/tmp/demo-repo")
    assert env["PYTHONPATH"].startswith(str(Path("/tmp/demo-repo/src").resolve()))
    assert env["PYTHONPATH"].endswith("existing-path")


def test_load_review_payload_parses_noisy_subprocess_stdout(monkeypatch, tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    repo_root.mkdir()

    captured: dict[str, object] = {}

    def _fake_run(*_args, **kwargs):
        captured.update(kwargs)
        return SimpleNamespace(
            returncode=2,
            stdout='boot log\n{"status":"watch","findings_count":3}\n',
            stderr="",
        )

    monkeypatch.setattr(adaptive_postcheck.subprocess, "run", _fake_run)
    payload = adaptive_postcheck._load_review_payload(str(repo_root), None)
    assert payload == {"status": "watch", "findings_count": 3}
    assert captured["cwd"] == str(repo_root)
    env = captured["env"]
    assert isinstance(env, dict)
    assert str((repo_root / "src").resolve()) in str(env.get("PYTHONPATH", ""))


def test_doctor_summary_parses_noisy_subprocess_stdout(monkeypatch, tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    repo_root.mkdir()

    captured: dict[str, object] = {}

    def _fake_run(*_args, **kwargs):
        captured.update(kwargs)
        return SimpleNamespace(
            returncode=2,
            stdout=(
                "doctor preface\n"
                '{"ok": false, "score": 70, "quality": {"failed_checks": 2, "failed_check_ids": ["deps", "ci"]}}\n'
            ),
            stderr="",
        )

    monkeypatch.setattr(adaptive_postcheck.subprocess, "run", _fake_run)
    payload = adaptive_postcheck._doctor_summary(str(repo_root))
    assert payload == {
        "ok": False,
        "score": 70,
        "failed_checks": 2,
        "failed_check_ids": ["deps", "ci"],
    }
    assert captured["cwd"] == str(repo_root)
    env = captured["env"]
    assert isinstance(env, dict)
    assert str((repo_root / "src").resolve()) in str(env.get("PYTHONPATH", ""))


def test_load_review_payload_raises_with_stdout_and_stderr_context(
    monkeypatch, tmp_path: Path
) -> None:
    repo_root = tmp_path / "repo"
    repo_root.mkdir()

    def _fake_run(*_args, **_kwargs):
        return SimpleNamespace(
            returncode=1,
            stdout="not-json-output",
            stderr="module import failure",
        )

    monkeypatch.setattr(adaptive_postcheck.subprocess, "run", _fake_run)
    with pytest.raises(RuntimeError) as excinfo:
        adaptive_postcheck._load_review_payload(str(repo_root), None)
    message = str(excinfo.value)
    assert "stdout='not-json-output'" in message
    assert "stderr='module import failure'" in message


def test_load_review_payload_truncates_stdout_snippet_in_error(monkeypatch, tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    very_long_stdout = "x" * 400

    def _fake_run(*_args, **_kwargs):
        return SimpleNamespace(
            returncode=1,
            stdout=very_long_stdout,
            stderr="boom",
        )

    monkeypatch.setattr(adaptive_postcheck.subprocess, "run", _fake_run)
    with pytest.raises(RuntimeError) as excinfo:
        adaptive_postcheck._load_review_payload(str(repo_root), None)

    message = str(excinfo.value)
    assert ("stdout='" + ("x" * 200) + "'") in message
    assert ("stdout='" + ("x" * 201)) not in message


def test_main_writes_output_artifact_for_mocked_inputs(monkeypatch, tmp_path: Path) -> None:
    out_path = tmp_path / "adaptive-postcheck.json"
    payload = {"adaptive_database": {"release_readiness_contract": {}}}
    scenario = {
        "enabled_checks": ["adaptive_database_present"],
        "warn_only_checks": [],
    }

    monkeypatch.setattr(
        adaptive_postcheck, "_load_review_payload", lambda *_args, **_kwargs: payload
    )
    monkeypatch.setattr(adaptive_postcheck, "_load_scenario", lambda *_args, **_kwargs: scenario)
    monkeypatch.setattr(adaptive_postcheck, "_doctor_summary", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(
        adaptive_postcheck.sys,
        "argv",
        ["adaptive_postcheck.py", ".", "--scenario", "fast", "--out", str(out_path)],
    )

    rc = adaptive_postcheck.main()
    assert rc == 0
    written = json.loads(out_path.read_text(encoding="utf-8"))
    assert written["summary"]["ok"] is True
    assert written["summary"]["failed_required"] == 0
