from __future__ import annotations

import json
from pathlib import Path

from sdetkit import upgrade_audit


def _report(**overrides: object) -> upgrade_audit.PackageReport:
    payload: dict[str, object] = {
        "name": "pkg",
        "sources": ["pyproject.toml"],
        "groups": ["default"],
        "requirements": ["pkg==1.0.0"],
        "pinned_versions": ["1.0.0"],
        "project_python_requires": ">=3.11",
        "current_version": "1.0.0",
        "target_version": "1.0.0",
        "target_release_date": None,
        "latest_compatible_version": "1.0.0",
        "latest_compatible_release_date": None,
        "compatibility_status": "compatible-latest",
        "alignment": "aligned",
        "constraint_status": "allowed",
        "latest_version": "1.0.0",
        "latest_release_date": None,
        "metadata_source": "pypi",
        "version_gap": "up-to-date",
        "release_age_days": None,
        "upgrade_signal": "watch",
        "risk_score": 10,
        "manifest_action": "none",
        "suggested_version": None,
        "next_action": "Keep under observation; no immediate action required.",
        "notes": [],
    }
    payload.update(overrides)
    return upgrade_audit.PackageReport(**payload)


def test_load_dependencies_collects_pyproject_and_requirements(tmp_path: Path) -> None:
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text(
        """
[project]
dependencies = ["httpx>=0.27,<1"]

[project.optional-dependencies]
dev = ["ruff==0.15.6"]
""".strip()
        + "\n",
        encoding="utf-8",
    )
    requirements = tmp_path / "requirements.txt"
    requirements.write_text(
        """
# comment
-e .
httpx==0.28.1
ruff==0.15.6
-r nested.txt
""".strip()
        + "\n",
        encoding="utf-8",
    )

    deps = upgrade_audit._load_dependencies(pyproject, [requirements])

    assert [dep.name for dep in deps] == ["httpx", "ruff", "httpx", "ruff"]
    assert [dep.source for dep in deps] == [
        "pyproject.toml",
        "pyproject.toml",
        "requirements.txt",
        "requirements.txt",
    ]
    assert deps[0].pinned_version is None
    assert deps[1].pinned_version == "0.15.6"
    assert deps[2].pinned_version == "0.28.1"


def test_load_dependencies_follows_nested_requirement_files(tmp_path: Path) -> None:
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text("[project]\ndependencies=[]\n", encoding="utf-8")
    requirements = tmp_path / "requirements.txt"
    requirements.write_text("-r nested.txt\nhttpx==0.28.1\n", encoding="utf-8")
    nested = tmp_path / "nested.txt"
    nested.write_text("ruff==0.15.6\n", encoding="utf-8")

    deps = upgrade_audit._load_dependencies(pyproject, [requirements])

    assert [dep.name for dep in deps] == ["ruff", "httpx"]
    assert [dep.source for dep in deps] == ["nested.txt", "requirements.txt"]


def test_build_package_report_flags_drift_and_priority() -> None:
    deps = [
        upgrade_audit.Dependency(
            source="pyproject.toml",
            group="default",
            raw="httpx>=0.27,<1",
            name="httpx",
            pinned_version=None,
        ),
        upgrade_audit.Dependency(
            source="requirements.txt",
            group="requirements",
            raw="httpx==0.28.1",
            name="httpx",
            pinned_version="0.28.1",
        ),
    ]

    report = upgrade_audit._build_package_report(
        "httpx",
        deps,
        latest_version="0.29.0",
        release_date="2026-01-01T00:00:00Z",
    )

    assert report.alignment == "floor-lock"
    assert report.constraint_status == "blocked"
    assert report.current_version == "0.28.1"
    assert report.version_gap == "minor"
    assert report.upgrade_signal == "medium"
    assert report.risk_score >= 40
    assert report.latest_version == "0.29.0"
    assert report.latest_release_date == "2026-01-01T00:00:00Z"
    assert report.metadata_source == "pypi"
    assert "Queue the upgrade" in report.next_action
    assert "floor-and-lock pattern" in " ".join(report.notes)


