from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from types import ModuleType

from sdetkit.pr_quality_adaptive_diagnosis import (
    ADAPTIVE_DIAGNOSIS_EXPORT_SCHEMA_VERSION,
    AUTHORITY_EXPECTATIONS,
    attach_adaptive_diagnosis,
)

ROOT = Path(__file__).resolve().parents[1]


def _load_tool(name: str) -> ModuleType:
    path = ROOT / "tools" / name
    spec = importlib.util.spec_from_file_location(path.stem, path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


BUILDER = _load_tool("build_pr_quality_adaptive_diagnosis_bundle.py")
VERIFIER = _load_tool("verify_pr_quality_adaptive_diagnosis_bundle.py")


def _model() -> dict[str, object]:
    model: dict[str, object] = {
        "primary_failure": {
            "available": True,
            "expected": "heavy_workflow_count <= 8",
            "observed": "heavy_workflow_count = 9",
            "message": "workflow budget regression",
            "test_node": "tests/test_workflow_contracts.py::test_repository_workflow_contracts_pass",
            "reproduction_command": (
                "python -m pytest -q "
                "tests/test_workflow_contracts.py::test_repository_workflow_contracts_pass "
                "-o addopts="
            ),
            "mapping_confidence": "high",
            "provenance_status": "confirmed",
            "step_evidence_status": "confirmed",
            "workflow_exact_head_verified": True,
            "reporting_only": True,
            "families": [{"failure_code": "PYTEST_ASSERTION_FAILURE"}],
        }
    }
    attach_adaptive_diagnosis(model)
    return model


def _bundle(tmp_path: Path) -> Path:
    bundle_dir = tmp_path / "bundle"
    BUILDER.build_bundle(_model(), bundle_dir)
    return bundle_dir


def test_verifier_accepts_builder_output(tmp_path: Path) -> None:
    bundle_dir = _bundle(tmp_path)

    report = VERIFIER.verify_bundle(bundle_dir)

    assert report["ok"] is True
    assert report["mismatch_count"] == 0
    assert report["artifacts_checked"] == list(VERIFIER.EXPECTED_ARTIFACTS)
    assert report["decision_boundary"] == VERIFIER.DECISION_BOUNDARY


def test_verifier_detects_tampered_artifact(tmp_path: Path) -> None:
    bundle_dir = _bundle(tmp_path)
    path = bundle_dir / "adaptive-diagnosis.md"
    path.write_text(path.read_text(encoding="utf-8") + "tampered\n", encoding="utf-8")

    report = VERIFIER.verify_bundle(bundle_dir)

    assert report["ok"] is False
    assert "artifact size mismatch: adaptive-diagnosis.md" in report["mismatches"]
    assert "artifact sha256 mismatch: adaptive-diagnosis.md" in report["mismatches"]


def test_verifier_detects_manifest_authority_expansion(tmp_path: Path) -> None:
    bundle_dir = _bundle(tmp_path)
    manifest_path = bundle_dir / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["authority"]["merge_authorized"] = True
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    report = VERIFIER.verify_bundle(bundle_dir)

    assert report["ok"] is False
    assert "manifest authority boundary mismatch" in report["mismatches"]


def test_verifier_detects_export_contract_drift(tmp_path: Path) -> None:
    bundle_dir = _bundle(tmp_path)
    export_path = bundle_dir / "adaptive-diagnosis.json"
    export = json.loads(export_path.read_text(encoding="utf-8"))
    export["schema_version"] = "unexpected.schema.v1"
    export["authority"] = dict(AUTHORITY_EXPECTATIONS)
    export_path.write_text(json.dumps(export), encoding="utf-8")

    manifest_path = bundle_dir / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    for record in manifest["artifacts"]:
        if record["path"] == "adaptive-diagnosis.json":
            content = export_path.read_bytes()
            import hashlib

            record["size_bytes"] = len(content)
            record["sha256"] = hashlib.sha256(content).hexdigest()
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    report = VERIFIER.verify_bundle(bundle_dir)

    assert report["ok"] is False
    assert "adaptive diagnosis export schema_version mismatch" in report["mismatches"]
    assert ADAPTIVE_DIAGNOSIS_EXPORT_SCHEMA_VERSION != export["schema_version"]


def test_verifier_detects_missing_and_unexpected_records(tmp_path: Path) -> None:
    bundle_dir = _bundle(tmp_path)
    manifest_path = bundle_dir / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["artifacts"] = [
        record
        for record in manifest["artifacts"]
        if record["path"] != "adaptive-diagnosis.html"
    ]
    manifest["artifacts"].append(
        {
            "path": "unexpected.txt",
            "size_bytes": 0,
            "sha256": "0" * 64,
        }
    )
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    report = VERIFIER.verify_bundle(bundle_dir)

    assert report["ok"] is False
    assert "missing artifact record: adaptive-diagnosis.html" in report["mismatches"]
    assert "unexpected artifact record: unexpected.txt" in report["mismatches"]
