from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from sdetkit import upgrade_audit


def _report(**overrides: object) -> upgrade_audit.PackageReport:
    payload: dict[str, object] = {
        "name": "pkg",
        "sources": ["pyproject.toml"],
        "groups": ["default"],
        "requirements": ["pkg==1.0.0"],
        "pinned_versions": ["1.0.0"],
        "project_python_requires": ">=3.10",
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
        "impact_area": "repo-tooling",
        "repo_usage_count": 0,
        "repo_usage_tier": "declared-only",
        "repo_usage_files": [],
        "validation_commands": ["bash ci.sh quick --skip-docs --artifact-dir build"],
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


def test_load_dependencies_collects_dependency_groups_and_include_group_entries(
    tmp_path: Path,
) -> None:
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text(
        """
[project]
dependencies = ["httpx>=0.27,<1"]

[dependency-groups]
lint = ["ruff==0.15.7"]
docs = ["mkdocs==1.6.1"]
dev = [
  {include-group = "lint"},
  {include-group = "docs"},
  "pytest==8.4.2",
]
""".strip()
        + "\n",
        encoding="utf-8",
    )

    deps = upgrade_audit._load_dependencies(pyproject, [])

    assert [(dep.group, dep.name) for dep in deps] == [
        ("default", "httpx"),
        ("lint", "ruff"),
        ("docs", "mkdocs"),
        ("dev", "ruff"),
        ("dev", "mkdocs"),
        ("dev", "pytest"),
    ]
    assert [dep.pinned_version for dep in deps[1:]] == [
        "0.15.7",
        "1.6.1",
        "0.15.7",
        "1.6.1",
        "8.4.2",
    ]


def test_load_dependencies_ignores_recursive_dependency_group_includes(tmp_path: Path) -> None:
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text(
        """
[project]
dependencies = []

[dependency-groups]
lint = [{include-group = "dev"}, "ruff==0.15.7"]
dev = [{include-group = "lint"}, "pytest==8.4.2"]
""".strip()
        + "\n",
        encoding="utf-8",
    )

    deps = upgrade_audit._load_dependencies(pyproject, [])

    assert [(dep.group, dep.name) for dep in deps] == [
        ("lint", "pytest"),
        ("lint", "ruff"),
        ("dev", "ruff"),
        ("dev", "pytest"),
    ]


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


def test_collect_repo_usage_tracks_imported_packages(tmp_path: Path) -> None:
    src_dir = tmp_path / "src" / "demo"
    src_dir.mkdir(parents=True)
    (src_dir / "init_.py").write_text("import httpx\n", encoding="utf-8")
    (src_dir / "client.py").write_text("from telegram import Bot\n", encoding="utf-8")
    tests_dir = tmp_path / "tests"
    tests_dir.mkdir()
    (tests_dir / "test_client.py").write_text("import pytest_asyncio\n", encoding="utf-8")

    usage = upgrade_audit._collect_repo_usage(
        tmp_path,
        ["httpx", "python-telegram-bot", "pytest-asyncio", "twilio"],
    )

    assert usage["httpx"] == ["src/demo/init_.py"]
    assert usage["python-telegram-bot"] == ["src/demo/client.py"]
    assert usage["pytest-asyncio"] == ["tests/test_client.py"]
    assert usage["twilio"] == []


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
    assert report.impact_area == "runtime-core"
    assert report.validation_commands == [
        "bash ci.sh quick --skip-docs --artifact-dir build",
        "bash quality.sh cov",
    ]
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
        project_python_requires=">=3.10",
        compatible_version="0.29.0",
        compatible_release_date="2026-02-01T00:00:00Z",
        compatibility_status="compatible-available",
    )

    assert report.target_version == "0.29.0"
    assert report.version_gap == "minor"
    assert report.suggested_version == "0.29.0"
    assert report.compatibility_status == "compatible-available"
    assert "using compatible target 0.29.0" in " ".join(report.notes)


