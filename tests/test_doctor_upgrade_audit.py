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
    assert (
        payload["checks"]["upgrade_audit"]["meta"]["hotspots"][0]["path"]
        == "src/sdetkit/netclient.py"
    )
    assert any("httpx: raise-floor" in hint for hint in payload["hints"])
    assert any("impact runtime-core" in hint for hint in payload["hints"])
    assert any("hotspot src/sdetkit/netclient.py" in hint for hint in payload["hints"])
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
    assert meta["action_summary"][0]["manifest_action"] == "plan-major-upgrade"
    assert meta["group_summary"][0]["group"] == "dev"
    assert meta["source_summary"][0]["source"] == "pyproject.toml"
    assert any("mypy" in hint for hint in payload["hints"])


def test_doctor_upgrade_audit_supports_package_source_and_usage_filters(
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
            source="requirements-docs.txt",
            group="docs",
            raw="mkdocs-material==9.7.5",
            name="mkdocs-material",
            pinned_version="9.7.5",
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
            "httpx": ["src/sdetkit/netclient.py", "tests/test_netclient_extra.py"],
            "mkdocs-material": [],
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
                source="cache-stale",
            ),
            "mkdocs-material": doctor.upgrade_audit.PackageMetadata(
                latest_version="9.7.6",
                release_date="2026-03-01T00:00:00+00:00",
                compatible_version="9.7.6",
                compatible_release_date="2026-03-01T00:00:00+00:00",
                compatibility_status="compatible-latest",
                source="pypi",
            ),
        },
    )

    rc = doctor.main(
        [
            "--upgrade-audit",
            "--upgrade-audit-package",
            "httpx",
            "--upgrade-audit-source",
            "pyproject.toml",
            "--upgrade-audit-metadata-source",
            "cache-stale",
            "--upgrade-audit-repo-usage-tier",
            "active",
            "--upgrade-audit-used-in-repo-only",
            "--format",
            "json",
        ]
    )

    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    meta = payload["checks"]["upgrade_audit"]["meta"]
    assert meta["packages_audited"] == 2
    assert meta["packages_in_scope"] == 1
    assert meta["filters"]["packages"] == ["httpx"]
    assert meta["filters"]["sources"] == ["pyproject.toml"]
    assert meta["filters"]["metadata_sources"] == ["cache-stale"]
    assert meta["filters"]["repo_usage_tiers"] == ["active"]
    assert meta["filters"]["used_in_repo_only"] is True
    assert meta["priority_queue"][0]["name"] == "httpx"
    assert meta["source_summary"][0]["source"] == "pyproject.toml"


def test_doctor_upgrade_audit_supports_release_age_filters_and_freshness_hints(
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
            raw="ruff==0.15.6",
            name="ruff",
            pinned_version="0.15.6",
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
            "ruff": [],
        },
    )
    monkeypatch.setattr(
        doctor.upgrade_audit,
        "_collect_package_metadata",
        lambda *_args, **_kwargs: {
            "httpx": doctor.upgrade_audit.PackageMetadata(
                latest_version="0.29.0",
                release_date="2026-03-15T00:00:00+00:00",
                compatible_version="0.29.0",
                compatible_release_date="2026-03-15T00:00:00+00:00",
                compatibility_status="compatible-latest",
                source="cache",
            ),
            "ruff": doctor.upgrade_audit.PackageMetadata(
                latest_version="0.15.6",
                release_date="2025-01-01T00:00:00+00:00",
                compatible_version="0.15.6",
                compatible_release_date="2025-01-01T00:00:00+00:00",
                compatibility_status="compatible-latest",
                source="cache",
            ),
        },
    )

    rc = doctor.main(
        [
            "--upgrade-audit",
            "--upgrade-audit-max-release-age-days",
            "14",
            "--format",
            "json",
        ]
    )

    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    meta = payload["checks"]["upgrade_audit"]["meta"]
    assert meta["packages_audited"] == 2
    assert meta["packages_in_scope"] == 1
    assert meta["filters"]["max_release_age_days"] == 14
    assert meta["priority_queue"][0]["name"] == "httpx"
    assert meta["release_freshness_summary"][0]["release_freshness"] == "fresh-release"
    assert any("release freshness fresh-release" in hint for hint in payload["hints"])
    assert any("Fresh release watchlist" in item for item in payload["recommendations"])


