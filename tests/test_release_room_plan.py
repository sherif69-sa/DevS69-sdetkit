from __future__ import annotations

import json
import subprocess
import sys


def run_cmd(*args: str):
    return subprocess.run([sys.executable, "-m", "sdetkit", *args], capture_output=True, text=True)


def test_operator_json_contract(tmp_path):
    proc = run_cmd(
        "release-room",
        "plan",
        str(tmp_path),
        "--deep",
        "--learn",
        "--db",
        str(tmp_path / "a.db"),
        "--format",
        "operator-json",
    )
    assert proc.returncode == 0
    payload = json.loads(proc.stdout)
    assert payload["schema_version"] == "sdetkit.release_room.plan.v1"
    required = {
        "schema_version",
        "repo_path",
        "decision",
        "confidence",
        "source_status",
        "top_risks",
        "patch_candidates",
        "recommended_fixes",
        "validation_commands",
        "evidence_paths",
        "next_pr_recommendation",
    }
    assert required <= set(payload)
    assert isinstance(payload["source_status"], dict)
    assert isinstance(payload["validation_commands"], list)
    assert isinstance(payload["evidence_paths"], list)
    assert payload["next_pr_recommendation"]
    assert payload["decision"] in {"SHIP", "REVIEW", "NO-SHIP", "UNKNOWN"}
    assert isinstance(payload.get("patch_candidates"), list)
    assert isinstance(payload.get("signals"), dict)


def test_text_respects_max_lines(tmp_path):
    proc = run_cmd(
        "release-room",
        "plan",
        str(tmp_path),
        "--db",
        str(tmp_path / "a.db"),
        "--max-lines",
        "12",
        "--format",
        "text",
    )
    assert proc.returncode == 0
    lines = [line for line in proc.stdout.splitlines() if line.strip()]
    assert len(lines) <= 12


def test_evidence_dir_writes_expected_files(tmp_path):
    evidence = tmp_path / "ev"
    proc = run_cmd(
        "release-room",
        "plan",
        str(tmp_path),
        "--db",
        str(tmp_path / "a.db"),
        "--evidence-dir",
        str(evidence),
        "--format",
        "operator-json",
    )
    assert proc.returncode == 0
    for name in (
        "release-room-plan.json",
        "release-room-plan.txt",
        "index.json",
        "boost-v2.json",
        "adaptive-review.json",
        "memory-history.json",
        "memory-explain.json",
    ):
        assert (evidence / name).exists()


def test_validation_plan_contains_required_commands(tmp_path):
    proc = run_cmd(
        "release-room",
        "plan",
        str(tmp_path),
        "--db",
        str(tmp_path / "a.db"),
        "--format",
        "operator-json",
    )
    payload = json.loads(proc.stdout)
    joined = "\n".join(payload["validation_commands"])
    assert "pytest" in joined
    assert "ruff check" in joined
    assert "ruff format --check" in joined
    assert "repo check" in joined
    assert "mkdocs build --strict" in joined


def test_patch_candidates_is_list_even_on_failures(tmp_path):
    proc = run_cmd(
        "release-room",
        "plan",
        str(tmp_path),
        "--db",
        str(tmp_path / "a.db"),
        "--format",
        "operator-json",
    )
    payload = json.loads(proc.stdout)
    assert isinstance(payload.get("patch_candidates"), list)


def test_operator_json_hygiene_fields_present(tmp_path):
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "x.py").write_text("# FIXME\n", encoding="utf-8")
    (tmp_path / ".sdetkit").mkdir()
    (tmp_path / ".sdetkit" / "cache.txt").write_text("FIXME\n", encoding="utf-8")
    proc = run_cmd("release-room", "plan", str(tmp_path), "--db", str(tmp_path / "a.db"), "--format", "operator-json")
    payload = json.loads(proc.stdout)
    for key in (
        "risk_hygiene_summary",
        "source_risks",
        "generated_artifact_risks",
        "suppressed_risks",
        "suppression_reasons",
        "workspace_noise_detected",
    ):
        assert key in payload


def test_release_room_prioritizes_source_risks_over_generated_noise(tmp_path):
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "x.py").write_text("# FIXME\n", encoding="utf-8")
    (tmp_path / "build").mkdir()
    (tmp_path / "build" / "noise.txt").write_text("FIXME\n", encoding="utf-8")
    proc = run_cmd("release-room", "plan", str(tmp_path), "--db", str(tmp_path / "a.db"), "--format", "operator-json")
    payload = json.loads(proc.stdout)
    assert any(str(r.get("file", "")).startswith("repo") for r in payload.get("top_risks", []))


def test_no_evidence_or_db_tracked_in_repo_status(tmp_path):
    subprocess.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True, text=True)
    subprocess.run(["git", "config", "user.email", "a@b.c"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.name", "t"], cwd=tmp_path, check=True)
    (tmp_path / "README.md").write_text("# x\n", encoding="utf-8")
    subprocess.run(["git", "add", "README.md"], cwd=tmp_path, check=True)
    subprocess.run(["git", "commit", "-m", "init"], cwd=tmp_path, check=True, capture_output=True, text=True)
    run_cmd("release-room", "plan", str(tmp_path), "--db", str(tmp_path / "build" / "a.db"), "--evidence-dir", str(tmp_path / "build" / "ev"), "--format", "operator-json")
    tracked = subprocess.run(["git", "ls-files"], cwd=tmp_path, check=True, capture_output=True, text=True).stdout
    assert "build/" not in tracked
