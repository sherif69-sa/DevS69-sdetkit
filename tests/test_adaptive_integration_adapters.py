from __future__ import annotations

import json
from pathlib import Path

from sdetkit import adaptive_integration_adapters
from sdetkit.cli import main as top_level_main


def _write_required(root: Path) -> dict[str, str]:
    diagnosis = root / "adaptive-diagnosis.json"
    brief = root / "operator-brief.md"
    diagnosis.write_text('{"schema_version":"sdetkit.adaptive.diagnosis.v1"}\n', encoding="utf-8")
    brief.write_text("# brief\n", encoding="utf-8")
    return {
        "adaptive_diagnosis_json": diagnosis.name,
        "operator_brief_md": brief.name,
    }


def test_integration_adapter_contract_ready_for_supported_providers(tmp_path: Path) -> None:
    artifacts = _write_required(tmp_path)

    for provider in ["github-actions", "gitlab", "jenkins", "local"]:
        payload = adaptive_integration_adapters.validate_adapter_contract(
            provider=provider, artifacts=artifacts, root=tmp_path
        )
        assert payload["ok"] is True
        assert payload["recommendation"] == "READY"
        assert payload["missing_inputs"] == []
        assert payload["outputs"]["upload_target"]


def test_integration_adapter_contract_blocks_missing_required_artifact(tmp_path: Path) -> None:
    artifacts = {"adaptive_diagnosis_json": "missing.json"}

    payload = adaptive_integration_adapters.validate_adapter_contract(
        provider="github-actions", artifacts=artifacts, root=tmp_path
    )

    assert payload["ok"] is False
    assert payload["recommendation"] == "BLOCKED"
    assert payload["missing_inputs"] == ["adaptive_diagnosis_json", "operator_brief_md"]


def test_integration_adapter_cli_and_top_level_passthrough(tmp_path: Path) -> None:
    artifacts = tmp_path / "artifacts.json"
    out = tmp_path / "adapter.json"
    artifacts.write_text(json.dumps({"artifacts": _write_required(tmp_path)}), encoding="utf-8")

    rc = top_level_main(
        [
            "adaptive",
            "integration-adapter",
            "validate",
            "--provider",
            "gitlab",
            "--artifacts",
            str(artifacts),
            "--root",
            str(tmp_path),
            "--format",
            "json",
            "--out",
            str(out),
        ]
    )

    assert rc == 0
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["provider"] == "gitlab"
    assert payload["ok"] is True
