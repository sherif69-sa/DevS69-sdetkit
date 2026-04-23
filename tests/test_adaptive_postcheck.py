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
    csv_path = tmp_path / "owner-routing.csv"
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
        [
            "adaptive_postcheck.py",
            ".",
            "--scenario",
            "fast",
            "--out",
            str(out_path),
            "--owner-routing-csv",
            str(csv_path),
        ],
    )

    rc = adaptive_postcheck.main()
    assert rc == 0
    written = json.loads(out_path.read_text(encoding="utf-8"))
    assert written["summary"]["ok"] is True
    assert written["summary"]["failed_required"] == 0
    assert written["owner_routing"] == []
    csv_text = csv_path.read_text(encoding="utf-8")
    assert "check,owner,severity,sla,details" in csv_text
    assert len(csv_text.strip().splitlines()) == 1


def test_build_owner_routing_maps_failing_checks_to_owners() -> None:
    checks = [
        {"check": "pr_outcome_feedback_present", "passed": False, "details": "missing feedback"},
        {"check": "adaptive_database_present", "passed": False, "details": "missing adaptive payload"},
        {"check": "intelligence_matrix_present", "passed": True, "details": "ok"},
    ]
    scenario = {
        "owner_routing": {
            "pr_outcome_feedback_present": {
                "owner": "review-intelligence",
                "severity": "high",
                "sla": "72h",
            },
            "adaptive_database_present": {
                "owner": "platform-ops",
                "severity": "critical",
                "sla": "24h",
            },
        }
    }
    rows = adaptive_postcheck._build_owner_routing(checks, scenario)
    assert len(rows) == 2
    by_check = {row["check"]: row for row in rows}
    assert by_check["pr_outcome_feedback_present"]["owner"] == "review-intelligence"
    assert by_check["adaptive_database_present"]["severity"] == "critical"


def test_write_owner_routing_csv_writes_rows(tmp_path: Path) -> None:
    out = tmp_path / "owner-routing.csv"
    adaptive_postcheck._write_owner_routing_csv(
        out,
        [
            {
                "check": "pr_outcome_feedback_present",
                "owner": "review-intelligence",
                "severity": "high",
                "sla": "72h",
                "details": "missing feedback",
            }
        ],
    )
    text = out.read_text(encoding="utf-8")
    assert "check,owner,severity,sla,details" in text
    assert "pr_outcome_feedback_present,review-intelligence,high,72h,missing feedback" in text


def test_run_alignment_checks_validates_pr_outcome_feedback_and_mistake_learning_depth() -> None:
    payload = {"adaptive_database": {"release_readiness_contract": {}}}
    scenario = {
        "enabled_checks": [
            "pr_outcome_feedback_present",
            "mistake_learning_signal_depth",
            "adaptive_learning_precision_ready",
        ],
        "warn_only_checks": [],
    }
    first_run = {"hint_count": 1}
    scenario_db = {
        "summary": {
            "kinds": {
                "pr_outcome_feedback": 4,
                "mistake_learning_event": 3,
            },
            "adaptive_learning": {"learning_signal_total": 7, "precision_ready": False},
        }
    }
    checks = adaptive_postcheck._run_alignment_checks(payload, scenario, first_run, scenario_db, None)
    by_name = {row["check"]: row for row in checks}
    assert by_name["pr_outcome_feedback_present"]["passed"] is False
    assert by_name["mistake_learning_signal_depth"]["passed"] is False
    assert by_name["adaptive_learning_precision_ready"]["passed"] is False


def test_run_alignment_checks_passes_new_feedback_depth_checks_when_counts_are_sufficient() -> None:
    payload = {"adaptive_database": {"release_readiness_contract": {}}}
    scenario = {
        "enabled_checks": [
            "pr_outcome_feedback_present",
            "mistake_learning_signal_depth",
            "adaptive_learning_precision_ready",
        ],
        "warn_only_checks": [],
    }
    first_run = {"hint_count": 2}
    scenario_db = {
        "summary": {
            "kinds": {
                "pr_outcome_feedback": 7,
                "mistake_learning_event": 10,
            },
            "adaptive_learning": {"learning_signal_total": 17, "precision_ready": True},
        }
    }
    checks = adaptive_postcheck._run_alignment_checks(payload, scenario, first_run, scenario_db, None)
    by_name = {row["check"]: row for row in checks}
    assert by_name["pr_outcome_feedback_present"]["passed"] is True
    assert by_name["mistake_learning_signal_depth"]["passed"] is True
    assert by_name["adaptive_learning_precision_ready"]["passed"] is True


def test_run_alignment_checks_honors_scenario_specific_minimums() -> None:
    payload = {"adaptive_database": {"release_readiness_contract": {}}}
    scenario = {
        "enabled_checks": [
            "pr_outcome_feedback_present",
            "mistake_learning_signal_depth",
            "adaptive_learning_precision_ready",
        ],
        "minimum_pr_outcome_feedback": 3,
        "minimum_mistake_learning_event": 3,
        "minimum_learning_signal_total": 6,
        "warn_only_checks": [],
    }
    scenario_db = {
        "summary": {
            "kinds": {
                "pr_outcome_feedback": 3,
                "mistake_learning_event": 3,
            },
            "adaptive_learning": {"learning_signal_total": 6, "precision_ready": True},
        }
    }
    checks = adaptive_postcheck._run_alignment_checks(payload, scenario, {}, scenario_db, None)
    by_name = {row["check"]: row for row in checks}
    assert by_name["pr_outcome_feedback_present"]["passed"] is True
    assert by_name["mistake_learning_signal_depth"]["passed"] is True
    assert by_name["adaptive_learning_precision_ready"]["passed"] is True
