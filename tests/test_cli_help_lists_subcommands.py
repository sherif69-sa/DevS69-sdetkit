from __future__ import annotations

import subprocess
import sys


def test_help_lists_doctor_patch_cassette_get_repo_dev_report_maintenance_agent_proof_docs_qa_weekly_review_first_contribution_contributor_funnel_triage_templates_and_docs_nav_and_startup_and_enterprise_and_github_actions_quickstart_use_case() -> (
    None
):
    r = subprocess.run(
        [sys.executable, "-m", "sdetkit", "--help"],
        text=True,
        capture_output=True,
    )
    assert r.returncode == 0
    out = r.stdout
    assert "kv" in out
    assert "apiget" in out
    assert "doctor" in out
    assert "patch" in out
    assert "cassette-get" in out
    assert "repo" in out
    assert "dev" in out

    assert "report" in out
    assert "maintenance" in out
    assert "agent" in out
    assert "proof" in out
    assert "docs-qa" in out
    assert "weekly-review" in out
    assert "first-contribution" in out
    assert "contributor-funnel" in out
    assert "triage-templates" in out
    assert "docs-nav" in out
    assert "startup-use-case" in out
    assert "enterprise-use-case" in out
    assert "github-actions-quickstart" in out
    assert "gitlab-ci-quickstart" in out
    assert "quality-contribution-delta" in out
    assert "reliability-evidence-pack" in out
    assert "release-readiness-board" in out
    assert "release-narrative" in out
    assert "trust-signal-upgrade" in out
    assert "faq-objections" in out
    assert "community-activation" in out
    assert "external-contribution-push" in out
    assert "kpi-audit" in out
    assert "day29-phase1-hardening" in out
    assert "day30-phase1-wrap" in out
    assert "day31-phase2-kickoff" in out