def test_build_package_report_uses_compatible_target_when_latest_needs_newer_python() -> None:
    deps = [
        upgrade_audit.Dependency(
            source="pyproject.toml",
            group="default",
            raw="httpx==0.28.1",
            name="httpx",
            pinned_version="0.28.1",
        )
    ]

    report = upgrade_audit._build_package_report(
        "httpx",
        deps,
        latest_version="0.30.0",
        release_date="2026-03-01T00:00:00Z",
        project_python_requires=">=3.11",
        compatible_version="0.29.0",
        compatible_release_date="2026-02-01T00:00:00Z",
        compatibility_status="compatible-available",
    )

    assert report.target_version == "0.29.0"
    assert report.version_gap == "minor"
    assert report.suggested_version == "0.29.0"
    assert report.compatibility_status == "compatible-available"
    assert "using compatible target 0.29.0" in " ".join(report.notes)


def test_build_package_report_marks_compatible_policy_covered_manifests() -> None:
    deps = [
        upgrade_audit.Dependency(
            source="pyproject.toml",
            group="default",
            raw="httpx>=0.27,<1",
            name="httpx",
            pinned_version=None,
        ),
        upgrade_audit.Dependency(
            source="requirements.txt",
            group="requirements",
            raw="httpx==0.28.1",
            name="httpx",
            pinned_version="0.28.1",
        ),
    ]

    report = upgrade_audit._build_package_report(
        "httpx",
        deps,
        latest_version="0.28.1",
        release_date="2026-01-01T00:00:00Z",
    )

    assert report.alignment == "floor-lock"
    assert report.constraint_status == "allowed"
    assert report.upgrade_signal == "watch"
    assert report.manifest_action == "none"
    assert "floor-and-lock pattern" in " ".join(report.notes)
    assert "already allowed by the declared version policy" in " ".join(report.notes)


def test_build_package_report_flags_major_jump_as_critical() -> None:
    deps = [
        upgrade_audit.Dependency(
            source="pyproject.toml",
            group="default",
            raw="httpx==0.28.1",
            name="httpx",
            pinned_version="0.28.1",
        )
    ]

    report = upgrade_audit._build_package_report(
        "httpx",
        deps,
        latest_version="1.1.0",
        release_date="2026-01-01T00:00:00Z",
    )

    assert report.current_version == "0.28.1"
    assert report.version_gap == "major"
    assert report.upgrade_signal == "high"
    assert report.risk_score >= 45
    assert any("major-version jump" in note for note in report.notes)


def test_render_json_summary_counts() -> None:
    reports = [
        _report(
            name="httpx",
            sources=["pyproject.toml", "requirements.txt"],
            groups=["default", "requirements"],
            requirements=["httpx>=0.27,<1", "httpx==0.28.1"],
            pinned_versions=["0.28.1"],
            current_version="0.28.1",
            target_version="0.29.0",
            target_release_date="2026-01-01T00:00:00Z",
            latest_compatible_version="0.29.0",
            latest_compatible_release_date="2026-01-01T00:00:00Z",
            compatibility_status="compatible-latest",
            alignment="drift",
            constraint_status="blocked",
            latest_version="0.29.0",
            latest_release_date="2026-01-01T00:00:00Z",
            metadata_source="pypi",
            version_gap="minor",
            release_age_days=0,
            upgrade_signal="high",
            risk_score=85,
            manifest_action="stage-upgrade",
            suggested_version="0.29.0",
            next_action="Plan an upgrade spike with regression coverage before the next release cut.",
            notes=["Cross-manifest requirement drift detected."],
        ),
        _report(
            name="ruff",
            sources=["pyproject.toml", "requirements.txt"],
            groups=["dev", "requirements"],
            requirements=["ruff==0.15.6"],
            pinned_versions=["0.15.6"],
            current_version="0.15.6",
            alignment="aligned",
            constraint_status="allowed",
            latest_version="0.15.6",
            latest_release_date=None,
            metadata_source="cache",
            version_gap="up-to-date",
            release_age_days=None,
            upgrade_signal="watch",
            risk_score=10,
            manifest_action="none",
            suggested_version=None,
            next_action="Keep under observation; no immediate action required.",
            notes=[],
        ),
    ]

    payload = json.loads(
        upgrade_audit._render_json(
            reports,
            pyproject_path=Path("pyproject.toml"),
            requirement_paths=[Path("requirements.txt")],
        )
    )

    assert payload["summary"] == {
        "actionable_packages": 1,
        "cached_metadata_packages": 1,
        "compatible_constraint_packages": 0,
        "critical_upgrade_signals": 0,
        "floor_lock_packages": 0,
        "high_priority_upgrade_signals": 1,
        "investigate_upgrade_signals": 0,
        "manifest_drift_packages": 1,
        "max_risk_score": 85,
        "medium_priority_upgrade_signals": 0,
        "packages_audited": 2,
        "policy_blocked_packages": 1,
        "policy_covered_packages": 1,
        "python_compatible_fallback_packages": 0,
        "python_compatible_latest_packages": 2,
        "python_incompatible_latest_packages": 0,
        "stale_metadata_packages": 0,
    }
    assert payload["packages"][0]["name"] == "httpx"


