from __future__ import annotations

import json
from pathlib import Path

from sdetkit.workflow_governance_report import (
    SCHEMA_VERSION,
    analyze_workflow,
    build_workflow_governance_report,
    write_workflow_governance_report,
)


def _write(path: Path, content: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


def test_workflow_governance_detects_professional_workflow_contract(tmp_path: Path) -> None:
    workflow = _write(
        tmp_path / ".github" / "workflows" / "ci.yml",
        """
name: ci

on:
  pull_request:
  push:

permissions:
  contents: read

concurrency:
  group: ci-${{ github.workflow }}-${{ github.ref }}
  cancel-in-progress: true

jobs:
  test:
    name: quality
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@0123456789abcdef0123456789abcdef01234567
      - uses: actions/setup-python@abcdef0123456789abcdef0123456789abcdef01
      - run: python -m pip install -c constraints-ci.txt -e '.[dev,test]'
      - run: make proof-after-format
      - uses: actions/upload-artifact@1111111111111111111111111111111111111111
        with:
          name: proof
          path: build/proof
          retention-days: 7
""",
    )

    payload = analyze_workflow(tmp_path, workflow)

    assert payload["status"] == "passed"
    assert payload["checklist"]["permissions_least_privilege"] == "yes"
    assert payload["checklist"]["actions_pinned_to_sha"] == "yes"
    assert payload["checklist"]["install_uses_constraints"] == "yes"
    assert payload["checklist"]["cache_key_appropriate"] == "not_applicable"
    assert payload["checklist"]["artifacts_have_retention"] == "yes"
    assert payload["findings"] == []
    assert payload["review_first"] is True
    assert payload["safe_to_patch"] is False


def test_workflow_governance_flags_review_first_findings(tmp_path: Path) -> None:
    _write(
        tmp_path / ".github" / "workflows" / "ci.yml",
        """
name: ci
on: [pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: python -m pip install -e '.[dev,test]'
      - run: python -m mkdocs build
""",
    )

    payload = build_workflow_governance_report(tmp_path)

    assert payload["schema_version"] == SCHEMA_VERSION
    assert payload["report_status"] == "review_required"
    assert payload["workflow_count"] == 1
    assert payload["review_required_count"] == 1
    assert payload["finding_counts"]["permissions_least_privilege"] == 1
    assert payload["finding_counts"]["actions_pinned_to_sha"] == 1
    assert payload["finding_counts"]["install_uses_constraints"] == 1
    assert payload["finding_counts"]["docs_build_strict"] == 1
    assert payload["rules"]["advisory_only"] is True
    assert payload["rules"]["workflow_mutation"] is False
    assert payload["automation_allowed"] is False
    assert payload["patch_application_allowed"] is False
    assert payload["merge_authorized"] is False
    assert payload["semantic_equivalence_proven"] is False


def test_workflow_governance_writes_json_and_markdown(tmp_path: Path) -> None:
    _write(
        tmp_path / ".github" / "workflows" / "ci.yml",
        """
name: ci
on: [push]
permissions:
  contents: read
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
""",
    )
    out = tmp_path / "build" / "workflow-governance-report.json"

    payload = write_workflow_governance_report(repo_root=tmp_path, out=out)

    markdown = out.with_suffix(".md")
    assert out.is_file()
    assert markdown.is_file()
    assert json.loads(out.read_text(encoding="utf-8"))["schema_version"] == SCHEMA_VERSION
    assert "# SDETKit workflow governance report" in markdown.read_text(encoding="utf-8")
    assert payload["workflow_count"] == 1


def test_workflow_governance_cli_dispatch(tmp_path: Path, capsys) -> None:
    _write(
        tmp_path / ".github" / "workflows" / "ci.yml",
        """
name: ci
on: [push]
permissions:
  contents: read
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
""",
    )
    out = tmp_path / "build" / "workflow-governance-report.json"

    from sdetkit.cli import main as cli_main

    rc = cli_main(
        [
            "workflow-governance-report",
            "--root",
            str(tmp_path),
            "--out",
            str(out),
            "--format",
            "text",
        ]
    )

    assert rc == 0
    stdout = capsys.readouterr().out
    assert "# SDETKit workflow governance report" in stdout
    assert "workflow_mutation: false" in stdout
    assert out.is_file()
    assert out.with_suffix(".md").is_file()


def test_workflow_governance_accepts_setup_python_cache_dependency_path(tmp_path: Path) -> None:
    workflow = _write(
        tmp_path / ".github" / "workflows" / "setup-python-cache.yml",
        """
name: setup-python-cache
on: [push]
permissions:
  contents: read
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@0123456789abcdef0123456789abcdef01234567
      - uses: actions/setup-python@abcdef0123456789abcdef0123456789abcdef01
        with:
          python-version: "3.12"
          cache: "pip"
          cache-dependency-path: |
            pyproject.toml
            requirements-test.txt
            constraints-ci.txt
      - run: python -m pip install -c constraints-ci.txt -e '.[test]'
      - run: python -m pytest -q tests/test_workflow_governance_report.py -o addopts=
""",
    )

    payload = analyze_workflow(tmp_path, workflow)

    assert payload["checklist"]["cache_key_appropriate"] == "yes"
    assert "cache_key_appropriate" not in payload["findings"]


def test_workflow_governance_flags_setup_python_cache_without_dependency_path(
    tmp_path: Path,
) -> None:
    workflow = _write(
        tmp_path / ".github" / "workflows" / "setup-python-cache.yml",
        """
name: setup-python-cache
on: [push]
permissions:
  contents: read
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@0123456789abcdef0123456789abcdef01234567
      - uses: actions/setup-python@abcdef0123456789abcdef0123456789abcdef01
        with:
          python-version: "3.12"
          cache: "pip"
      - run: python -m pip install -c constraints-ci.txt -e '.[test]'
      - run: python -m pytest -q tests/test_workflow_governance_report.py -o addopts=
""",
    )

    payload = analyze_workflow(tmp_path, workflow)

    assert payload["checklist"]["cache_key_appropriate"] == "no"
    assert "cache_key_appropriate" in payload["findings"]
