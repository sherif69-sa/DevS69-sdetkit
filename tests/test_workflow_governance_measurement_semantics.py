from __future__ import annotations

from pathlib import Path

from sdetkit.workflow_governance_report import (
    analyze_workflow,
    workflow_governance_input_provenance,
)


def _write(path: Path, content: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


def test_governance_uses_canonical_local_equivalent_catalog(tmp_path: Path) -> None:
    workflow = _write(
        tmp_path / ".github" / "workflows" / "catalog-only.yml",
        """
name: catalog-only
on: [push]
permissions:
  contents: read
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@0123456789abcdef0123456789abcdef01234567
""",
    )
    catalog = _write(
        tmp_path / "docs" / "ci" / "workflow-local-equivalents.md",
        """
# Workflow local equivalents

## `.github/workflows/catalog-only.yml`

Local equivalent command:

```bash
python -m pytest -q tests/test_workflow_governance_report.py
```
""",
    )

    payload = analyze_workflow(tmp_path, workflow)
    before = workflow_governance_input_provenance(tmp_path)
    catalog.write_text(
        catalog.read_text(encoding="utf-8") + "\n# changed\n",
        encoding="utf-8",
    )
    after = workflow_governance_input_provenance(tmp_path)

    assert payload["checklist"]["local_equivalent_command_documented"] == "yes"
    assert "local_equivalent_command_documented" not in payload["findings"]
    assert before["input_count"] == before["workflow_file_count"] + 3
    assert before["input_digest"] != after["input_digest"]


def test_governance_catalog_requires_exact_workflow_section(tmp_path: Path) -> None:
    workflow = _write(
        tmp_path / ".github" / "workflows" / "missing.yml",
        """
name: missing
on: [push]
permissions:
  contents: read
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@0123456789abcdef0123456789abcdef01234567
""",
    )
    _write(
        tmp_path / "docs" / "ci" / "workflow-local-equivalents.md",
        """
## `.github/workflows/other.yml`

Local equivalent command:

```bash
python -m pytest -q
```
""",
    )

    payload = analyze_workflow(tmp_path, workflow)

    assert payload["checklist"]["local_equivalent_command_documented"] == "no"
    assert "local_equivalent_command_documented" in payload["findings"]


def test_governance_accepts_exact_public_pypi_verification(tmp_path: Path) -> None:
    workflow = _write(
        tmp_path / ".github" / "workflows" / "public-verify.yml",
        """
# Local equivalent: python -m pytest -q
name: public-verify
on: [push]
permissions:
  contents: read
jobs:
  verify:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@0123456789abcdef0123456789abcdef01234567
      - run: python -m pip install --no-cache-dir --index-url https://pypi.org/simple/ "sdetkit==1.2.0"
""",
    )

    payload = analyze_workflow(tmp_path, workflow)

    assert payload["checklist"]["install_uses_constraints"] == "yes"
    assert "install_uses_constraints" not in payload["findings"]


def test_governance_still_flags_unpinned_public_index_install(tmp_path: Path) -> None:
    workflow = _write(
        tmp_path / ".github" / "workflows" / "public-unpinned.yml",
        """
# Local equivalent: python -m pytest -q
name: public-unpinned
on: [push]
permissions:
  contents: read
jobs:
  verify:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@0123456789abcdef0123456789abcdef01234567
      - run: python -m pip install --no-cache-dir --index-url https://pypi.org/simple/ sdetkit
""",
    )

    payload = analyze_workflow(tmp_path, workflow)

    assert payload["checklist"]["install_uses_constraints"] == "no"
    assert "install_uses_constraints" in payload["findings"]


def test_governance_flags_mixed_exact_and_unpinned_public_index_install(
    tmp_path: Path,
) -> None:
    workflow = _write(
        tmp_path / ".github" / "workflows" / "public-mixed.yml",
        """
# Local equivalent: python -m pytest -q
name: public-mixed
on: [push]
permissions:
  contents: read
jobs:
  verify:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@0123456789abcdef0123456789abcdef01234567
      - run: python -m pip install --no-cache-dir --index-url https://pypi.org/simple/ sdetkit requests==2.34.2
""",
    )

    payload = analyze_workflow(tmp_path, workflow)

    assert payload["checklist"]["install_uses_constraints"] == "no"
    assert "install_uses_constraints" in payload["findings"]
