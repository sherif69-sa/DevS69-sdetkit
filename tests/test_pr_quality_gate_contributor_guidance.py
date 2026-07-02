from __future__ import annotations

import json
from pathlib import Path

from sdetkit import pr_quality_evidence_narrative as narrative


def _write(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def _write_json(path: Path, payload: dict[str, object]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def test_failure_guidance_rejects_cleanup_and_selects_exact_formatter_proof(
    tmp_path: Path,
) -> None:
    quality = _write(
        tmp_path / "quality.log",
        "Would reformat: tests/test_probe.py\nProcess completed with exit code 1\n",
    )
    bundle = _write_json(
        tmp_path / "failure-bundle.json",
        {
            "primary_diagnosis_code": "RUFF_FORMAT_FAILURE",
            "diagnoses": [
                {
                    "code": "RUFF_FORMAT_FAILURE",
                    "title": "Ruff format check failed",
                    "diagnosis": "Would reformat: tests/test_probe.py",
                    "evidence": ["Would reformat: tests/test_probe.py"],
                    "proof_commands": [
                        "rm -rf dist build/lib build/bdist.*",
                        "python -m ruff format --check .",
                    ],
                }
            ],
        },
    )

    payload = narrative.build_narrative(
        quality_log=quality,
        quality_outcome="failure",
        sentinel_control_room=None,
        evidence_graph=None,
        failure_bundle=bundle,
        changed_files=None,
    )

    assert payload["next_proof"] == [
        "python -m ruff format --check tests/test_probe.py && python -m pre_commit run -a"
    ]
    assert "rm -rf" not in " ".join(payload["next_proof"])
    assert payload["operator_action"] == [
        "Fix the first actionable failure shown above.",
        "Run the exact proof command below, then push the commit.",
        "The SDET Quality Gate refreshes automatically on the new PR head.",
    ]


def test_failure_guidance_preserves_review_first_authority() -> None:
    commands = narrative._commands_from_failure(
        {
            "code": "PYTEST_ASSERTION_FAILURE",
            "diagnosis": "FAILED tests/test_probe.py::test_probe - AssertionError",
            "proof_commands": ["rm -rf build"],
        }
    )

    assert commands == [
        "python -m pytest -q tests/test_probe.py::test_probe -o addopts= "
        "&& python -m pre_commit run -a"
    ]
