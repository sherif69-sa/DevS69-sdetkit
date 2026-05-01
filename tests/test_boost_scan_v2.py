from __future__ import annotations

import json
import subprocess
import sys


def run_cmd(*args: str):
    return subprocess.run(
        [sys.executable, "-m", "sdetkit", *args], capture_output=True, text=True, check=False
    )


def test_v1_still_default(tmp_path):
    (tmp_path / "README.md").write_text("# x\n", encoding="utf-8")
    proc = run_cmd("boost", "scan", str(tmp_path), "--format", "operator-json")
    assert proc.returncode == 0
    payload = json.loads(proc.stdout)
    assert payload["schema_version"] == "sdetkit.boost.scan.v1"


def test_deep_operator_json(tmp_path):
    (tmp_path / "README.md").write_text("# x\n", encoding="utf-8")
    proc = run_cmd("boost", "scan", str(tmp_path), "--deep", "--format", "operator-json")
    payload = json.loads(proc.stdout)
    assert payload["schema_version"] == "sdetkit.boost.scan.v2"
    assert "index_summary" in payload
    assert "counts" in payload["index_summary"]
    assert isinstance(payload["high_signal_files"], list)
    assert isinstance(payload["top_risks"], list)


def test_learn_operator_json(tmp_path):
    db = tmp_path / "adaptive.db"
    proc = run_cmd(
        "boost",
        "scan",
        str(tmp_path),
        "--deep",
        "--learn",
        "--db",
        str(db),
        "--format",
        "operator-json",
    )
    payload = json.loads(proc.stdout)
    assert payload["schema_version"] == "sdetkit.boost.scan.v2"
    assert "adaptive_memory" in payload
    assert payload["adaptive_memory"]["db"]
    assert payload["adaptive_memory"]["run_count"] >= 1
    assert isinstance(payload["recurring_risks"], list)
    assert isinstance(payload["recommended_fixes"], list)


def test_learn_idempotent(tmp_path):
    db = tmp_path / "adaptive.db"
    for _ in range(2):
        proc = run_cmd(
            "boost",
            "scan",
            str(tmp_path),
            "--deep",
            "--learn",
            "--db",
            str(db),
            "--format",
            "operator-json",
        )
        assert proc.returncode == 0
    hist = run_cmd("adaptive", "history", "--db", str(db), "--format", "operator-json")
    payload = json.loads(hist.stdout)
    assert payload["run_count"] >= 1


def test_text_max_lines(tmp_path):
    db = tmp_path / "adaptive.db"
    proc = run_cmd(
        "boost",
        "scan",
        str(tmp_path),
        "--deep",
        "--learn",
        "--db",
        str(db),
        "--format",
        "text",
        "--max-lines",
        "30",
    )
    assert proc.returncode == 0
    lines = [line for line in proc.stdout.splitlines() if line.strip()]
    assert len(lines) <= 30
    assert "decision:" in proc.stdout.lower()
    assert "score:" in proc.stdout.lower()


def test_evidence_dir(tmp_path):
    db = tmp_path / "adaptive.db"
    evidence = tmp_path / "evidence"
    proc = run_cmd(
        "boost",
        "scan",
        str(tmp_path),
        "--deep",
        "--learn",
        "--db",
        str(db),
        "--evidence-dir",
        str(evidence),
        "--format",
        "operator-json",
    )
    assert proc.returncode == 0
    for name in (
        "boost-scan.json",
        "boost-scan.txt",
        "index.json",
        "memory-history.json",
        "memory-explain.json",
    ):
        assert (evidence / name).exists()
        if name.endswith(".json"):
            json.loads((evidence / name).read_text(encoding="utf-8"))
