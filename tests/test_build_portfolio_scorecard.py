from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


def _run_builder(input_path: Path, output_path: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            sys.executable,
            "scripts/build_portfolio_scorecard.py",
            "--in",
            str(input_path),
            "--out",
            str(output_path),
        ],
        text=True,
        capture_output=True,
        check=False,
    )


def test_build_portfolio_scorecard_from_jsonl(tmp_path: Path) -> None:
    input_path = tmp_path / "records.jsonl"
    output_path = tmp_path / "summary.json"
    input_path.write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "repo": "repo-a",
                        "team": "team-1",
                        "lane": "scale",
                        "gate_fast_ok": True,
                        "gate_release_ok": True,
                        "doctor_ok": True,
                        "failed_steps_count": 0,
                    }
                ),
                json.dumps(
                    {
                        "repo": "repo-b",
                        "team": "team-2",
                        "lane": "regulated",
                        "gate_fast_ok": True,
                        "gate_release_ok": False,
                        "doctor_ok": True,
                        "failed_steps_count": 2,
                    }
                ),
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    result = _run_builder(input_path, output_path)

    assert result.returncode == 0, result.stderr
    summary = json.loads(output_path.read_text(encoding="utf-8"))
    assert summary["total_repos"] == 2
    assert summary["risk_counts"] == {"low": 1, "high": 1}
    assert summary["pct_low_risk"] == 50.0
    assert summary["pct_release_gate_failure"] == 50.0


def test_build_portfolio_scorecard_from_json_array(tmp_path: Path) -> None:
    input_path = tmp_path / "records.json"
    output_path = tmp_path / "summary.json"
    input_path.write_text(
        json.dumps(
            [
                {
                    "repo": "repo-c",
                    "team": "team-3",
                    "lane": "startup",
                    "gate_fast_ok": True,
                    "gate_release_ok": True,
                    "doctor_ok": False,
                    "failed_steps_count": 1,
                }
            ]
        ),
        encoding="utf-8",
    )

    result = _run_builder(input_path, output_path)

    assert result.returncode == 0, result.stderr
    summary = json.loads(output_path.read_text(encoding="utf-8"))
    assert summary["total_repos"] == 1
    assert summary["risk_counts"] == {"medium": 1}
    assert summary["pct_low_risk"] == 0.0


def test_build_portfolio_scorecard_rejects_non_list_json(tmp_path: Path) -> None:
    input_path = tmp_path / "bad.json"
    output_path = tmp_path / "summary.json"
    input_path.write_text(json.dumps({"repo": "not-a-list"}), encoding="utf-8")

    result = _run_builder(input_path, output_path)

    assert result.returncode != 0
    assert "JSON input must be a list of records" in result.stderr
