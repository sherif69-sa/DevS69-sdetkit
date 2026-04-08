# CI artifact walkthrough (canonical evidence decoder)

Use this page when a CI run completes and you need a fast, artifact-first trust decision.

## Start here: canonical real-repo adoption lane

Primary artifact bundle: `adoption-real-repo-canonical`.

Review order (single lane):
1. `build/adoption-proof-summary.json`
2. `build/release-preflight.json`
3. `build/gate-fast.json`
4. `build/doctor.json`
5. `build/*.rc`

Why this order works:
- the summary file gives command + expectation match in one view,
- JSON artifacts expose true gate/doctor contracts,
- rc files prove process-level pass/fail independently of JSON content.

See [Real repo adoption proof](real-repo-adoption.md) for local replay equivalence.

## Artifact-to-action map (canonical lane)

| Artifact/file | What it proves | Look here first | Healthy means | Unhealthy means |
| --- | --- | --- | --- | --- |
| `build/adoption-proof-summary.json` | Command-level evidence map (`observed_*` vs `expected_*`) | `all_expectations_met`, then per-command `rc_matches_expected`/`ok_matches_expected` | Fixture behavior matches intended trust contract | Drift in command semantics, fixture wiring, or artifact generation |
| `build/release-preflight.json` | Release preflight decision contract | `ok`, `failed_steps`, `profile` | Release preflight behaves exactly as expected for fixture | Unexpected step failures/successes require contract review |
| `build/gate-fast.json` | Fast gate decision contract | `ok`, first `failed_steps`, `profile` | Expected first-run triage failure shape is preserved | Gate behavior drifted from canonical expectation |
| `build/doctor.json` | Doctor quality contract | `ok`, `quality.failed_check_ids`, `recommendations` | Doctor remains actionable and non-blocking in fixture | Doctor contract/output drift or environment regression |
| `build/*.rc` | Raw process exit codes | numeric values | RCs match fixture truth model (2/2/0) | Process-level behavior drifted even if JSON exists |

## Other CI artifact families (secondary)

Grounded in current workflow uploads:
- CI fast lane diagnostics: `ci-gate-diagnostics-py3.11` / `ci-gate-diagnostics-py3.12`
- Release diagnostics: `release-diagnostics`

Use those lanes after canonical adoption evidence is understood.

## Copy-paste evidence snippet (PR/release discussion)

```md
### Canonical adoption evidence
- `build/adoption-proof-summary.json`: `all_expectations_met=<value>`
- `build/gate-fast.rc` / `build/release-preflight.rc` / `build/doctor.rc`: `<value>/<value>/<value>`
- `build/gate-fast.json`: `ok=<value>`, `failed_steps=<value>`
- `build/release-preflight.json`: `ok=<value>`, `failed_steps=<value>`
- `build/doctor.json`: `ok=<value>`, `quality.failed_check_ids=<value>`

Decision: <trust lane healthy / drift investigation required>
```

For deeper troubleshooting, continue to [adoption-troubleshooting.md](adoption-troubleshooting.md).
