from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


def test_real_workflow_followup_generates_recommendations(tmp_path: Path) -> None:
    summary = tmp_path / "first-proof-summary.json"
    rollup = tmp_path / "first-proof-learning-rollup.json"
    threshold = tmp_path / "weekly-threshold-check.json"
    release_preflight = tmp_path / "release-preflight.json"
    out_json = tmp_path / "followup.json"
    out_md = tmp_path / "followup.md"
    history = tmp_path / "followup-history.jsonl"
    history_rollup = tmp_path / "followup-history-rollup.json"

    summary.write_text(
        json.dumps(
            {
                "decision": "NO-SHIP",
                "failed_steps": ["gate-fast", "gate-release"],
            }
        ),
        encoding="utf-8",
    )
    rollup.write_text(
        json.dumps(
            {
                "summary": {
                    "top_failed_steps": [
                        {"step": "gate-fast", "count": 4},
                        {"step": "gate-release", "count": 2},
                    ]
                }
            }
        ),
        encoding="utf-8",
    )
    threshold.write_text(json.dumps({"breach": True}), encoding="utf-8")
    release_preflight.write_text(
        json.dumps(
            {
                "failed_steps": ["doctor_release"],
                "recommendations": ["Inspect release readiness output."],
            }
        ),
        encoding="utf-8",
    )

    cmd = [
        sys.executable,
        "scripts/real_workflow_followup.py",
        "--summary",
        str(summary),
        "--rollup",
        str(rollup),
        "--threshold",
        str(threshold),
        "--release-preflight",
        str(release_preflight),
        "--out-json",
        str(out_json),
        "--out-md",
        str(out_md),
        "--history",
        str(history),
        "--history-rollup-out",
        str(history_rollup),
        "--format",
        "json",
    ]
    subprocess.run(cmd, check=True)

    payload = json.loads(out_json.read_text(encoding="utf-8"))
    assert payload["decision"] == "NO-SHIP"
    assert payload["threshold_breach"] is True
    assert payload["next_command"] == "make ops-daily"
    assert payload["recommendations"]
    assert any(item["priority"] == "P0" for item in payload["recommendations"])
    assert any(
        item["title"] == "Unblock release doctor checks" for item in payload["recommendations"]
    )

    md_text = out_md.read_text(encoding="utf-8")
    assert "Real workflow follow-up" in md_text
    assert "Recommendations" in md_text
    history_lines = history.read_text(encoding="utf-8").splitlines()
    assert len(history_lines) == 1
    rollup_payload = json.loads(history_rollup.read_text(encoding="utf-8"))
    assert rollup_payload["summary"]["total_runs"] == 1


def test_real_workflow_followup_ship_path_suggests_premerge(tmp_path: Path) -> None:
    summary = tmp_path / "first-proof-summary.json"
    out_json = tmp_path / "followup.json"
    out_md = tmp_path / "followup.md"
    history = tmp_path / "followup-history.jsonl"
    history_rollup = tmp_path / "followup-history-rollup.json"

    summary.write_text(json.dumps({"decision": "SHIP", "failed_steps": []}), encoding="utf-8")

    cmd = [
        sys.executable,
        "scripts/real_workflow_followup.py",
        "--summary",
        str(summary),
        "--rollup",
        str(tmp_path / "missing-rollup.json"),
        "--threshold",
        str(tmp_path / "missing-threshold.json"),
        "--release-preflight",
        str(tmp_path / "missing-release.json"),
        "--out-json",
        str(out_json),
        "--out-md",
        str(out_md),
        "--history",
        str(history),
        "--history-rollup-out",
        str(history_rollup),
    ]
    subprocess.run(cmd, check=True)

    payload = json.loads(out_json.read_text(encoding="utf-8"))
    assert payload["decision"] == "SHIP"
    assert payload["next_command"] == "make ops-premerge"
    assert any(
        item["title"] == "Proceed to pre-merge verification" for item in payload["recommendations"]
    )
    rollup_payload = json.loads(history_rollup.read_text(encoding="utf-8"))
    assert rollup_payload["summary"]["ship_runs"] == 1


def test_real_workflow_followup_history_accumulates(tmp_path: Path) -> None:
    summary = tmp_path / "first-proof-summary.json"
    history = tmp_path / "followup-history.jsonl"
    history_rollup = tmp_path / "followup-history-rollup.json"
    out_json = tmp_path / "followup.json"
    out_md = tmp_path / "followup.md"
    release_preflight = tmp_path / "release-preflight.json"

    summary.write_text(
        json.dumps({"decision": "NO-SHIP", "failed_steps": ["gate-fast"]}), encoding="utf-8"
    )
    release_preflight.write_text(json.dumps({"failed_steps": ["doctor_release"]}), encoding="utf-8")

    base_cmd = [
        sys.executable,
        "scripts/real_workflow_followup.py",
        "--summary",
        str(summary),
        "--rollup",
        str(tmp_path / "missing-rollup.json"),
        "--threshold",
        str(tmp_path / "missing-threshold.json"),
        "--release-preflight",
        str(release_preflight),
        "--out-json",
        str(out_json),
        "--out-md",
        str(out_md),
        "--history",
        str(history),
        "--history-rollup-out",
        str(history_rollup),
    ]
    subprocess.run(base_cmd, check=True)
    subprocess.run(base_cmd, check=True)

    history_lines = history.read_text(encoding="utf-8").splitlines()
    assert len(history_lines) == 2
    rollup_payload = json.loads(history_rollup.read_text(encoding="utf-8"))
    assert rollup_payload["summary"]["total_runs"] == 2
