from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _workflow(name: str) -> str:
    return (ROOT / ".github" / "workflows" / name).read_text(encoding="utf-8")


def test_release_workflow_installs_release_dependencies_with_constraints() -> None:
    text = _workflow("release.yml")

    assert (
        "python -m pip install -c constraints-ci.txt -r requirements-test.txt "
        "-r requirements-docs.txt -e .[packaging]"
    ) in text
    assert (
        "python -m pip install -r requirements-test.txt -r requirements-docs.txt -e .[packaging]"
    ) not in text


def test_impact_release_control_uses_least_privilege_permissions_and_constraints() -> None:
    text = _workflow("impact-release-control.yml")

    assert "\npermissions:\n  contents: read\n" in text
    assert "python -m pip install -c constraints-ci.txt -e ." in text
    assert "python -m pip install -c constraints-ci.txt -r requirements-test.txt" in text
    assert "python -m pip install --upgrade pip" not in text


def test_artifact_publish_and_governance_workflows_declare_permissions() -> None:
    for workflow_name in [
        "first-proof-artifact-publish.yml",
        "phase4-governance-contract.yml",
    ]:
        text = _workflow(workflow_name)
        assert "\npermissions:\n  contents: read\n" in text


def test_phase4_governance_contract_install_uses_constraints() -> None:
    text = _workflow("phase4-governance-contract.yml")

    assert "python -m pip install -c constraints-ci.txt -e ." in text
    assert "pip install -e ." not in text


def test_full_ci_docs_build_is_strict() -> None:
    text = _workflow("ci.yml")

    assert "NO_MKDOCS_2_WARNING=1 python -m mkdocs build --strict" in text
    assert "NO_MKDOCS_2_WARNING=1 python -m mkdocs build\n" not in text
