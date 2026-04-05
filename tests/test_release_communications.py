from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from sdetkit import cli
from sdetkit import release_communications as rn


def _write_release_summary(path: Path, gate_status: str = "pass", score: float = 96.4) -> Path:
    summary = path / "release-summary.json"
    summary.write_text(
        json.dumps(
            {
                "summary": {"release_score": score, "gate_status": gate_status},
                "recommendations": ["Track one follow-up risk in backlog."],
            }
        )
        + "\n",
        encoding="utf-8",
    )
    return summary


def _write_release_communications_page(root: Path) -> None:
    path = root / "docs/release-communications.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(rn._DEFAULT_PAGE_TEMPLATE, encoding="utf-8")


def test_release_communications_json(tmp_path: Path, capsys) -> None:
    summary = _write_release_summary(tmp_path)
    _write_release_communications_page(tmp_path)

    rc = rn.main(
        [
            "--root",
            str(tmp_path),
            "--release-summary",
            str(summary.relative_to(tmp_path)),
            "--format",
            "json",
        ]
    )
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert out["name"] == "release-communications"
    assert out["summary"]["readiness_label"] == "ready"
    assert out["score"] == 100.0


def test_release_communications_emit_pack_and_execute(tmp_path: Path) -> None:
    summary = _write_release_summary(tmp_path)
    _write_release_communications_page(tmp_path)

    rc = rn.main(
        [
            "--root",
            str(tmp_path),
            "--release-summary",
            str(summary.relative_to(tmp_path)),
            "--emit-pack-dir",
            "artifacts/release-communications-pack",
            "--execute",
            "--evidence-dir",
            "artifacts/release-communications-pack/evidence",
            "--format",
            "json",
        ]
    )
    assert rc == 0
    assert (
        tmp_path / "artifacts/release-communications-pack/release-communications-summary.json"
    ).exists()
    assert (tmp_path / "artifacts/release-communications-pack/release-communications.md").exists()
    assert (
        tmp_path / "artifacts/release-communications-pack/release-communications-audience-blurbs.md"
    ).exists()
    assert (
        tmp_path / "artifacts/release-communications-pack/release-communications-channel-posts.md"
    ).exists()
    assert (
        tmp_path
        / "artifacts/release-communications-pack/release-communications-validation-commands.md"
    ).exists()
    assert (
        tmp_path
        / "artifacts/release-communications-pack/evidence/release-communications-execution-summary.json"
    ).exists()


def test_release_communications_strict_gate_fails_when_not_ready(tmp_path: Path) -> None:
    summary = _write_release_summary(tmp_path, gate_status="warn", score=83)
    _write_release_communications_page(tmp_path)

    rc = rn.main(
        [
            "--root",
            str(tmp_path),
            "--release-summary",
            str(summary.relative_to(tmp_path)),
            "--format",
            "json",
            "--strict",
        ]
    )
    assert rc == 1


def test_release_communications_strict_gate_fails_when_docs_contract_missing(
    tmp_path: Path,
) -> None:
    summary = _write_release_summary(tmp_path)
    path = tmp_path / "docs/release-communications.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("# Release communications\n", encoding="utf-8")

    rc = rn.main(
        [
            "--root",
            str(tmp_path),
            "--release-summary",
            str(summary.relative_to(tmp_path)),
            "--format",
            "json",
            "--strict",
        ]
    )
    assert rc == 1


def test_cli_dispatch(tmp_path: Path, capsys) -> None:
    summary = _write_release_summary(tmp_path)
    _write_release_communications_page(tmp_path)

    rc = cli.main(
        [
            "release-communications",
            "--root",
            str(tmp_path),
            "--release-summary",
            str(summary.relative_to(tmp_path)),
            "--format",
            "text",
        ]
    )
    assert rc == 0
    assert "Release communications" in capsys.readouterr().out


def test_execute_commands_run_inside_requested_root(monkeypatch, tmp_path: Path) -> None:
    calls: list[dict[str, object]] = []

    def _fake_run(argv, **kwargs):
        calls.append({"argv": argv, **kwargs})
        return subprocess.CompletedProcess(argv, 0, stdout="ok", stderr="")

    monkeypatch.setattr(rn.subprocess, "run", _fake_run)

    rows = rn._execute_commands(
        tmp_path,
        [
            "python -m sdetkit release-communications --format json --strict",
            "python scripts/check_release_communications_contract.py --skip-evidence",
        ],
        5,
    )

    assert len(rows) == 2
    assert all(call["cwd"] == str(tmp_path) for call in calls)
    assert calls[0]["argv"][0] == sys.executable
    assert calls[1]["argv"][1].endswith("scripts/check_release_communications_contract.py")
