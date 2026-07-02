from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

MODULE_PATH = (
    Path(__file__).resolve().parents[1]
    / "tools"
    / "render_pr_quality_adaptive_diagnosis.py"
)
SPEC = importlib.util.spec_from_file_location("adaptive_diagnosis_renderer", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
renderer = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(renderer)


def _card() -> dict[str, object]:
    return {
        "schema_version": "sdetkit.adaptive_diagnosis_card.v1",
        "status": "review_first",
        "failure_class": "test",
        "diagnostic_completeness": "complete",
        "confidence": "high",
        "checks": {
            "exact_failure_detail_present": True,
            "expected_observed_specific": True,
            "owner_file_resolved": True,
            "reproduction_command_resolved": True,
            "step_provenance_confirmed": True,
            "authority_boundary_preserved": True,
        },
        "evidence_gaps": [],
        "owner_files": ["docs/contracts/quality-truth-baseline.v1.json"],
        "proof_commands": [
            "python -m pytest -q "
            "tests/test_quality_truth_baseline.py::"
            "test_quality_truth_baseline_matches_current_repository_configuration "
            "-o addopts="
        ],
        "next_human_action": (
            "Run the focused proof, inspect the owner file, and review the first contract."
        ),
        "review_first": True,
        "reporting_only": True,
        "automation_allowed": False,
        "patch_application_allowed": False,
        "security_dismissal_allowed": False,
        "merge_authorized": False,
        "semantic_equivalence_proven": False,
    }


def test_render_exposes_adaptive_diagnosis_for_contributors() -> None:
    html = renderer.render_from_model({"adaptive_diagnosis": _card()})

    assert "<h1>Adaptive Diagnosis</h1>" in html
    assert "Complete" in html
    assert "High" in html
    assert "Test" in html
    assert "docs/contracts/quality-truth-baseline.v1.json" in html
    assert "python -m pytest -q" in html
    assert "authority_boundary_preserved" in html
    assert "automation_allowed" in html
    assert ">false<" in html


def test_render_reads_card_from_primary_failure() -> None:
    html = renderer.render_from_model(
        {"primary_failure": {"adaptive_diagnosis": _card()}}
    )
    assert "Review first" in html


def test_render_escapes_untrusted_evidence() -> None:
    card = _card()
    card["next_human_action"] = "<script>alert('unsafe')</script>"

    html = renderer.render_adaptive_diagnosis_html(card)

    assert "<script>alert" not in html
    assert "&lt;script&gt;" in html


def test_render_rejects_model_without_adaptive_card() -> None:
    with pytest.raises(ValueError, match="no adaptive diagnosis card"):
        renderer.render_from_model({})


def test_cli_writes_standalone_html(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    model_path = tmp_path / "model.json"
    out = tmp_path / "adaptive-diagnosis.html"
    model_path.write_text(
        json.dumps({"adaptive_diagnosis": _card()}),
        encoding="utf-8",
    )

    assert renderer.main(
        ["--review-model", str(model_path), "--out", str(out)]
    ) == 0

    rendered = out.read_text(encoding="utf-8")
    captured = capsys.readouterr().out
    assert "<h1>Adaptive Diagnosis</h1>" in rendered
    assert "adaptive_diagnosis_render=passed" in captured
    assert "reporting_only=true" in captured
    assert "automation_allowed=false" in captured
    assert "merge_authorized=false" in captured
