from __future__ import annotations

import json
from pathlib import Path

from sdetkit.cli import main as cli_main
from sdetkit.inspect_project import (
    audit_mock_purity,
    render_mock_purity_markdown,
    render_mock_purity_text,
    verify_mocks_main,
)
from sdetkit.safety_gate import evaluate_ship_gate


def test_clean_mocks_passes(tmp_path: Path) -> None:
    test_file = tmp_path / "test_clean.py"
    test_file.write_text(
        "from unittest.mock import Mock, patch\n\n"
        "def test_example():\n"
        "    m = Mock(spec=list)\n"
        "    m.append(1)\n"
        "    m.append.assert_called_once_with(1)\n"
        "    with patch('os.getcwd'):\n"
        "        pass\n",
        encoding="utf-8",
    )
    report = audit_mock_purity(tmp_path, targets=[str(test_file)])
    assert report["ok"] is True
    assert report["verdict"] == "PASS"
    assert report["mock_purity_score"] == 100.0
    assert report["findings_count"] == 0
    assert report["mocks_detected"] >= 1
    assert report["smell_breakdown"]["typo_assertion"] == 0


def test_detects_called_as_function(tmp_path: Path) -> None:
    test_file = tmp_path / "test_called.py"
    test_file.write_text(
        "from unittest.mock import Mock\n\n"
        "def test_bad():\n"
        "    m = Mock(spec=dict)\n"
        "    m.called()\n",
        encoding="utf-8",
    )
    report = audit_mock_purity(tmp_path, targets=[str(test_file)])
    assert report["ok"] is False
    assert report["verdict"] == "FAIL"
    assert report["smell_breakdown"]["typo_assertion"] == 1
    assert report["mock_purity_score"] <= 75.0
    findings = [f for f in report["findings"] if f["smell_type"] == "TYPO_ASSERTION"]
    assert len(findings) == 1
    assert "called" in findings[0]["symbol"]


def test_detects_uncalled_assertion_attribute(tmp_path: Path) -> None:
    test_file = tmp_path / "test_uncalled.py"
    test_file.write_text(
        "from unittest.mock import Mock\n\n"
        "def test_bare_assert():\n"
        "    m = Mock(spec=dict)\n"
        "    m.clear\n"
        "    m.assert_called_once\n",
        encoding="utf-8",
    )
    report = audit_mock_purity(tmp_path, targets=[str(test_file)])
    assert report["ok"] is False
    assert report["smell_breakdown"]["typo_assertion"] == 1
    findings = [f for f in report["findings"] if f["smell_type"] == "TYPO_ASSERTION"]
    assert len(findings) == 1
    assert findings[0]["symbol"] == "assert_called_once"


def test_detects_misspelled_assertion_method(tmp_path: Path) -> None:
    test_file = tmp_path / "test_misspelled.py"
    test_file.write_text(
        "from unittest.mock import Mock\n\n"
        "def test_misspelled():\n"
        "    m = Mock(spec=dict)\n"
        "    m.assert_called_times(1)\n",
        encoding="utf-8",
    )
    report = audit_mock_purity(tmp_path, targets=[str(test_file)])
    assert report["ok"] is False
    assert report["smell_breakdown"]["typo_assertion"] == 1
    findings = [f for f in report["findings"] if f["smell_type"] == "TYPO_ASSERTION"]
    assert len(findings) == 1
    assert "assert_called_times" in findings[0]["symbol"]


def test_detects_unspecced_mock(tmp_path: Path) -> None:
    test_file = tmp_path / "test_unspecced.py"
    test_file.write_text(
        "from unittest.mock import Mock\n\n"
        "def test_no_spec():\n"
        "    m = Mock()\n"
        "    m.some_call()\n",
        encoding="utf-8",
    )
    report = audit_mock_purity(tmp_path, targets=[str(test_file)])
    assert report["smell_breakdown"]["unspecced_mock"] == 1
    assert report["mock_purity_score"] == 90.0
    # In non-strict mode with default threshold 70, unspecced alone allows PASS
    assert report["ok"] is True

    # In strict mode, unspecced fails
    report_strict = audit_mock_purity(tmp_path, targets=[str(test_file)], strict=True)
    assert report_strict["ok"] is False
    assert report_strict["verdict"] == "FAIL"


