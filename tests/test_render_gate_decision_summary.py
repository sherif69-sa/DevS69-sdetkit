from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

SCRIPT = Path("scripts/render_gate_decision_summary.py").resolve()


def test_render_gate_decision_summary_no_ship_json(tmp_path: Path) -> None:
    release = tmp_path / "release.json"
    fast = tmp_path / "fast.json"
    release.write_text(
        json.dumps({"ok": False, "failed_steps": ["gate_fast"], "profile": "release"}),
        encoding="utf-8",
    )
    fast.write_text(
        json.dumps({"ok": False, "failed_steps": ["ruff"], "profile": "fast"}), encoding="utf-8"
    )

    proc = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--release",
            str(release),
            "--fast",
            str(fast),
            "--format",
            "json",
        ],
        check=False,
        text=True,
        capture_output=True,
    )
    assert proc.returncode == 0
    payload = json.loads(proc.stdout)
    assert payload["decision"] == "NO-SHIP"
    assert payload["review_required"] is True
    assert payload["validation_errors"] == []
    assert payload["artifacts"]["release"]["failed_steps"] == ["gate_fast"]
    assert payload["artifacts"]["fast"]["failed_steps"] == ["ruff"]
    assert payload["artifacts"]["fast"]["evidence_status"] == "current_valid"
    assert payload["next_action"]["decision"] == "NO-SHIP"
    assert payload["next_action"]["authority"] == "review-first"
    assert "python -m sdetkit gate fast" in payload["next_action"]["next_command"]


def test_render_gate_decision_summary_missing_fast_is_no_ship(tmp_path: Path) -> None:
    release = tmp_path / "release.json"
    release.write_text(
        json.dumps({"ok": True, "failed_steps": [], "profile": "release"}), encoding="utf-8"
    )

    proc = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--release",
            str(release),
            "--fast",
            str(tmp_path / "missing-fast.json"),
            "--allow-missing-fast",
            "--format",
            "text",
        ],
        check=False,
        text=True,
        capture_output=True,
    )
    assert proc.returncode == 0
    assert "- **Decision:** ❌ NO-SHIP" in proc.stdout
    assert "## Reviewer checklist" in proc.stdout
    assert "- not provided" in proc.stdout
    assert "next_action:" in proc.stdout
    assert (
        "python -m sdetkit gate fast --format json --stable-json --out build/gate-fast.json"
        in proc.stdout
    )


def test_render_gate_decision_summary_requires_both_artifacts_ok(tmp_path: Path) -> None:
    release = tmp_path / "release.json"
    fast = tmp_path / "fast.json"
    release.write_text(
        json.dumps({"ok": True, "failed_steps": [], "profile": "release"}),
        encoding="utf-8",
    )
    fast.write_text(
        json.dumps({"ok": False, "failed_steps": ["pytest"], "profile": "fast"}),
        encoding="utf-8",
    )

    proc = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--release",
            str(release),
            "--fast",
            str(fast),
            "--format",
            "json",
        ],
        check=False,
        text=True,
        capture_output=True,
    )
    assert proc.returncode == 0
    payload = json.loads(proc.stdout)
    assert payload["decision"] == "NO-SHIP"
    assert payload["review_required"] is True
    assert payload["artifacts"]["fast"]["ok"] is False
    assert payload["artifacts"]["fast"]["failed_steps"] == ["pytest"]


def test_render_gate_decision_summary_ship_requires_empty_failed_steps(
    tmp_path: Path,
) -> None:
    release = tmp_path / "release.json"
    fast = tmp_path / "fast.json"
    release.write_text(
        json.dumps({"ok": True, "failed_steps": ["gate_fast"], "profile": "release"}),
        encoding="utf-8",
    )
    fast.write_text(
        json.dumps({"ok": True, "failed_steps": [], "profile": "fast"}),
        encoding="utf-8",
    )

    proc = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--release",
            str(release),
            "--fast",
            str(fast),
            "--format",
            "json",
        ],
        check=False,
        text=True,
        capture_output=True,
    )
    assert proc.returncode == 0
    payload = json.loads(proc.stdout)
    assert payload["decision"] == "NO-SHIP"
    assert payload["review_required"] is True


