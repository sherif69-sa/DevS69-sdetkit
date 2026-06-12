from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
CARD = REPO_ROOT / "docs/ci/workflow-permission-review-cards/deployment-oidc-pages.md"


def test_deployment_oidc_pages_review_card_is_evidence_only() -> None:
    text = CARD.read_text(encoding="utf-8")

    assert "workflow=.github/workflows/pages.yml" in text
    assert 'current_write_scopes=["id-token: write", "pages: write"]' in text
    assert "review_group=deployment_or_oidc" in text
    assert "proposed_change=none" in text
    assert "human_reviewer=pending" in text
    assert "decision=defer_pending_human_review" in text

    assert "It is evidence-only." in text
    assert "does not approve a permission reduction" in text
    assert "does not approve a permission reduction, mutate workflow YAML" in text
    assert "safe_to_patch=false" in text
    assert "next_allowed_action=collect_human_review_evidence" in text


def test_deployment_oidc_pages_review_card_mentions_observed_pages_actions() -> None:
    text = CARD.read_text(encoding="utf-8")

    assert "actions/configure-pages" in text
    assert "actions/upload-pages-artifact" in text
    assert "actions/deploy-pages" in text
    assert "github-pages" in text
    assert "pages: write" in text
    assert "id-token: write" in text


PR_ISSUE_CARD = REPO_ROOT / "docs/ci/workflow-permission-review-cards/pr-issue-interaction.md"


def test_pr_issue_interaction_review_card_is_evidence_only() -> None:
    text = PR_ISSUE_CARD.read_text(encoding="utf-8")

    assert "workflow_group=pr_issue_interaction" in text
    assert "review_group=pr_issue_interaction" in text
    assert 'current_write_scopes=["issues: write", "pull-requests: write"]' in text
    assert "proposed_change=none" in text
    assert "human_reviewer=pending" in text
    assert "decision=defer_pending_human_review" in text

    assert "It is evidence-only." in text
    assert "does not approve a permission reduction" in text
    assert "mutate workflow YAML" in text
    assert "safe_to_patch=false" in text
    assert "next_allowed_action=collect_human_review_evidence" in text


def test_pr_issue_interaction_review_card_mentions_observed_workflows() -> None:
    text = PR_ISSUE_CARD.read_text(encoding="utf-8")

    assert ".github/workflows/contributor-onboarding-bot.yml" in text
    assert ".github/workflows/maintenance-autopilot.yml" in text
    assert ".github/workflows/pr-helper-bot.yml" in text
    assert ".github/workflows/pr-quality-comment.yml" in text
    assert "issues: write" in text
    assert "pull-requests: write" in text
    assert "GitHub API or gh-based PR/issue interaction detected." in text
    assert "PR or issue comment/review API usage detected." in text