def test_detects_leaked_patch(tmp_path: Path) -> None:
    test_file = tmp_path / "test_leaked.py"
    test_file.write_text(
        "from unittest.mock import patch\n\n"
        "def test_leak():\n"
        "    p = patch('os.getcwd')\n"
        "    p.start()\n",
        encoding="utf-8",
    )
    report = audit_mock_purity(tmp_path, targets=[str(test_file)])
    assert report["ok"] is False
    assert report["verdict"] == "FAIL"
    assert report["smell_breakdown"]["leaked_patch"] == 1
    assert report["mock_purity_score"] == 80.0


def test_proper_patch_cleanup_passes(tmp_path: Path) -> None:
    test_file = tmp_path / "test_clean_patch.py"
    test_file.write_text(
        "from unittest.mock import patch\n\n"
        "def test_cleanup():\n"
        "    p = patch('os.getcwd')\n"
        "    p.start()\n"
        "    p.stop()\n",
        encoding="utf-8",
    )
    report = audit_mock_purity(tmp_path, targets=[str(test_file)])
    assert report["smell_breakdown"]["leaked_patch"] == 0
    assert report["ok"] is True


def test_detects_dormant_mock(tmp_path: Path) -> None:
    test_file = tmp_path / "test_dormant.py"
    test_file.write_text(
        "from unittest.mock import Mock\n\ndef test_dormant():\n    unused = Mock(spec=dict)\n",
        encoding="utf-8",
    )
    report = audit_mock_purity(tmp_path, targets=[str(test_file)])
    assert report["smell_breakdown"]["dormant_mock"] == 1
    assert report["mock_purity_score"] == 95.0


def test_min_score_threshold(tmp_path: Path) -> None:
    test_file = tmp_path / "test_score.py"
    test_file.write_text(
        "from unittest.mock import Mock\n\n"
        "def test_low_score():\n"
        "    m1 = Mock()\n"
        "    m1.action()\n",
        encoding="utf-8",
    )
    report = audit_mock_purity(tmp_path, targets=[str(test_file)], min_score=95.0)
    assert report["mock_purity_score"] == 90.0
    assert report["ok"] is False
    assert report["verdict"] == "FAIL"


def test_render_outputs(tmp_path: Path) -> None:
    test_file = tmp_path / "test_render.py"
    test_file.write_text(
        "from unittest.mock import Mock\n\n"
        "def test_dummy():\n"
        "    m = Mock(spec=dict)\n"
        "    m.clear()\n",
        encoding="utf-8",
    )
    report = audit_mock_purity(tmp_path, targets=[str(test_file)])
    txt = render_mock_purity_text(report)
    md = render_mock_purity_markdown(report)
    assert "SDETKit Mock Purity Audit: verdict=PASS" in txt
    assert "# Mock Purity & Leakage Audit" in md
    assert "TYPO_ASSERTION" in md


def test_cli_execution_and_file_outputs(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    tests_dir = tmp_path / "tests"
    tests_dir.mkdir()
    (tests_dir / "test_sample.py").write_text(
        "from unittest.mock import Mock\n\n"
        "def test_ok():\n"
        "    m = Mock(spec=dict)\n"
        "    m.clear()\n",
        encoding="utf-8",
    )
    out_file = tmp_path / "mock_report.json"
    summary_file = tmp_path / "mock_summary.md"

    rc = verify_mocks_main(
        [
            "--repo-root",
            str(tmp_path),
            "--out",
            str(out_file),
            "--summary-out",
            str(summary_file),
            "--format",
            "json",
        ]
    )
    assert rc == 0
    assert out_file.exists()
    assert summary_file.exists()
    payload = json.loads(out_file.read_text(encoding="utf-8"))
    assert payload["schema_version"] == "sdetkit.mock_purity.v1"
    assert payload["ok"] is True


def test_cli_subcommand_dispatch(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    tests_dir = tmp_path / "tests"
    tests_dir.mkdir()
    (tests_dir / "test_sample.py").write_text("def test_dummy(): pass\n", encoding="utf-8")

    rc_verify_mocks = cli_main(["verify-mocks", "--repo-root", str(tmp_path)])
    assert rc_verify_mocks == 0

    rc_subcommand = cli_main(["verify", "mocks", "--repo-root", str(tmp_path)])
    assert rc_subcommand == 0


def test_safety_gate_integration(tmp_path: Path) -> None:
    tests_dir = tmp_path / "tests"
    tests_dir.mkdir()
    (tests_dir / "test_sample.py").write_text("def test_dummy(): pass\n", encoding="utf-8")

    rep = evaluate_ship_gate(
        repo_root=tmp_path,
        tier="1",
        min_mock_purity=80.0,
    )
    names = [c["name"] for c in rep.get("checks", [])]
    assert "mock_purity" in names
