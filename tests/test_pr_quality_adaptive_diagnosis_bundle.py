from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path

import pytest

MODULE_PATH = (
    Path(__file__).resolve().parents[1] / "tools" / "build_pr_quality_adaptive_diagnosis_bundle.py"
)
SPEC = importlib.util.spec_from_file_location("adaptive_diagnosis_bundle", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
builder = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(builder)


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
        "next_human_action": "Run focused proof and inspect the owner file.",
        "review_first": True,
        "reporting_only": True,
        "automation_allowed": False,
        "patch_application_allowed": False,
        "security_dismissal_allowed": False,
        "merge_authorized": False,
        "semantic_equivalence_proven": False,
    }


def test_bundle_writes_portable_operator_artifacts(tmp_path: Path) -> None:
    manifest = builder.build_bundle({"adaptive_diagnosis": _card()}, tmp_path)

    assert manifest["status"] == "passed"
    assert manifest["authority_validated"] is True
    assert {item["path"] for item in manifest["artifacts"]} == {
        "adaptive-diagnosis.html",
        "adaptive-diagnosis.md",
        "adaptive-diagnosis.json",
    }
    assert (tmp_path / "manifest.json").is_file()
    assert "<h1>Adaptive Diagnosis</h1>" in (tmp_path / "adaptive-diagnosis.html").read_text(
        encoding="utf-8"
    )
    assert (
        (tmp_path / "adaptive-diagnosis.md")
        .read_text(encoding="utf-8")
        .startswith("# Adaptive Diagnosis")
    )
    payload = json.loads((tmp_path / "adaptive-diagnosis.json").read_text(encoding="utf-8"))
    assert payload["diagnosis"]["failure_class"] == "test"


def test_manifest_hashes_match_artifact_bytes(tmp_path: Path) -> None:
    manifest = builder.build_bundle({"adaptive_diagnosis": _card()}, tmp_path)

    for record in manifest["artifacts"]:
        content = (tmp_path / record["path"]).read_bytes()
        assert record["size_bytes"] == len(content)
        assert record["sha256"] == hashlib.sha256(content).hexdigest()


@pytest.mark.parametrize(
    ("field", "unsafe_value"),
    [
        ("reporting_only", False),
        ("automation_allowed", True),
        ("patch_application_allowed", True),
        ("security_dismissal_allowed", True),
        ("merge_authorized", True),
        ("semantic_equivalence_proven", True),
    ],
)
def test_bundle_fails_closed_for_unsafe_authority(
    tmp_path: Path,
    field: str,
    unsafe_value: bool,
) -> None:
    card = _card()
    card[field] = unsafe_value

    with pytest.raises(ValueError, match="unsafe adaptive diagnosis authority"):
        builder.build_bundle({"adaptive_diagnosis": card}, tmp_path)

    assert not list(tmp_path.iterdir())


def test_bundle_rejects_missing_card(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="no adaptive diagnosis card"):
        builder.build_bundle({}, tmp_path)


def test_bundle_cli_writes_manifest(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    model = tmp_path / "model.json"
    out_dir = tmp_path / "bundle"
    model.write_text(json.dumps({"adaptive_diagnosis": _card()}), encoding="utf-8")

    assert builder.main(["--review-model", str(model), "--out-dir", str(out_dir)]) == 0

    manifest = json.loads((out_dir / "manifest.json").read_text(encoding="utf-8"))
    stdout = capsys.readouterr().out
    assert manifest["authority_validated"] is True
    assert "adaptive_diagnosis_bundle=passed" in stdout
    assert "artifact_count=3" in stdout
    assert "automation_allowed=false" in stdout