def test_run_renders_markdown_without_network(monkeypatch, capsys, tmp_path: Path) -> None:
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text(
        """
[project]
dependencies = ["httpx>=0.27,<1"]
""".strip()
        + "\n",
        encoding="utf-8",
    )
    requirements = tmp_path / "requirements.txt"
    requirements.write_text("httpx==0.28.1\n", encoding="utf-8")

    monkeypatch.setattr(
        upgrade_audit,
        "_latest_pypi_metadata",
        lambda package, timeout_s, project_python_requires=None: (
            "0.29.0",
            "2026-01-01T00:00:00Z",
            "0.29.0",
            "2026-01-01T00:00:00Z",
            "compatible-latest",
        ),
    )

    rc = upgrade_audit.run(
        pyproject,
        timeout_s=0.1,
        requirement_paths=[requirements],
        output_format="md",
        cache_path=tmp_path / "audit-cache.json",
    )

    assert rc == 0
    out = capsys.readouterr().out
    assert "# Upgrade audit" in out
    assert "manifest drift packages: 0" in out
    assert "compatible multi-manifest packages: 0" in out
    assert "floor-and-lock baseline packages: 1" in out
    assert "packages using cached metadata: 0" in out
    assert "stale cached metadata packages: 0" in out
    assert "latest releases compatible with repo Python policy: 1" in out
    assert "actionable upgrade candidates: 1" in out
    assert "Current | Target | Latest PyPI | Py policy | Source | Gap | Alignment | Policy | Signal | Risk | Action | Suggested" in out
    assert "`httpx` | `0.28.1` | `0.29.0` | `0.29.0` | compatible-latest | pypi | minor | floor-lock | blocked | medium | 50 | stage-upgrade | 0.29.0 |" in out
    assert "Priority queue" in out
    assert "Focus notes" in out
    assert (
        "Queue the upgrade for the next maintenance batch and validate targeted smoke tests." in out
    )


def test_run_returns_failure_when_signal_threshold_is_met(monkeypatch, tmp_path: Path) -> None:
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text(
        """
[project]
dependencies = ["httpx>=0.27,<1"]
""".strip()
        + "\n",
        encoding="utf-8",
    )
    requirements = tmp_path / "requirements.txt"
    requirements.write_text("httpx==0.28.1\n", encoding="utf-8")

    monkeypatch.setattr(
        upgrade_audit,
        "_latest_pypi_metadata",
        lambda package, timeout_s, project_python_requires=None: (
            "1.0.0",
            "2026-01-01T00:00:00Z",
            "1.0.0",
            "2026-01-01T00:00:00Z",
            "compatible-latest",
        ),
    )

    rc = upgrade_audit.run(
        pyproject,
        timeout_s=0.1,
        requirement_paths=[requirements],
        output_format="json",
        fail_on="high",
        cache_path=tmp_path / "audit-cache.json",
    )

    assert rc == 1