def test_render_gate_decision_summary_ship_when_both_ok_and_empty(tmp_path: Path) -> None:
    release = tmp_path / "release.json"
    fast = tmp_path / "fast.json"
    release.write_text(
        json.dumps({"ok": True, "failed_steps": [], "profile": "release"}),
        encoding="utf-8",
    )
    fast.write_text(
        json.dumps({"ok": True, "failed_steps": [], "profile": "fast"}),
        encoding="utf-8",
    )

    proc = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--release",
            str(release),
            "--fast",
            str(fast),
            "--format",
            "json",
        ],
        check=False,
        text=True,
        capture_output=True,
    )
    assert proc.returncode == 0
    payload = json.loads(proc.stdout)
    assert payload["decision"] == "SHIP"
    assert payload["review_required"] is False
    assert payload["validation_errors"] == []
    assert payload["artifacts"]["release"]["evidence_status"] == "current_valid"
    assert payload["artifacts"]["fast"]["evidence_status"] == "current_valid"
    provenance = payload["input_provenance"]
    assert provenance["digest_algorithm"] == "sha256"
    assert len(provenance["input_digest"]) == 64
    assert len(provenance["generated_from_head_sha"]) == 40
    assert "release" in provenance["input_digests"]
    assert "fast" in provenance["input_digests"]
    card = payload["next_action"]
    assert card["decision"] == "SHIP"
    assert card["classification"] == ""
    assert card["first_failure"] == ""
    assert card["affected_file"] == ""
    assert card["next_command"] == "make gate-decision-summary-contract"
    assert card["authority"] == "review-first"


def test_render_gate_decision_summary_fails_with_missing_release(tmp_path: Path) -> None:
    proc = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--release",
            str(tmp_path / "missing-release.json"),
            "--format",
            "json",
        ],
        check=False,
        text=True,
        capture_output=True,
    )
    assert proc.returncode == 1
    payload = json.loads(proc.stdout)
    assert payload["ok"] is False
    assert "missing-release.json" in payload["release"]


def test_render_gate_decision_summary_classifies_missing_fast_as_unavailable(
    tmp_path: Path,
) -> None:
    release = tmp_path / "release.json"
    release.write_text(
        json.dumps({"ok": True, "failed_steps": [], "profile": "release"}), encoding="utf-8"
    )

    proc = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--release",
            str(release),
            "--fast",
            str(tmp_path / "missing-fast.json"),
            "--allow-missing-fast",
            "--format",
            "json",
        ],
        check=False,
        text=True,
        capture_output=True,
    )
    assert proc.returncode == 0
    payload = json.loads(proc.stdout)
    assert payload["decision"] == "NO-SHIP"
    assert payload["artifacts"]["fast"]["present"] is False
    assert payload["artifacts"]["fast"]["evidence_status"] == "unavailable"
    assert payload["next_action"]["next_command"] == (
        "python -m sdetkit gate fast --format json --stable-json --out build/gate-fast.json"
    )
    assert payload["input_provenance"]["input_digests"]["fast"] == ""


def test_render_gate_decision_summary_reports_non_boolean_ok(tmp_path: Path) -> None:
    release = tmp_path / "release.json"
    release.write_text(
        json.dumps({"ok": "true", "failed_steps": [], "profile": "release"}),
        encoding="utf-8",
    )
    proc = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--release",
            str(release),
            "--allow-missing-fast",
            "--format",
            "json",
        ],
        check=False,
        text=True,
        capture_output=True,
    )
    assert proc.returncode == 0
    payload = json.loads(proc.stdout)
    assert payload["decision"] == "NO-SHIP"
    assert any("expected boolean `ok`" in row for row in payload["validation_errors"])
    assert payload["artifacts"]["release"]["evidence_status"] == "malformed"
    assert payload["next_action"]["decision"] == "NO-SHIP"
    assert payload["next_action"]["authority"] == "review-first"
