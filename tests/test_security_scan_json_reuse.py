from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path


def _run(repo_root: Path, cwd: Path, *args: str) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(repo_root / "src")
    return subprocess.run(
        [sys.executable, "-m", "sdetkit", "security", *args],
        cwd=cwd,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )


def test_security_check_and_report_can_reuse_scan_json(tmp_path: Path) -> None:
    repo_root = Path(__file__).resolve().parents[1]

    allow = tmp_path / "allow.json"
    allow.write_text(
        json.dumps({"version": 1, "entries": []}, sort_keys=True) + "\n", encoding="utf-8"
    )

    baseline = tmp_path / "baseline.json"
    baseline.write_text(
        json.dumps({"version": 1, "entries": []}, sort_keys=True) + "\n", encoding="utf-8"
    )

    vuln = tmp_path / "vuln.py"
    vuln.write_text("eval('1')\n", encoding="utf-8")

    scan_json = tmp_path / "scan.json"
    proc = _run(
        repo_root,
        tmp_path,
        "scan",
        "--root",
        str(tmp_path),
        "--allowlist",
        str(allow),
        "--format",
        "json",
        "--out",
        str(scan_json),
        "--fail-on",
        "none",
    )
    assert proc.returncode == 0, proc.stderr
    assert scan_json.exists()

    vuln.unlink()

    proc = _run(
        repo_root,
        tmp_path,
        "check",
        "--root",
        str(tmp_path),
        "--allowlist",
        str(allow),
        "--scan-json",
        str(scan_json),
        "--baseline",
        str(baseline),
        "--format",
        "json",
        "--fail-on",
        "high",
    )
    assert proc.returncode == 1
    payload = json.loads(proc.stdout)
    assert payload["version"] == 1
    assert len(payload["findings"]) == 1
    assert payload["findings"][0]["rule_id"] == "SEC_DANGEROUS_EVAL"

    proc = _run(
        repo_root,
        tmp_path,
        "report",
        "--root",
        str(tmp_path),
        "--allowlist",
        str(allow),
        "--scan-json",
        str(scan_json),
        "--format",
        "sarif",
    )
    assert proc.returncode == 0, proc.stderr
    sarif = json.loads(proc.stdout)
    results = sarif["runs"][0]["results"]
    assert any(r.get("ruleId") == "SEC_DANGEROUS_EVAL" for r in results)
