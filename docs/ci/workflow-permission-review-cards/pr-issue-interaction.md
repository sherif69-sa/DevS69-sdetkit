# Workflow permission review card: pr_issue_interaction

This card records human-review evidence for the `pr_issue_interaction` workflow permission group.

It is evidence-only. It does not approve a permission reduction, mutate workflow YAML, authorize automation, authorize merge, or claim semantic equivalence.

## Review card

```text
workflow_group=pr_issue_interaction
workflows=[
  ".github/workflows/contributor-onboarding-bot.yml",
  ".github/workflows/maintenance-autopilot.yml",
  ".github/workflows/pr-helper-bot.yml",
  ".github/workflows/pr-quality-publisher.yml"
]
current_write_scopes=["issues: write", "pull-requests: write"]
review_group=pr_issue_interaction
inferred_reasons=[
  "GitHub API or gh-based PR/issue interaction detected.",
  "Issue create/update API usage detected.",
  "PR or issue comment/review API usage detected.",
  "The trusted PR Quality Publisher uses workflow_run evidence to update or post the diagnostic PR comment without checking out PR code.",
  "Exact scope removal is not authorized from report output alone."
]
proposed_change=none
human_reviewer=pending
proof=python -m pytest -q tests/test_workflow_governance_report.py tests/test_product_maturity_radar.py tests/test_workflow_pr_issue_interaction_evidence_contract.py tests/test_workflow_permission_review_cards.py -o addopts= && python -m pre_commit run -a
rollback=single review-card revert
decision=defer_pending_human_review
```

## Evidence observed

- `.github/workflows/contributor-onboarding-bot.yml` is part of the `pr_issue_interaction` permission review group.
- `.github/workflows/maintenance-autopilot.yml` is part of the `pr_issue_interaction` permission review group.
- `.github/workflows/pr-helper-bot.yml` is part of the `pr_issue_interaction` permission review group.
- `.github/workflows/pr-quality-publisher.yml` is part of the `pr_issue_interaction` permission review group.
- The group grants PR/issue interaction write scopes such as `issues: write` and `pull-requests: write`.
- Existing generated evidence for `pr_issue_interaction` says `requires_human_review=true`, `safe_to_patch=false`, and `next_allowed_action=collect_human_review_evidence`.

## Reviewer decision

Pending.

A future permission-only PR may only be considered after a human reviewer records a concrete decision for each workflow and each write scope.

## Scoped PR Quality decision

A repository-owner decision approving the PR Quality trust-boundary move is recorded at `docs/ci/workflow-permission-decisions/pr-quality-trusted-publisher.md`. The remaining workflows in this permission group remain pending human review.
