from __future__ import annotations

import json
from pathlib import Path

from sdetkit import cli
from sdetkit import phase1_wrap_30 as d30


def _seed_repo(root: Path) -> None:

    (root / "templates/ci/gitlab").mkdir(parents=True, exist_ok=True)

    (root / "templates/ci/jenkins").mkdir(parents=True, exist_ok=True)

    (root / "templates/ci/tekton").mkdir(parents=True, exist_ok=True)

    (root / "docs/roadmap/plans").mkdir(parents=True, exist_ok=True)

    (root / "docs/roadmap/reports").mkdir(parents=True, exist_ok=True)

    (root / "docs/artifacts").mkdir(parents=True, exist_ok=True)
    (root / "README.md").write_text(
        "docs/integrations-phase1-wrap.md\nphase1-wrap\n",
        encoding="utf-8",
    )
    (root / "docs").mkdir(parents=True, exist_ok=True)
    (root / "docs/index.md").write_text(
        "impact-30-ultra-upgrade-report.md\nintegrations-phase1-wrap.md\n",
        encoding="utf-8",
    )
    (root / "docs/top-10-github-strategy.md").write_text(
        '- ** — Phase-1 wrap + handoff:** publish a full report and lock Phase-2 backlog.\n'
        '- ** — Phase-2 kickoff:** set baseline metrics from end of Phase 1 and define weekly growth targets.\n',
        encoding="utf-8",
    )
    (root / "docs/integrations-phase1-wrap.md").write_text(
        d30._DEFAULT_PAGE_TEMPLATE, encoding="utf-8"
    )
    (root / "docs/impact-30-ultra-upgrade-report.md").write_text(
        '#  report\n', encoding="utf-8"
    )

    for rel in [
        "docs/artifacts/kpi-audit-pack/kpi-audit-summary.json",
        "docs/artifacts/weekly-review-pack/weekly-review-summary.json",
        "docs/artifacts/phase1-hardening-pack/phase1-hardening-summary.json",
    ]:
        p = root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps({"summary": {"activation_score": 93}}, indent=2), encoding="utf-8")


def test_phase1_wrap_wrap_json(tmp_path: Path, capsys) -> None:
    _seed_repo(tmp_path)
    rc = d30.main(["--root", str(tmp_path), "--format", "json", "--strict"])
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert out["name"] == "phase1-wrap"
    assert out["summary"]["activation_score"] >= 90


def test_phase1_wrap_emit_pack_and_execute(tmp_path: Path) -> None:
    _seed_repo(tmp_path)
    rc = d30.main(
        [
            "--root",
            str(tmp_path),
            "--emit-pack-dir",
            "artifacts/phase1-wrap-pack",
            "--execute",
            "--evidence-dir",
            "artifacts/phase1-wrap-pack/evidence",
            "--format",
            "json",
            "--strict",
        ]
    )
    assert rc == 0
    assert (tmp_path / "artifacts/phase1-wrap-pack/phase1-wrap-summary.json").exists()
    assert (tmp_path / "artifacts/phase1-wrap-pack/phase1-wrap-summary.md").exists()
    assert (tmp_path / "artifacts/phase1-wrap-pack/phase1-wrap-phase2-backlog.md").exists()
    assert (tmp_path / "artifacts/phase1-wrap-pack/phase1-wrap-handoff-actions.md").exists()
    assert (tmp_path / "artifacts/phase1-wrap-pack/phase1-wrap-validation-commands.md").exists()
    assert (
        tmp_path / "artifacts/phase1-wrap-pack/evidence/phase1-wrap-execution-summary.json"
    ).exists()


def test_phase1_wrap_strict_fails_when_inputs_missing(tmp_path: Path) -> None:
    _seed_repo(tmp_path)
    (tmp_path / "docs/artifacts/phase1-hardening-pack/phase1-hardening-summary.json").unlink()
    rc = d30.main(["--root", str(tmp_path), "--strict", "--format", "json"])
    assert rc == 1


def test_phase1_wrap_cli_dispatch(tmp_path: Path, capsys) -> None:
    _seed_repo(tmp_path)
    rc = cli.main(["phase1-wrap", "--root", str(tmp_path), "--format", "text"])
    assert rc == 0
    assert ' phase-1 wrap summary' in capsys.readouterr().out
