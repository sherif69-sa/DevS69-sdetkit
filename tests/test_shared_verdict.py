"""One verdict contract, and decision tools that pass results forward."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from sdetkit import gate, merge_readiness, verdict


def _git(cwd: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-c", "user.name=t", "-c", "user.email=t@example.invalid", *args],
        cwd=cwd,
        check=True,
        capture_output=True,
        text=True,
    ).stdout


def _repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "README.md").write_text("demo\n", encoding="utf-8")
    (repo / ".gitignore").write_text("build/\n", encoding="utf-8")
    _git(repo, "init", "-q")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", "init")
    return repo


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("CONTINUE", "SHIP"),
        ("NO-SHIP", "NO_SHIP"),
        ("SHIP_WITH_FINDINGS", "REVIEW"),
        ("verified_candidate", "REVIEW"),
        ("blocked_review_first", "NO_SHIP"),
        ("proof_not_run", "NOT_RUN"),
        ("something new", "NOT_RUN"),
        ("REVIEW", "REVIEW"),
    ],
)
def test_legacy_vocabularies_map_onto_four_decisions(raw: str, expected: str) -> None:
    assert verdict.normalize_decision(raw) == expected


def test_the_most_severe_verdict_wins() -> None:
    combined = verdict.combine_verdicts(
        "merge",
        [
            verdict.build_verdict(source="checks", decision="SHIP"),
            verdict.build_verdict(source="loop", decision="REVIEW", next_action="review patch"),
            verdict.build_verdict(source="gate", decision="NO-SHIP", next_action="fix gate"),
        ],
    )

    assert combined["decision"] == "NO_SHIP"
    assert combined["next_action"] == "fix gate"
    assert "gate: NO_SHIP" in combined["reasons"]
    assert combined["merge_authorized"] is False


def test_an_empty_combination_is_not_run() -> None:
    assert verdict.combine_verdicts("x", [])["decision"] == "NOT_RUN"


def test_gate_fast_records_provenance_and_verdict(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    repo = _repo(tmp_path)
    monkeypatch.setattr(
        gate,
        "_run",
        lambda cmd, cwd: {"cmd": cmd, "rc": 0, "ok": True, "stdout": "", "stderr": ""},
    )

    rc = gate.main(["fast", "--root", str(repo), "--format", "json", "--no-doctor"])

    payload = json.loads(capsys.readouterr().out)
    assert rc == 0
    assert payload["provenance"]["head_sha"] == _git(repo, "rev-parse", "HEAD").strip()
    assert payload["provenance"]["tree_clean"] is True
    assert payload["verdict"]["schema_version"] == "sdetkit.verdict.v1"
    assert payload["verdict"]["decision"] == "SHIP"


def _fast_artifact(repo: Path, *, ok: bool = True, head: str | None = None) -> Path:
    path = repo / "build" / "gate-fast.json"
    path.parent.mkdir(exist_ok=True)
    payload = {
        "profile": "fast",
        "ok": ok,
        "failed_steps": [] if ok else ["pytest"],
        "steps": [],
        "provenance": {
            "head_sha": head or _git(repo, "rev-parse", "HEAD").strip(),
            "tree_clean": True,
        },
    }
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def test_gate_release_reuses_a_fresh_gate_fast_result(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    repo = _repo(tmp_path)
    artifact = _fast_artifact(repo)
    calls: list[list[str]] = []

    def fake_run(cmd: list[str], cwd: Path) -> dict[str, object]:
        calls.append(cmd)
        return {"cmd": cmd, "rc": 0, "ok": True, "stdout": "", "stderr": ""}

    monkeypatch.setattr(gate, "_run", fake_run)

    rc = gate.main(
        ["release", "--root", str(repo), "--format", "json", "--reuse-fast", str(artifact)]
    )

    payload = json.loads(capsys.readouterr().out)
    assert rc == 0
    assert [cmd[3] for cmd in calls] == ["doctor", "security"]
    fast_step = payload["steps"][-1]
    assert fast_step["id"] == "gate_fast"
    assert fast_step["reused_from"] == artifact.as_posix()
    assert payload["verdict"]["decision"] == "SHIP"


def test_a_reused_failing_gate_fast_fails_the_release(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    repo = _repo(tmp_path)
    artifact = _fast_artifact(repo, ok=False)
    monkeypatch.setattr(
        gate,
        "_run",
        lambda cmd, cwd: {"cmd": cmd, "rc": 0, "ok": True, "stdout": "", "stderr": ""},
    )

    rc = gate.main(
        ["release", "--root", str(repo), "--format", "json", "--reuse-fast", str(artifact)]
    )

    payload = json.loads(capsys.readouterr().out)
    assert rc == 2
    assert payload["failed_steps"] == ["gate_fast"]
    assert payload["verdict"]["decision"] == "NO_SHIP"


@pytest.mark.parametrize("problem", ["other_commit", "dirty_tree", "missing", "not_fast"])
def test_gate_release_reruns_gate_fast_when_the_result_cannot_be_trusted(
    problem: str,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    repo = _repo(tmp_path)
    artifact = _fast_artifact(repo, head="0" * 40 if problem == "other_commit" else None)
    if problem == "dirty_tree":
        (repo / "README.md").write_text("changed\n", encoding="utf-8")
    if problem == "missing":
        artifact.unlink()
    if problem == "not_fast":
        artifact.write_text(json.dumps({"profile": "release"}), encoding="utf-8")
    calls: list[list[str]] = []

    def fake_run(cmd: list[str], cwd: Path) -> dict[str, object]:
        calls.append(cmd)
        return {"cmd": cmd, "rc": 0, "ok": True, "stdout": "", "stderr": ""}

    monkeypatch.setattr(gate, "_run", fake_run)

    gate.main(["release", "--root", str(repo), "--format", "json", "--reuse-fast", str(artifact)])

    payload = json.loads(capsys.readouterr().out)
    assert [cmd[3] for cmd in calls] == ["doctor", "security", "gate"]
    assert payload["steps"][-1]["reuse_rejected"]


def _checks(tmp_path: Path, conclusion: str = "success") -> Path:
    path = tmp_path / "checks.json"
    path.write_text(
        json.dumps(
            {
                "required_contexts": ["ci"],
                "checks": [{"name": "ci", "status": "completed", "conclusion": conclusion}],
            }
        ),
        encoding="utf-8",
    )
    return path


def test_merge_readiness_takes_the_most_severe_upstream_verdict(tmp_path: Path) -> None:
    gate_result = tmp_path / "gate-release.json"
    gate_result.write_text(
        json.dumps({"verdict": verdict.build_verdict(source="gate release", decision="NO-SHIP")}),
        encoding="utf-8",
    )

    report = merge_readiness.build_merge_readiness(
        checks_json=_checks(tmp_path), evidence_paths=[gate_result]
    )

    assert report["status"] == "green"
    assert report["verdict"]["decision"] == "NO_SHIP"
    assert report["upstream_verdicts"][0]["verdict"]["source"] == "gate release"
    assert report["merge_authorized"] is False


def test_merge_readiness_ships_only_when_checks_and_evidence_agree(tmp_path: Path) -> None:
    loop = tmp_path / "loop.json"
    loop.write_text(
        json.dumps({"verdict": verdict.build_verdict(source="diagnose run", decision="SHIP")}),
        encoding="utf-8",
    )

    report = merge_readiness.build_merge_readiness(
        checks_json=_checks(tmp_path), evidence_paths=[loop]
    )

    assert report["verdict"]["decision"] == "SHIP"


def test_merge_readiness_treats_evidence_without_a_verdict_as_not_run(tmp_path: Path) -> None:
    other = tmp_path / "other.json"
    other.write_text(json.dumps({"hello": "world"}), encoding="utf-8")

    report = merge_readiness.build_merge_readiness(
        checks_json=_checks(tmp_path), evidence_paths=[other]
    )

    assert report["verdict"]["decision"] == "NOT_RUN"
    assert "no sdetkit.verdict.v1" in report["upstream_verdicts"][0]["error"]


def test_merge_readiness_cli_accepts_evidence(tmp_path: Path) -> None:
    gate_result = tmp_path / "gate.json"
    gate_result.write_text(
        json.dumps({"verdict": verdict.build_verdict(source="gate fast", decision="CONTINUE")}),
        encoding="utf-8",
    )

    rc = merge_readiness.main(
        [
            "--checks-json",
            str(_checks(tmp_path, conclusion="failure")),
            "--evidence",
            str(gate_result),
            "--out-dir",
            str(tmp_path / "out"),
        ]
    )

    report = json.loads((tmp_path / "out" / "merge-readiness.json").read_text(encoding="utf-8"))
    assert rc == 0
    assert report["verdict"]["decision"] == "NO_SHIP"
    markdown = (tmp_path / "out" / "merge-readiness.md").read_text(encoding="utf-8")
    assert "Verdict: `NO_SHIP`" in markdown


def test_mission_control_and_the_remediation_loop_emit_the_shared_verdict(
    tmp_path: Path,
) -> None:
    from sdetkit import mission_control, remediation_loop

    bundle = mission_control.build_bundle(repo=tmp_path, out_dir=tmp_path / "mc")
    assert bundle["verdict"]["decision"] == "NOT_RUN"

    log = tmp_path / "logs" / "tests" / "ci_log.txt"
    log.parent.mkdir(parents=True)
    log.write_text(
        "Run python -m pytest -q\nFAILED tests/test_a.py::test_b - AssertionError\n"
        "Process completed with exit code 1\n",
        encoding="utf-8",
    )
    summary = remediation_loop.run_remediation_loop(
        log_paths=[log], repo_root=tmp_path, out_dir=tmp_path / "loop", memory_path=None
    )
    assert summary["verdict"]["decision"] == "REVIEW"
