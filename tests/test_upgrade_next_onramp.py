import os
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


def test_makefile_upgrade_next_exposes_guided_five_step_path() -> None:
    makefile = (REPO_ROOT / "Makefile").read_text(encoding="utf-8")
    assert "upgrade-next:" in makefile
    assert "operator-onramp: upgrade-next onboarding-next first-proof-dashboard" in makefile
    assert "operator-onramp-dry-run:" in makefile
    assert (
        "operator-onramp-verify: operator-onramp first-proof-schema-contract "
        "first-proof-execution-contract first-proof-followup-ready" in makefile
    )
    assert "make first-proof" in makefile
    assert "make first-proof-health-score" in makefile
    assert "make first-proof-verify" in makefile
    assert "make first-proof-freshness" in makefile
    assert "make doctor-remediate" in makefile
    assert "UPGRADE_NEXT_RUN=1" in makefile
    assert "UPGRADE_NEXT_DRY_RUN=1" in makefile


def test_upgrade_next_doc_includes_auto_run_flag() -> None:
    docs_page = (REPO_ROOT / "docs" / "upgrade-next-commands.md").read_text(encoding="utf-8")
    assert "make upgrade-next" in docs_page
    assert "make operator-onramp" in docs_page
    assert "make operator-onramp-dry-run" in docs_page
    assert "make operator-onramp-verify" in docs_page
    assert "UPGRADE_NEXT_RUN=1 make upgrade-next" in docs_page
    assert "UPGRADE_NEXT_DRY_RUN=1 make upgrade-next" in docs_page


def test_readme_links_upgrade_next_intent_router() -> None:
    readme = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
    assert "## Upgrade next (intent router)" in readme
    assert "docs/upgrade-next-commands.md" in readme


def test_upgrade_next_dry_run_prints_all_commands_without_execution() -> None:
    proc = subprocess.run(
        ["make", "upgrade-next"],
        cwd=REPO_ROOT,
        env={**os.environ, "UPGRADE_NEXT_RUN": "1", "UPGRADE_NEXT_DRY_RUN": "1"},
        capture_output=True,
        text=True,
        check=True,
    )
    out = proc.stdout
    assert "Running guided path..." in out
    assert "DRY RUN: make first-proof" in out
    assert "DRY RUN: make first-proof-health-score" in out
    assert "DRY RUN: make first-proof-verify" in out
    assert "DRY RUN: make first-proof-freshness" in out
    assert "DRY RUN: make doctor-remediate" in out


def test_operator_onramp_dry_run_prints_sequence() -> None:
    proc = subprocess.run(
        ["make", "operator-onramp-dry-run"],
        cwd=REPO_ROOT,
        env={**os.environ},
        capture_output=True,
        text=True,
        check=True,
    )
    out = proc.stdout
    assert "DRY RUN: make upgrade-next" in out
    assert "DRY RUN: make onboarding-next" in out
    assert "DRY RUN: make first-proof-dashboard" in out
