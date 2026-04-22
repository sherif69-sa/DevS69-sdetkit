from __future__ import annotations

import importlib
from pathlib import Path
from types import SimpleNamespace

from sdetkit.checks.base import CheckContext, CheckDefinition


def test_builtin_module_import_and_command_helpers(tmp_path: Path, monkeypatch) -> None:
    builtin = importlib.import_module("sdetkit.checks.builtin")
    assert len(builtin.BUILTIN_CHECKS) >= 5

    ctx = CheckContext(repo_root=tmp_path, out_dir=tmp_path / "out", python_executable="python")
    assert builtin._repo_layout_command(ctx)[0] == "python"
    assert "ruff" in " ".join(builtin._format_check_command(ctx))
    assert "pytest" in " ".join(
        builtin._tests_full_command(
            ctx.for_check(
                check_id="x", target_mode="targeted", selected_targets=("tests/test_x.py",)
            )
        )
    )
    assert "security" in " ".join(builtin._security_scan_command(ctx))
    assert "doctor" in " ".join(builtin._doctor_core_command(ctx))


def test_builtin_skip_and_subprocess_runner(tmp_path: Path, monkeypatch) -> None:
    builtin = importlib.import_module("sdetkit.checks.builtin")
    ctx = CheckContext(repo_root=tmp_path, out_dir=tmp_path / "out", python_executable="python")

    check = CheckDefinition(
        id="tests_full",
        title="Tests",
        category="tests",
        cost="cheap",
        truth_level="smoke",
        required_tools=("tool-that-does-not-exist",),
        command=("python", "-m", "pytest"),
        evidence_outputs=("artifact.json",),
    )
    skipped = builtin._skip_missing_prereqs(check, ctx)
    assert skipped is not None
    assert skipped.status == "skipped"

    (tmp_path / "artifact.json").write_text("{}", encoding="utf-8")
    check2 = CheckDefinition(
        id="tests_full",
        title="Tests",
        category="tests",
        cost="cheap",
        truth_level="smoke",
        command=("python", "-m", "pytest"),
        evidence_outputs=("artifact.json",),
    )

    calls = {"n": 0}

    def _fake_run(*_a, **_k):
        calls["n"] += 1
        if calls["n"] == 1:
            return SimpleNamespace(returncode=1, stdout="first", stderr="boom")
        return SimpleNamespace(returncode=0, stdout="second", stderr="")

    monkeypatch.setattr(builtin.subprocess, "run", _fake_run)
    record = builtin._run_subprocess(check2, ctx, ("python", "-m", "pytest"))
    assert record.status == "passed"
    assert record.metadata["attempts"] == 2
    assert "artifact.json" in record.evidence_paths

    runner = builtin._make_command_runner(lambda _ctx: ("python", "-m", "pytest"))
    monkeypatch.setattr(builtin, "_run_subprocess", lambda *_a, **_k: record)
    out = runner(check2, ctx)
    assert out.id == "tests_full"
