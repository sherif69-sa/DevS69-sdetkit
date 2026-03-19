from __future__ import annotations

import json
from pathlib import Path

from sdetkit import doctor


def _write_minimal_pyproject(root: Path) -> None:
    (root / "pyproject.toml").write_text(
        "[project]\nname='demo'\nversion='1.0.0'\ndependencies=['httpx>=0.28.1,<1']\n",
        encoding="utf-8",
    )


def test_doctor_upgrade_audit_emits_priority_hints(tmp_path: Path, monkeypatch, capsys) -> None:
    _write_minimal_pyproject(tmp_path)
    monkeypatch.chdir(tmp_path)

    dep = doctor.upgrade_audit.Dependency(
        source="pyproject.toml",
        group="default",
        raw="httpx>=0.28.1,<1",
        name="httpx",
        pinned_version=None,
    )

    monkeypatch.setattr(
        doctor.upgrade_audit, "_discover_requirement_files", lambda *_args, **_kwargs: []
    )
    monkeypatch.setattr(doctor.upgrade_audit, "_load_dependencies", lambda *_args, **_kwargs: [dep])
    monkeypatch.setattr(
        doctor.upgrade_audit,
        "_load_project_python_requires",
        lambda *_args, **_kwargs: ">=3.11",
    )
    monkeypatch.setattr(
        doctor.upgrade_audit,
        "_collect_repo_usage",
        lambda *_args, **_kwargs: {"httpx": ["src/sdetkit/netclient.py"]},
    )
    monkeypatch.setattr(
        doctor.upgrade_audit,
        "_collect_package_metadata",
        lambda *_args, **_kwargs: {
            "httpx": doctor.upgrade_audit.PackageMetadata(
                latest_version="0.29.0",
                release_date="2026-03-01T00:00:00+00:00",
                compatible_version="0.29.0",
                compatible_release_date="2026-03-01T00:00:00+00:00",
                compatibility_status="compatible-latest",
                source="cache",
            )
        },
    )

    rc = doctor.main(["--upgrade-audit", "--json"])

    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["checks"]["upgrade_audit"]["ok"] is True
    assert payload["checks"]["upgrade_audit"]["meta"]["priority_queue"][0]["name"] == "httpx"
    assert (
        payload["checks"]["upgrade_audit"]["meta"]["lane_summary"][0]["lane"] == "refresh-baselines"
    )
    assert (
        payload["checks"]["upgrade_audit"]["meta"]["impact_summary"][0]["impact_area"]
        == "runtime-core"
    )
    assert any("httpx: raise-floor" in hint for hint in payload["hints"])
    assert any("impact runtime-core" in hint for hint in payload["hints"])
    assert any("Runtime lane follow-up" in item for item in payload["recommendations"])
    assert payload["quality"]["passed_checks"] >= 1
    assert payload["quality"]["hint_count"] == len(payload["hints"])


