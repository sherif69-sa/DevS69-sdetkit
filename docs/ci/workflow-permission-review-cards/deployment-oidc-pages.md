# Workflow permission review card: deployment_or_oidc / Pages

This card records human-review evidence for the `deployment_or_oidc` workflow permission group.

It is evidence-only. It does not approve a permission reduction, mutate workflow YAML, authorize automation, authorize merge, or claim semantic equivalence.

## Review card

```text
workflow=.github/workflows/pages.yml
current_write_scopes=["id-token: write", "pages: write"]
review_group=deployment_or_oidc
inferred_reasons=[
  "The workflow grants pages: write and uses actions/deploy-pages.",
  "The workflow grants id-token: write and deploys to the github-pages environment.",
  "The workflow also uses actions/configure-pages and actions/upload-pages-artifact before deploy-pages.",
  "Exact scope removal is not authorized from report output alone."
]
proposed_change=none
human_reviewer=pending
proof=python -m pytest -q tests/test_workflow_governance_report.py tests/test_product_maturity_radar.py tests/test_workflow_permission_review_cards.py -o addopts= && python -m pre_commit run -a
rollback=single review-card revert
decision=defer_pending_human_review
```

## Evidence observed

- `.github/workflows/pages.yml` grants `contents: read`, `pages: write`, and `id-token: write`.
- The build job uses pinned `actions/configure-pages`.
- The build job uploads the built site with pinned `actions/upload-pages-artifact`.
- The deploy job targets the `github-pages` environment.
- The deploy job uses pinned `actions/deploy-pages`.
- Existing generated evidence for `deployment_or_oidc` says `requires_human_review=true`, `safe_to_patch=false`, and `next_allowed_action=collect_human_review_evidence`.

## Deployment-stage failure triage note

A Pages deployment can fail after the site artifact is already built and uploaded. Treat this as a deployment-stage signal when the log shows all of the following:

1. `actions/deploy-pages` starts successfully.
2. The `github-pages` artifact metadata is found.
3. A Pages deployment is created for a concrete commit SHA.
4. The final status check returns a deployment failure after creation.

This signature is different from a documentation build failure, missing artifact, permission-reduction finding, or broken link. The first operator action is to verify whether the failure repeats on a later run before changing workflow permissions or build steps.

The Node `punycode` deprecation warning emitted by the action runtime is informational unless a later step turns it into a hard failure.

## Reviewer decision

Pending.

A future permission-only PR may only be considered after a human reviewer records a concrete decision for each write scope.