def test_upgrade_audit_json_and_markdown_include_release_freshness_sections() -> None:
    fresh = doctor.upgrade_audit.PackageReport(
        name="ruff",
        sources=["pyproject.toml"],
        groups=["dev"],
        requirements=["ruff==0.15.6"],
        pinned_versions=["0.15.6"],
        project_python_requires=">=3.11",
        current_version="0.15.6",
        target_version="0.15.6",
        target_release_date="2026-03-15T00:00:00+00:00",
        latest_compatible_version="0.15.6",
        latest_compatible_release_date="2026-03-15T00:00:00+00:00",
        compatibility_status="compatible-latest",
        alignment="aligned",
        constraint_status="allowed",
        latest_version="0.15.6",
        latest_release_date="2026-03-15T00:00:00+00:00",
        metadata_source="cache",
        version_gap="up-to-date",
        release_age_days=4,
        upgrade_signal="watch",
        risk_score=10,
        manifest_action="none",
        suggested_version=None,
        impact_area="quality-tooling",
        repo_usage_count=0,
        repo_usage_tier="declared-only",
        repo_usage_files=[],
        validation_commands=["bash quality.sh ci"],
        next_action="Keep validating recent quality-tooling releases.",
        notes=["Latest release is fresh enough to justify a fast-follow check."],
    )
    stale = doctor.upgrade_audit.PackageReport(
        name="httpx",
        sources=["pyproject.toml"],
        groups=["default"],
        requirements=["httpx==0.28.1"],
        pinned_versions=["0.28.1"],
        project_python_requires=">=3.11",
        current_version="0.28.1",
        target_version="0.28.1",
        target_release_date="2024-01-01T00:00:00+00:00",
        latest_compatible_version="0.28.1",
        latest_compatible_release_date="2024-01-01T00:00:00+00:00",
        compatibility_status="compatible-latest",
        alignment="aligned",
        constraint_status="allowed",
        latest_version="0.28.1",
        latest_release_date="2024-01-01T00:00:00+00:00",
        metadata_source="cache",
        version_gap="up-to-date",
        release_age_days=430,
        upgrade_signal="watch",
        risk_score=12,
        manifest_action="none",
        suggested_version=None,
        impact_area="runtime-core",
        repo_usage_count=2,
        repo_usage_tier="active",
        repo_usage_files=["src/sdetkit/netclient.py"],
        validation_commands=["bash quality.sh cov"],
        next_action="Review stale runtime-core baselines on the next maintenance pass.",
        notes=["Runtime dependency baseline is aging."],
    )

    reports = [stale, fresh]
    json_payload = json.loads(
        doctor.upgrade_audit._render_json(
            reports,
            pyproject_path=Path("pyproject.toml"),
            requirement_paths=[Path("requirements.txt")],
        )
    )
    markdown_payload = doctor.upgrade_audit._render_markdown(
        reports,
        pyproject_path=Path("pyproject.toml"),
        requirement_paths=[Path("requirements.txt")],
    )

    assert json_payload["summary"]["fresh_release_packages"] == 1
    assert json_payload["summary"]["stale_release_packages"] == 1
    assert json_payload["release_freshness"][0]["release_freshness"] in {
        "fresh-release",
        "stale",
    }
    assert "## Release freshness" in markdown_payload
    assert "fresh releases (<=14d)" in markdown_payload
    assert "stale releases (>365d)" in markdown_payload


def test_doctor_upgrade_audit_supports_lane_and_release_freshness_filters(
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
            source="pyproject.toml",
            group="dev",
            raw="ruff==0.15.6",
            name="ruff",
            pinned_version="0.15.6",
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
            "ruff": ["pyproject.toml"],
        },
    )
    monkeypatch.setattr(
        doctor.upgrade_audit,
        "_collect_package_metadata",
        lambda *_args, **_kwargs: {
            "httpx": doctor.upgrade_audit.PackageMetadata(
                latest_version="1.0.0",
                release_date="2026-03-15T00:00:00+00:00",
                compatible_version="1.0.0",
                compatible_release_date="2026-03-15T00:00:00+00:00",
                compatibility_status="compatible-latest",
                source="cache",
            ),
            "ruff": doctor.upgrade_audit.PackageMetadata(
                latest_version="0.15.6",
                release_date="2024-01-01T00:00:00+00:00",
                compatible_version="0.15.6",
                compatible_release_date="2024-01-01T00:00:00+00:00",
                compatibility_status="compatible-latest",
                source="cache",
            ),
        },
    )

    rc = doctor.main(
        [
            "--only",
            "upgrade_audit",
            "--upgrade-audit",
            "--upgrade-audit-lane",
            "upgrade-now",
            "--upgrade-audit-release-freshness",
            "fresh-release",
            "--format",
            "json",
        ]
    )

    assert rc == doctor.EXIT_FAILED
    payload = json.loads(capsys.readouterr().out)
    meta = payload["checks"]["upgrade_audit"]["meta"]
    assert meta["packages_audited"] == 2
    assert meta["packages_in_scope"] == 1
    assert meta["filters"]["lanes"] == ["upgrade-now"]
    assert meta["filters"]["release_freshness"] == ["fresh-release"]
    assert meta["priority_queue"][0]["name"] == "httpx"
    assert meta["risk_summary"][0]["risk_band"] in {"critical", "high"}
    assert (
        meta["validation_summary"][0]["command"]
        == "bash ci.sh quick --skip-docs --artifact-dir build"
    )
    assert any("risk " in hint for hint in payload["hints"])
