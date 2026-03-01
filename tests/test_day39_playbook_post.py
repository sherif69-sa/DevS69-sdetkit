from __future__ import annotations

import json
from pathlib import Path

from sdetkit import cli
from sdetkit import day39_playbook_post as d39


def _seed_repo(root: Path) -> None:

    (root / "templates/ci/gitlab").mkdir(parents=True, exist_ok=True)

    (root / "templates/ci/jenkins").mkdir(parents=True, exist_ok=True)

    (root / "templates/ci/tekton").mkdir(parents=True, exist_ok=True)

    (root / "docs/roadmap/plans").mkdir(parents=True, exist_ok=True)

    (root / "docs/roadmap/reports").mkdir(parents=True, exist_ok=True)

    (root / "docs/artifacts").mkdir(parents=True, exist_ok=True)
    (root / "README.md").write_text(
        "docs/integrations-day39-playbook-post.md\nday39-playbook-post\n",
        encoding="utf-8",
    )
    (root / "docs").mkdir(parents=True, exist_ok=True)
    (root / "docs/index.md").write_text(
        "day-39-big-upgrade-report.md\nintegrations-day39-playbook-post.md\n",
        encoding="utf-8",
    )
    (root / "docs/top-10-github-strategy.md").write_text(
        "- **Day 39 — Playbook post #1:** publish the first reliability playbook post from Day 38 data.\n"
        "- **Day 40 — Scale lane kickoff:** expand publication motion across additional channels.\n",
        encoding="utf-8",
    )
    (root / "docs/integrations-day39-playbook-post.md").write_text(
        d39._DAY39_DEFAULT_PAGE, encoding="utf-8"
    )
    (root / "docs/day-39-big-upgrade-report.md").write_text("# Day 39 report\n", encoding="utf-8")

    summary = (
        root / "docs/artifacts/day38-distribution-batch-pack/day38-distribution-batch-summary.json"
    )
    summary.parent.mkdir(parents=True, exist_ok=True)
    summary.write_text(
        json.dumps(
            {
                "summary": {"activation_score": 99, "strict_pass": True},
                "checks": [{"check_id": "ok", "passed": True}],
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    board = root / "docs/artifacts/day38-distribution-batch-pack/day38-delivery-board.md"
    board.write_text(
        "\n".join(
            [
                "# Day 38 delivery board",
                "- [ ] Day 38 channel plan committed",
                "- [ ] Day 38 post copy reviewed with owner + backup",
                "- [ ] Day 38 scheduling matrix exported",
                "- [ ] Day 38 KPI scorecard snapshot exported",
                "- [ ] Day 39 playbook post priorities drafted from Day 38 outcomes",
            ]
        )
        + "\n",
        encoding="utf-8",
    )


def test_day39_playbook_post_json(tmp_path: Path, capsys) -> None:
    _seed_repo(tmp_path)
    rc = d39.main(["--root", str(tmp_path), "--format", "json", "--strict"])
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert out["name"] == "day39-playbook-post"
    assert out["summary"]["activation_score"] >= 95


def test_day39_emit_pack_and_execute(tmp_path: Path) -> None:
    _seed_repo(tmp_path)
    rc = d39.main(
        [
            "--root",
            str(tmp_path),
            "--emit-pack-dir",
            "artifacts/day39-pack",
            "--execute",
            "--evidence-dir",
            "artifacts/day39-pack/evidence",
            "--format",
            "json",
            "--strict",
        ]
    )
    assert rc == 0
    assert (tmp_path / "artifacts/day39-pack/day39-playbook-post-summary.json").exists()
    assert (tmp_path / "artifacts/day39-pack/day39-playbook-post-summary.md").exists()
    assert (tmp_path / "artifacts/day39-pack/day39-playbook-draft.md").exists()
    assert (tmp_path / "artifacts/day39-pack/day39-rollout-plan.csv").exists()
    assert (tmp_path / "artifacts/day39-pack/day39-kpi-scorecard.json").exists()
    assert (tmp_path / "artifacts/day39-pack/day39-execution-log.md").exists()
    assert (tmp_path / "artifacts/day39-pack/day39-delivery-board.md").exists()
    assert (tmp_path / "artifacts/day39-pack/day39-validation-commands.md").exists()
    assert (tmp_path / "artifacts/day39-pack/evidence/day39-execution-summary.json").exists()


def test_day39_strict_fails_when_day38_inputs_missing(tmp_path: Path) -> None:
    _seed_repo(tmp_path)
    (
        tmp_path
        / "docs/artifacts/day38-distribution-batch-pack/day38-distribution-batch-summary.json"
    ).unlink()
    rc = d39.main(["--root", str(tmp_path), "--strict", "--format", "json"])
    assert rc == 1


def test_day39_cli_dispatch(tmp_path: Path, capsys) -> None:
    _seed_repo(tmp_path)
    rc = cli.main(["day39-playbook-post", "--root", str(tmp_path), "--format", "text"])
    assert rc == 0
    assert "Day 39 playbook post summary" in capsys.readouterr().out
