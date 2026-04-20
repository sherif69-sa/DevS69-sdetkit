from __future__ import annotations

from pathlib import Path

from scripts import check_phase1_flow_contract as contract


def test_extract_doc_targets() -> None:
    text = """\n```bash\nmake a\nmake b\n```\n"""
    assert contract._extract_doc_targets(text) == ["a", "b"]


def test_main_ok_with_repo_files() -> None:
    rc = contract.main(["--format", "json"])
    assert rc == 0


def test_main_missing_inputs(tmp_path: Path) -> None:
    rc = contract.main(
        [
            "--doc",
            str(tmp_path / "missing.md"),
            "--makefile",
            str(tmp_path / "M"),
            "--format",
            "json",
        ]
    )
    assert rc == 1
