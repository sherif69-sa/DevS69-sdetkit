from __future__ import annotations

import json
from pathlib import Path

import pytest

from sdetkit import cli, flake_hunter


@pytest.fixture
def sample_chaos_workspace(tmp_path: Path) -> Path:
    tests = tmp_path / "tests"
    tests.mkdir(parents=True)

    (tests / "test_calc.py").write_text(
        "def mul(a, b):\n    return a * b\n\n\ndef test_mul():\n    assert mul(2, 3) == 6\n",
        encoding="utf-8",
    )
    return tmp_path


def test_inject_chaos_bulletproof(sample_chaos_workspace: Path) -> None:
    report = flake_hunter.inject_chaos(
        sample_chaos_workspace,
        target="tests/test_calc.py",
        profile="combined",
        latency_ms=0,
        jitter_ms=0,
        switch_interval_us=10,
        runs=2,
    )

    assert report["schema_version"] == flake_hunter.CHAOS_SCHEMA_VERSION
    assert report["verdict"] == "BULLETPROOF"
    assert report["resilience_score"] == 100.0
    assert report["resilience_rate"] == 100.0
    assert report["runs_planned"] == 2
    assert report["passed_runs"] == 2
    assert report["failed_runs"] == 0


def test_inject_chaos_with_command(tmp_path: Path) -> None:
    import sys

    report = flake_hunter.inject_chaos(
        tmp_path,
        command=[sys.executable, "-c", "import sys; sys.exit(0)"],
        profile="race",
        switch_interval_us=5,
        runs=2,
    )

    assert report["schema_version"] == flake_hunter.CHAOS_SCHEMA_VERSION
    assert report["verdict"] == "BULLETPROOF"
    assert report["resilience_score"] == 100.0
    assert report["passed_runs"] == 2


def test_inject_chaos_broken_baseline(sample_chaos_workspace: Path) -> None:
    tests = sample_chaos_workspace / "tests"
    (tests / "test_broken.py").write_text(
        "def test_fail():\n    assert 1 == 99\n", encoding="utf-8"
    )

    report = flake_hunter.inject_chaos(
        sample_chaos_workspace,
        target="tests/test_broken.py",
        profile="combined",
        runs=2,
    )

    assert report["schema_version"] == flake_hunter.CHAOS_SCHEMA_VERSION
    assert report["verdict"] == "BROKEN_BASELINE"
    assert report["resilience_score"] == 0.0
    assert report["baseline_passed"] is False


def test_render_chaos_markdown(sample_chaos_workspace: Path) -> None:
    report = flake_hunter.inject_chaos(
        sample_chaos_workspace,
        target="tests/test_calc.py",
        profile="combined",
        latency_ms=0,
        jitter_ms=0,
        runs=1,
    )
    md = flake_hunter.render_chaos_markdown(report)

    assert "### [CHAOS: BULLETPROOF (100.0%)]" in md
    assert "SDETKit Chaos Resilience & Injection Engine" in md
    assert "Duration Benchmark" in md
    assert "Policy Decision" in md


def test_chaos_cli_main_json_and_md(
    sample_chaos_workspace: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    out_file = tmp_path / "chaos_report.json"
    rc = flake_hunter.chaos_main(
        [
            "--repo-root",
            str(sample_chaos_workspace),
            "--target",
            "tests/test_calc.py",
            "--latency-ms",
            "0",
            "--jitter-ms",
            "0",
            "--runs",
            "1",
            "--format",
            "json",
            "--out",
            str(out_file),
        ]
    )
    assert rc == 0
    assert out_file.is_file()
    data = json.loads(out_file.read_text(encoding="utf-8"))
    assert data["schema_version"] == flake_hunter.CHAOS_SCHEMA_VERSION

    # Test markdown output format
    rc_md = flake_hunter.chaos_main(
        [
            "--repo-root",
            str(sample_chaos_workspace),
            "--target",
            "tests/test_calc.py",
            "--latency-ms",
            "0",
            "--jitter-ms",
            "0",
            "--runs",
            "1",
            "--format",
            "md",
        ]
    )
    assert rc_md == 0
    captured = capsys.readouterr()
    assert "SDETKit Chaos Resilience & Injection Engine" in captured.out


def test_chaos_cli_dispatch(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as exc:
        cli.main(["chaos", "--help"])
    assert exc.value.code == 0
    captured = capsys.readouterr()
    assert "Inject controlled chaos" in captured.out


def test_chaos_verify_cli_dispatch(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as exc:
        cli.main(["verify", "chaos", "--help"])
    assert exc.value.code == 0
    captured = capsys.readouterr()
    assert "Inject controlled chaos" in captured.out
