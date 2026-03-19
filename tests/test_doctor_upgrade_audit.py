from __future__ import annotations

import json
from pathlib import Path

from sdetkit import doctor


def _write_minimal_pyproject(root: Path) -> None:
    (root / "pyproject.toml").write_text(
        "[project]\nname='demo'\nversion='1.0.0'\ndependencies=['httpx>=0.28.1,<1']\n",
        encoding="utf-8",
    )


def test_doctor_upgrade_audit_emits_priority_hints(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    _write_minimal_pyproject(tmp_path)
    monkeypatch.chdir(tmp_path)

    dep = doctor.upgrade_audit.Dependency(
        source="pyproject.toml",
        group="default",
        raw="httpx>=0.28.1,<1",
        name="httpx",
        pinned_version=None,
    )

    monkeypatch.setattr(doctor.upgrade_audit, "_discover_requirement_files", lambda *_args, **_kwargs: [])
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
    assert any("httpx" in hint for hint in payload["hints"])


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

    monkeypatch.setattr(doctor.upgrade_audit, "_discover_requirement_files", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(doctor.upgrade_audit, "_load_dependencies", lambda *_args, **_kwargs: deps)
    monkeypatch.setattr(doctor.upgrade_audit, "_load_project_python_requires", lambda *_args, **_kwargs: ">=3.11")
    monkeypatch.setattr(
        doctor.upgrade_audit,
        "_collect_repo_usage",
        lambda *_args, **_kwargs: {"httpx": ["src/sdetkit/netclient.py", "tests/test_netclient_extra.py"]},
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
