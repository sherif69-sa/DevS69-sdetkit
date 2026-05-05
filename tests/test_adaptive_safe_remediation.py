import json

from sdetkit import adaptive_safe_remediation


def _plan(commands=None, **overrides):
    payload = {
        "schema_version": "sdetkit.adaptive_safe_fix.v1",
        "source_schema_version": "sdetkit.adaptive.diagnosis.v1",
        "ok": True,
        "source_status": "needs_fix",
        "source_code": "PRE_COMMIT_FORMAT_DRIFT",
        "safe_to_auto_fix": True,
        "fix_type": "format_only",
        "confidence": "high",
        "requires_human_review": False,
        "reason": "format-only drift",
        "commands": commands
        if commands is not None
        else [
            "PYTHONPATH=src python -m ruff format src/sdetkit/example.py",
            "PYTHONPATH=src python -m ruff format --check src/sdetkit/example.py",
            "PYTHONPATH=src python -m ruff check src/sdetkit/example.py",
        ],
        "proof_commands": [],
        "affected_files": ["src/sdetkit/example.py"],
    }
    payload.update(overrides)
    return payload


def _runner_factory(results=None):
    calls = []
    queued = list(results or [])

    def runner(parts, cwd):
        calls.append((list(parts), cwd))
        result = (
            queued.pop(0) if queued else {"ok": True, "returncode": 0, "stdout": "ok", "stderr": ""}
        )
        return dict(result)

    return calls, runner


def test_validate_plan_accepts_format_only_allowlist():
    ok, errors = adaptive_safe_remediation.validate_plan(_plan())

    assert ok is True
    assert errors == []


def test_validate_plan_accepts_ruff_fixable_lint_allowlist():
    ok, errors = adaptive_safe_remediation.validate_plan(
        _plan(
            source_code="RUFF_FIXABLE_LINT",
            fix_type="ruff_fixable_lint",
            commands=[
                "PYTHONPATH=src python -m ruff check --fix src/sdetkit/example.py",
                "PYTHONPATH=src python -m ruff format src/sdetkit/example.py",
                "PYTHONPATH=src python -m ruff check src/sdetkit/example.py",
                "PYTHONPATH=src python -m ruff format --check src/sdetkit/example.py",
            ],
        )
    )

    assert ok is True
    assert errors == []


def test_validate_plan_rejects_ruff_fix_in_format_only_plan():
    ok, errors = adaptive_safe_remediation.validate_plan(
        _plan(commands=["PYTHONPATH=src python -m ruff check --fix src/sdetkit/example.py"])
    )

    assert ok is False
    assert "ruff --fix is only allowed" in errors[0]


def test_validate_plan_rejects_ruff_command_outside_affected_files():
    ok, errors = adaptive_safe_remediation.validate_plan(
        _plan(
            source_code="RUFF_FIXABLE_LINT",
            fix_type="ruff_fixable_lint",
            commands=[
                "PYTHONPATH=src python -m ruff check --fix tests/test_other.py",
            ],
        )
    )

    assert ok is False
    assert "outside affected_files" in errors[0]


def test_validate_plan_rejects_review_required_or_unsafe_commands():
    for plan in [
        _plan(safe_to_auto_fix=False),
        _plan(requires_human_review=True),
        _plan(fix_type="review_required"),
        _plan(commands=["git push origin HEAD"]),
        _plan(commands=["PYTHONPATH=src python -m ruff format <touched-python-files>"]),
        _plan(commands=["python -m pip install -r requirements.txt"]),
    ]:
        ok, errors = adaptive_safe_remediation.validate_plan(plan)
        assert ok is False
        assert errors


def test_run_plan_executes_commands_in_order_with_fake_runner(tmp_path):
    calls, runner = _runner_factory()

    result = adaptive_safe_remediation.run_plan(_plan(), cwd=tmp_path, command_runner=runner)

    assert result["ok"] is True
    assert result["status"] == "success"
    assert result["attempted"] is True
    assert result["command_count"] == 3
    assert [call[0] for call in calls] == [
        ["PYTHONPATH=src", "python", "-m", "ruff", "format", "src/sdetkit/example.py"],
        ["PYTHONPATH=src", "python", "-m", "ruff", "format", "--check", "src/sdetkit/example.py"],
        ["PYTHONPATH=src", "python", "-m", "ruff", "check", "src/sdetkit/example.py"],
    ]
    assert all(call[1] == tmp_path for call in calls)


def test_run_plan_stops_after_first_failed_command(tmp_path):
    calls, runner = _runner_factory(
        [
            {"ok": True, "returncode": 0, "stdout": "format ok", "stderr": ""},
            {"ok": False, "returncode": 1, "stdout": "", "stderr": "format check failed"},
            {"ok": True, "returncode": 0, "stdout": "should not run", "stderr": ""},
        ]
    )

    result = adaptive_safe_remediation.run_plan(_plan(), cwd=tmp_path, command_runner=runner)

    assert result["ok"] is False
    assert result["status"] == "failed"
    assert result["command_count"] == 2
    assert len(calls) == 2
    assert result["commands"][1]["stderr"] == "format check failed"


def test_run_plan_blocks_invalid_plan_without_running_commands(tmp_path):
    calls, runner = _runner_factory()

    result = adaptive_safe_remediation.run_plan(
        _plan(commands=["git commit -am bad"]), cwd=tmp_path, command_runner=runner
    )

    assert result["ok"] is False
    assert result["status"] == "blocked"
    assert result["attempted"] is False
    assert result["command_count"] == 0
    assert calls == []
    assert "blocked mutation token" in result["validation_errors"][0]


def test_run_plan_file_writes_json_and_markdown(tmp_path):
    plan_path = tmp_path / "safe-fix-plan.json"
    out_json = tmp_path / "result.json"
    out_md = tmp_path / "result.md"
    plan_path.write_text(json.dumps(_plan()), encoding="utf-8")
    calls, runner = _runner_factory()

    result = adaptive_safe_remediation.run_plan_file(
        plan_path,
        out_json=out_json,
        out_md=out_md,
        cwd=tmp_path,
        command_runner=runner,
    )

    assert result["ok"] is True
    assert result["plan_path"] == plan_path.as_posix()
    assert json.loads(out_json.read_text(encoding="utf-8"))["status"] == "success"
    assert "# Adaptive Safe Remediation Result" in out_md.read_text(encoding="utf-8")
    assert len(calls) == 3


def test_cli_returns_nonzero_for_blocked_plan(tmp_path, capsys):
    plan_path = tmp_path / "safe-fix-plan.json"
    plan_path.write_text(json.dumps(_plan(commands=["git status"])), encoding="utf-8")

    rc = adaptive_safe_remediation.main([str(plan_path)])

    assert rc == 1
    output = capsys.readouterr().out
    assert "status: blocked" in output
    assert "validation_error:" in output


def test_cli_rejects_bad_schema(tmp_path, capsys):
    plan_path = tmp_path / "safe-fix-plan.json"
    plan_path.write_text(json.dumps({"schema_version": "bad"}), encoding="utf-8")

    rc = adaptive_safe_remediation.main([str(plan_path)])

    assert rc == 2
    assert "unsupported safe fix plan schema" in capsys.readouterr().out
