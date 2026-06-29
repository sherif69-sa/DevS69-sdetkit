from __future__ import annotations

import re
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]


def _declared_python_floor() -> str:
    pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    match = re.search(r'requires-python\s*=\s*">=(\d+\.\d+)"', pyproject)
    assert match is not None, "pyproject.toml must declare an explicit minimum Python version"
    return match.group(1)


def test_declared_python_floor_is_covered_by_first_proof_matrix() -> None:
    workflow = yaml.safe_load(
        (ROOT / ".github" / "workflows" / "first-proof.yml").read_text(encoding="utf-8")
    )
    versions = workflow["jobs"]["first-proof"]["strategy"]["matrix"]["python-version"]

    assert _declared_python_floor() in {str(version) for version in versions}
