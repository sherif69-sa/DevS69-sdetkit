# Permission decision: PR Quality trusted publisher

```text
decision_id=pr_quality_trusted_publisher_v1
reviewer=sherif69-sa
decision=approved_scoped_permission_move
source_workflow=.github/workflows/pr-quality-comment.yml
publisher_workflow=.github/workflows/pr-quality-publisher.yml
source_write_scopes=[]
publisher_write_scopes=["issues: write", "pull-requests: write"]
publisher_trigger=workflow_run
publisher_checkout_allowed=false
publisher_repository_code_execution_allowed=false
artifact_exact_head_required=true
artifact_digest_verification_required=true
current_pr_head_revalidation_required=true
automation_allowed=false
patch_application_allowed=false
security_dismissal_allowed=false
merge_authorized=false
semantic_equivalence_proven=false
remaining_group_workflows_pending=true

lifecycle_workflow=.github/workflows/pr-quality-lifecycle-reconciliation.yml
lifecycle_triggers=["pull_request_target:closed", "workflow_dispatch", "trusted_bootstrap_push"]
lifecycle_write_scopes=["issues: write"]
lifecycle_pull_request_read_required=true
lifecycle_checkout_allowed=false
lifecycle_repository_code_execution_allowed=false
lifecycle_comment_creation_allowed=false
lifecycle_existing_bot_comment_update_only=true
lifecycle_requires_merged_pr=true
lifecycle_requires_head_and_merge_commit_identity=true
lifecycle_reporting_only=true
lifecycle_merge_authorized=false
lifecycle_semantic_equivalence_proven=false
```

This approval is limited to moving PR Quality comment publication into the trusted publisher
workflow and reconciling the existing bot-owned Quality Gate comment after GitHub records a pull
request as merged. The lifecycle workflow may update an existing canonical bot comment, but it may
not create a comment, checkout pull-request code, execute repository code, authorize a merge, or
claim that the merged state retroactively proves individual checks. It does not approve permission
changes for contributor onboarding, maintenance autopilot, or PR helper workflows.
