from __future__ import annotations

from pathlib import Path

from scripts import baseline_run_all as run_all


def test_build_command_plan_default() -> None:
    cmds = run_all.build_command_plan(include=False)
    assert cmds[0] == ["make", "baseline-baseline"]
    assert all(cmd != ["make", "baseline-completion-report"] for cmd in cmds)


def test_build_command_plan_with() -> None:
    cmds = run_all.build_command_plan(include=True)
    assert cmds[-1] == ["make", "baseline-completion-report"]


def test_main_writes_outputs(tmp_path: Path) -> None:
    # Run only a safe command set by monkeypatching command plan.
    original = run_all.build_command_plan
    run_all.build_command_plan = lambda include=False: [["python", "-c", "print('ok')"]]
    try:
        rc = run_all.main(
            [
                "--out-json",
                str(tmp_path / "run.json"),
                "--out-md",
                str(tmp_path / "run.md"),
                "--format",
                "json",
            ]
        )
        assert rc == 0
        assert (tmp_path / "run.json").exists()
        assert (tmp_path / "run.md").exists()
    finally:
        run_all.build_command_plan = original
