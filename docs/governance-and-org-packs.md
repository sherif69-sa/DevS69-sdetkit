# Governance and org packs

Governance packs bundle policy, ownership, and operating rhythm artifacts.

- Governance baseline: [Policy and baselines](policy-and-baselines.md)
- Enterprise framing: [Enterprise productization blueprint](enterprise-productization-blueprint.md)

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

## Enterprise adaptive governance report

Use the enterprise governance report when scenario packs or learning exports cross repo boundaries.

```bash
python -m sdetkit adaptive enterprise-governance report --root . --format json --out build/adaptive-enterprise-governance.json
```

The report enforces these controls:

- duplicate scenario-code overrides must be explicitly approved by the layered pack policy,
- scenarios tagged `security-sensitive`, `secret-sensitive`, or `private-sensitive` must also carry `security-isolated`,
- governance output includes an `APPROVED` or `BLOCKED` recommendation and the next owner action.

For cross-repo learning exports, anonymize local identifiers before sharing outside the source repo:

```bash
python -m sdetkit adaptive enterprise-governance anonymize-learning \
  .sdetkit/adaptive-fix-audit.jsonl \
  --format json \
  --out build/adaptive-learning-export.anonymized.json
```

The anonymized export redacts repo identifiers, source paths, changed-file scope, affected files, and free-form notes while preserving scenario codes, outcomes, and aggregate learning signals.
