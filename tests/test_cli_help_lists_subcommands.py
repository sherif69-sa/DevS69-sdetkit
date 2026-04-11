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
    assert "inspect" in out
    assert "inspect-compare" in out
    assert "inspect-project" in out
    assert "apiget" in out
    assert "doctor" in out
    assert "patch" in out
    assert "cassette-get" in out
    assert "repo" in out
    assert "dev" in out
    assert "playbooks" in out

    assert "report" in out
    assert "author" in out
    assert "maintenance" in out
    assert "agent" in out
    assert "evidence-assets" in out
    assert "proof" not in out
    assert "docs-quality" in out
    assert "docs-qa" not in out
    assert "weekly-review" in out
    assert "first-contribution" in out
    assert "contributor-funnel" in out
    assert "triage-templates" in out
    assert "docs-governance" in out
    assert "docs-nav" not in out
    assert "startup-readiness" in out
    assert "upgrade-hub" in out
    assert "startup-use-case" not in out
    assert "enterprise-readiness" in out
    assert "enterprise-use-case" not in out
    assert "github-actions-onboarding" in out
    assert "github-actions-quickstart" not in out
    assert "gitlab-ci-onboarding" in out
    assert "gitlab-ci-quickstart" not in out
    assert "contribution-quality-report" in out
    assert "quality-contribution-delta" not in out
    assert "reliability-evidence-pack" in out
    assert "release-readiness" in out
    assert "release-readiness-board" not in out
    assert "release-communications" in out
    assert "release-narrative" not in out
    assert "trust-assets" in out
    assert "feature-registry" in out
    assert "trust-signal-upgrade" not in out
    assert "objection-handling" in out
    assert "faq-objections" not in out
    assert "community-activation" in out
    assert "external-contribution" in out
    assert "external-contribution-push" not in out
    assert "kpi-audit" in out
    assert "usage:" in out.lower()
    assert "expansion-automation" not in out
    assert "optimization-closeout-foundation" not in out
    assert "acceleration-closeout" not in out
    assert "scale-closeout" not in out
    r3 = subprocess.run(
        [sys.executable, "-m", "sdetkit", "playbooks", "list", "--format", "json"],
        text=True,
        capture_output=True,
    )
    assert r3.returncode == 0
    import json as _json

    j = _json.loads(r3.stdout)
    assert "playbooks" in j
    assert "startup-readiness" in j["playbooks"]
    assert "enterprise-readiness" in j["playbooks"]
    assert "external-contribution" in j["playbooks"]
    assert "objection-handling" in j["playbooks"]
    assert "onboarding-optimization" in j["playbooks"]
    assert "startup-use-case" not in j["aliases"]
    assert "enterprise-use-case" not in j["aliases"]
    assert "external-contribution-push" not in j["aliases"]
    assert "faq-objections" not in j["aliases"]
    assert "onboarding-time-upgrade" not in j["aliases"]
    assert "phase1-hardening" in j["playbooks"]
    assert all(name for name in j["playbooks"])
    r2 = subprocess.run(
        [sys.executable, "-m", "sdetkit", "playbooks"],
        text=True,
        capture_output=True,
    )
    assert r2.returncode == 0
    out2 = r2.stdout
    assert "phase1-hardening" in out2
    assert "phase1-wrap" in out2
    assert "scale-closeout" in out2
    assert "playbooks" in out2.lower()
    assert "Run: sdetkit playbooks run <name>" in out2


def test_playbooks_run_unknown_name_fails() -> None:
    import subprocess
    import sys

    r = subprocess.run(
        [sys.executable, "-m", "sdetkit", "playbooks", "run", "nope-nope-nope"],
        text=True,
        capture_output=True,
    )
    assert r.returncode == 2
    assert r.stdout == ""
    assert r.stderr.strip() == "playbooks: unknown name"
