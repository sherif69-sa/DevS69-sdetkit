# Governance and org packs

Governance packs bundle policy, ownership, and operating rhythm artifacts.

- Governance baseline: [Policy and baselines](policy-and-baselines.md)

## Adaptive scenario pack overlay governance

SDETKit loads adaptive scenario intelligence in deterministic layers:

1. built-in SDETKit scenario pack,
2. repo-local `.sdetkit/adaptive/scenarios.json`,
3. additional organization or private packs listed in `SDETKIT_ADAPTIVE_SCENARIO_PACKS`.

Use this governance policy when an organization pack changes diagnosis behavior across multiple repositories.

### Approval rules

- New scenario codes are allowed when the pack validates against `schemas/adaptive-scenario-pack.schema.json`.
- Overriding an existing scenario code requires the replacing scenario to include the explicit `override-approved` tag.
- Approved overrides should include owner review notes in the PR description and a proof command that shows the new scenario ranking or proof path.
- Security-sensitive scenarios should live in private packs and avoid embedding secret values, customer identifiers, or unredacted internal hostnames.

### Validation commands

```bash
python - <<'PY'
from pathlib import Path
from sdetkit import adaptive_diagnosis

report = adaptive_diagnosis.validate_layered_scenario_packs(Path('.'))
print(report['schema_version'])
print(report['layer_count'])
print(report['overrides'])
PY
```

For inspection without enforcing override approval, use:

```bash
python - <<'PY'
from pathlib import Path
from sdetkit import adaptive_diagnosis

report = adaptive_diagnosis.layered_scenario_pack_report(Path('.'))
print(report['layers'])
print(report['merged_codes'][:10])
PY
```

### Review checklist

- [ ] Pack schema validates and loads deterministically.
- [ ] Pack source appears in the layer metadata as `repo-local` or `overlay-N`.
- [ ] Any duplicate scenario code is intentional and tagged with `override-approved`.
- [ ] Override PR includes before/after diagnosis evidence.
- [ ] Proof commands do not require secrets or write access.
- [ ] Rollback is simple: remove the overlay pack or revert the scenario row.
