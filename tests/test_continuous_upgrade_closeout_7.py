from __future__ import annotations

import json
from pathlib import Path

from sdetkit import cli
from sdetkit import continuous_upgrade_closeout_7 as c7


def _default_page() -> str:
    return (
        getattr(c7, "_CYCLE7_DEFAULT_PAGE", None)
        or getattr(c7, "_CYCLE7_DEFAULT_PAGE", None)
        or c7._CYCLE7_DEFAULT_PAGE
    )


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _seed_previous_cycle_artifacts(root: Path) -> None:
    summary_payload = {"summary": {"activation_score": 100, "strict_pass": True}, "checks": [1]}
    board_text = (
        "\n".join(
            [
                "# Cycle 6 delivery board",
                "- [ ] Cycle 6 evidence brief committed",
                "- [ ] Cycle 6 continuous upgrade plan committed",
                "- [ ] Cycle 6 template ledger exported",
                "- [ ] Cycle 6 storyline outcomes ledger exported",
                "- [ ] Next-impact roadmap draft captured from cycle 6 outcomes",
            ]
        )
        + "\n"
    )

    candidates = [
        (
            root
            / "docs/artifacts/continuous-upgrade-closeout-pack-6/continuous-upgrade-closeout-summary-6.json",
            json.dumps(summary_payload),
        ),
        (
            root
            / "docs/artifacts/continuous-upgrade-closeout-pack-6/continuous-upgrade-delivery-board-6.md",
            board_text,
        ),
        (
            root
            / "docs/artifacts/continuous-upgrade-closeout-pack-6/continuous-upgrade-closeout-summary-6.json",
            json.dumps(summary_payload),
        ),
        (
            root
            / "docs/artifacts/continuous-upgrade-closeout-pack-6/continuous-upgrade-delivery-board-6.md",
            board_text.replace("Cycle 6", "Cycle 6").replace("cycle 6", "Cycle 6"),
        ),
        (
            root
            / "docs/artifacts/continuous-upgrade-closeout-pack-6/continuous-upgrade-closeout-summary-6.json",
            json.dumps(summary_payload),
        ),
        (
            root
            / "docs/artifacts/continuous-upgrade-closeout-pack-6/continuous-upgrade-delivery-board-6.md",
            board_text.replace("Cycle 6", "Cycle 6").replace("cycle 6", "Cycle 6"),
        ),
    ]

    for path, content in candidates:
        _write(path, content)


def _seed_repo(root: Path) -> None:
    (root / "templates/ci/gitlab").mkdir(parents=True, exist_ok=True)
    (root / "templates/ci/jenkins").mkdir(parents=True, exist_ok=True)
    (root / "templates/ci/tekton").mkdir(parents=True, exist_ok=True)
    (root / "docs/roadmap/plans").mkdir(parents=True, exist_ok=True)
    (root / "docs/roadmap/reports").mkdir(parents=True, exist_ok=True)
    (root / "docs/artifacts").mkdir(parents=True, exist_ok=True)

    _write(
        root / "README.md",
        "\n".join(
            [
                "docs/integrations-continuous-upgrade-closeout-7.md",
                "continuous-upgrade-closeout-7",
                "continuous-upgrade-closeout-7",
            ]
        )
        + "\n",
    )

    (root / "docs").mkdir(parents=True, exist_ok=True)
    _write(
        root / "docs/index.md",
        "\n".join(
            [
                "impact-97-big-upgrade-report.md",
                "integrations-continuous-upgrade-closeout-7.md",
                "artifacts/continuous-upgrade-closeout-7-pack/continuous-upgrade-closeout-7-summary.json",
            ]
        )
        + "\n",
    )

    _write(
        root / "docs/top-10-github-strategy.md",
        "\n".join(
            [
                "- **Cycle 6 — Continuous upgrade closeout lane:** close Cycle 6 continuous-upgrade quality loop.",
                "- **Cycle 6 — Continuous upgrade closeout lane:** close cycle 6 continuous-upgrade quality loop.",
                "- **Cycle 7 — Continuous upgrade closeout lane:** start next-impact continuous upgrade execution.",
                "- **Cycle 7 — Continuous upgrade closeout lane:** start next-impact continuous upgrade execution.",
            ]
        )
        + "\n",
    )

    _write(root / "docs/integrations-continuous-upgrade-closeout-7.md", _default_page())
    _write(root / "docs/impact-97-big-upgrade-report.md", "# Cycle 7 report\n")

    (root / "scripts").mkdir(parents=True, exist_ok=True)
    checker_body = (
        "from __future__ import annotations\n\nif __name__ == 'main_':\n    raise SystemExit(0)\n"
    )
    _write(root / "scripts/check_continuous_upgrade_contract_7.py", checker_body)
    _write(root / "scripts/check_continuous_upgrade_contract_7.py", checker_body)

    _seed_previous_cycle_artifacts(root)

    plan = root / "docs/roadmap/plans/continuous-upgrade-plan-7.json"
    _write(
        plan,
        json.dumps(
            {
                "plan_id": "continuous-upgrade-cycle7-001",
                "contributors": ["maintainers", "release-ops"],
                "upgrade_channels": ["readme", "docs-index", "cli-lanes"],
                "baseline": {"strict_pass_rate": 0.9, "doc_link_coverage": 0.88},
                "target": {"strict_pass_rate": 0.93, "doc_link_coverage": 0.9},
                "owner": "maintainers",
                "rollback_owner": "release-ops",
                "confidence_floor": 0.8,
                "cadence_days": 7,
            },
            indent=2,
        )
        + "\n",
    )


