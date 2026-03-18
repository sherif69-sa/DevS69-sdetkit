from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "upgrade_audit.py"
SPEC = importlib.util.spec_from_file_location("upgrade_audit", SCRIPT_PATH)
assert SPEC is not None and SPEC.loader is not None
upgrade_audit = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = upgrade_audit
SPEC.loader.exec_module(upgrade_audit)


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

    assert report.alignment == "drift"
    assert report.upgrade_signal == "high"
    assert report.latest_version == "0.29.0"
    assert report.latest_release_date == "2026-01-01T00:00:00Z"


def test_render_json_summary_counts() -> None:
    reports = [
        upgrade_audit.PackageReport(
            name="httpx",
            sources=["pyproject.toml", "requirements.txt"],
            groups=["default", "requirements"],
            requirements=["httpx>=0.27,<1", "httpx==0.28.1"],
            pinned_versions=["0.28.1"],
            alignment="drift",
            latest_version="0.29.0",
            latest_release_date="2026-01-01T00:00:00Z",
            upgrade_signal="high",
        ),
        upgrade_audit.PackageReport(
            name="ruff",
            sources=["pyproject.toml", "requirements.txt"],
            groups=["dev", "requirements"],
            requirements=["ruff==0.15.6"],
            pinned_versions=["0.15.6"],
            alignment="aligned",
            latest_version="0.15.6",
            latest_release_date=None,
            upgrade_signal="watch",
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
        "packages_audited": 2,
        "manifest_drift_packages": 1,
        "high_priority_upgrade_signals": 1,
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
        lambda package, timeout_s: ("0.29.0", "2026-01-01T00:00:00Z"),
    )

    rc = upgrade_audit.run(
        pyproject,
        timeout_s=0.1,
        requirement_paths=[requirements],
        output_format="md",
    )

    assert rc == 0
    out = capsys.readouterr().out
    assert "# Upgrade audit" in out
    assert "manifest drift packages: 1" in out
    assert "`httpx` | drift | high | `0.29.0`" in out
