from __future__ import annotations

from pathlib import Path

MUTATION_WORKFLOW = Path(".github/workflows/mutation-tests.yml")
REQUIREMENTS_TEST = Path("requirements-test.txt")


def test_mutation_workflow_uses_requirements_test_for_mutmut() -> None:
    workflow = MUTATION_WORKFLOW.read_text(encoding="utf-8")
    requirements = REQUIREMENTS_TEST.read_text(encoding="utf-8")

    assert "mutmut==3.5.0" in requirements
    assert "python -m pip install -c constraints-ci.txt -r requirements-test.txt" in workflow
    assert "python -m pip install mutmut" not in workflow