def test_sort_reports_surfaces_highest_risk_first() -> None:
    reports = [
        _report(
            name="watch-pkg",
            sources=["requirements.txt"],
            groups=["requirements"],
            requirements=["watch-pkg==1.0.0"],
            pinned_versions=["1.0.0"],
            current_version="1.0.0",
            alignment="aligned",
            constraint_status="blocked",
            latest_version="1.0.1",
            latest_release_date=None,
            metadata_source="pypi",
            version_gap="patch",
            release_age_days=None,
            upgrade_signal="watch",
            risk_score=10,
            manifest_action="stage-upgrade",
            suggested_version="1.0.1",
            next_action="Track the package and batch it with nearby dependency maintenance work.",
            notes=[],
        ),
        _report(
            name="critical-pkg",
            sources=["pyproject.toml", "requirements.txt"],
            groups=["default", "requirements"],
            requirements=["critical-pkg>=1,<2", "critical-pkg==1.2.3"],
            pinned_versions=["1.2.3"],
            current_version="1.2.3",
            alignment="drift",
            constraint_status="blocked",
            latest_version="2.0.0",
            latest_release_date=None,
            metadata_source="pypi",
            version_gap="major",
            release_age_days=None,
            upgrade_signal="critical",
            risk_score=90,
            manifest_action="plan-major-upgrade",
            suggested_version="2.0.0",
            next_action="Resolve manifest drift first, then validate the major upgrade in a dedicated branch.",
            notes=[],
        ),
    ]

    sorted_reports = upgrade_audit._sort_reports(reports)

    assert [report.name for report in sorted_reports] == ["critical-pkg", "watch-pkg"]


def test_run_uses_cache_in_offline_mode(capsys, tmp_path: Path) -> None:
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text(
        """
[project]
dependencies = ["httpx==0.28.1"]
""".strip()
        + "\n",
        encoding="utf-8",
    )
    cache_path = tmp_path / "cache.json"
    cache_path.write_text(
        json.dumps(
            {
                "generated_at": "2026-01-02T00:00:00+00:00",
                "packages": {
                    "httpx": {
                        "fetched_at": 1_767_000_000.0,
                        "latest_version": "0.28.1",
                        "release_date": "2026-01-01T00:00:00Z",
                        "compatible_version": "0.28.1",
                        "compatible_release_date": "2026-01-01T00:00:00Z",
                        "compatibility_status": "compatible-latest",
                    }
                },
            }
        ),
        encoding="utf-8",
    )

    rc = upgrade_audit.run(
        pyproject,
        timeout_s=0.1,
        requirement_paths=[],
        output_format="json",
        offline=True,
        cache_path=cache_path,
        cache_ttl_hours=9999,
    )

    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["summary"]["cached_metadata_packages"] == 1
    assert payload["summary"]["stale_metadata_packages"] == 0
    assert payload["packages"][0]["latest_version"] == "0.28.1"
    assert payload["packages"][0]["metadata_source"] == "cache"
    assert "Latest metadata source: cache." in payload["packages"][0]["notes"]


def test_filter_reports_supports_package_metadata_source_and_outdated_only() -> None:
    reports = [
        _report(
            name="httpx",
            sources=["pyproject.toml"],
            groups=["default"],
            requirements=["httpx==0.28.1"],
            pinned_versions=["0.28.1"],
            current_version="0.28.1",
            target_version="0.29.0",
            target_release_date="2026-01-01T00:00:00Z",
            latest_compatible_version="0.29.0",
            latest_compatible_release_date="2026-01-01T00:00:00Z",
            compatibility_status="compatible-latest",
            alignment="aligned",
            constraint_status="blocked",
            latest_version="0.29.0",
            latest_release_date="2026-01-01T00:00:00Z",
            metadata_source="cache-stale",
            version_gap="minor",
            release_age_days=0,
            upgrade_signal="medium",
            risk_score=55,
            manifest_action="stage-upgrade",
            suggested_version="0.29.0",
            next_action="Queue the upgrade for the next maintenance batch and validate targeted smoke tests.",
            notes=[],
        ),
        _report(
            name="ruff",
            sources=["requirements.txt"],
            groups=["requirements"],
            requirements=["ruff==0.15.6"],
            pinned_versions=["0.15.6"],
            current_version="0.15.6",
            alignment="aligned",
            constraint_status="allowed",
            latest_version="0.15.6",
            latest_release_date=None,
            metadata_source="pypi",
            version_gap="up-to-date",
            release_age_days=None,
            upgrade_signal="watch",
            risk_score=10,
            manifest_action="none",
            suggested_version=None,
            next_action="Keep under observation; no immediate action required.",
            notes=[],
        ),
    ]

    filtered = upgrade_audit._filter_reports(
        reports,
        packages=["http*"],
        metadata_sources=["cache-stale"],
        outdated_only=True,
    )

    assert [report.name for report in filtered] == ["httpx"]


