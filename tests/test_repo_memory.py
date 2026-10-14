"""RepoMemory: remediation history that accumulates and informs the scorer."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from sdetkit import remediation_loop, repo_memory, trajectory_store
from tests._cli_inprocess import run_cli

FORMAT_LOG = (
    "Run python -m ruff format --check src\n"
    "Would reformat: src/app.py\n"
    "1 file would be reformatted\n"
    "Process completed with exit code 1\n"
)
PRE_COMMIT_CONFIG = """repos:
  - repo: local
    hooks:
      - id: ruff-format
        name: ruff format
        entry: python -m ruff format --check
        language: system
        types: [python]
"""


def _record(decision: str, *, classification: str = "formatting_only", surface: str = "formatting"):
    return {
        "loop_decision": decision,
        "plan_classification": classification,
        "failure_surface": surface,
        "action": "run_pre_commit",
        "diagnostic_id": f"{classification}-1",
        "safety_gate": {"review_first": False, "safe_fix_allowed": True, "reporting_only": True},
    }


def test_a_fix_pattern_counts_as_proven_only_after_repeated_verification() -> None:
    once = repo_memory.build_pattern_insights([_record("verified_candidate")])
    twice = repo_memory.build_pattern_insights([_record("verified_candidate")] * 2)

    assert once["recurring_safe_fix_patterns"] == []
    assert twice["recurring_safe_fix_patterns"] == [
        {"failure_class": "formatting_only", "action": "run_pre_commit", "verified_count": 2}
    ]
    assert twice["automation_allowed"] is False
    assert twice["safety_gate_evidence"]["safe_fix_allowed_count"] == 2


def test_repeatedly_blocked_surfaces_are_held_for_review() -> None:
    insights = repo_memory.build_pattern_insights(
        [_record("blocked_review_first"), _record("blocked_review_first")]
    )

    assert insights["recurring_review_first_surfaces"] == [
        {"value": "formatting", "blocked_count": 2}
    ]


def test_profile_and_query_summarise_the_history(tmp_path: Path) -> None:
    memory = tmp_path / "memory.jsonl"
    repo_memory.append_records(
        memory,
        [_record("verified_candidate"), _record("review_first", classification="test_failure")],
    )
    memory.write_text(memory.read_text(encoding="utf-8") + "not json\n", encoding="utf-8")

    records = repo_memory.load_records(memory)
    profile = repo_memory.build_profile(records)

    assert profile["profile_status"] == "observed"
    assert profile["record_count"] == 2
    assert profile["by_decision"] == {"review_first": 1, "verified_candidate": 1}
    assert (
        repo_memory.query_records(records, failure_class="test_failure")[0]["loop_decision"]
        == "review_first"
    )
    assert repo_memory.build_profile([])["profile_status"] == "empty"


def test_memory_cli_views(tmp_path: Path) -> None:
    memory = tmp_path / "memory.jsonl"
    repo_memory.append_records(memory, [_record("verified_candidate")] * 2)

    profile = run_cli("diagnose", "memory", "--memory", str(memory))
    insights = run_cli(
        "diagnose", "memory", "insights", "--memory", str(memory), "--format", "json"
    )
    query = run_cli("diagnose", "memory", "query", "--memory", str(memory), "--decision", "x")
    invalid = run_cli("diagnose", "memory", "--memory", str(memory), "--min-repeats", "0")

    assert profile.returncode == 0
    assert "proven_fix=formatting_only/run_pre_commit verified=2" in profile.stdout
    assert json.loads(insights.stdout)["recurring_safe_fix_patterns"][0]["verified_count"] == 2
    assert "matched=0" in query.stdout
    assert invalid.returncode == 2


def test_trajectory_store_can_append(tmp_path: Path) -> None:
    out = tmp_path / "trajectory.jsonl"
    trajectory_store.write_trajectory_records([{"a": 1}], out)
    trajectory_store.write_trajectory_records([{"b": 2}], out, append=True)
    trajectory_store.write_trajectory_records([{"c": 3}], out, append=True)

    assert len(out.read_text(encoding="utf-8").splitlines()) == 3


def _git(cwd: Path, *args: str) -> None:
    subprocess.run(
        ["git", "-c", "user.name=t", "-c", "user.email=t@example.invalid", *args],
        cwd=cwd,
        check=True,
        capture_output=True,
    )


def test_the_loop_stops_penalising_a_fix_it_has_verified_before(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    repo = tmp_path / "repo"
    (repo / "src").mkdir(parents=True)
    (repo / "src" / "app.py").write_text("x  =  1\n", encoding="utf-8")
    (repo / ".pre-commit-config.yaml").write_text(PRE_COMMIT_CONFIG, encoding="utf-8")
    _git(repo, "init", "-q")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", "init")
    log = tmp_path / "logs" / "lint" / "ci_log.txt"
    log.parent.mkdir(parents=True)
    log.write_text(FORMAT_LOG, encoding="utf-8")
    memory = tmp_path / "memory.jsonl"

    scores: list[int] = []
    flags: list[list[str]] = []
    for run in range(3):
        out = tmp_path / f"out{run}"
        summary = remediation_loop.run_remediation_loop(
            log_paths=[log],
            repo_root=repo,
            out_dir=out,
            prove=True,
            timeout_seconds=120,
            memory_path=memory,
        )
        assert summary["decision"] == "verified_candidate", summary["reasons"]
        score = json.loads((out / "patch-score.json").read_text(encoding="utf-8"))
        scores.append(score["score"])
        flags.append([flag["code"] for flag in score["risk_flags"]])

    assert scores == [90, 90, 100]
    assert "SAFE_PATTERN_NOT_REPEATED" in flags[0]
    assert "SAFE_PATTERN_NOT_REPEATED" not in flags[2]
    assert summary["memory"]["records_before"] == 2
    assert summary["memory"]["proven_fix_patterns"] == 1
    assert "2 earlier records, 1 proven fix patterns" in (out / "loop-report.md").read_text(
        encoding="utf-8"
    )


def test_no_memory_leaves_no_history_behind(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    log = tmp_path / "logs" / "lint" / "ci_log.txt"
    log.parent.mkdir(parents=True)
    log.write_text(FORMAT_LOG, encoding="utf-8")

    summary = remediation_loop.run_remediation_loop(
        log_paths=[log], repo_root=tmp_path, out_dir=tmp_path / "out", memory_path=None
    )

    assert summary["memory"] == {"enabled": False}
    assert not (tmp_path / ".sdetkit").exists()
