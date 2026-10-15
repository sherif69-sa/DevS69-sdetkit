"""One lockfile detector: every command recognises uv, Poetry, PDM, Pipenv and pip locks.

Before this, the readiness score demanded both requirements.lock and poetry.lock, `repo
check` accepted only poetry.lock or uv.lock, and the security gate's offline vulnerability
scan and SBOM read only requirements files, so a uv or Poetry project got no SBOM.
"""

from __future__ import annotations

import json
from pathlib import Path

from sdetkit import repo as repo_mod
from sdetkit.gates import security_gate as sg
from sdetkit.lockfiles import PinnedPackage, pinned_python_packages, python_lockfiles
from sdetkit.readiness.readiness import _check_dependency_locks

UV_LOCK = """version = 1
requires-python = ">=3.10"

[[package]]
name = "demo"
version = "0.1.0"
source = { editable = "." }
dependencies = [
    { name = "filelock" },
]

[[package]]
name = "filelock"
version = "3.18.0"
source = { registry = "https://pypi.org/simple" }

[[package]]
name = "PyYAML"
version = "6.0.3"
source = { registry = "https://pypi.org/simple" }
wheels = [
    { url = "https://example.invalid/pyyaml.whl", hash = "sha256:0" },
]

[package.optional-dependencies]
dev = [
    { name = "filelock" },
]
"""

POETRY_LOCK = """[[package]]
name = "requests"
version = "2.32.5"
description = "HTTP"

[package.dependencies]
idna = ">=2.5"

[[package]]
name = "idna"
version = "3.10"

[metadata]
lock-version = "2.1"
"""


def test_uv_lock_pins_with_lines_and_without_the_project_itself(tmp_path: Path) -> None:
    (tmp_path / "uv.lock").write_text(UV_LOCK, encoding="utf-8")

    assert pinned_python_packages(tmp_path) == [
        PinnedPackage("uv.lock", 12, "filelock", "3.18.0"),
        PinnedPackage("uv.lock", 17, "pyyaml", "6.0.3"),
    ]


def test_poetry_pdm_pipfile_and_requirements_pins(tmp_path: Path) -> None:
    (tmp_path / "poetry.lock").write_text(POETRY_LOCK, encoding="utf-8")
    (tmp_path / "pdm.lock").write_text('[[package]]\nname = "rich"\nversion = "14.1.0"\n')
    (tmp_path / "Pipfile.lock").write_text(
        json.dumps({"default": {"six": {"version": "==1.17.0"}}, "develop": {"x": {}}})
    )
    (tmp_path / "requirements.txt").write_text("# pins\nAttrs==25.3.0\nloose>=1\n")

    pins = {(p.path, p.name, p.version) for p in pinned_python_packages(tmp_path)}

    assert pins == {
        ("poetry.lock", "requests", "2.32.5"),
        ("poetry.lock", "idna", "3.10"),
        ("pdm.lock", "rich", "14.1.0"),
        ("Pipfile.lock", "six", "1.17.0"),
        ("requirements.txt", "attrs", "25.3.0"),
    }
    assert python_lockfiles(tmp_path) == ["poetry.lock", "pdm.lock", "Pipfile.lock"]


def test_any_single_lockfile_satisfies_every_command(tmp_path: Path) -> None:
    (tmp_path / "pyproject.toml").write_text("[project]\nname = 'demo'\n", encoding="utf-8")
    assert not _check_dependency_locks(tmp_path).passed
    assert "missing_python_lockfile" in {
        f.code for f in repo_mod._scan_dependency_hygiene(tmp_path, None)
    }

    (tmp_path / "uv.lock").write_text(UV_LOCK, encoding="utf-8")

    assert _check_dependency_locks(tmp_path).passed
    assert "missing_python_lockfile" not in {
        f.code for f in repo_mod._scan_dependency_hygiene(tmp_path, None)
    }


def test_security_gate_scans_and_inventories_uv_lock(tmp_path: Path) -> None:
    (tmp_path / "uv.lock").write_text(UV_LOCK, encoding="utf-8")

    vulns = sg._scan_dependency_vulns_offline(tmp_path)
    sbom = sg._generate_sbom_cyclonedx(tmp_path)

    assert [(v.rule_id, v.path, v.line) for v in vulns] == [("SEC_DEP_VULN", "uv.lock", 12)]
    assert [c["purl"] for c in sbom["components"]] == [
        "pkg:pypi/filelock@3.18.0",
        "pkg:pypi/pyyaml@6.0.3",
    ]
