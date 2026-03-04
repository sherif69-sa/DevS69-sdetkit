import json
import subprocess
import sys
from pathlib import Path


def _run(args: list[str]) -> None:
    proc = subprocess.run(args, capture_output=True, text=True)
    assert proc.returncode == 0, proc.stdout + "\n" + proc.stderr


def test_security_check_filters_info_from_new_findings_by_default(tmp_path: Path) -> None:
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "x.py").write_text("print('x')\n", encoding="utf-8")
    baseline = tmp_path / "baseline.json"
    baseline.write_text('{"version": 1, "entries": []}\n', encoding="utf-8")
    out = tmp_path / "out.json"

    _run(
        [
            sys.executable,
            "-m",
            "sdetkit",
            "security",
            "check",
            "--root",
            str(tmp_path),
            "--baseline",
            str(baseline),
            "--format",
            "json",
            "--output",
            str(out),
            "--fail-on",
            "none",
        ]
    )

    data = json.loads(out.read_text(encoding="utf-8"))
    assert len(data.get("new_findings", [])) == 0


def test_security_check_include_info_flag_restores_info_new_findings(tmp_path: Path) -> None:
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "x.py").write_text("print('x')\n", encoding="utf-8")
    baseline = tmp_path / "baseline.json"
    baseline.write_text('{"version": 1, "entries": []}\n', encoding="utf-8")
    out = tmp_path / "out.json"

    _run(
        [
            sys.executable,
            "-m",
            "sdetkit",
            "security",
            "check",
            "--root",
            str(tmp_path),
            "--baseline",
            str(baseline),
            "--include-info",
            "--format",
            "json",
            "--output",
            str(out),
            "--fail-on",
            "none",
        ]
    )

    data = json.loads(out.read_text(encoding="utf-8"))
    new_findings = data.get("new_findings", [])
    assert len(new_findings) == 1
    assert new_findings[0]["rule_id"] == "SEC_DEBUG_PRINT"


def test_security_baseline_excludes_info_by_default(tmp_path: Path) -> None:
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "x.py").write_text("print('x')\n", encoding="utf-8")
    out = tmp_path / "baseline.json"

    _run(
        [
            sys.executable,
            "-m",
            "sdetkit",
            "security",
            "baseline",
            "--root",
            str(tmp_path),
            "--output",
            str(out),
        ]
    )

    data = json.loads(out.read_text(encoding="utf-8"))
    assert data["entries"] == []


def test_security_baseline_include_info_flag_includes_info(tmp_path: Path) -> None:
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "x.py").write_text("print('x')\n", encoding="utf-8")
    out = tmp_path / "baseline.json"

    _run(
        [
            sys.executable,
            "-m",
            "sdetkit",
            "security",
            "baseline",
            "--root",
            str(tmp_path),
            "--include-info",
            "--output",
            str(out),
        ]
    )

    data = json.loads(out.read_text(encoding="utf-8"))
    assert len(data["entries"]) == 1
    assert data["entries"][0]["rule_id"] == "SEC_DEBUG_PRINT"


def test_security_scan_sarif_excludes_info_by_default(tmp_path: Path) -> None:
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "x.py").write_text("print('x')\n", encoding="utf-8")
    out = tmp_path / "scan.sarif"

    _run(
        [
            sys.executable,
            "-m",
            "sdetkit",
            "security",
            "scan",
            "--root",
            str(tmp_path),
            "--format",
            "sarif",
            "--output",
            str(out),
            "--fail-on",
            "none",
        ]
    )

    data = json.loads(out.read_text(encoding="utf-8"))
    assert data["runs"][0]["results"] == []


def test_security_scan_sarif_include_info_restores_info_findings(tmp_path: Path) -> None:
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "x.py").write_text("print('x')\n", encoding="utf-8")
    out = tmp_path / "scan.sarif"

    _run(
        [
            sys.executable,
            "-m",
            "sdetkit",
            "security",
            "scan",
            "--root",
            str(tmp_path),
            "--format",
            "sarif",
            "--include-info",
            "--output",
            str(out),
            "--fail-on",
            "none",
        ]
    )

    data = json.loads(out.read_text(encoding="utf-8"))
    results = data["runs"][0]["results"]
    assert len(results) == 1
    assert results[0]["ruleId"] == "SEC_DEBUG_PRINT"
