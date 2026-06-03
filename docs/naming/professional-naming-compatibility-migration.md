# Professional naming compatibility migration

## Purpose

This document authorizes a planned compatibility migration from legacy professional-naming terms to production names.

This is not a blind rename. Public surfaces, workflows, artifact paths, JSON keys, CLI commands, historical reports, and template-locked docs require aliases, preservation rules, or explicit migration tests.

## Canonical rename map

| Legacy name | Canonical name |
| --- | --- |
| phase1 | baseline |
| phase2 | release_readiness |
| phase3 | platform_readiness |
| phase4 | operational_readiness |
| phase5 | adoption_readiness |
| phase6 | scale_readiness |
| gate-phase2 | release_readiness_gate |
| closeout | completion_report |
| demo | example |
| toy | sample |
| scratch | workspace |
| temp | temporary_workspace |
| tutorial | guide |
| lesson | guide |
| education | operator_guidance |
| finish-signal | completion_signal |
| retire-plan | deprecation_plan |
| next-pass | followup_pass |

## Migration classes

```text
safe_content_rewrite=plain prose and internal non-public text
alias_required=CLI names, public source surfaces, JSON keys, workflow names
preserve_history=historical report titles, chronology headings, artifact slugs
template_locked=contract docs guarded by tests
manual_review=ambiguous paths or generated evidence
```

## Compatibility boundary

```text
blind_rename_allowed=false
public_surface_change_without_alias=false
workflow_rename_without_alias=false
json_key_rename_without_alias=false
artifact_slug_rename_without_redirect=false
template_locked_rewrite=false
```

## Required proof before large rename

```text
rename_map_committed=true
alias_tests_present=true
template_locked_paths_preserved=true
inventory_before_after_recorded=true
rollback_plan_present=true
```

## Rollback

Rollback is a normal revert of the migration PR. Aliases must be additive first so old names continue to work during the migration window.
