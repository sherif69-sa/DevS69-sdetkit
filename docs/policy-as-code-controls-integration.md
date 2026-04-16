# Policy-as-Code Controls Integration (P2.1)

Status: Active proposal (v1)  
Date: 2026-04-16

## Objective

Map enterprise controls to enforceable policy checks and define a machine-readable control catalog for CI validation.

## Control mapping model

Each control includes:

- `control_id`: stable identifier (example: `CTRL-SEC-001`)
- `domain`: security / release / quality / governance / reliability
- `policy_rule_id`: rule key used by CI policy checks
- `evidence_artifact`: required JSON/markdown output proving control state
- `enforcement_level`: advisory / required / blocking
- `owner_team`: team accountable for remediation

## Initial control set (v1)

1. **CTRL-SEC-001** — Vulnerability reporting policy exists and is explicit.
2. **CTRL-REL-001** — Release checklist present and maintained.
3. **CTRL-REL-002** — Changelog entries are versioned and dated.
4. **CTRL-QLT-001** — Gate fast + gate release evidence generated.
5. **CTRL-OPS-001** — Enterprise repo audit passes at required threshold.
6. **CTRL-RLY-001** — Reliability SLO snapshot is produced weekly.
7. **CTRL-CST-001** — CI cost telemetry snapshot is produced weekly.

## CI validation guidance

### Validation command pattern

```bash
python -m json.tool docs/contracts/policy-control-catalog.v1.json >/dev/null
python -m json.tool docs/artifacts/policy-control-catalog-sample-2026-04-16.json >/dev/null
```

### Policy check flow

1. Load control catalog.
2. Validate required artifacts referenced by each control.
3. Emit control status summary (`pass`, `warn`, `fail`).
4. Apply enforcement level:
   - `advisory`: report only
   - `required`: fail PR if missing
   - `blocking`: block release until remediated

### Suggested CI outputs

- `docs/artifacts/policy-control-status-YYYY-MM-DD.json`
- `docs/artifacts/policy-control-summary-YYYY-MM-DD.md`

## Governance rules

- New controls require owner assignment and evidence artifact definition.
- Raising enforcement from advisory -> required/blocking needs 2-week notice.
- Blocking controls require rollback/exception path with expiry.

## Machine-readable schema

See `docs/contracts/policy-control-catalog.v1.json`.

## Acceptance criteria (P2.1)

- [x] Control mapping documented.
- [x] Machine-readable control catalog schema published.
- [x] CI validation guidance documented.
