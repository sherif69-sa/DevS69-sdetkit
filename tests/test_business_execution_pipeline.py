from __future__ import annotations

import importlib.util
import json
import zipfile
from pathlib import Path

_SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "business_execution_pipeline.py"
_SPEC = importlib.util.spec_from_file_location("business_execution_pipeline_script", _SCRIPT_PATH)
assert _SPEC is not None and _SPEC.loader is not None
pipeline_script = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(pipeline_script)


def test_pipeline_writes_full_artifact_set(tmp_path: Path) -> None:
    out_dir = tmp_path / "artifacts"
    challenge_prompt = tmp_path / "workflow_execution_prompt.md"
    guidelines_zip = tmp_path / "workflow_execution_guidelines_bundle.zip"
    challenge_prompt.write_text("# prompt\nline\n", encoding="utf-8")
    with zipfile.ZipFile(guidelines_zip, "w") as zf:
        zf.writestr("guideline-a.txt", "a")
        zf.writestr("guideline-b.txt", "b")
    rc = pipeline_script.main(
        [
            "--out-dir",
            str(out_dir),
            "--start-date",
            "2026-04-28",
            "--program-owner",
            "Founder",
            "--done",
            "Confirm owners and operating cadence.",
            "--challenge-prompt",
            str(challenge_prompt),
            "--guidelines-zip",
            str(guidelines_zip),
        ]
    )
    assert rc == 0
    assert (out_dir / "business-execution-week1.json").exists()
    assert (out_dir / "business-execution-week1-progress.json").exists()
    assert (out_dir / "business-execution-week1-next.json").exists()
    assert (out_dir / "business-execution-handoff.json").exists()
    assert (out_dir / "business-execution-escalation.json").exists()
    assert (out_dir / "business-execution-followup.json").exists()
    assert (out_dir / "business-execution-followup-history.jsonl").exists()
    assert (out_dir / "business-execution-followup-rollup.json").exists()
    assert (out_dir / "business-execution-continue.json").exists()
    assert (out_dir / "business-execution-horizon.json").exists()
    inputs = out_dir / "business-execution-inputs.json"
    assert inputs.exists()
    payload = json.loads(inputs.read_text(encoding="utf-8"))
    assert payload["challenge_prompt"]["line_count"] == 2
    assert payload["guidelines_zip"]["entry_count"] == 2


def test_pipeline_autodiscovers_canonical_input_files(tmp_path: Path, monkeypatch) -> None:
    out_dir = tmp_path / "artifacts"
    challenge_prompt = tmp_path / "workflow_execution_prompt.md"
    guidelines_zip = tmp_path / "workflow_execution_guidelines_bundle.zip"
    challenge_prompt.write_text("# prompt\nline\n", encoding="utf-8")
    with zipfile.ZipFile(guidelines_zip, "w") as zf:
        zf.writestr("guideline-a.txt", "a")

    monkeypatch.chdir(tmp_path)
    rc = pipeline_script.main(["--out-dir", str(out_dir), "--program-owner", "Founder"])

    assert rc == 0
    payload = json.loads((out_dir / "business-execution-inputs.json").read_text(encoding="utf-8"))
    assert payload["challenge_prompt"]["path"].endswith("workflow_execution_prompt.md")
    assert payload["guidelines_zip"]["path"].endswith("workflow_execution_guidelines_bundle.zip")


def test_pipeline_rejects_partial_external_input_pair(tmp_path: Path) -> None:
    out_dir = tmp_path / "artifacts"
    challenge_prompt = tmp_path / "workflow_execution_prompt.md"
    challenge_prompt.write_text("# prompt\n", encoding="utf-8")

    try:
        pipeline_script.main(
            [
                "--out-dir",
                str(out_dir),
                "--challenge-prompt",
                str(challenge_prompt),
            ]
        )
    except ValueError as exc:
        assert "requires both --challenge-prompt and --guidelines-zip" in str(exc)
    else:
        raise AssertionError("Expected ValueError for partial external input pair")


def test_pipeline_single_operator_mode_assigns_all_roles(tmp_path: Path) -> None:
    out_dir = tmp_path / "artifacts"
    rc = pipeline_script.main(
        [
            "--out-dir",
            str(out_dir),
            "--single-operator",
            "Sherif",
        ]
    )
    assert rc == 0
    week1_payload = json.loads(
        (out_dir / "business-execution-week1.json").read_text(encoding="utf-8")
    )
    assert week1_payload["status"] == "go"
    assert set(week1_payload["owners"].values()) == {"Sherif"}
