# Azure DevOps proof discovery feature card

```text
feature_card:
  title=Conservative Azure DevOps proof-command discovery
  user_problem=Operators need source-grounded proof recommendations from checked-in Azure DevOps pipelines without unsafe template evaluation.
  public_behavior=adoption-surface reports Azure DevOps presence, literal commands, source file, job, script key, purpose, confidence, and review-first unknowns.
  non_goals=No command execution, template expansion, variable resolution, matrix evaluation, task interpretation, service-connection access, or pipeline mutation.
  compatibility=Existing provider discovery remains unchanged.
  expected_outputs=ci_systems entry, recommended_proof_commands entries, and review_first_unknowns.
  test_plan=literal commands, dynamic boundaries, multiple providers, capability matrix, quality truth, strict docs.
  docs_needed=yes
  release_note_needed=no
  rollout=single_pr
  risk=medium-low
```

```text
product_pr_card:
  problem=Azure DevOps is the first active provider-depth gap in the product roadmap.
  repo_surface=src/sdetkit/adoption_surface, tests, provider docs, capability matrix, roadmap, quality truth.
  change_class=enterprise_integration
  risk=medium-low
  review_first=true
  automation_authority=none
  future_benefit=Extends the shared provider evidence contract beyond GitHub, GitLab, Jenkins, and CircleCI.
```
