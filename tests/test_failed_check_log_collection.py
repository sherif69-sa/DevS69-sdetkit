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
    assert manifest[logs.WORKFLOW_JOB_EVIDENCE_QUALITY_KEY]["failed_checks"] == 1
    assert manifest[logs.WORKFLOW_JOB_EVIDENCE_QUALITY_KEY]["download_script_required"] is True

    item = manifest["logs"][0]
    assert item["check_name"] == "Fast CI lane (py3.12)"
    assert item["run_id"] == "123456"
    assert item["job_id"] == "789"
    assert item["check_run_id"] == ""
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


def test_failed_check_log_collection_summarizes_workflow_job_evidence_quality(
    tmp_path: Path,
) -> None:
    existing = tmp_path / "existing.log"
    existing.write_text("existing failure log\n", encoding="utf-8")

    checks = _write_json(
        tmp_path / "check-runs.json",
        {
            "check_runs": [
                {
                    "name": "Existing log",
                    "status": "completed",
                    "conclusion": "failure",
                    "log_path": existing.as_posix(),
                },
                {
                    "name": "Actions job",
                    "status": "completed",
                    "conclusion": "failure",
                    "html_url": "https://github.com/acme/project/actions/runs/123456/job/789",
                },
                {
                    "name": "Check annotation",
                    "status": "completed",
                    "conclusion": "failure",
                    "url": "https://api.github.com/repos/acme/project/check-runs/555",
                },
                {
                    "name": "Unlinked vendor check",
                    "status": "completed",
                    "conclusion": "failure",
                },
            ]
        },
    )

    manifest = logs.write_failed_check_log_artifacts(
        checks_json=checks,
        out_dir=tmp_path / "check-logs",
    )

    quality = manifest[logs.WORKFLOW_JOB_EVIDENCE_QUALITY_KEY]
    assert quality["schema_version"] == logs.WORKFLOW_JOB_EVIDENCE_QUALITY_SCHEMA_VERSION
    assert quality["failed_checks"] == 4
    assert quality["existing_logs_collected"] == 1
    assert quality["github_actions_log_download_supported"] == 1
    assert quality["check_run_annotation_collection_supported"] == 1
    assert quality["uncollectible_failed_checks"] == 1
    assert quality["run_id_present"] == 1
    assert quality["job_id_present"] == 1
    assert quality["check_run_id_present"] == 1
    assert quality["pending_downloads"] == 2
    assert quality["download_script_required"] is True
    assert quality["evidence_gaps"] == [
        "download_script_required",
        "uncollectible_failed_checks",
        "workflow_run_metadata_missing",
        "workflow_job_metadata_missing",
        "workflow_job_steps_missing",
    ]
    assert quality["reporting_only"] is True
    assert quality["patch_application_allowed"] is False
    assert quality["automation_allowed"] is False
    assert quality["merge_authorized"] is False
    assert quality["semantic_equivalence_proven"] is False


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
    assert (
        stdout[logs.WORKFLOW_JOB_EVIDENCE_QUALITY_KEY]["github_actions_log_download_supported"] == 1
    )
    assert Path(stdout["manifest_path"]).exists()
    assert Path(stdout["download_script"]).exists()


def test_failed_check_log_collection_prefers_actions_url_over_check_run_api_url(
    tmp_path: Path,
) -> None:
    checks = _write_json(
        tmp_path / "check-runs.json",
        {
            "check_runs": [
                {
                    "name": "Fast CI lane (py3.11)",
                    "status": "completed",
                    "conclusion": "failure",
                    "url": "https://api.github.com/repos/acme/project/check-runs/76639814418",
                    "details_url": "https://github.com/acme/project/actions/runs/"
                    "26063321385/job/76628412038",
                }
            ]
        },
    )

    manifest = logs.write_failed_check_log_artifacts(
        checks_json=checks,
        out_dir=tmp_path / "check-logs",
    )

    item = manifest["logs"][0]
    assert item["url"] == "https://github.com/acme/project/actions/runs/26063321385/job/76628412038"
    assert item["run_id"] == "26063321385"
    assert item["job_id"] == "76628412038"
    assert item["download_supported"] is True

    script = Path(manifest["download_script"]).read_text(encoding="utf-8")
    assert "gh run view 26063321385 --job 76628412038 --log-failed" in script
    assert "api.github.com" not in script


def test_failed_check_log_collection_hydrates_workflow_job_steps(tmp_path: Path) -> None:
    checks = _write_json(
        tmp_path / "check-runs.json",
        {
            "check_runs": [
                {
                    "name": "Validate (ubuntu-latest / py3.11)",
                    "status": "completed",
                    "conclusion": "failure",
                    "head_sha": "head-sha",
                    "details_url": "https://github.com/acme/project/actions/runs/42/job/99",
                }
            ]
        },
    )
    out_dir = tmp_path / "check-logs"
    first = logs.write_failed_check_log_artifacts(checks_json=checks, out_dir=out_dir)
    row = first["logs"][0]
    _write_json(
        Path(row["workflow_run_path"]),
        {
            "id": 42,
            "name": "GitHub Actions Advanced Reference",
            "run_number": 7,
            "run_attempt": 1,
            "status": "completed",
            "conclusion": "failure",
            "head_sha": "head-sha",
            "html_url": "https://github.com/acme/project/actions/runs/42",
        },
    )
    _write_json(
        Path(row["workflow_job_path"]),
        {
            "id": 99,
            "run_id": 42,
            "name": "Validate (ubuntu-latest / py3.11)",
            "status": "completed",
            "conclusion": "failure",
            "head_sha": "head-sha",
            "html_url": "https://github.com/acme/project/actions/runs/42/job/99",
            "steps": [
                {"name": "Checkout", "number": 2, "status": "completed", "conclusion": "success"},
                {
                    "name": "Lint + tests",
                    "number": 6,
                    "status": "completed",
                    "conclusion": "failure",
                },
            ],
        },
    )

    second = logs.write_failed_check_log_artifacts(checks_json=checks, out_dir=out_dir)
    hydrated = json.loads(Path(second["hydrated_checks_json"]).read_text(encoding="utf-8"))
    record = hydrated["check_runs"][0]

    assert record["workflow_run"]["name"] == "GitHub Actions Advanced Reference"
    assert record["workflow_job"]["id"] == 99
    assert record["steps"][1]["name"] == "Lint + tests"
    assert record["failure_provenance_collection"]["status"] == "confirmed"
    quality = second[logs.WORKFLOW_JOB_EVIDENCE_QUALITY_KEY]
    assert quality["workflow_run_metadata_present"] == 1
    assert quality["workflow_job_metadata_present"] == 1
    assert quality["workflow_job_steps_present"] == 1
    assert "workflow_job_metadata_missing" not in quality["evidence_gaps"]
    script = Path(second["download_script"]).read_text(encoding="utf-8")
    assert 'actions/runs/42"' in script
    assert 'actions/jobs/99"' in script
