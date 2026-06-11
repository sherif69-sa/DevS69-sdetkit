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
    assert "decision=defer_until_human_reviewer_confirms_scope_usage" in text

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
