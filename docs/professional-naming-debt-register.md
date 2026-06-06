# Professional naming debt register

This register tracks legacy naming surfaces that make the repository look less production-grade than its actual engineering quality.

## Policy

New public surfaces should use durable production names.

Avoid new names containing:

- `phase1`, `phase2`, `phase3`, `phase4`, `phase5`, `phase6`
- `do-it`
- `closeout`
- `finish-signal`
- `retire-plan`
- `next-pass`
- `gate-phase2`
- `lesson`
- `tutorial`
- `education`
- `demo`
- numbered “big upgrade” / “ultra upgrade” labels for active surfaces

Existing legacy names may remain when they are public compatibility surfaces, generated artifact names, historical reports, or references required by existing contracts.

## Replacement vocabulary

| Legacy wording | Preferred wording |
| --- | --- |
| phase 1 / phase1 | operational readiness |
| phase 2 / phase2 | workflow readiness |
| phase 3 / phase3 | quality governance |
| phase 4 / phase4 | governance contract |
| phase 5 / phase5 | ecosystem contract |
| phase 6 / phase6 | metrics contract |
| closeout | completion, evidence pack, delivery summary, release evidence |
| demo | product proof, example workflow, sample output |
| next-pass | follow-up, handoff, remediation plan |
| finish-signal | readiness signal |
| retire-plan | migration plan |
| gate-phase2 | readiness gate |
| big upgrade report | upgrade assessment report |
| ultra upgrade report | implementation report |

## Migration waves

1. Docs and aliases prefer production names.
2. Test names migrate when reference scans are clean.
3. Internal scripts migrate behind wrappers.
4. Workflow display names and filenames migrate with guardrails.
5. Public CLI/Make/schema names migrate only with aliases, docs, and deprecation notes.

## Known legacy categories

| Category | Status | Compatibility strategy |
| --- | --- | --- |
| Historical roadmap reports | Keep for now | Do not rename in bulk; classify as archive/history |
| Generated artifact packs | Keep for now | Preserve artifact paths unless generator changes with migration |
| Public CLI commands | Keep aliases | Add production aliases before docs prefer new names |
| Make targets | Keep aliases | Do not remove legacy targets without release policy |
| Test filenames/functions | Rename gradually | Reference scan first |
| Internal scripts | Rename gradually | Wrapper scripts first |
| Docs H1 titles | Safe first wave | Prefer production wording without moving files |

## First-wave candidates

These are safer because they can improve visible professionalism without breaking links:

- docs H1 headings that say `Lane — ...`
- docs H1 headings that say `Phase-1`, `Phase-2`, or similar
- docs H1 headings that say `Demo asset`
- front-door references to `closeout` where `completion`, `evidence`, or `delivery summary` is clearer
- docs-map labels that expose legacy terms

## Non-goals for the first PR

- No public CLI removals.
- No Make target removals.
- No generated artifact path moves.
- No bulk file renames.
- No historical report rewrite.

## Public command surface progress

The public Makefile surface now prefers professional names for baseline, operations,
release-readiness, platform-readiness, adoption-readiness, and scale-readiness lanes.

Compatibility aliases remain available for transition-era `phase1`, `phase2`, `phase3`,
`phase5`, `phase6`, `phase-current`, `do-it`, `finish-signal`, `next-pass`, and
`retire-plan` names where removal would break existing users or historical automation.

Current sweep policy:

- update active docs and operator contracts first
- keep compatibility aliases tested
- do not rewrite generated evidence for line count
- do not change schema identifiers without a migration contract
- do not rename historical closeout reports as part of public command sweeps

## Execution docs terminology progress

The active execution-plan and execution-guide documentation now prefers readiness-stage,
quality-governance, operational-governance, ecosystem-readiness, and metrics-readiness
language in visible headings and navigation labels.

Compatibility command names, generated artifact paths, and state-field names remain stable.
