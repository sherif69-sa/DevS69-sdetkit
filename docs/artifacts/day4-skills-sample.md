# Day 4 Skills Sample — Built-in Agent Templates

Generated from `templates/automations/*.yaml`.

## Included skills/templates

1. `baseline-update-gated`
2. `change-only-audit`
3. `ci-artifact-bundle`
4. `dependency-outdated-report`
5. `precommit-style-checks`
6. `repo-health-audit`
7. `report-dashboard`
8. `security-governance-summary`

## Suggested Day 4 execution

```bash
python -m sdetkit agent templates list
python -m sdetkit agent templates run-all --output-dir .sdetkit/agent/template-runs
```

## Notes

- Outputs are stored in per-template directories under `.sdetkit/agent/template-runs/`.
- Keep this artifact under `docs/artifacts/` for traceability in PRs and release notes.
