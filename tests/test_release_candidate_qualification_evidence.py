from __future__ import annotations

import importlib.util
import json
from copy import deepcopy
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "build_release_candidate_qualification.py"
WORKFLOW = ROOT / ".github" / "workflows" / "release-candidate.yml"


def _module():
    spec = importlib.util.spec_from_file_location("build_release_candidate_qualification", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _manifest() -> dict[str, object]:
    return {
        "schema_version": "sdetkit.release_distribution_manifest.v1",
        "source_sha": "a" * 40,
        "tag": "v1.2.0",
        "version": "1.2.0",
        "files": [
            {
                "name": "sdetkit-1.2.0-py3-none-any.whl",
                "size_bytes": 1234,
                "sha256": "b" * 64,
            },
            {
                "name": "sdetkit-1.2.0.tar.gz",
                "size_bytes": 2345,
                "sha256": "c" * 64,
            },
        ],
    }


def _evidence(tmp_path: Path) -> dict[str, Path]:
    tmp_path.mkdir(parents=True, exist_ok=True)
    paths = {}
    for name in ("gate_fast", "gate_release", "doctor"):
        path = tmp_path / f"{name}.json"
        path.write_text(json.dumps({"status": "passed", "name": name}) + "\n", encoding="utf-8")
        paths[name] = path
    return paths


def _record(module, tmp_path: Path, python_version: str) -> dict[str, object]:
    return module.build_python_record(
        manifest=_manifest(),
        python_version=python_version,
        runtime_python_version=python_version,
        evidence_paths=_evidence(tmp_path / python_version),
    )


def test_python_record_binds_exact_wheel_and_evidence(tmp_path: Path) -> None:
    module = _module()

    record = _record(module, tmp_path, "3.12")

    assert record["status"] == "exact_wheel_qualification_passed"
    assert record["source_sha"] == "a" * 40
    assert record["python_version"] == "3.12"
    assert record["wheel"] == {
        "name": "sdetkit-1.2.0-py3-none-any.whl",
        "sha256": "b" * 64,
        "size_bytes": 1234,
    }
    assert {item["name"] for item in record["evidence_artifacts"]} == {
        "doctor",
        "gate_fast",
        "gate_release",
    }
    assert record["publish_authorized"] is False
    assert record["tag_created"] is False


def test_verdict_requires_exact_python_set_and_same_wheel(tmp_path: Path) -> None:
    module = _module()
    records = [_record(module, tmp_path, version) for version in ("3.10", "3.11", "3.12")]

    verdict = module.build_verdict(
        records=records,
        candidate_tag="v1.2.0",
        version="1.2.0",
        source_sha="a" * 40,
    )

    assert verdict["status"] == "repository_qualification_passed"
    assert verdict["qualified_python_versions"] == ["3.10", "3.11", "3.12"]
    assert verdict["qualification_record_count"] == 3
    assert verdict["exact_wheel"]["same_digest_across_matrix"] is True
    assert verdict["exact_wheel"]["sha256"] == "b" * 64
    assert verdict["external_settings_verified"] is False
    assert verdict["publish_authorized"] is False
    assert verdict["next_action"] == "verify external publishing settings before creating v1.2.0"


def test_verdict_rejects_missing_python_record(tmp_path: Path) -> None:
    module = _module()
    records = [_record(module, tmp_path, version) for version in ("3.10", "3.12")]

    try:
        module.build_verdict(
            records=records,
            candidate_tag="v1.2.0",
            version="1.2.0",
            source_sha="a" * 40,
        )
    except ValueError as exc:
        assert "exactly three Python records" in str(exc)
    else:
        raise AssertionError("missing Python record was accepted")


def test_verdict_rejects_wheel_digest_drift(tmp_path: Path) -> None:
    module = _module()
    records = [_record(module, tmp_path, version) for version in ("3.10", "3.11", "3.12")]
    drifted = deepcopy(records[1])
    drifted["wheel"] = dict(drifted["wheel"])
    drifted["wheel"]["sha256"] = "d" * 64
    records[1] = drifted

    try:
        module.build_verdict(
            records=records,
            candidate_tag="v1.2.0",
            version="1.2.0",
            source_sha="a" * 40,
        )
    except ValueError as exc:
        assert "same exact wheel" in str(exc)
    else:
        raise AssertionError("wheel digest drift was accepted")


def test_verdict_rejects_publication_authority_claim(tmp_path: Path) -> None:
    module = _module()
    records = [_record(module, tmp_path, version) for version in ("3.10", "3.11", "3.12")]
    records[0]["publish_authorized"] = True

    try:
        module.build_verdict(
            records=records,
            candidate_tag="v1.2.0",
            version="1.2.0",
            source_sha="a" * 40,
        )
    except ValueError as exc:
        assert "must not authorize publication" in str(exc)
    else:
        raise AssertionError("publication authority claim was accepted")


def test_workflow_aggregates_exact_matrix_records() -> None:
    workflow = WORKFLOW.read_text(encoding="utf-8")

    assert "scripts/build_release_candidate_qualification.py record" in workflow
    assert '--python-version "${{ matrix.python-version }}"' in workflow
    assert "qualification-record.json" in workflow
    assert "pattern: release-candidate-qualification-py*" in workflow
    assert "mapfile -t records" in workflow
    assert 'test "${#records[@]}" -eq 3' in workflow
    assert 'python "$builder" verdict' in workflow
    assert len(workflow.splitlines()) < 250
    assert "qualification-verdict:" in workflow
    verdict = workflow.split("  qualification-verdict:", 1)[1]
    assert "actions/checkout@" not in verdict
    assert "pypa/gh-action-pypi-publish" not in workflow
    assert "softprops/action-gh-release" not in workflow
