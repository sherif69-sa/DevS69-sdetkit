from __future__ import annotations

import json
from pathlib import Path

import pytest

from sdetkit import cli, flake_hunter


def test_scan_flake_genome_pristine(tmp_path: Path) -> None:
    test_file = tmp_path / "test_clean.py"
    test_file.write_text(
        "def test_pure_logic():\n    x = 40 + 2\n    assert x == 42\n",
        encoding="utf-8",
    )

    report = flake_hunter.scan_flake_genome(test_file, root=tmp_path)

    assert report["schema_version"] == "sdetkit.flake_genome.v1"
    assert report["files_scanned"] == 1
    assert report["total_markers"] == 0
    assert report["flake_risk_score"] == 0.0
    assert report["risk_tier"] == "PRISTINE"
    assert report["verdict"] == "PASS"
    assert report["recipes"] == []


def test_scan_flake_genome_anti_patterns(tmp_path: Path) -> None:
    test_file = tmp_path / "test_dirty.py"
    test_file.write_text(
        "import time, os, random\n"
        "from datetime import datetime\n\n"
        "def test_flaky():\n"
        "    time.sleep(0.5)\n"
        "    os.environ['TEMP_FLAG'] = 'true'\n"
        "    del os.environ['TEMP_FLAG']\n"
        "    now = datetime.now()\n"
        "    val = random.choice([1, 2, 3])\n"
        "    port = 8080\n"
        "    assert val > 0\n",
        encoding="utf-8",
    )

    report = flake_hunter.scan_flake_genome(test_file, root=tmp_path)

    assert report["files_scanned"] == 1
    assert report["total_markers"] >= 5
    assert report["flake_risk_score"] >= 70.0
    assert report["risk_tier"] in ("HIGH", "CRITICAL")
    assert report["verdict"] == "REJECT"

    by_type = report["markers_by_type"]
    assert "ARBITRARY_SLEEP" in by_type
    assert "GLOBAL_STATE_MUTATION" in by_type
    assert "UNMOCKED_WALL_CLOCK" in by_type
    assert "UNSEEDED_RANDOMNESS" in by_type
    assert "PORT_COLLISION" in by_type
    assert len(report["recipes"]) >= 4


def test_scan_flake_genome_in_memory() -> None:
    code = "import time\ndef test_sleepy():\n    time.sleep(2)\n"
    report = flake_hunter.scan_flake_genome(source_code=code)
    assert report["files_scanned"] == 1
    assert report["total_markers"] == 1
    assert report["markers"][0]["type"] == "ARBITRARY_SLEEP"


def test_scan_flake_genome_syntax_error(tmp_path: Path) -> None:
    test_file = tmp_path / "test_broken.py"
    test_file.write_text("def test_broken(:\n    pass\n", encoding="utf-8")

    report = flake_hunter.scan_flake_genome(test_file, root=tmp_path)
    assert report["total_markers"] == 1
    assert report["markers"][0]["type"] == "SYNTAX_ERROR"
    assert report["verdict"] == "REJECT"


def test_render_genome_markdown(tmp_path: Path) -> None:
    test_file = tmp_path / "test_sample.py"
    test_file.write_text(
        "import time\ndef test_one(): time.sleep(1)\n",
        encoding="utf-8",
    )
    report = flake_hunter.scan_flake_genome(test_file, root=tmp_path)
    md = flake_hunter.render_genome_markdown(report)

    assert "SDETKit Flake Genome & Test Anti-Pattern Analysis" in md
    assert "Detected Anti-Pattern Markers" in md
    assert "ARBITRARY_SLEEP" in md
    assert "Prescriptive Auto-Remediation Recipes" in md


def test_genome_cli_main_formats(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    tests_dir = tmp_path / "tests"
    tests_dir.mkdir(parents=True)
    clean_test = tests_dir / "test_clean.py"
    clean_test.write_text("def test_ok(): assert 1 == 1\n", encoding="utf-8")

    # Format JSON
    rc = flake_hunter.genome_main(["--root", str(tmp_path), "--format", "json"])
    assert rc == 0
    out_json = capsys.readouterr().out
    data = json.loads(out_json)
    assert data["schema_version"] == "sdetkit.flake_genome.v1"
    assert data["risk_tier"] == "PRISTINE"

    # Format MD
    rc = flake_hunter.genome_main(["--root", str(tmp_path), "--format", "md"])
    assert rc == 0
    out_md = capsys.readouterr().out
    assert "SDETKit Flake Genome & Test Anti-Pattern Analysis" in out_md

    # Out to file
    out_file = tmp_path / "genome.json"
    rc = flake_hunter.genome_main(
        ["--root", str(tmp_path), "--out", str(out_file), "--format", "json"]
    )
    assert rc == 0
    assert out_file.exists()


def test_cli_dispatch_genome(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[tuple[str, list[str]]] = []

    def _fake_run(module_name: str, args: list[str]) -> int:
        calls.append((module_name, list(args)))
        return 0

    monkeypatch.setattr(cli, "_run_module_main", _fake_run)

    rc = cli.main(["genome", "tests/test_api.py"])
    assert rc == 0
    assert calls == [("sdetkit.flake_hunter", ["genome", "tests/test_api.py"])]

    calls.clear()
    rc_verify = cli.main(["verify", "genome", "--max-risk", "40"])
    assert rc_verify == 0
    assert calls == [("sdetkit.flake_hunter", ["--max-risk", "40"])]
