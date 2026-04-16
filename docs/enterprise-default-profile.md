# Enterprise Default Profile Contract (P0.4)

Status: Active (v1)  
Effective date: 2026-04-16

## Purpose

Define a default enterprise execution profile with bounded runtime and explicit fail policy so CI behavior is predictable, auditable, and cost-controlled.

## Profile name

`enterprise-default-v1`

## Intended usage

Use this profile as the baseline enterprise lane for pull requests and release readiness checks.

## Runtime budget

### PR lane budget

- Target runtime: <= 15 minutes
- Hard limit: 20 minutes
- Required checks:
  1. `python -m sdetkit gate fast --format json --out build/gate-fast.json`
  2. `python -m sdetkit repo audit . --profile enterprise --format json --output build/repo-audit-enterprise.json`
  3. `python -m sdetkit readiness . --format json --output build/readiness.json`

### Release lane budget

- Target runtime: <= 30 minutes
- Hard limit: 40 minutes
- Required checks:
  1. `python -m sdetkit gate release --format json --out build/release-preflight.json`
  2. `python -m sdetkit doctor --release --format json --output build/doctor-release.json`
  3. `python -m sdetkit repo audit . --profile enterprise --format json --output build/repo-audit-enterprise-release.json`

## Fail policy

### Fail-closed checks (block merge/release on failure)

- `gate fast` (PR lane)
- `gate release` (release lane)
- `repo audit --profile enterprise`

### Soft-fail checks (warn, do not block by default)

- `readiness` (trend and governance indicator)
- non-critical informational security findings

### Escalation policy

- Two consecutive hard-limit timeouts trigger profile tuning review.
- Two consecutive false-positive fail-closed events trigger temporary exception + root-cause task.
- All exceptions require owner, expiry date, and remediation ticket reference.

## Starter CI usage pattern

```bash
# PR baseline lane
python -m sdetkit gate fast --format json --out build/gate-fast.json
python -m sdetkit repo audit . --profile enterprise --format json --output build/repo-audit-enterprise.json
python -m sdetkit readiness . --format json --output build/readiness.json

# release lane
python -m sdetkit gate release --format json --out build/release-preflight.json
python -m sdetkit doctor --release --format json --output build/doctor-release.json
python -m sdetkit repo audit . --profile enterprise --format json --output build/repo-audit-enterprise-release.json
```

## Validation guidance

1. Run this profile in shadow mode for 2 weeks before making it mandatory.
2. Capture median runtime, p95 runtime, and failure categories per lane.
3. Promote to required status only when:
   - hard-limit timeouts < 5% of runs,
   - no critical coverage gaps identified,
   - top 3 recurring failures have documented remediation playbooks.

## Machine-readable contract

See `docs/contracts/enterprise-default-profile.v1.json`.

## Acceptance criteria (P0.4)

- [x] Runtime budget declared (target + hard limit).
- [x] Fail policy declared (fail-closed vs soft-fail).
- [x] Starter usage pattern documented.
- [x] Validation guidance documented.
- [x] Machine-readable contract published.
