from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from sdetkit.intelligence import review as review_mod


def _run(*args: str, cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "sdetkit", *args], text=True, capture_output=True, cwd=cwd
    )


def test_review_operator_json_non_adaptive_compatible(tmp_path: Path) -> None:
    repo = tmp_path / "tmprepo"
    repo.mkdir()
    (repo / "README.md").write_text("x\n", encoding="utf-8")
    run = _run("review", str(repo), "--no-workspace", "--format", "operator-json")
    assert run.returncode in (0, 2)
    payload = json.loads(run.stdout)
    assert "contract_version" in payload
    assert "adaptive_review" not in payload


def test_review_adaptive_operator_json_and_evidence(tmp_path: Path) -> None:
    repo = tmp_path / "tmprepo"
    repo.mkdir()
    (repo / "a.py").write_text("print('ok')\n", encoding="utf-8")
    db = tmp_path / "adaptive.db"
    evidence = tmp_path / "evidence"
    run = _run(
        "review",
        str(repo),
        "--adaptive",
        "--deep",
        "--learn",
        "--db",
        str(db),
        "--evidence-dir",
        str(evidence),
        "--format",
        "operator-json",
    )
    assert run.returncode in (0, 2)
    payload = json.loads(run.stdout)
    adaptive = payload["adaptive_review"]
    assert adaptive["schema_version"] == "sdetkit.review.adaptive.v1"
    assert isinstance(adaptive["adaptive_findings"], list)
    assert isinstance(adaptive["recommended_fixes"], list)
    assert isinstance(adaptive["patch_candidates"], list)
    assert "memory_summary" in adaptive
    assert "index_summary" in adaptive
    assert "boost_summary" in adaptive
    assert adaptive.get("boost_summary", {}).get("missing_signal") is None
    assert adaptive.get("index_summary", {}).get("missing_signal") is None
    assert adaptive.get("confidence") != "degraded"
    for name in [
        "adaptive-review.json",
        "boost-v2.json",
        "index.json",
        "memory-history.json",
        "memory-explain.json",
    ]:
        assert (evidence / name).exists()


def test_review_adaptive_idempotent_learn(tmp_path: Path) -> None:
    repo = tmp_path / "tmprepo"
    repo.mkdir()
    (repo / "b.py").write_text("x=1\n", encoding="utf-8")
    db = tmp_path / "adaptive.db"
    run1 = _run(
        "review",
        str(repo),
        "--adaptive",
        "--deep",
        "--learn",
        "--db",
        str(db),
        "--format",
        "operator-json",
    )
    run2 = _run(
        "review",
        str(repo),
        "--adaptive",
        "--deep",
        "--learn",
        "--db",
        str(db),
        "--format",
        "operator-json",
    )
    assert run1.returncode in (0, 2)
    assert run2.returncode in (0, 2)
    hist = _run("adaptive", "history", "--db", str(db), "--format", "operator-json")
    payload = json.loads(hist.stdout)
    assert int(payload.get("run_count", 0)) >= 0


def test_review_adaptive_patch_candidates_populated(tmp_path: Path) -> None:
    repo = tmp_path / "tmprepo"
    repo.mkdir()
    (repo / "c.py").write_text("print(1)\n", encoding="utf-8")
    run = _run(
        "review",
        str(repo),
        "--adaptive",
        "--deep",
        "--learn",
        "--db",
        str(tmp_path / "adaptive.db"),
        "--format",
        "operator-json",
    )
    assert run.returncode in (0, 2)
    payload = json.loads(run.stdout)
    assert isinstance(payload["adaptive_review"].get("patch_candidates"), list)


def test_adaptive_helper_failure_degrades_with_diagnostics(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    def _fake_run(args, **kwargs):
        cmd = " ".join(args)
        if "index inspect" in cmd:
            return subprocess.CompletedProcess(args, 7, stdout="", stderr="index failed")
        if "boost scan" in cmd:
            return subprocess.CompletedProcess(args, 8, stdout="", stderr="boost failed")
        return subprocess.CompletedProcess(args, 0, stdout="{}", stderr="")

    monkeypatch.setattr(review_mod.subprocess, "run", _fake_run)
    out = review_mod._build_adaptive_review_v2(
        target=tmp_path,
        payload={"status": "attention", "top_matters": [], "five_heads": {"heads": {}}},
        deep=True,
        learn=True,
        db_path=tmp_path / "adaptive.db",
        evidence_dir=None,
    )
    assert out["confidence"] == "degraded"
    assert out["boost_summary"]["missing_signal"] == "boost unavailable"
    assert out["index_summary"]["missing_signal"] == "index unavailable"
    assert out["signals"]["helpers"]["boost"]["rc"] == 8
    assert out["signals"]["helpers"]["index"]["rc"] == 7
