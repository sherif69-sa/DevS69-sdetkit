from __future__ import annotations

import json
from pathlib import Path

import pytest

from sdetkit import flake_hunter


@pytest.fixture
def sample_repo(tmp_path: Path) -> Path:
    tests_dir = tmp_path / "tests"
    tests_dir.mkdir(parents=True)
    (tests_dir / "test_sample.py").write_text(
        "def test_stable(): assert True\ndef test_flake(): assert True\n",
        encoding="utf-8",
    )
    return tmp_path


def test_quarantine_add_and_list(sample_repo: Path) -> None:
    manifest = sample_repo / "quarantine.json"
    res = flake_hunter.add_to_quarantine(
        sample_repo,
        "tests/test_sample.py::test_flake",
        reason="Intermittent async race",
        ttl_days=7,
        owner="@devs69",
        issue_url="https://github.com/org/repo/issues/100",
        classification="TIMING_RACE",
        manifest_path=manifest,
    )

    assert res["ok"] is True
    assert res["test_id"] == "tests/test_sample.py::test_flake"
    assert res["file_exists"] is True
    assert res["status"] == "active"

    # List manifest
    listed = flake_hunter.list_quarantine(sample_repo, manifest_path=manifest)
    assert listed["total_count"] == 1
    assert listed["active_count"] == 1
    assert listed["expired_count"] == 0
    rec = listed["records"][0]
    assert rec["test_id"] == "tests/test_sample.py::test_flake"
    assert rec["reason"] == "Intermittent async race"
    assert rec["owner"] == "@devs69"
    assert rec["classification"] == "TIMING_RACE"
    assert rec["days_remaining"] > 0


def test_quarantine_filter_k_and_ignore(sample_repo: Path) -> None:
    manifest = sample_repo / "quarantine.json"
    flake_hunter.add_to_quarantine(
        sample_repo,
        "tests/test_sample.py::test_flake",
        manifest_path=manifest,
    )
    flake_hunter.add_to_quarantine(
        sample_repo,
        "tests/test_sample.py::test_another[param1]",
        manifest_path=manifest,
    )

    k_res = flake_hunter.filter_quarantine(sample_repo, manifest_path=manifest, mode="k")
    assert k_res["active_count"] == 2
    assert "not test_flake" in k_res["pytest_args"]
    assert "not test_another" in k_res["pytest_args"]

    ignore_res = flake_hunter.filter_quarantine(sample_repo, manifest_path=manifest, mode="ignore")
    assert "--ignore=tests/test_sample.py" in ignore_res["pytest_args"]


def test_quarantine_audit_detects_expired_and_zombies(sample_repo: Path) -> None:
    manifest = sample_repo / "quarantine.json"

    # Valid test
    flake_hunter.add_to_quarantine(
        sample_repo,
        "tests/test_sample.py::test_flake",
        manifest_path=manifest,
    )

    # Zombie test (file does not exist)
    flake_hunter.add_to_quarantine(
        sample_repo,
        "tests/test_nonexistent.py::test_missing",
        manifest_path=manifest,
    )

    # Manually backdate one entry to test expiration
    data = flake_hunter.load_quarantine(manifest)
    data["records"]["tests/test_sample.py::test_flake"]["expires_at"] = "2020-01-01T00:00:00+00:00"
    flake_hunter.save_quarantine(manifest, data)

    audit_res = flake_hunter.audit_quarantine(sample_repo, manifest_path=manifest)
    assert audit_res["active_quarantined_count"] == 2
    assert audit_res["expired_count"] == 1
    assert "tests/test_sample.py::test_flake" in audit_res["expired_tests"]
    assert audit_res["zombie_count"] == 1
    assert "tests/test_nonexistent.py::test_missing" in audit_res["zombie_tests"]
    assert audit_res["health_score"] < 100
    assert len(audit_res["recommendations"]) >= 2


