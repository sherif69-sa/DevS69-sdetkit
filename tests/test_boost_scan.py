from __future__ import annotations

import json
import subprocess
import sys


def test_boost_scan_operator_json_contract(tmp_path):
    (tmp_path / "README.md").write_text("# x\n", encoding="utf-8")
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "test_smoke.py").write_text("def test_ok():\n    assert True\n", encoding="utf-8")

    proc = subprocess.run(
        [sys.executable, "-m", "sdetkit", "boost", "scan", str(tmp_path), "--format", "operator-json"],
        capture_output=True,
        text=True,
        check=False,
    )

    assert proc.returncode == 0
    payload = json.loads(proc.stdout)
    assert payload["schema_version"] == "sdetkit.boost.scan.v1"
    assert payload["tool"] == "sdetkit boost scan"
    assert payload.get("decision") in {"SHIP", "BOOST", "NO-SHIP"}
    assert payload.get("score") is not None
    assert isinstance(payload["budget"], dict)
    assert isinstance(payload["summary"], str)
    assert isinstance(payload["recommended_fixes"], list)
    assert isinstance(payload["top_risks"], list)
    assert isinstance(payload["high_signal_files"], list)
    assert isinstance(payload["next_pr_candidates"], list)
    assert isinstance(payload["evidence_files"], list)
    assert isinstance(payload["signals"], dict)


def test_boost_scan_text_max_lines(tmp_path):
    (tmp_path / "README.md").write_text("# x\n", encoding="utf-8")

    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "sdetkit",
            "boost",
            "scan",
            str(tmp_path),
            "--format",
            "text",
            "--max-lines",
            "20",
        ],
        capture_output=True,
        text=True,
        check=False,
    )

    assert proc.returncode == 0
    lines = [line for line in proc.stdout.splitlines() if line.strip()]
    assert len(lines) <= 20
    text = proc.stdout.lower()
    assert "decision:" in text
    assert "score:" in text
    assert ("recommended fixes" in text) or ("next pr candidates" in text)


def test_boost_scan_budget_arguments_accept_small_repo(tmp_path):
    (tmp_path / "README.md").write_text("# tiny\n", encoding="utf-8")

    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "sdetkit",
            "boost",
            "scan",
            str(tmp_path),
            "--minutes",
            "1",
            "--max-lines",
            "10",
            "--format",
            "text",
        ],
        capture_output=True,
        text=True,
        check=False,
    )

    assert proc.returncode == 0
