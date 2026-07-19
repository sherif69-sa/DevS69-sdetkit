from __future__ import annotations

from pathlib import Path

from sdetkit.adoption_surface import discover_adoption_surface


def test_azure_devops_mapping_script_preserves_display_name_for_review_first_output(
    tmp_path: Path,
) -> None:
    (tmp_path / "azure-pipelines.yml").write_text(
        (
            "jobs:\n  - job: quality\n    steps:\n      - script: |\n"
            "          python -m pytest -q\n        displayName: Full test suite\n"
        ),
        encoding="utf-8",
    )

    payload = discover_adoption_surface(tmp_path)

    assert (
        "Azure DevOps job quality step Full test suite has multiline script content that was not guessed"
        in payload["review_first_unknowns"]
    )
