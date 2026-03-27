# Objection handling report

## FAQ and objections report

Objection handling delivers a production-grade objection-handling lane that translates recurring adoption blockers into strict, testable, and artifact-backed outcomes.

## Problem statement

External adopters repeatedly ask:

- when should we use sdetkit,
- when should we *not* use sdetkit,
- and how can we prove readiness without hand-written narratives.

Without deterministic answers, onboarding confidence drops and launch momentum stalls.

## Implementation scope

- Added a new CLI command: `sdetkit objection-handling`.
- Added strict scoring + critical-failure gating for FAQ/objection readiness.
- Added deterministic execution mode for evidence capture.
- Added artifact-pack emitter for release and review workflows.
- Added docs contract checker and expanded user-facing docs links.

## Diff target

- Product code: new objection-handling module and CLI wiring.
- Tests: command behavior + strict failure modes + CLI dispatch.
- Docs: objection-handling integration guide, artifacts, and index/README updates.
- CI/automation: objection-handling contract check script.

## Validation commands

```bash
python -m pytest tests/test_objection_handling.py tests/test_cli_help_lists_subcommands.py
python -m sdetkit objection-handling --format json --strict
python -m sdetkit objection-handling --emit-pack-dir docs/artifacts/objection-handling-pack --format json --strict
python -m sdetkit objection-handling --execute --evidence-dir docs/artifacts/objection-handling-pack/evidence --format json --strict
python scripts/check_objection_handling_contract.py
```

## Artifacts

- `docs/artifacts/objection-handling-sample.md`
- `docs/artifacts/objection-handling-pack/objection-handling-summary.json`
- `docs/artifacts/objection-handling-pack/objection-handling-scorecard.md`
- `docs/artifacts/objection-handling-pack/objection-handling-response-matrix.md`
- `docs/artifacts/objection-handling-pack/objection-handling-playbook.md`
- `docs/artifacts/objection-handling-pack/objection-handling-validation-commands.md`
- `docs/artifacts/objection-handling-pack/evidence/objection-handling-execution-summary.json`

## Rollback plan

1. Remove the legacy objection-handling compatibility alias from CLI dispatch.
2. Remove `src/sdetkit/objection_handling.py` and objection-handling docs pages.
3. Remove objection-handling contract checks from validation scripts.
4. Re-run baseline tests to confirm stable fallback.
