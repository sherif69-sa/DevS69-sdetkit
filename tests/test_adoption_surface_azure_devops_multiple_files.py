from __future__ import annotations

from pathlib import Path

from sdetkit.adoption_surface import discover_adoption_surface


def test_azure_devops_discovery_keeps_multiple_pipeline_files_review_first(
    tmp_path: Path,
) -> None:
    (tmp_path / "azure-pipelines.yml").write_text(
        "steps:\n  - script: python -m pytest -q\n",
        encoding="utf-8",
    )
    (tmp_path / "azure-pipelines.yaml").write_text(
        "steps:\n  - script: python -m ruff check .\n",
        encoding="utf-8",
    )

    payload = discover_adoption_surface(tmp_path)
    ci_systems = {str(item["name"]): item for item in payload["ci_systems"]}

    assert ci_systems["azure_devops"]["files"] == [
        "azure-pipelines.yaml",
        "azure-pipelines.yml",
    ]
    assert (
        "Multiple Azure DevOps pipeline files detected; active pipeline was not inferred"
        in payload["review_first_unknowns"]
    )
