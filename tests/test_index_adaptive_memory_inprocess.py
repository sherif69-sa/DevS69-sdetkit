from __future__ import annotations

import json
from pathlib import Path

import pytest

from sdetkit import adaptive_memory, index


def _sample_repo(root: Path) -> Path:
    (root / "src").mkdir(parents=True)
    (root / "tests").mkdir()
    (root / "docs").mkdir()
    (root / ".github" / "workflows").mkdir(parents=True)
    (root / "src" / "app.py").write_text(
        "def handler():\n    # TODO: retry\n    return 1\n\n\nclass Service:\n    pass\n",
        encoding="utf-8",
    )
    (root / "src" / "big.py").write_text("x = 1\n" * 1600, encoding="utf-8")
    (root / "tests" / "test_app.py").write_text(
        "def test_handler():\n    assert True\n", encoding="utf-8"
    )
    (root / "docs" / "guide.md").write_text("# Guide\n", encoding="utf-8")
    (root / ".github" / "workflows" / "ci.yml").write_text("on: push\n", encoding="utf-8")
    (root / "pyproject.toml").write_text("[project]\nname='x'\n", encoding="utf-8")
    return root


def test_index_build_records_files_symbols_and_hotspots(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    repo = _sample_repo(tmp_path / "repo")
    out = tmp_path / "index"

    assert index.main(["build", str(repo), "--out", str(out)]) == 0
    capsys.readouterr()

    payload = json.loads((out / "index.json").read_text(encoding="utf-8"))
    counts = payload["counts"]
    assert counts["source_files"] >= 2
    assert counts["test_files"] == 1
    assert counts["docs_files"] == 1
    assert counts["workflow_files"] == 1
    hotspot_types = {h["type"] for h in payload["hotspots"]}
    assert {"large_file", "todo_marker"} <= hotspot_types
    symbol_names = {s.get("name") for s in payload["symbols"]}
    assert {"handler", "Service"} <= symbol_names
    for key in ("files_jsonl", "symbols_jsonl", "hotspots_jsonl"):
        assert Path(payload["evidence_files"][key]).is_file()


def test_index_inspect_text_and_json(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    repo = _sample_repo(tmp_path / "repo")
    out = tmp_path / "index"
    index.main(["build", str(repo), "--out", str(out)])
    capsys.readouterr()

    assert index.main(["inspect", str(out), "--format", "operator-json"]) == 0
    inspected = json.loads(capsys.readouterr().out)
    assert inspected["counts"]["test_files"] == 1

    assert index.main(["inspect", str(out)]) == 0
    assert capsys.readouterr().out.strip()


def test_adaptive_memory_ingest_is_idempotent_and_explains_hotspots(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    repo = _sample_repo(tmp_path / "repo")
    out = tmp_path / "index"
    db = tmp_path / "adaptive.db"
    index.main(["build", str(repo), "--out", str(out)])

    assert adaptive_memory.main(["init", "--db", str(db)]) == 0
    for _ in range(2):
        assert adaptive_memory.main(["ingest", str(out / "index.json"), "--db", str(db)]) == 0
    capsys.readouterr()

    assert adaptive_memory.main(["history", "--db", str(db), "--format", "operator-json"]) == 0
    history = json.loads(capsys.readouterr().out)
    assert history["run_count"] == 1
    assert history["totals"]["hotspots"] >= 2
    assert history["latest_run"] is not None
    assert any(row["file"].endswith("big.py") for row in history["top_risk_files"])

    assert (
        adaptive_memory.main(["explain", "big.py", "--db", str(db), "--format", "operator-json"])
        == 0
    )
    explained = json.loads(capsys.readouterr().out)
    assert explained["path"] == "big.py"
    assert explained["recurring_hotspots"]

    assert adaptive_memory.main(["history", "--db", str(db)]) == 0
    assert "Runs: 1" in capsys.readouterr().out
    assert adaptive_memory.main(["explain", "app.py", "--db", str(db)]) == 0
    assert "Path: app.py" in capsys.readouterr().out


def test_adaptive_memory_history_on_empty_db(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    db = tmp_path / "fresh.db"

    assert adaptive_memory.main(["history", "--db", str(db)]) == 0
    out = capsys.readouterr().out
    assert "Runs: 0" in out
    assert "Latest: none" in out


def test_index_inspect_builds_index_for_a_repository_path(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    repo = _sample_repo(tmp_path / "repo")

    assert index.main(["inspect", str(repo), "--format", "operator-json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["counts"]["test_files"] == 1
    assert (repo / "build" / "sdetkit-index" / "index.json").is_file()
