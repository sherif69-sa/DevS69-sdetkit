from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

MODULE_PATH = (
    Path(__file__).resolve().parents[1]
    / "tools"
    / "render_pr_quality_adaptive_diagnosis_markdown.py"
)
SPEC = importlib.util.spec_from_file_location("adaptive_diagnosis_markdown", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
renderer = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(renderer)


def _card() -> dict[str, object]:
    return {
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
        "next_human_action": "Run the focused proof and inspect the owner file.",
        "review_first": True,
        "reporting_only": True,
        "automation_allowed": False,
        "patch_application_allowed": False,
        "security_dismissal_allowed": False,
        "merge_authorized": False,
        "semantic_equivalence_proven": False,
    }


def test_markdown_exposes_operator_handoff() -> None:
    text = renderer.render_from_model({"adaptive_diagnosis": _card()})

    assert text.startswith("# Adaptive Diagnosis")
    assert "- Completeness: `complete`" in text
    assert "- Confidence: `high`" in text
    assert "- Failure class: `test`" in text
    assert "`docs/contracts/quality-truth-baseline.v1.json`" in text
    assert "python -m pytest -q" in text
    assert "`authority_boundary_preserved`: `pass`" in text
    assert "`automation_allowed=false`" in text
    assert "`merge_authorized=false`" in text


def test_markdown_reads_nested_card() -> None:
    text = renderer.render_from_model({"primary_failure": {"adaptive_diagnosis": _card()}})
    assert "- Status: `review_first`" in text


def test_markdown_exposes_missing_safeguards_and_gaps() -> None:
    card = _card()
    card["checks"] = {"step_provenance_confirmed": False}
    card["evidence_gaps"] = ["step_provenance_confirmed"]

    text = renderer.render_adaptive_diagnosis_markdown(card)

    assert "`step_provenance_confirmed`: `missing`" in text
    assert "- `step_provenance_confirmed`" in text


def test_markdown_rejects_missing_card() -> None:
    with pytest.raises(ValueError, match="no adaptive diagnosis card"):
        renderer.render_from_model({})


def test_markdown_cli_writes_handoff(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    model = tmp_path / "model.json"
    out = tmp_path / "adaptive-diagnosis.md"
    model.write_text(json.dumps({"adaptive_diagnosis": _card()}), encoding="utf-8")

    assert renderer.main(["--review-model", str(model), "--out", str(out)]) == 0

    assert out.read_text(encoding="utf-8").startswith("# Adaptive Diagnosis")
    stdout = capsys.readouterr().out
    assert "adaptive_diagnosis_markdown_render=passed" in stdout
    assert "reporting_only=true" in stdout
    assert "automation_allowed=false" in stdout
