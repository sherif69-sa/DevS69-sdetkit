"""Decision cards and recorded human decisions on remediation-loop results."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from sdetkit import decision_card, human_decision, merge_readiness, remediation_loop, repo_memory
from tests._cli_inprocess import run_cli

FORMAT_LOG = (
    "Run python -m ruff format --check src\n"
    "Would reformat: src/app.py\n"
    "1 file would be reformatted\n"
    "Process completed with exit code 1\n"
)
TEST_LOG = (
    "Run python -m pytest -q\n"
    "FAILED tests/test_a.py::test_b - AssertionError\n"
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


@pytest.fixture(autouse=True)
def _isolated_cwd(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)


def _git(cwd: Path, *args: str) -> None:
    subprocess.run(
        ["git", "-c", "user.name=t", "-c", "user.email=t@example.invalid", *args],
        cwd=cwd,
        check=True,
        capture_output=True,
    )


def _run(tmp_path: Path, log_text: str = FORMAT_LOG, *, prove: bool = True) -> Path:
    repo = tmp_path / "repo"
    if not repo.exists():
        (repo / "src").mkdir(parents=True)
        (repo / "src" / "app.py").write_text("x  =  1\n", encoding="utf-8")
        (repo / ".pre-commit-config.yaml").write_text(PRE_COMMIT_CONFIG, encoding="utf-8")
        _git(repo, "init", "-q")
        _git(repo, "remote", "add", "origin", "https://github.com/acme/widget.git")
        _git(repo, "add", "-A")
        _git(repo, "commit", "-qm", "init")
    log = tmp_path / "logs" / "lint" / "ci_log.txt"
    log.parent.mkdir(parents=True, exist_ok=True)
    log.write_text(log_text, encoding="utf-8")
    out = tmp_path / "out"
    remediation_loop.run_remediation_loop(
        log_paths=[log],
        repo_root=repo,
        out_dir=out,
        prove=prove,
        timeout_seconds=120,
        memory_path=None,
    )
    return out


def _card(out: Path) -> dict:
    return json.loads((out / decision_card.CARD_JSON).read_text(encoding="utf-8"))


def test_a_verified_run_ends_with_an_approvable_card(tmp_path: Path) -> None:
    out = _run(tmp_path)
    card = _card(out)

    assert card["loop_decision"] == "verified_candidate"
    assert card["card_id"] == decision_card.card_digest(card)
    assert card["proposal"]["files"] == ["src/app.py"]
    assert card["proposal"]["additions"] == 1
    assert card["proof"]["chain"]["ok"] is True
    assert card["pattern"]["plan_classification"] == "formatting_only"
    assert [option["decision"] for option in card["options"]] == ["approve", "reject"]
    assert all(card[flag] is False for flag in decision_card.DECISION_BOUNDARY)

    comment = (out / decision_card.CARD_MARKDOWN).read_text(encoding="utf-8")
    assert comment.startswith(decision_card.COMMENT_MARKER)
    assert "| Proof chain | verified |" in comment
    assert f"git apply --check {(out / 'proposed.patch').as_posix()}" in comment
    loop = json.loads((out / "loop.json").read_text(encoding="utf-8"))
    assert loop["artifacts"]["decision_card"].endswith(decision_card.CARD_JSON)


def test_a_review_first_run_can_only_be_rejected(tmp_path: Path) -> None:
    out = _run(tmp_path, TEST_LOG)
    card = _card(out)

    assert card["loop_decision"] == "review_first"
    assert card["proposal"]["present"] is False
    assert [option["decision"] for option in card["options"]] == ["reject"]
    with pytest.raises(human_decision.DecisionRefused, match="approve is not an option"):
        human_decision.record_decision(
            card_path=out / decision_card.CARD_JSON,
            decision="approve",
            reviewer="sam",
            memory_path=None,
        )


def test_an_approval_is_bound_to_the_card_and_patch_and_applies_nothing(tmp_path: Path) -> None:
    out = _run(tmp_path)
    card = _card(out)
    memory = tmp_path / "memory.jsonl"

    record = human_decision.record_decision(
        card_path=out / decision_card.CARD_JSON,
        decision="approve",
        reviewer="sam",
        note="looks right",
        memory_path=memory,
    )

    assert record["card_id"] == card["card_id"]
    assert record["patch_sha256"] == card["proposal"]["sha256"]
    assert record["verdict"]["decision"] == "REVIEW"
    assert record["patch_application_allowed"] is False
    assert "git apply" in record["next_action"]
    # The repository is untouched: approving records a decision, the person applies.
    assert (tmp_path / "repo" / "src" / "app.py").read_text(encoding="utf-8") == "x  =  1\n"
    stored = repo_memory.load_records(memory)
    assert stored[-1]["loop_decision"] == "human_approved"
    assert stored[-1]["reviewer"] == "sam"


@pytest.mark.parametrize("tamper", ["patch", "card", "artifact"])
def test_a_changed_card_or_patch_cannot_be_approved(tmp_path: Path, tamper: str) -> None:
    out = _run(tmp_path)
    card_path = out / decision_card.CARD_JSON
    if tamper == "patch":
        with (out / "proposed.patch").open("a", encoding="utf-8") as handle:
            handle.write("+extra\n")
    elif tamper == "card":
        card = _card(out)
        card["proof"]["patch_score"] = 100
        card_path.write_text(json.dumps(card), encoding="utf-8")
    else:
        verifier = out / "protected-verifier-result.json"
        verifier.write_text(verifier.read_text(encoding="utf-8") + " ", encoding="utf-8")

    with pytest.raises(human_decision.DecisionRefused):
        human_decision.record_decision(
            card_path=card_path, decision="approve", reviewer="sam", memory_path=None
        )


def test_repeated_rejections_hold_a_surface_for_review(tmp_path: Path) -> None:
    out = _run(tmp_path)
    memory = tmp_path / "memory.jsonl"
    for _ in range(2):
        human_decision.record_decision(
            card_path=out / decision_card.CARD_JSON,
            decision="reject",
            reviewer="sam",
            memory_path=memory,
        )

    insights = repo_memory.build_pattern_insights(repo_memory.load_records(memory))

    assert insights["recurring_review_first_surfaces"] == [
        {"value": "formatting", "blocked_count": 2}
    ]


def test_merge_readiness_reads_the_decision_record(tmp_path: Path) -> None:
    out = _run(tmp_path)
    human_decision.record_decision(
        card_path=out / decision_card.CARD_JSON,
        decision="approve",
        reviewer="sam",
        memory_path=None,
    )
    checks = tmp_path / "checks.json"
    checks.write_text(
        json.dumps(
            {
                "required_contexts": ["ci"],
                "checks": [{"name": "ci", "status": "completed", "conclusion": "success"}],
            }
        ),
        encoding="utf-8",
    )

    report = merge_readiness.build_merge_readiness(
        checks_json=checks, evidence_paths=[out / human_decision.RECORD_JSON]
    )

    assert report["verdict"]["decision"] == "REVIEW"
    assert report["merge_authorized"] is False


def test_card_and_decide_commands(tmp_path: Path) -> None:
    out = _run(tmp_path)

    card = run_cli("diagnose", "card", "--loop-dir", str(out))
    comment = run_cli("diagnose", "card", "--loop-dir", str(out), "--format", "md")
    refused = run_cli(
        "diagnose", "decide", "--card", str(out / "missing.json"), "--reject", "--reviewer", "sam"
    )
    decided = run_cli(
        "diagnose",
        "decide",
        "--card",
        str(out / decision_card.CARD_JSON),
        "--reject",
        "--reviewer",
        "sam",
        "--no-memory",
    )

    assert card.returncode == 0
    assert "options=approve,reject" in card.stdout
    assert comment.stdout.startswith(decision_card.COMMENT_MARKER)
    assert refused.returncode == 2
    assert decided.returncode == 0
    assert "decision=reject" in decided.stdout
    assert run_cli("diagnose", "card", "--loop-dir", str(tmp_path / "nope")).returncode == 2
