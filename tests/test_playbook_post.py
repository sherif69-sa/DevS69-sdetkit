from __future__ import annotations

import json
from pathlib import Path

from sdetkit import cli
from sdetkit import playbook_post_39 as d39


def _seed_repo(root: Path) -> None:
    (root / "templates/ci/gitlab").mkdir(parents=True, exist_ok=True)

    (root / "templates/ci/jenkins").mkdir(parents=True, exist_ok=True)

    (root / "templates/ci/tekton").mkdir(parents=True, exist_ok=True)

    (root / "docs/roadmap/plans").mkdir(parents=True, exist_ok=True)

    (root / "docs/roadmap/reports").mkdir(parents=True, exist_ok=True)

    (root / "docs/artifacts").mkdir(parents=True, exist_ok=True)
    (root / "README.md").write_text(
        "docs/integrations-playbook-post.md\nplaybook-post\n",
        encoding="utf-8",
    )
    (root / "docs").mkdir(parents=True, exist_ok=True)
    (root / "docs/index.md").write_text(
        "impact-39-big-upgrade-report.md\nintegrations-playbook-post.md\n",
        encoding="utf-8",
    )
    (root / "docs/top-10-github-strategy.md").write_text(
        "- ** — Playbook post #1:** publish the first reliability playbook post from  data.\n"
        "- ** — Scale lane kickoff:** expand publication motion across additional channels.\n",
        encoding="utf-8",
    )
    (root / "docs/integrations-playbook-post.md").write_text(
        d39._DEFAULT_PAGE_TEMPLATE, encoding="utf-8"
    )
    (root / "docs/impact-39-big-upgrade-report.md").write_text("#  report\n", encoding="utf-8")

    summary = root / "docs/artifacts/distribution-batch-pack/distribution-batch-summary.json"
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
    board = root / "docs/artifacts/distribution-batch-pack/delivery-board.md"
    board.write_text(
        "\n".join(
            [
                "#  delivery board",
                "- [ ]  channel plan committed",
                "- [ ]  post copy reviewed with owner + backup",
                "- [ ]  scheduling matrix exported",
                "- [ ]  KPI scorecard snapshot exported",
                "- [ ]  playbook post priorities drafted from  outcomes",
            ]
        )
        + "\n",
        encoding="utf-8",
    )


def test_lane39_playbook_post_json(tmp_path: Path, capsys) -> None:
    _seed_repo(tmp_path)
    rc = d39.main(["--root", str(tmp_path), "--format", "json", "--strict"])
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert out["name"] == "playbook-post"
    assert out["summary"]["activation_score"] >= 95


def test_lane39_emit_pack_and_execute(tmp_path: Path) -> None:
    _seed_repo(tmp_path)
    rc = d39.main(
        [
            "--root",
            str(tmp_path),
            "--emit-pack-dir",
            "artifacts/playbook-post-pack",
            "--execute",
            "--evidence-dir",
            "artifacts/playbook-post-pack/evidence",
            "--format",
            "json",
            "--strict",
        ]
    )
    assert rc == 0
    assert (tmp_path / "artifacts/playbook-post-pack/playbook-post-summary.json").exists()
    assert (tmp_path / "artifacts/playbook-post-pack/playbook-post-summary.md").exists()
    assert (tmp_path / "artifacts/playbook-post-pack/playbook-draft.md").exists()
    assert (tmp_path / "artifacts/playbook-post-pack/rollout-plan.csv").exists()
    assert (tmp_path / "artifacts/playbook-post-pack/kpi-scorecard.json").exists()
    assert (tmp_path / "artifacts/playbook-post-pack/execution-log.md").exists()
    assert (tmp_path / "artifacts/playbook-post-pack/delivery-board.md").exists()
    assert (tmp_path / "artifacts/playbook-post-pack/validation-commands.md").exists()
    assert (tmp_path / "artifacts/playbook-post-pack/evidence/execution-summary.json").exists()


def test_lane39_strict_fails_when_lane38_inputs_missing(tmp_path: Path) -> None:
    _seed_repo(tmp_path)
    (tmp_path / "docs/artifacts/distribution-batch-pack/distribution-batch-summary.json").unlink()
    rc = d39.main(["--root", str(tmp_path), "--strict", "--format", "json"])
    assert rc == 1


def test_lane39_cli_dispatch(tmp_path: Path, capsys) -> None:
    _seed_repo(tmp_path)
    rc = cli.main(["playbook-post", "--root", str(tmp_path), "--format", "text"])
    assert rc == 0
    assert " playbook post summary" in capsys.readouterr().out
