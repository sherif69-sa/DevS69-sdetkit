from __future__ import annotations

import json
from pathlib import Path

from sdetkit import cli
from sdetkit import trust_signal_upgrade as tsu


def _write_day22_page(root: Path) -> None:
    path = root / "docs/integrations-trust-signal-upgrade.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(tsu._DAY22_DEFAULT_PAGE, encoding="utf-8")


def _write_repo_basics(root: Path, *, include_policy_link: bool = True) -> None:
    readme = root / "README.md"
    policy_link = "[policy baselines](docs/policy-and-baselines.md)" if include_policy_link else "policy baselines"
    readme.write_text(
        "\n".join(
            [
                "https://github.com/x/actions/workflows/ci.yml/badge.svg",
                "https://github.com/x/actions/workflows/quality.yml/badge.svg",
                "https://github.com/x/actions/workflows/mutation-tests.yml/badge.svg",
                "https://github.com/x/actions/workflows/security.yml/badge.svg",
                "https://github.com/x/actions/workflows/pages.yml/badge.svg",
                "[Security Docs](docs/security.md)",
                "[Security docs](docs/security.md)",
                policy_link,
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    (root / "SECURITY.md").write_text("# Security\n", encoding="utf-8")
    (root / "docs").mkdir(exist_ok=True)
    (root / "docs/security.md").write_text("# Security docs\n", encoding="utf-8")
    (root / "docs/policy-and-baselines.md").write_text("# Policy\n", encoding="utf-8")
    (root / "docs/index.md").write_text("day-22-ultra-upgrade-report.md\n", encoding="utf-8")

    workflows = root / ".github/workflows"
    workflows.mkdir(parents=True, exist_ok=True)
    for name in ["ci.yml", "security.yml", "pages.yml"]:
        (workflows / name).write_text("name: test\n", encoding="utf-8")


def test_day22_trust_signal_json(tmp_path: Path, capsys) -> None:
    _write_repo_basics(tmp_path)
    _write_day22_page(tmp_path)

    rc = tsu.main(["--root", str(tmp_path), "--format", "json"])
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert out["name"] == "day22-trust-signal-upgrade"
    assert out["summary"]["trust_label"] == "strong"
    assert out["summary"]["trust_score"] == 100.0
    assert out["score"] == 100.0


def test_day22_trust_signal_emit_pack_and_execute(tmp_path: Path) -> None:
    _write_repo_basics(tmp_path)
    _write_day22_page(tmp_path)

    rc = tsu.main(
        [
            "--root",
            str(tmp_path),
            "--emit-pack-dir",
            "artifacts/day22-pack",
            "--execute",
            "--evidence-dir",
            "artifacts/day22-pack/evidence",
            "--format",
            "json",
        ]
    )
    assert rc == 0
    assert (tmp_path / "artifacts/day22-pack/day22-trust-summary.json").exists()
    assert (tmp_path / "artifacts/day22-pack/day22-trust-scorecard.md").exists()
    assert (tmp_path / "artifacts/day22-pack/day22-visibility-checklist.md").exists()
    assert (tmp_path / "artifacts/day22-pack/day22-trust-action-plan.md").exists()
    assert (tmp_path / "artifacts/day22-pack/day22-validation-commands.md").exists()
    assert (tmp_path / "artifacts/day22-pack/evidence/day22-execution-summary.json").exists()


def test_day22_trust_signal_strict_fails_when_docs_contract_missing(tmp_path: Path) -> None:
    _write_repo_basics(tmp_path)
    path = tmp_path / "docs/integrations-trust-signal-upgrade.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("# Trust signal upgrade (Day 22)\n", encoding="utf-8")

    rc = tsu.main(["--root", str(tmp_path), "--format", "json", "--strict"])
    assert rc == 1


def test_day22_trust_signal_strict_fails_when_critical_check_missing(tmp_path: Path) -> None:
    _write_repo_basics(tmp_path)
    _write_day22_page(tmp_path)
    (tmp_path / ".github/workflows/security.yml").unlink()

    rc = tsu.main(["--root", str(tmp_path), "--format", "json", "--strict"])
    assert rc == 1


def test_day22_trust_signal_score_reduces_when_policy_link_missing(tmp_path: Path) -> None:
    _write_repo_basics(tmp_path, include_policy_link=False)
    _write_day22_page(tmp_path)

    payload = tsu.build_trust_signal_summary(tmp_path)
    assert payload["summary"]["trust_score"] < 100.0
    assert payload["policy_checks"]["policy_baseline_exists"] is False


def test_day22_cli_dispatch(tmp_path: Path, capsys) -> None:
    _write_repo_basics(tmp_path)
    _write_day22_page(tmp_path)

    rc = cli.main(["trust-signal-upgrade", "--root", str(tmp_path), "--format", "text"])
    assert rc == 0
    assert "Day 22 trust signal upgrade" in capsys.readouterr().out