def test_quarantine_shadow_run(sample_repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    manifest = sample_repo / "quarantine.json"
    flake_hunter.add_to_quarantine(
        sample_repo,
        "tests/test_sample.py::test_flake",
        manifest_path=manifest,
    )

    # Mock subprocess.run to simulate a test run
    class MockProc:
        returncode = 1
        stdout = "1 failed in 0.05s"
        stderr = ""

    monkeypatch.setattr(
        flake_hunter.subprocess,
        "run",
        lambda *args, **kwargs: MockProc(),
    )

    res = flake_hunter.shadow_run_quarantine(sample_repo, manifest_path=manifest)
    assert res["ok"] is True  # Non-blocking for CI
    assert res["executed"] is True
    assert res["test_returncode"] == 1
    assert "Shadow run executed" in res["message"]


def test_quarantine_graduate_success_and_failure(
    sample_repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    manifest = sample_repo / "quarantine.json"
    test_id = "tests/test_sample.py::test_flake"

    flake_hunter.add_to_quarantine(
        sample_repo,
        test_id,
        manifest_path=manifest,
    )

    # 1. Graduation Failure (test is still flaky)
    monkeypatch.setattr(
        flake_hunter,
        "hunt_flakes",
        lambda *args, **kwargs: {
            "flake_rate": 30.0,
            "passed_runs": 7,
            "failed_runs": 3,
            "runs_completed": 10,
        },
    )

    fail_res = flake_hunter.graduate_test(sample_repo, test_id, runs=10, manifest_path=manifest)
    assert fail_res["graduated"] is False
    assert "failed graduation check" in fail_res["message"]

    # Manifest should still show active
    listed = flake_hunter.list_quarantine(sample_repo, manifest_path=manifest)
    assert listed["records"][0]["status"] == "active"

    # 2. Graduation Success (test is now 100% stable)
    monkeypatch.setattr(
        flake_hunter,
        "hunt_flakes",
        lambda *args, **kwargs: {
            "flake_rate": 0.0,
            "passed_runs": 10,
            "failed_runs": 0,
            "runs_completed": 10,
        },
    )

    pass_res = flake_hunter.graduate_test(sample_repo, test_id, runs=10, manifest_path=manifest)
    assert pass_res["graduated"] is True
    assert "GRADUATED" in pass_res["message"]

    # Manifest should now show graduated
    data = flake_hunter.load_quarantine(manifest)
    assert data["records"][test_id]["status"] == "graduated"


def test_quarantine_cli_flow(sample_repo: Path, capsys: pytest.CaptureFixture[str]) -> None:
    manifest = sample_repo / "test_q.json"
    m_arg = str(manifest)
    root_arg = str(sample_repo)

    # CLI add
    rc = flake_hunter.main(
        [
            "quarantine",
            "add",
            "tests/test_sample.py::test_flake",
            "--reason",
            "flake test",
            "--manifest",
            m_arg,
            "--repo-root",
            root_arg,
        ]
    )
    assert rc == 0
    _ = capsys.readouterr()

    # CLI list json
    rc = flake_hunter.main(
        [
            "quarantine",
            "list",
            "--manifest",
            m_arg,
            "--repo-root",
            root_arg,
            "--format",
            "json",
        ]
    )
    assert rc == 0
    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    assert payload["total_count"] == 1

    # CLI filter
    rc = flake_hunter.main(
        [
            "quarantine",
            "filter",
            "--manifest",
            m_arg,
            "--repo-root",
            root_arg,
        ]
    )
    assert rc == 0
    captured = capsys.readouterr()
    assert "-k" in captured.out
    assert "not test_flake" in captured.out

    # CLI audit
    rc = flake_hunter.main(
        [
            "quarantine",
            "audit",
            "--manifest",
            m_arg,
            "--repo-root",
            root_arg,
        ]
    )
    assert rc == 0
    captured = capsys.readouterr()
    assert "Quarantine Audit" in captured.out


def test_quarantine_markdown_renderers() -> None:
    list_payload = {
        "total_count": 1,
        "active_count": 1,
        "expired_count": 0,
        "graduated_count": 0,
        "records": [
            {
                "status": "active",
                "test_id": "tests/test_x.py::test_1",
                "days_remaining": 5.5,
                "owner": "@alice",
                "reason": "flaky timeout",
            }
        ],
    }
    md_list = flake_hunter.render_quarantine_list_markdown(list_payload)
    assert "### SDETKit Test Quarantine Manifest" in md_list
    assert "| `ACTIVE` | `tests/test_x.py::test_1` | 5.5d | `@alice` |" in md_list

    audit_payload = {
        "health_score": 90,
        "verdict": "HEALTHY",
        "active_quarantined_count": 1,
        "expired_count": 0,
        "zombie_count": 0,
        "healthy_count": 1,
        "recommendations": ["Manifest is in prime shape."],
    }
    md_audit = flake_hunter.render_quarantine_audit_markdown(audit_payload)
    assert "SDETKit Quarantine Audit: HEALTHY (90/100)" in md_audit