def test_filter_reports_supports_signal_policy_and_top() -> None:
    reports = [
        _report(
            name="critical-pkg",
            sources=["pyproject.toml"],
            groups=["default"],
            requirements=["critical-pkg==1.0.0"],
            pinned_versions=["1.0.0"],
            current_version="1.0.0",
            target_version="2.0.0",
            target_release_date="2026-01-01T00:00:00Z",
            latest_compatible_version="2.0.0",
            latest_compatible_release_date="2026-01-01T00:00:00Z",
            compatibility_status="compatible-latest",
            alignment="aligned",
            constraint_status="blocked",
            latest_version="2.0.0",
            latest_release_date="2026-01-01T00:00:00Z",
            metadata_source="pypi",
            version_gap="major",
            release_age_days=0,
            upgrade_signal="high",
            risk_score=80,
            manifest_action="plan-major-upgrade",
            suggested_version="2.0.0",
            next_action="Plan an upgrade spike with regression coverage before the next release cut.",
            notes=[],
        ),
        _report(
            name="watch-pkg",
            sources=["requirements.txt"],
            groups=["requirements"],
            requirements=["watch-pkg==1.0.0"],
            pinned_versions=["1.0.0"],
            current_version="1.0.0",
            alignment="aligned",
            constraint_status="allowed",
            latest_version="1.0.1",
            latest_release_date=None,
            metadata_source="cache",
            version_gap="patch",
            release_age_days=None,
            upgrade_signal="watch",
            risk_score=10,
            manifest_action="none",
            suggested_version=None,
            next_action="Keep under observation; no immediate action required.",
            notes=[],
        ),
    ]

    filtered = upgrade_audit._filter_reports(
        reports,
        signals=["high", "critical"],
        policies=["blocked"],
        top=1,
    )

    assert [report.name for report in filtered] == ["critical-pkg"]


def test_run_applies_signal_policy_and_top_filters(monkeypatch, capsys, tmp_path: Path) -> None:
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text(
        """
[project]
dependencies = ["httpx>=0.27,<1", "ruff==0.15.6"]
""".strip()
        + "\n",
        encoding="utf-8",
    )
    requirements = tmp_path / "requirements.txt"
    requirements.write_text("httpx==0.28.1\nruff==0.15.6\n", encoding="utf-8")

    def _fake_metadata(
        package: str,
        timeout_s: float,
        project_python_requires: str | None = None,
    ) -> tuple[str, str | None, str | None, str | None, str]:
        if package == "httpx":
            return (
                "0.29.0",
                "2026-01-01T00:00:00Z",
                "0.29.0",
                "2026-01-01T00:00:00Z",
                "compatible-latest",
            )
        return (
            "0.15.6",
            "2026-01-01T00:00:00Z",
            "0.15.6",
            "2026-01-01T00:00:00Z",
            "compatible-latest",
        )

    monkeypatch.setattr(upgrade_audit, "_latest_pypi_metadata", _fake_metadata)

    rc = upgrade_audit.run(
        pyproject,
        timeout_s=0.1,
        requirement_paths=[requirements],
        output_format="json",
        cache_path=tmp_path / "audit-cache.json",
        signals=["medium"],
        policies=["blocked"],
        top=1,
    )

    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["summary"]["packages_audited"] == 1
    assert payload["priority_queue"][0]["name"] == "httpx"
    assert [item["name"] for item in payload["packages"]] == ["httpx"]


