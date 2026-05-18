from __future__ import annotations

import json
from pathlib import Path

from sdetkit import failed_check_log_collection as logs


def _write_json(path: Path, payload: dict) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def test_failed_check_log_collection_plans_github_actions_job_download(tmp_path: Path) -> None:
    checks = _write_json(
        tmp_path / "check-runs.json",
        {
            "check_runs": [
                {
                    "name": "Fast CI lane (py3.12)",
                    "status": "completed",
                    "conclusion": "failure",
                    "html_url": "https://github.com/acme/project/actions/runs/123456/job/789",
                }
            ]
        },
    )

    manifest = logs.write_failed_check_log_artifacts(
        checks_json=checks,
        out_dir=tmp_path / "check-logs",
    )

    assert manifest["schema_version"] == "sdetkit.pr_quality.failed_check_logs.v1"
    assert manifest["failed_check_count"] == 1
    assert manifest["collected_log_count"] == 0

    item = manifest["logs"][0]
    assert item["check_name"] == "Fast CI lane (py3.12)"
    assert item["run_id"] == "123456"
    assert item["job_id"] == "789"
    assert item["download_supported"] is True
    assert item["collected"] is False
    assert item["log_path"].endswith("01-fast-ci-lane-py3-12.log")

    script = Path(manifest["download_script"]).read_text(encoding="utf-8")
    assert "gh run view 123456 --job 789 --log-failed" in script
    assert "01-fast-ci-lane-py3-12.log" in script


def test_failed_check_log_collection_collects_inline_and_log_path_sources(
    tmp_path: Path,
) -> None:
    existing = tmp_path / "quality.log"
    existing.write_text("quality.sh cov failed\nerror: coverage dropped\n", encoding="utf-8")

    checks = _write_json(
        tmp_path / "check-runs.json",
        {
            "check_runs": [
                {
                    "name": "PR Quality local quality gate",
                    "status": "completed",
                    "conclusion": "failure",
                    "log_path": existing.as_posix(),
                },
                {
                    "name": "pre-commit",
                    "status": "completed",
                    "conclusion": "failure",
                    "output": "ruff format failed\n1 file reformatted\n",
                },
            ]
        },
    )

    manifest = logs.write_failed_check_log_artifacts(
        checks_json=checks,
        out_dir=tmp_path / "check-logs",
    )

    assert manifest["failed_check_count"] == 2
    assert manifest["collected_log_count"] == 2
    for item in manifest["logs"]:
        assert item["collected"] is True
        assert Path(item["log_path"]).read_text(encoding="utf-8").strip()


def test_failed_check_log_collection_cli_writes_manifest_and_script(
    tmp_path: Path,
    capsys,
) -> None:
    checks = _write_json(
        tmp_path / "check-runs.json",
        {
            "check_runs": [
                {
                    "name": "ci",
                    "status": "completed",
                    "conclusion": "failure",
                    "details_url": "https://github.com/acme/project/actions/runs/42",
                }
            ]
        },
    )

    rc = logs.main(
        [
            "--checks-json",
            str(checks),
            "--out-dir",
            str(tmp_path / "check-logs"),
        ]
    )

    assert rc == 0
    stdout = json.loads(capsys.readouterr().out)
    assert stdout["failed_check_count"] == 1
    assert Path(stdout["manifest_path"]).exists()
    assert Path(stdout["download_script"]).exists()
