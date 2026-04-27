from __future__ import annotations

import json
from pathlib import Path

from sdetkit import cli
from sdetkit import trust_assets as tsu


def _write_trust_assets_page(root: Path) -> None:
    path = root / "docs/trust-assets.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(tsu._DEFAULT_PAGE_TEMPLATE, encoding="utf-8")


def _write_repo_basics(root: Path, *, include_policy_link: bool = True) -> None:
    readme = root / "README.md"
    policy_link = (
        "[policy baselines](docs/policy-and-baselines.md)"
        if include_policy_link
        else "policy baselines"
    )
    readme.write_text(
        "\n".join(
            [
                "https://github.com/x/actions/workflows/ci.yml/badge.svg",
                "https://github.com/x/actions/workflows/quality.yml/badge.svg",
                "https://github.com/x/actions/workflows/mutation-tests.yml/badge.svg",
                "https://github.com/x/actions/workflows/security.yml/badge.svg",
                "https://github.com/x/actions/workflows/pages.yml/badge.svg",
                "[SECURITY.md](SECURITY.md)",
                "[Security docs](docs/security.md)",
                policy_link,
                "[Trust assets](docs/trust-assets.md)",
                "trust-assets",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    (root / "SECURITY.md").write_text("# Security\n", encoding="utf-8")
    (root / "docs").mkdir(exist_ok=True)
    (root / "docs/security.md").write_text("# Security docs\n", encoding="utf-8")
    (root / "docs/policy-and-baselines.md").write_text("# Policy\n", encoding="utf-8")
    (root / "docs/index.md").write_text(
        "impact-22-ultra-upgrade-report.md\ndocs/trust-assets.md\nTrust assets\n",
        encoding="utf-8",
    )

    workflows = root / ".github/workflows"
    workflows.mkdir(parents=True, exist_ok=True)
    for name in ["ci.yml", "quality.yml", "mutation-tests.yml", "security.yml", "pages.yml"]:
        (workflows / name).write_text("name: test\n", encoding="utf-8")


def test_trust_signal_json(tmp_path: Path, capsys) -> None:
    _write_repo_basics(tmp_path)
    _write_trust_assets_page(tmp_path)

    rc = tsu.main(["--root", str(tmp_path), "--format", "json"])
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert out["name"] == "trust-assets"
    assert out["summary"]["trust_label"] == "strong"
    assert out["summary"]["trust_score"] == 100.0
    assert out["score"] == 100.0


def test_trust_signal_emit_pack_and_execute(tmp_path: Path) -> None:
    _write_repo_basics(tmp_path)
    _write_trust_assets_page(tmp_path)

    rc = tsu.main(
        [
            "--root",
            str(tmp_path),
            "--emit-pack-dir",
            "artifacts/trust-assets-pack",
            "--execute",
            "--evidence-dir",
            "artifacts/trust-assets-pack/evidence",
            "--format",
            "json",
        ]
    )
    assert rc == 0
    assert (tmp_path / "artifacts/trust-assets-pack/trust-assets-summary.json").exists()
    assert (tmp_path / "artifacts/trust-assets-pack/trust-assets-scorecard.md").exists()
    assert (tmp_path / "artifacts/trust-assets-pack/trust-assets-visibility-checklist.md").exists()
    assert (tmp_path / "artifacts/trust-assets-pack/trust-assets-action-plan.md").exists()
    assert (tmp_path / "artifacts/trust-assets-pack/trust-assets-validation-commands.md").exists()
    assert (
        tmp_path / "artifacts/trust-assets-pack/evidence/trust-assets-execution-summary.json"
    ).exists()


def test_trust_signal_strict_fails_when_docs_contract_missing(tmp_path: Path) -> None:
    _write_repo_basics(tmp_path)
    path = tmp_path / "docs/trust-assets.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("# Trust assets\n", encoding="utf-8")

    rc = tsu.main(["--root", str(tmp_path), "--format", "json", "--strict"])
    assert rc == 1


def test_trust_signal_strict_fails_when_critical_check_missing(tmp_path: Path) -> None:
    _write_repo_basics(tmp_path)
    _write_trust_assets_page(tmp_path)
    (tmp_path / ".github/workflows/security.yml").unlink()

    rc = tsu.main(["--root", str(tmp_path), "--format", "json", "--strict"])
    assert rc == 1


def test_trust_signal_score_reduces_when_policy_link_missing(tmp_path: Path) -> None:
    _write_repo_basics(tmp_path, include_policy_link=False)
    _write_trust_assets_page(tmp_path)

    payload = tsu.build_trust_signal_summary(tmp_path)
    assert payload["summary"]["trust_score"] < 100.0
    assert payload["policy_checks"]["policy_baseline_exists"] is False


def test_trust_signal_main_score_matches_summary_when_not_strict(tmp_path: Path, capsys) -> None:
    _write_repo_basics(tmp_path, include_policy_link=False)
    _write_trust_assets_page(tmp_path)

    rc = tsu.main(["--root", str(tmp_path), "--format", "json"])
    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["summary"]["trust_score"] < 100.0
    assert payload["score"] == payload["summary"]["trust_score"]


def test_trust_signal_policy_link_matching_uses_target_not_link_text(tmp_path: Path) -> None:
    _write_repo_basics(tmp_path)
    _write_trust_assets_page(tmp_path)

    readme = tmp_path / "README.md"
    readme.write_text(
        readme.read_text(encoding="utf-8").replace(
            "[SECURITY.md](SECURITY.md)", "[Security policy](SECURITY.md)"
        ),
        encoding="utf-8",
    )

    payload = tsu.build_trust_signal_summary(tmp_path)
    assert payload["policy_checks"]["security_doc_exists"] is True


def test_cli_dispatch(tmp_path: Path, capsys) -> None:
    _write_repo_basics(tmp_path)
    _write_trust_assets_page(tmp_path)

    rc = cli.main(["trust-assets", "--root", str(tmp_path), "--format", "text"])
    assert rc == 0
    assert "Trust assets" in capsys.readouterr().out
