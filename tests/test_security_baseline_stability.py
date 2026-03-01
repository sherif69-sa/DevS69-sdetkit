import json
import subprocess
import sys
from pathlib import Path


def _run_security(args: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    p = subprocess.run(
        [sys.executable, "-m", "sdetkit", "security", *args],
        cwd=str(cwd),
        text=True,
        capture_output=True,
    )
    assert p.returncode == 0, p.stderr or p.stdout
    return p


def test_baseline_suppresses_findings_after_line_shift(tmp_path: Path) -> None:
    root = tmp_path / "proj"
    (root / "src").mkdir(parents=True)

    target = root / "src" / "x.py"
    target.write_text("print('x')\n", encoding="utf-8")

    baseline = root / "baseline.json"
    _run_security(["baseline", "--root", ".", "--output", str(baseline)], cwd=root)

    out1 = root / "scan1.json"
    _run_security(
        [
            "check",
            "--root",
            ".",
            "--baseline",
            str(baseline),
            "--format",
            "json",
            "--output",
            str(out1),
        ],
        cwd=root,
    )
    d1 = json.loads(out1.read_text(encoding="utf-8"))
    assert d1.get("new_findings") == []

    target.write_text("\n" + target.read_text(encoding="utf-8"), encoding="utf-8")

    out2 = root / "scan2.json"
    _run_security(
        [
            "check",
            "--root",
            ".",
            "--baseline",
            str(baseline),
            "--format",
            "json",
            "--output",
            str(out2),
        ],
        cwd=root,
    )
    d2 = json.loads(out2.read_text(encoding="utf-8"))
    assert d2.get("new_findings") == []
