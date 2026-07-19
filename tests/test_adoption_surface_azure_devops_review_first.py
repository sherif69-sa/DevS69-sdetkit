from __future__ import annotations

from pathlib import Path

from sdetkit.adoption_surface import discover_adoption_surface


def test_azure_devops_discovery_never_authorizes_actions(tmp_path: Path) -> None:
    (tmp_path / "azure-pipelines.yml").write_text(
        "steps:\n  - script: python -m pytest -q\n",
        encoding="utf-8",
    )

    payload = discover_adoption_surface(tmp_path)

    assert payload["automation_allowed"] is False
    assert payload["patch_application_allowed"] is False
    assert payload["merge_authorized"] is False
    assert payload["semantic_equivalence_proven"] is False
