from __future__ import annotations

import json
from pathlib import Path

from sdetkit import cli
from sdetkit import triage_speed_case_study_prep as d70
from tests.workflow_fixture_seed import seed_contract_anchors


def _seed_repo(root: Path) -> None:
    (root / "docs/roadmap/plans").mkdir(parents=True, exist_ok=True)
    (root / "docs/artifacts").mkdir(parents=True, exist_ok=True)
    (root / "README.md").write_text(
        "docs/integrations-case-study-prep2-workflow.md\ncase-study-prep2-closeout\n",
        encoding="utf-8",
    )
    (root / "docs/index.md").write_text(
        "impact-70-big-upgrade-report.md\nintegrations-case-study-prep2-workflow.md\n",
        encoding="utf-8",
    )
    (root / "docs/top-10-github-strategy.md").write_text("\n\n", encoding="utf-8")
    (root / "docs/integrations-case-study-prep2-workflow.md").write_text(
        d70._DEFAULT_PAGE_TEMPLATE, encoding="utf-8"
    )

    summary = (
        root
        / "docs/artifacts/case-study-prep1-closeout-pack/case-study-prep1-closeout-summary.json"
    )
    summary.parent.mkdir(parents=True, exist_ok=True)
    summary.write_text(
        json.dumps(
            {
                "summary": {"activation_score": 100, "strict_pass": True},
                "checks": [{"passed": True}],
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    board = (
        root / "docs/artifacts/case-study-prep1-closeout-pack/case-study-prep1-delivery-board.md"
    )
    board.write_text(
        "\n".join(["#  delivery board", *["- [ ]  item" for _ in range(5)]]) + "\n",
        encoding="utf-8",
    )
    (root / "docs/roadmap/plans/triage-speed-case-study.json").write_text(
        json.dumps(
            {
                "case_id": "case-study-prep2-001",
                "metric": "triage-speed",
                "baseline": {"value": 41},
                "after": {"value": 19},
                "confidence": 0.92,
                "owner": "ops-quality",
            },
            indent=2,
        ),
        encoding="utf-8",
    )


def test_case_study_prep2_json(tmp_path: Path, capsys) -> None:
    _seed_repo(tmp_path)
    seed_contract_anchors(tmp_path)
    rc = d70.main(["--root", str(tmp_path), "--format", "json", "--strict"])
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert out["name"] == "case-study-prep2-closeout"
    assert out["summary"]["strict_pass"] is True


def test_case_study_prep2_emit_pack_and_execute(tmp_path: Path) -> None:
    _seed_repo(tmp_path)
    seed_contract_anchors(tmp_path)
    rc = d70.main(
        [
            "--root",
            str(tmp_path),
            "--emit-pack-dir",
            "artifacts/case-study-prep2-closeout-pack",
            "--execute",
            "--evidence-dir",
            "artifacts/case-study-prep2-closeout-pack/evidence",
            "--format",
            "json",
            "--strict",
        ]
    )
    assert rc == 0
    assert (
        tmp_path / "artifacts/case-study-prep2-closeout-pack/case-study-prep2-closeout-summary.json"
    ).exists()
    assert (
        tmp_path / "artifacts/case-study-prep2-closeout-pack/case-study-prep2-delivery-board.md"
    ).exists()
    assert (
        tmp_path
        / "artifacts/case-study-prep2-closeout-pack/evidence/case-study-prep2-execution-summary.json"
    ).exists()


def test_case_study_prep2_strict_fails_without_case_study_prep1_summary(
    tmp_path: Path,
) -> None:
    _seed_repo(tmp_path)
    seed_contract_anchors(tmp_path)
    (
        tmp_path
        / "docs/artifacts/case-study-prep1-closeout-pack/case-study-prep1-closeout-summary.json"
    ).unlink()
    assert d70.main(["--root", str(tmp_path), "--strict", "--format", "json"]) == 1


def test_case_study_prep2_cli_dispatch(tmp_path: Path, capsys) -> None:
    _seed_repo(tmp_path)
    seed_contract_anchors(tmp_path)
    rc = cli.main(["case-study-prep2-closeout", "--root", str(tmp_path), "--format", "text"])
    assert rc == 0
    alias_rc = cli.main(["case-study-prep2-closeout", "--root", str(tmp_path), "--format", "text"])
    assert alias_rc == 0
    assert "Case Study Prep 2 Closeout summary" in capsys.readouterr().out
