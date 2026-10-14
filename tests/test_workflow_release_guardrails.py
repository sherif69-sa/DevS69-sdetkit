from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _workflow(name: str) -> str:
    return (ROOT / ".github" / "workflows" / name).read_text(encoding="utf-8")


def test_release_workflow_installs_release_dependencies_with_constraints() -> None:
    text = _workflow("release.yml")
    install_step = text[
        text.index("      - name: Install release validation dependencies") : text.index(
            "      - name: Run release quality gates"
        )
    ]

    assert "python -m pip install -c constraints-ci.txt" in install_step
    assert "-r requirements-test.txt" in install_step
    assert "-r requirements-docs.txt" in install_step
    assert "-e .[packaging]" in install_step
    assert "python -m pip install -r requirements-test.txt" not in install_step


def test_full_ci_docs_build_is_strict() -> None:
    text = _workflow("ci.yml")

    assert "NO_MKDOCS_2_WARNING=1 python -m mkdocs build --strict" in text
    assert "NO_MKDOCS_2_WARNING=1 python -m mkdocs build\n" not in text


def test_active_workflows_declare_top_level_or_job_level_permissions() -> None:
    workflow_dir = ROOT / ".github" / "workflows"
    offenders = []

    for workflow_path in sorted(workflow_dir.glob("*.yml")) + sorted(workflow_dir.glob("*.yaml")):
        text = workflow_path.read_text(encoding="utf-8")
        has_top_level_permissions = any(
            line.startswith("permissions:") for line in text.splitlines()
        )
        has_job_level_permissions = any(
            line.startswith("    permissions:") for line in text.splitlines()
        )
        if not has_top_level_permissions and not has_job_level_permissions:
            offenders.append(workflow_path.name)

    assert not offenders, (
        "Active workflows must declare explicit top-level or job-level permissions "
        "so GitHub token scope is intentional:\n" + "\n".join(offenders)
    )