def test_render_json_includes_lane_summary_and_priority_lane() -> None:
    reports = [
        _report(
            name="critical-pkg",
            sources=["pyproject.toml", "requirements.txt"],
            groups=["default", "requirements"],
            requirements=["critical-pkg>=1,<2", "critical-pkg==1.2.3"],
            pinned_versions=["1.2.3"],
            current_version="1.2.3",
            target_version="2.0.0",
            target_release_date="2026-01-01T00:00:00Z",
            latest_compatible_version="2.0.0",
            latest_compatible_release_date="2026-01-01T00:00:00Z",
            compatibility_status="compatible-latest",
            alignment="drift",
            constraint_status="blocked",
            latest_version="2.0.0",
            latest_release_date="2026-01-01T00:00:00Z",
            metadata_source="pypi",
            version_gap="major",
            release_age_days=0,
            upgrade_signal="critical",
            risk_score=90,
            manifest_action="plan-major-upgrade",
            suggested_version="2.0.0",
            next_action="Resolve manifest drift first, then validate the major upgrade in a dedicated branch.",
            notes=["Cross-manifest requirement drift detected."],
        ),
        _report(
            name="watch-pkg",
            sources=["requirements.txt"],
            groups=["requirements"],
            requirements=["watch-pkg==1.0.0"],
            pinned_versions=["1.0.0"],
            current_version="1.0.0",
            alignment="aligned",
            constraint_status="allowed",
            latest_version="1.0.1",
            latest_release_date=None,
            metadata_source="cache",
            version_gap="patch",
            release_age_days=None,
            upgrade_signal="watch",
            risk_score=10,
            manifest_action="none",
            suggested_version=None,
            next_action="Keep under observation; no immediate action required.",
            notes=["Latest metadata source: cache."],
        ),
    ]

    payload = json.loads(
        upgrade_audit._render_json(
            reports,
            pyproject_path=Path("pyproject.toml"),
            requirement_paths=[Path("requirements.txt")],
        )
    )

    assert payload["priority_queue"][0]["lane"] == "stabilize-manifests"
    assert payload["lanes"][0]["lane"] == "stabilize-manifests"
    assert payload["lanes"][0]["packages"] == ["critical-pkg"]
    assert payload["groups"][0]["group"] == "requirements"
    assert payload["groups"][0]["actionable_packages"] == 1
    assert payload["sources"][0]["source"] == "requirements.txt"
    assert payload["sources"][0]["count"] == 2


def test_render_markdown_includes_recommended_upgrade_lanes() -> None:
    reports = [
        _report(
            name="httpx",
            sources=["pyproject.toml", "requirements.txt"],
            groups=["default", "requirements"],
            requirements=["httpx>=0.27,<1", "httpx==0.28.1"],
            pinned_versions=["0.28.1"],
            current_version="0.28.1",
            target_version="0.29.0",
            target_release_date="2026-01-01T00:00:00Z",
            latest_compatible_version="0.29.0",
            latest_compatible_release_date="2026-01-01T00:00:00Z",
            compatibility_status="compatible-latest",
            alignment="compatible",
            constraint_status="blocked",
            latest_version="0.29.0",
            latest_release_date="2026-01-01T00:00:00Z",
            metadata_source="pypi",
            version_gap="minor",
            release_age_days=0,
            upgrade_signal="medium",
            risk_score=55,
            manifest_action="stage-upgrade",
            suggested_version="0.29.0",
            next_action="Queue the upgrade for the next maintenance batch and validate targeted smoke tests.",
            notes=["Cross-manifest requirements differ but remain mutually compatible."],
        )
    ]

    rendered = upgrade_audit._render_markdown(
        reports,
        pyproject_path=Path("pyproject.toml"),
        requirement_paths=[Path("requirements.txt")],
    )

    assert "## Recommended upgrade lanes" in rendered
    assert "## Dependency groups" in rendered
    assert "## Manifest sources" in rendered
    assert "**next-maintenance-batch**" in rendered