def _find_existing(paths: list[Path]) -> Path:
    for path in paths:
        if path.exists():
            return path
    raise AssertionError(f"none of these paths exist: {[str(p) for p in paths]}")


def test_cycle7_json(tmp_path: Path, capsys) -> None:
    _seed_repo(tmp_path)
    rc = c7.main(["--root", str(tmp_path), "--format", "json", "--strict"])
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert out["name"] == "continuous-upgrade-closeout-7"
    assert out["summary"]["activation_score"] >= 95


def test_cycle7_emit_pack_and_execute(tmp_path: Path) -> None:
    _seed_repo(tmp_path)
    rc = c7.main(
        [
            "--root",
            str(tmp_path),
            "--emit-pack-dir",
            "artifacts/continuous-upgrade-cycle7-pack",
            "--execute",
            "--evidence-dir",
            "artifacts/continuous-upgrade-cycle7-pack/evidence",
            "--format",
            "json",
            "--strict",
        ]
    )
    assert rc == 0

    pack = tmp_path / "artifacts/continuous-upgrade-cycle7-pack"

    _find_existing(
        [
            pack / "continuous-upgrade-closeout-7-summary.json",
        ]
    )
    _find_existing(
        [
            pack / "continuous-upgrade-closeout-7-summary.md",
        ]
    )
    _find_existing(
        [
            pack / "continuous-upgrade-cycle7-evidence-brief.md",
        ]
    )
    _find_existing(
        [
            pack / "continuous-upgrade-cycle7-plan.md",
        ]
    )
    _find_existing(
        [
            pack / "continuous-upgrade-cycle7-template-ledger.json",
        ]
    )
    _find_existing(
        [
            pack / "continuous-upgrade-cycle7-storyline-outcomes-ledger.json",
        ]
    )
    _find_existing(
        [
            pack / "continuous-upgrade-cycle7-kpi-scorecard.json",
        ]
    )
    _find_existing(
        [
            pack / "continuous-upgrade-cycle7-execution-log.md",
        ]
    )
    _find_existing(
        [
            pack / "continuous-upgrade-cycle7-delivery-board.md",
        ]
    )
    _find_existing(
        [
            pack / "continuous-upgrade-cycle7-validation-commands.md",
        ]
    )

    execution_summary = _find_existing(
        [
            pack / "evidence/continuous-upgrade-cycle7-execution-summary.json",
        ]
    )
    execution_data = json.loads(execution_summary.read_text(encoding="utf-8"))
    assert execution_data["failed_commands"] == 0
    assert execution_data["strict_pass"] is True


def test_cycle7_execute_strict_fails_on_command_error(tmp_path: Path, monkeypatch) -> None:
    _seed_repo(tmp_path)
    monkeypatch.setattr(c7, "_EXECUTION_COMMANDS", ['python -c "import sys; sys.exit(3)"'])
    rc = c7.main(
        [
            "--root",
            str(tmp_path),
            "--execute",
            "--evidence-dir",
            "artifacts/continuous-upgrade-cycle7-pack/evidence",
            "--format",
            "json",
            "--strict",
        ]
    )
    assert rc == 1
    execution_summary = _find_existing(
        [
            tmp_path
            / "artifacts/continuous-upgrade-cycle7-pack/evidence/continuous-upgrade-cycle7-execution-summary.json",
        ]
    )
    execution_data = json.loads(execution_summary.read_text(encoding="utf-8"))
    assert execution_data["failed_commands"] == 1
    assert execution_data["strict_pass"] is False


def test_cycle7_strict_fails_without_previous_cycle(tmp_path: Path) -> None:
    _seed_repo(tmp_path)

    removed = False
    for candidate in [
        tmp_path
        / "docs/artifacts/continuous-upgrade-closeout-pack-6/continuous-upgrade-closeout-summary-6.json",
        tmp_path
        / "docs/artifacts/continuous-upgrade-closeout-pack-6/continuous-upgrade-delivery-board-6.md",
        tmp_path
        / "docs/artifacts/continuous-upgrade-closeout-pack-5/continuous-upgrade-closeout-summary-5.json",
        tmp_path
        / "docs/artifacts/continuous-upgrade-closeout-pack-5/continuous-upgrade-delivery-board-5.md",
        tmp_path
        / "docs/artifacts/continuous-upgrade-closeout-pack-6/continuous-upgrade-closeout-summary-6.json",
        tmp_path
        / "docs/artifacts/continuous-upgrade-closeout-pack-6/continuous-upgrade-closeout-summary-6.json",
    ]:
        if candidate.exists():
            candidate.unlink()
            removed = True

    assert removed is True
    assert c7.main(["--root", str(tmp_path), "--strict", "--format", "json"]) == 1


def test_cycle7_cli_dispatch(tmp_path: Path, capsys) -> None:
    _seed_repo(tmp_path)
    rc = cli.main(["continuous-upgrade-closeout-7", "--root", str(tmp_path), "--format", "text"])
    assert rc == 0
    assert "continuous upgrade closeout summary" in capsys.readouterr().out.lower()