def test_build_package_report_includes_repo_usage_and_risk_boost() -> None:
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
        latest_version="0.29.0",
        release_date="2026-03-01T00:00:00Z",
        repo_usage_files=[
            "src/sdetkit/apiclient.py",
            "src/sdetkit/netclient.py",
            "tests/test_apiclient.py",
            "tests/test_netclient_extra.py",
            "tests/test_apiget_request_builder.py",
        ],
    )

    assert report.repo_usage_count == 5
    assert report.repo_usage_tier == "hot-path"
    assert report.repo_usage_files[0] == "src/sdetkit/apiclient.py"
    assert report.risk_score >= 60
    assert "tier hot-path" in " ".join(report.notes)


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
            impact_area="runtime-core",
            validation_commands=[
                "bash ci.sh quick --skip-docs --artifact-dir build",
                "bash quality.sh cov",
            ],
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
            impact_area="quality-tooling",
            validation_commands=["bash quality.sh ci", "bash quality.sh cov"],
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
        "active_usage_packages": 0,
        "aging_release_packages": 0,
        "cached_metadata_packages": 1,
        "compatible_constraint_packages": 0,
        "current_release_packages": 0,
        "critical_upgrade_signals": 0,
        "declared_only_packages": 2,
        "edge_usage_packages": 0,
        "floor_lock_packages": 0,
        "fresh_release_packages": 1,
        "high_priority_upgrade_signals": 1,
        "hot_path_packages": 0,
        "integration_adapter_packages": 0,
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
        "quality_tooling_packages": 1,
        "runtime_core_packages": 1,
        "stale_release_packages": 0,
        "stale_metadata_packages": 0,
        "unknown_release_age_packages": 1,
    }
    assert payload["repo_usage"][0]["repo_usage_tier"] == "declared-only"
    assert payload["hotspots"] == []
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
        lambda package, timeout_s, project_python_requires=None, include_prereleases=False: (
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
    assert "declared-only packages: 1" in out
    assert "runtime core packages: 1" in out
    assert (
        "Impact | Repo usage | Current | Target | Latest PyPI | Py policy | Source | Gap | Alignment | Policy | Signal | Risk | Action | Suggested"
        in out
    )
    assert (
        "`httpx` | runtime-core | declared-only (0) | `0.28.1` | `0.29.0` | `0.29.0` | compatible-latest | pypi | minor | floor-lock | blocked | medium | 50 | stage-upgrade | 0.29.0 |"
        in out
    )
    assert "Priority queue" in out
    assert "Repo usage tiers" in out
    assert "Repo impact map" in out
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
        lambda package, timeout_s, project_python_requires=None, include_prereleases=False: (
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
                        "include_prereleases": False,
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
        include_prereleases: bool = False,
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
            impact_area="runtime-core",
            validation_commands=[
                "bash ci.sh quick --skip-docs --artifact-dir build",
                "bash quality.sh cov",
            ],
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
            impact_area="repo-tooling",
            validation_commands=["bash ci.sh quick --skip-docs --artifact-dir build"],
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
    assert payload["impact"][0]["impact_area"] == "runtime-core"
    assert payload["impact"][0]["validation_commands"] == [
        "bash ci.sh quick --skip-docs --artifact-dir build",
        "bash quality.sh cov",
    ]
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
            impact_area="runtime-core",
            validation_commands=[
                "bash ci.sh quick --skip-docs --artifact-dir build",
                "bash quality.sh cov",
            ],
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
    assert "## Repo hotspots" in rendered
    assert "## Repo impact map" in rendered
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


def test_latest_compatible_release_skips_prereleases_by_default() -> None:
    payload = {
        "info": {"version": "0.28.1"},
        "releases": {
            "0.28.1": [
                {
                    "upload_time_iso_8601": "2024-12-06T15:37:21.509172Z",
                    "requires_python": ">=3.8",
                }
            ],
            "1.0.dev3": [
                {
                    "upload_time_iso_8601": "2025-09-15T16:15:10.458000Z",
                    "requires_python": ">=3.10",
                }
            ],
        },
    }

    compatible_version, release_date, status = upgrade_audit._latest_compatible_release(
        payload,
        project_python_requires=">=3.10",
        include_prereleases=False,
    )

    assert compatible_version == "0.28.1"
    assert release_date == "2024-12-06T15:37:21.509172Z"
    assert status == "compatible-latest"


def test_latest_compatible_release_can_include_prereleases() -> None:
    payload = {
        "info": {"version": "0.28.1"},
        "releases": {
            "0.28.1": [
                {
                    "upload_time_iso_8601": "2024-12-06T15:37:21.509172Z",
                    "requires_python": ">=3.8",
                }
            ],
            "1.0.dev3": [
                {
                    "upload_time_iso_8601": "2025-09-15T16:15:10.458000Z",
                    "requires_python": ">=3.10",
                }
            ],
        },
    }

    compatible_version, release_date, status = upgrade_audit._latest_compatible_release(
        payload,
        project_python_requires=">=3.10",
        include_prereleases=True,
    )

    assert compatible_version == "1.0.dev3"
    assert release_date == "2025-09-15T16:15:10.458000Z"
    assert status == "compatible-available"


def test_run_respects_package_filter_without_shadowing(monkeypatch, capsys, tmp_path: Path) -> None:
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text(
        """
[project]
dependencies = ["httpx==0.28.1", "ruff==0.15.6"]
""".strip()
        + "\n",
        encoding="utf-8",
    )

    def _fake_metadata(
        package: str,
        timeout_s: float,
        project_python_requires: str | None = None,
        include_prereleases: bool = False,
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
        requirement_paths=[],
        output_format="json",
        cache_path=tmp_path / "audit-cache.json",
        packages=["ruff"],
    )

    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["summary"]["packages_audited"] == 1
    assert [item["name"] for item in payload["packages"]] == ["ruff"]


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


def test_filter_reports_supports_manifest_action_filters() -> None:
    reports = [
        _report(name="httpx", manifest_action="stage-upgrade"),
        _report(name="ruff", manifest_action="none"),
    ]

    filtered = upgrade_audit._filter_reports(reports, manifest_actions=["stage-upgrade"])

    assert [report.name for report in filtered] == ["httpx"]


def test_run_prefilters_dependency_metadata_collection(monkeypatch, tmp_path: Path) -> None:
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text(
        """
[project]
dependencies = ["httpx==0.28.1", "filelock==3.25.2"]
""".strip()
        + "\n",
        encoding="utf-8",
    )

    requested_packages: list[str] = []

    def _fake_collect(
        packages: list[str],
        *,
        timeout_s: float,
        cache_path: Path,
        cache_ttl_hours: float,
        offline: bool,
        max_workers: int,
        project_python_requires: str | None,
        include_prereleases: bool,
    ) -> dict[str, upgrade_audit.PackageMetadata]:
        requested_packages.extend(packages)
        return {
            package: upgrade_audit.PackageMetadata(
                latest_version="0.28.1" if package == "httpx" else "3.25.2",
                release_date="2026-01-01T00:00:00Z",
                compatible_version="0.28.1" if package == "httpx" else "3.25.2",
                compatible_release_date="2026-01-01T00:00:00Z",
                compatibility_status="compatible-latest",
                source="pypi",
            )
            for package in packages
        }

    monkeypatch.setattr(upgrade_audit, "_collect_package_metadata", _fake_collect)

    rc = upgrade_audit.run(
        pyproject,
        timeout_s=0.1,
        requirement_paths=[],
        output_format="json",
        packages=["http*"],
    )

    assert rc == 0
    assert requested_packages == ["httpx"]


def test_action_summary_groups_packages_by_manifest_action() -> None:
    reports = [
        _report(name="httpx", manifest_action="stage-upgrade", risk_score=50),
        _report(name="ruff", manifest_action="none", risk_score=10),
        _report(name="pytest", manifest_action="stage-upgrade", risk_score=40),
    ]

    summary = upgrade_audit._action_summary(reports)

    assert summary[0]["manifest_action"] == "stage-upgrade"
    assert summary[0]["count"] == 2
    assert summary[0]["packages"] == ["httpx", "pytest"]


def test_repo_hotspots_prioritize_actionable_shared_paths() -> None:
    reports = [
        _report(
            name="httpx",
            manifest_action="stage-upgrade",
            risk_score=60,
            repo_usage_files=["src/sdetkit/netclient.py", "src/sdetkit/doctor.py"],
            validation_commands=["bash ci.sh quick --skip-docs --artifact-dir build"],
        ),
        _report(
            name="pytest",
            manifest_action="refresh-pin",
            risk_score=50,
            repo_usage_files=["src/sdetkit/doctor.py"],
            validation_commands=["bash quality.sh ci"],
        ),
        _report(
            name="ruff",
            manifest_action="none",
            risk_score=10,
            repo_usage_files=["src/sdetkit/doctor.py"],
            validation_commands=["bash quality.sh cov"],
        ),
    ]

    hotspots = upgrade_audit._repo_hotspots(reports)

    assert hotspots[0]["path"] == "src/sdetkit/doctor.py"
    assert hotspots[0]["actionable_packages"] == 2
    assert hotspots[0]["packages"] == ["httpx", "pytest", "ruff"]
    assert hotspots[0]["validation_commands"] == [
        "bash ci.sh quick --skip-docs --artifact-dir build",
        "bash quality.sh ci",
        "bash quality.sh cov",
    ]


def test_filter_reports_supports_impact_area_filters() -> None:
    reports = [
        _report(
            name="httpx",
            impact_area="runtime-core",
            validation_commands=[
                "bash ci.sh quick --skip-docs --artifact-dir build",
                "bash quality.sh cov",
            ],
        ),
        _report(
            name="ruff",
            impact_area="quality-tooling",
            validation_commands=["bash quality.sh ci", "bash quality.sh cov"],
        ),
    ]

    filtered = upgrade_audit._filter_reports(reports, impact_areas=["quality-tooling"])

    assert [report.name for report in filtered] == ["ruff"]


def test_filter_reports_supports_repo_usage_filters() -> None:
    reports = [
        _report(name="httpx", repo_usage_count=7, repo_usage_tier="hot-path"),
        _report(name="ruff", repo_usage_count=2, repo_usage_tier="active"),
        _report(name="twilio", repo_usage_count=0, repo_usage_tier="declared-only"),
    ]

    filtered = upgrade_audit._filter_reports(
        reports,
        repo_usage_tiers=["active", "hot-path"],
        used_in_repo_only=True,
    )

    assert [report.name for report in filtered] == ["httpx", "ruff"]


def test_filter_reports_supports_text_query_across_actions_and_notes() -> None:
    reports = [
        _report(
            name="httpx",
            manifest_action="stage-upgrade",
            impact_area="runtime-core",
            next_action="Queue the upgrade for the next maintenance batch.",
            notes=["Observed in src/sdetkit/netclient.py."],
            repo_usage_files=["src/sdetkit/netclient.py"],
            validation_commands=["bash ci.sh quick --skip-docs --artifact-dir build"],
        ),
        _report(
            name="ruff",
            manifest_action="none",
            impact_area="quality-tooling",
            next_action="Keep under observation; no immediate action required.",
            notes=["Latest metadata source: cache."],
            validation_commands=["bash quality.sh ci"],
        ),
    ]

    filtered = upgrade_audit._filter_reports(
        reports,
        queries=["runtime-core", "netclient.py", "stage-upgrade"],
    )

    assert [report.name for report in filtered] == ["httpx"]


def test_filter_reports_supports_lane_and_release_freshness_filters() -> None:
    reports = [
        _report(
            name="httpx",
            manifest_action="stage-upgrade",
            upgrade_signal="medium",
            risk_score=55,
            release_age_days=5,
        ),
        _report(
            name="ruff",
            manifest_action="raise-floor",
            constraint_status="allowed",
            upgrade_signal="watch",
            risk_score=20,
            release_age_days=420,
        ),
    ]

    filtered = upgrade_audit._filter_reports(
        reports,
        lanes=["next-maintenance-batch"],
        release_freshness=["fresh-release"],
    )

    assert [report.name for report in filtered] == ["httpx"]


def test_filter_reports_supports_validation_command_filters() -> None:
    reports = [
        _report(
            name="mkdocs-material",
            validation_commands=["bash ci.sh all --artifact-dir build", "make docs-build"],
        ),
        _report(
            name="ruff",
            validation_commands=["bash quality.sh ci", "bash quality.sh cov"],
        ),
    ]

    filtered = upgrade_audit._filter_reports(
        reports,
        validation_commands=["make docs-build", "bash quality.sh *"],
    )

    assert [report.name for report in filtered] == ["mkdocs-material", "ruff"]


def test_render_json_and_markdown_include_risk_and_validation_summaries() -> None:
    reports = [
        _report(
            name="httpx",
            risk_score=88,
            manifest_action="plan-major-upgrade",
            upgrade_signal="critical",
            validation_commands=[
                "bash ci.sh quick --skip-docs --artifact-dir build",
                "bash quality.sh cov",
            ],
        ),
        _report(
            name="ruff",
            impact_area="quality-tooling",
            risk_score=42,
            manifest_action="stage-upgrade",
            upgrade_signal="medium",
            validation_commands=["bash quality.sh ci"],
        ),
    ]

    payload = json.loads(
        upgrade_audit._render_json(
            reports,
            pyproject_path=Path("pyproject.toml"),
            requirement_paths=[Path("requirements.txt")],
        )
    )
    rendered = upgrade_audit._render_markdown(
        reports,
        pyproject_path=Path("pyproject.toml"),
        requirement_paths=[Path("requirements.txt")],
    )

    assert payload["risk"][0]["risk_band"] == "critical"
    assert (
        payload["validations"][0]["command"] == "bash ci.sh quick --skip-docs --artifact-dir build"
    )
    assert "## Risk bands" in rendered
    assert "## Validation commands" in rendered


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
            "--repo-usage-tier",
            "hot-path",
            "--lane",
            "upgrade-now",
            "--validation-command",
            "bash quality.sh *",
            "--release-freshness",
            "fresh-release",
            "--query",
            "runtime-core",
            "--used-in-repo-only",
        ]
    )

    requirement_paths = upgrade_audit._resolve_requirement_paths(args)

    assert args.outdated_only is True
    assert args.package == ["http*"]
    assert args.group == ["default"]
    assert args.source == ["pyproject.toml"]
    assert args.impact_area is None
    assert args.manifest_action is None
    assert args.repo_usage_tier == ["hot-path"]
    assert args.lane == ["upgrade-now"]
    assert args.validation_command == ["bash quality.sh *"]
    assert args.release_freshness == ["fresh-release"]
    assert args.query == ["runtime-core"]
    assert args.used_in_repo_only is True
    assert args.include_prereleases is False
    assert requirement_paths == []


def test_upgrade_audit_script_wrapper_emits_json(tmp_path: Path) -> None:
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text(
        """
[project]
name = "demo"
version = "0.1.0"
dependencies = ["httpx==0.28.1"]
""".strip()
        + "\n",
        encoding="utf-8",
    )
    result = subprocess.run(
        [
            sys.executable,
            "scripts/upgrade_audit.py",
            "--pyproject",
            str(pyproject),
            "--format",
            "json",
        ],
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0
    payload = json.loads(result.stdout)
    assert payload["pyproject"] == str(pyproject)
    assert payload["packages"][0]["name"] == "httpx"
