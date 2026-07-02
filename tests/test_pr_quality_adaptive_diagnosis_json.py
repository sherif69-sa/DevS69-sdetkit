from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

MODULE_PATH = (
    Path(__file__).resolve().parents[1] / "tools" / "export_pr_quality_adaptive_diagnosis_json.py"
)
SPEC = importlib.util.spec_from_file_location("adaptive_diagnosis_json", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
exporter = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(exporter)


def _card() -> dict[str, object]:
    return {
        "status": "review_first",
        "failure_class": "test",
        "diagnostic_completeness": "complete",
        "confidence": "high",
        "checks": {
            "exact_failure_detail_present": True,
            "authority_boundary_preserved": True,
        },
        "owner_files": ["docs/contracts/quality-truth-baseline.v1.json"],
        "proof_commands": ["python -m pytest -q tests/test_quality_truth_baseline.py -o addopts="],
        "evidence_gaps": [],
        "next_human_action": "Run the focused proof.",
        "review_first": True,
        "reporting_only": True,
        "automation_allowed": False,
        "patch_application_allowed": False,
        "security_dismissal_allowed": False,
        "merge_authorized": False,
        "semantic_equivalence_proven": False,
    }


def test_export_normalizes_machine_readable_contract() -> None:
    payload = exporter.export_from_model({"adaptive_diagnosis": _card()})

    assert payload["schema_version"] == "sdetkit.adaptive_diagnosis_export.v1"
    assert payload["diagnosis"] == {
        "status": "review_first",
        "failure_class": "test",
        "diagnostic_completeness": "complete",
        "confidence": "high",
        "review_first": True,
    }
    assert payload["evidence"]["owner_files"] == ["docs/contracts/quality-truth-baseline.v1.json"]
    assert payload["evidence"]["checks"]["authority_boundary_preserved"] is True
    assert payload["authority"]["reporting_only"] is True
    assert payload["authority"]["automation_allowed"] is False
    assert payload["authority"]["merge_authorized"] is False


def test_export_is_deterministic() -> None:
    payload = exporter.export_from_model({"adaptive_diagnosis": _card()})
    first = exporter.serialize_export(payload)
    second = exporter.serialize_export(payload)

    assert first == second
    assert first.endswith("\n")


def test_export_reads_nested_card() -> None:
    payload = exporter.export_from_model({"primary_failure": {"adaptive_diagnosis": _card()}})
    assert payload["diagnosis"]["confidence"] == "high"


def test_export_rejects_missing_card() -> None:
    with pytest.raises(ValueError, match="no adaptive diagnosis card"):
        exporter.export_from_model({})


def test_export_cli_writes_json(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    model = tmp_path / "model.json"
    out = tmp_path / "adaptive-diagnosis.json"
    model.write_text(json.dumps({"adaptive_diagnosis": _card()}), encoding="utf-8")

    assert exporter.main(["--review-model", str(model), "--out", str(out)]) == 0

    payload = json.loads(out.read_text(encoding="utf-8"))
    stdout = capsys.readouterr().out
    assert payload["diagnosis"]["failure_class"] == "test"
    assert "adaptive_diagnosis_json_export=passed" in stdout
    assert "reporting_only=true" in stdout
    assert "automation_allowed=false" in stdout
