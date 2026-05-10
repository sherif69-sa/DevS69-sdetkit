from __future__ import annotations

import json
from pathlib import Path

from sdetkit import cli
from sdetkit import objection_handling as d48
from tests.workflow_fixture_seed import seed_contract_anchors


def _seed_repo(root: Path) -> None:
    (root / "docs").mkdir(parents=True, exist_ok=True)
    (root / "scripts").mkdir(parents=True, exist_ok=True)

    (root / "docs/objection-handling.md").write_text(
        """# Objection Handling

## Who should run objection-handling

Product, support, release, and engineering owners preparing sdetkit adoption.

## When to use sdetkit

Use sdetkit when teams need repeatable validation, evidence packs, and release-confidence gates.

## When not to use sdetkit

Do not use sdetkit as a replacement for product ownership, security review, or incident judgment.

## Top objections and responses

- Too much process: start with the fast gate and add only the evidence pack needed for the release.
- Hard to adopt: use the playbook path first, then wire the stricter gate after one green run.
- Unclear owner: keep support, release, and engineering sign-off visible in the rollout note.

## Fast verification commands

python -m sdetkit objection-handling --format json --strict
python -m sdetkit objection-handling --emit-pack-dir docs/artifacts/objection-handling-pack --format json --strict
python -m sdetkit objection-handling --execute --evidence-dir docs/artifacts/objection-handling-pack/evidence --format json --strict
python scripts/check_objection_handling_contract.py

## Escalation and rollout policy

Escalate unresolved adoption objections in release-communications before promotion.
""",
        encoding="utf-8",
    )

    (root / "README.md").write_text(
        "# README\\n\\nSee docs/objection-handling.md for objection handling.\\n",
        encoding="utf-8",
    )
    (root / "docs/index.md").write_text(
        "# Docs\n\n- docs/objection-handling.md\n- [Objection handling](objection-handling.md)\n",
        encoding="utf-8",
    )
    (root / "docs/release-communications.md").write_text(
        "# Release Communications\n\nrelease-communications includes docs/objection-handling.md and objection-handling rollout notes.\n",
        encoding="utf-8",
    )
    reliability_summary = root / "docs/artifacts/reliability-pack/reliability-summary.json"
    reliability_summary.parent.mkdir(parents=True, exist_ok=True)
    reliability_summary.write_text(
        '{"summary": {"weighted_points": {"earned": 100, "total": 100}, "faq_score": 100}}\n',
        encoding="utf-8",
    )

    (root / "scripts/check_objection_handling_contract.py").write_text(
        """from __future__ import annotations

if __name__ == '__main__':
    raise SystemExit(0)
""",
        encoding="utf-8",
    )


def test_objection_json(tmp_path: Path, capsys) -> None:
    _seed_repo(tmp_path)
    seed_contract_anchors(tmp_path)
    rc = d48.main(["--root", str(tmp_path), "--format", "json", "--strict"])
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert out["name"] == "objection-handling"
    assert out["summary"]["faq_score"] >= 85
    assert out["summary"]["weighted_points"]["earned"] >= 85


def test_objection_emit_pack_and_execute(tmp_path: Path) -> None:
    _seed_repo(tmp_path)
    seed_contract_anchors(tmp_path)
    rc = d48.main(
        [
            "--root",
            str(tmp_path),
            "--emit-pack-dir",
            "artifacts/objection-pack-48",
            "--execute",
            "--evidence-dir",
            "artifacts/objection-pack-48/evidence",
            "--format",
            "json",
            "--strict",
        ]
    )
    assert rc == 0
    expected_artifacts = [
        "objection-handling-summary.json",
        "objection-handling-scorecard.md",
        "objection-handling-response-matrix.md",
        "objection-handling-playbook.md",
        "objection-handling-validation-commands.md",
    ]
    for artifact in expected_artifacts:
        assert (tmp_path / "artifacts/objection-pack-48" / artifact).exists()


def test_objection_strict_fails_when_required_docs_page_missing(tmp_path: Path) -> None:
    _seed_repo(tmp_path)
    seed_contract_anchors(tmp_path)
    (tmp_path / "docs/objection-handling.md").unlink()
    rc = d48.main(["--root", str(tmp_path), "--strict", "--format", "json"])
    assert rc == 1


def test_objection_cli_dispatch(tmp_path: Path, capsys) -> None:
    _seed_repo(tmp_path)
    seed_contract_anchors(tmp_path)
    rc = cli.main(["objection-handling", "--root", str(tmp_path), "--format", "text"])
    assert rc == 0
    assert "Objection handling" in capsys.readouterr().out