def test_run_applies_package_metadata_source_and_outdated_filters(
    monkeypatch, capsys, tmp_path: Path
) -> None:
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text(
        """
[project]
dependencies = ["httpx==0.28.1", "ruff==0.15.6"]
""".strip()
        + "\n",
        encoding="utf-8",
    )
    cache_path = tmp_path / "cache.json"
    cache_path.write_text(
        json.dumps(
            {
                "generated_at": "2026-01-02T00:00:00+00:00",
                "packages": {
                    "httpx": {
                        "fetched_at": 1.0,
                        "latest_version": "0.29.0",
                        "release_date": "2026-01-01T00:00:00Z",
                        "compatible_version": "0.29.0",
                        "compatible_release_date": "2026-01-01T00:00:00Z",
                        "compatibility_status": "compatible-latest",
                    },
                    "ruff": {
                        "fetched_at": 1.0,
                        "latest_version": "0.15.6",
                        "release_date": "2026-01-01T00:00:00Z",
                        "compatible_version": "0.15.6",
                        "compatible_release_date": "2026-01-01T00:00:00Z",
                        "compatibility_status": "compatible-latest",
                    },
                },
            }
        ),
        encoding="utf-8",
    )

    rc = upgrade_audit.run(
        pyproject,
        timeout_s=0.1,
        requirement_paths=[],
        output_format="json",
        offline=True,
        cache_path=cache_path,
        cache_ttl_hours=0,
        packages=["http*"],
        metadata_sources=["cache-stale"],
        outdated_only=True,
    )

    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["summary"]["packages_audited"] == 1
    assert payload["summary"]["stale_metadata_packages"] == 1
    assert payload["summary"]["actionable_packages"] == 1
    assert [item["name"] for item in payload["packages"]] == ["httpx"]


def test_filter_reports_supports_group_and_source_filters() -> None:
    reports = [
        _report(
            name="httpx",
            sources=["pyproject.toml", "requirements.txt"],
            groups=["default", "requirements"],
            requirements=["httpx==0.28.1"],
            pinned_versions=["0.28.1"],
            current_version="0.28.1",
            target_version="0.29.0",
            target_release_date="2026-01-01T00:00:00Z",
            latest_compatible_version="0.29.0",
            latest_compatible_release_date="2026-01-01T00:00:00Z",
            compatibility_status="compatible-latest",
            alignment="aligned",
            constraint_status="blocked",
            latest_version="0.29.0",
            latest_release_date="2026-01-01T00:00:00Z",
            metadata_source="pypi",
            version_gap="minor",
            release_age_days=0,
            upgrade_signal="medium",
            risk_score=55,
            manifest_action="stage-upgrade",
            suggested_version="0.29.0",
            next_action="Queue the upgrade for the next maintenance batch and validate targeted smoke tests.",
            notes=[],
        ),
        _report(
            name="mkdocs",
            sources=["requirements-docs.txt"],
            groups=["docs"],
            requirements=["mkdocs==1.6.1"],
            pinned_versions=["1.6.1"],
            current_version="1.6.1",
            alignment="aligned",
            constraint_status="allowed",
            latest_version="1.6.1",
            latest_release_date=None,
            metadata_source="cache",
            version_gap="up-to-date",
            release_age_days=None,
            upgrade_signal="watch",
            risk_score=10,
            manifest_action="none",
            suggested_version=None,
            next_action="Keep under observation; no immediate action required.",
            notes=[],
        ),
    ]

    filtered = upgrade_audit._filter_reports(
        reports,
        groups=["default"],
        sources=["requirements.txt"],
    )

    assert [report.name for report in filtered] == ["httpx"]


def test_resolve_requirement_paths_supports_outdated_only_cli_defaults(tmp_path: Path) -> None:
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text("[project]\ndependencies=[]\n", encoding="utf-8")

    parser = upgrade_audit.build_parser()
    args = parser.parse_args(
        [
            "--pyproject",
            str(pyproject),
            "--outdated-only",
            "--package",
            "http*",
            "--group",
            "default",
            "--source",
            "pyproject.toml",
        ]
    )

    requirement_paths = upgrade_audit._resolve_requirement_paths(args)

    assert args.outdated_only is True
    assert args.package == ["http*"]
    assert args.group == ["default"]
    assert args.source == ["pyproject.toml"]
    assert requirement_paths == []
