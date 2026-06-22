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
```

This approval is limited to moving PR Quality comment publication into the trusted publisher
workflow. It does not approve permission changes for contributor onboarding, maintenance
autopilot, or PR helper workflows.
