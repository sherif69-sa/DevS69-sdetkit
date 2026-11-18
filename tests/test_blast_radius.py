from __future__ import annotations

import json
from pathlib import Path

import pytest

from sdetkit import cli
from sdetkit import dependency_map as dep_map


@pytest.fixture
def sample_repo(tmp_path: Path) -> Path:
    src = tmp_path / "src" / "sample"
    src.mkdir(parents=True)
    tests = tmp_path / "tests"
    tests.mkdir(parents=True)
    docs = tmp_path / "docs"
    docs.mkdir(parents=True)

    (src / "__init__.py").write_text("", encoding="utf-8")
    (src / "core.py").write_text("def core_fn(): return 42\n", encoding="utf-8")
    (src / "service.py").write_text(
        "from sample.core import core_fn\ndef run(): return core_fn() * 2\n",
        encoding="utf-8",
    )
    (src / "util.py").write_text("def helper(): return 'ok'\n", encoding="utf-8")

    (tests / "test_core.py").write_text(
        "from sample.core import core_fn\ndef test_c(): assert core_fn() == 42\n",
        encoding="utf-8",
    )
    (tests / "test_service.py").write_text(
        "from sample.service import run\ndef test_s(): assert run() == 84\n",
        encoding="utf-8",
    )
    (tests / "test_unrelated.py").write_text(
        "def test_u(): assert 1 == 1\n",
        encoding="utf-8",
    )

    (tmp_path / "pyproject.toml").write_text("[project]\nname = 'sample'\n", encoding="utf-8")
    (docs / "index.md").write_text("# Sample Documentation\n", encoding="utf-8")

    return tmp_path


def test_blast_radius_clean(sample_repo: Path) -> None:
    report = dep_map.evaluate_blast_radius(sample_repo, files=[])

    assert report["clean"] is True
    assert report["blast_radius_index"] == 0.0
    assert report["risk_tier"] == "LOW"
    assert report["fanout_pct"] == 0.0
    assert report["transitive_files_count"] == 0
    assert report["recommended_strategy"] == "FAST_TRACK"
    assert "clean" in report["recommendation"].lower()


def test_blast_radius_critical_infra(sample_repo: Path) -> None:
    report = dep_map.evaluate_blast_radius(sample_repo, files=["pyproject.toml"])

    assert report["clean"] is False
    assert report["critical_infra_modified"] is True
    assert report["blast_radius_index"] >= 75.0
    assert report["risk_tier"] in ("HIGH", "CRITICAL")
    assert report["recommended_strategy"] == "FULL_RELEASE_GATE"
    assert "gate release" in report["recommended_command"]


def test_blast_radius_source_impact(sample_repo: Path) -> None:
    report = dep_map.evaluate_blast_radius(sample_repo, files=["src/sample/core.py"])

    assert report["clean"] is False
    assert report["fanout_pct"] > 0.0
    assert report["impacted_sources_count"] >= 1  # service.py
    assert report["impacted_tests_count"] >= 2  # test_core.py, test_service.py
    assert "tests/test_core.py" in report["all_impacted_tests"]
    assert "tests/test_service.py" in report["all_impacted_tests"]
    assert report["test_defense_health"] in ("STRONG", "MODERATE", "ADEQUATE")


def test_blast_radius_docs_only_dampener(sample_repo: Path) -> None:
    report = dep_map.evaluate_blast_radius(sample_repo, files=["docs/index.md", "README.md"])

    assert report["clean"] is False
    assert report["blast_radius_index"] <= 5.0
    assert report["risk_tier"] == "LOW"
    assert report["recommended_strategy"] == "DOCS_FAST_LANE"
    assert "documentation" in report["recommendation"].lower()


def test_render_blast_radius_markdown(sample_repo: Path) -> None:
    clean_report = dep_map.evaluate_blast_radius(sample_repo, files=[])
    clean_md = dep_map.render_blast_radius_markdown(clean_report)
    assert "[RISK: CLEAN (0.0%)]" in clean_md

    dirty_report = dep_map.evaluate_blast_radius(sample_repo, files=["src/sample/core.py"])
    dirty_md = dep_map.render_blast_radius_markdown(dirty_report)
    assert "[RISK:" in dirty_md
    assert "Changed Files" in dirty_md
    assert "Transitive Reach" in dirty_md
    assert "Policy Decision" in dirty_md


def test_blast_radius_main_cli_json(sample_repo: Path, capsys: pytest.CaptureFixture[str]) -> None:
    rc = dep_map.blast_radius_main(
        ["--repo-root", str(sample_repo), "--files", "src/sample/core.py", "--format", "json"]
    )
    captured = capsys.readouterr()
    assert rc in (0, 1)
    data = json.loads(captured.out)
    assert data["schema_version"] == dep_map.BLAST_RADIUS_SCHEMA_VERSION
    assert "src/sample/core.py" in data["changed_files"]


def test_blast_radius_main_cli_markdown(
    sample_repo: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    rc = dep_map.blast_radius_main(
        ["--repo-root", str(sample_repo), "--files", "src/sample/core.py", "--format", "md"]
    )
    captured = capsys.readouterr()
    assert rc in (0, 1)
    assert "### [RISK:" in captured.out


def test_blast_radius_main_cli_out(sample_repo: Path, tmp_path: Path) -> None:
    out_file = tmp_path / "report.json"
    rc = dep_map.blast_radius_main(
        [
            "--repo-root",
            str(sample_repo),
            "--files",
            "src/sample/core.py",
            "--out",
            str(out_file),
        ]
    )
    assert rc in (0, 1)
    assert out_file.is_file()
    payload = json.loads(out_file.read_text(encoding="utf-8"))
    assert payload["schema_version"] == dep_map.BLAST_RADIUS_SCHEMA_VERSION


def test_cli_dispatch_blast_radius(sample_repo: Path, capsys: pytest.CaptureFixture[str]) -> None:
    rc = cli.main(
        [
            "blast-radius",
            "--repo-root",
            str(sample_repo),
            "--files",
            "docs/index.md",
            "--format",
            "json",
        ]
    )
    captured = capsys.readouterr()
    assert rc == 0
    payload = json.loads(captured.out)
    assert payload["risk_tier"] == "LOW"


def test_cli_dispatch_verify_blast_radius(
    sample_repo: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    rc = cli.main(
        [
            "verify",
            "blast-radius",
            "--repo-root",
            str(sample_repo),
            "--files",
            "docs/index.md",
            "--format",
            "json",
        ]
    )
    captured = capsys.readouterr()
    assert rc == 0
    payload = json.loads(captured.out)
    assert payload["risk_tier"] == "LOW"