def test_doctor_only_upgrade_audit_reports_drift_failure(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    _write_minimal_pyproject(tmp_path)
    monkeypatch.chdir(tmp_path)

    deps = [
        doctor.upgrade_audit.Dependency(
            source="pyproject.toml",
            group="default",
            raw="httpx==0.28.1",
            name="httpx",
            pinned_version="0.28.1",
        ),
        doctor.upgrade_audit.Dependency(
            source="requirements.txt",
            group="requirements",
            raw="httpx==1.0.0",
            name="httpx",
            pinned_version="1.0.0",
        ),
    ]

    monkeypatch.setattr(
        doctor.upgrade_audit, "_discover_requirement_files", lambda *_args, **_kwargs: []
    )
    monkeypatch.setattr(doctor.upgrade_audit, "_load_dependencies", lambda *_args, **_kwargs: deps)
    monkeypatch.setattr(
        doctor.upgrade_audit, "_load_project_python_requires", lambda *_args, **_kwargs: ">=3.11"
    )
    monkeypatch.setattr(
        doctor.upgrade_audit,
        "_collect_repo_usage",
        lambda *_args, **_kwargs: {
            "httpx": ["src/sdetkit/netclient.py", "tests/test_netclient_extra.py"]
        },
    )
    monkeypatch.setattr(
        doctor.upgrade_audit,
        "_collect_package_metadata",
        lambda *_args, **_kwargs: {
            "httpx": doctor.upgrade_audit.PackageMetadata(
                latest_version="2.0.0",
                release_date="2026-03-01T00:00:00+00:00",
                compatible_version="2.0.0",
                compatible_release_date="2026-03-01T00:00:00+00:00",
                compatibility_status="compatible-latest",
                source="cache",
            )
        },
    )

    rc = doctor.main(["--only", "upgrade_audit", "--format", "json"])

    assert rc == doctor.EXIT_FAILED
    payload = json.loads(capsys.readouterr().out)
    assert payload["checks"]["upgrade_audit"]["ok"] is False
    assert payload["failed_checks"] == ["upgrade_audit"]
    assert payload["selected_checks"] == ["upgrade_audit"]
    assert payload["quality"]["failed_checks"] == 1


def test_doctor_upgrade_audit_supports_query_and_action_filters(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    _write_minimal_pyproject(tmp_path)
    monkeypatch.chdir(tmp_path)

    deps = [
        doctor.upgrade_audit.Dependency(
            source="pyproject.toml",
            group="default",
            raw="httpx>=0.28.1,<1",
            name="httpx",
            pinned_version=None,
        ),
        doctor.upgrade_audit.Dependency(
            source="pyproject.toml",
            group="dev",
            raw="mypy==1.19.1",
            name="mypy",
            pinned_version="1.19.1",
        ),
    ]

    monkeypatch.setattr(
        doctor.upgrade_audit, "_discover_requirement_files", lambda *_args, **_kwargs: []
    )
    monkeypatch.setattr(doctor.upgrade_audit, "_load_dependencies", lambda *_args, **_kwargs: deps)
    monkeypatch.setattr(
        doctor.upgrade_audit, "_load_project_python_requires", lambda *_args, **_kwargs: ">=3.11"
    )
    monkeypatch.setattr(
        doctor.upgrade_audit,
        "_collect_repo_usage",
        lambda *_args, **_kwargs: {
            "httpx": ["src/sdetkit/netclient.py"],
            "mypy": ["src/sdetkit/doctor.py"],
        },
    )
    monkeypatch.setattr(
        doctor.upgrade_audit,
        "_collect_package_metadata",
        lambda *_args, **_kwargs: {
            "httpx": doctor.upgrade_audit.PackageMetadata(
                latest_version="0.29.0",
                release_date="2026-03-01T00:00:00+00:00",
                compatible_version="0.29.0",
                compatible_release_date="2026-03-01T00:00:00+00:00",
                compatibility_status="compatible-latest",
                source="cache",
            ),
            "mypy": doctor.upgrade_audit.PackageMetadata(
                latest_version="9.0.0",
                release_date="2026-03-01T00:00:00+00:00",
                compatible_version="9.0.0",
                compatible_release_date="2026-03-01T00:00:00+00:00",
                compatibility_status="compatible-latest",
                source="cache",
            ),
        },
    )

    rc = doctor.main(
        [
            "--upgrade-audit",
            "--upgrade-audit-query",
            "quality",
            "--upgrade-audit-impact-area",
            "quality-tooling",
            "--upgrade-audit-manifest-action",
            "plan-major-upgrade",
            "--upgrade-audit-top",
            "1",
            "--format",
            "json",
        ]
    )

    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    meta = payload["checks"]["upgrade_audit"]["meta"]
    assert meta["packages_audited"] == 2
    assert meta["packages_in_scope"] == 1
    assert meta["filters"]["queries"] == ["quality"]
    assert meta["filters"]["impact_areas"] == ["quality-tooling"]
    assert meta["filters"]["manifest_actions"] == ["plan-major-upgrade"]
    assert meta["filters"]["top"] == 1
    assert meta["priority_queue"][0]["name"] == "mypy"
    assert any("mypy" in hint for hint in payload["hints"])
