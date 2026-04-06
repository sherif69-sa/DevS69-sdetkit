# CI artifact walkthrough (canonical evidence decoder)

Use this page when a CI run is finished and you need the fastest artifact-first review.

This is the canonical decoder for release-confidence evidence.

Grounded in current workflow artifact uploads:
- CI fast lane diagnostics: `ci-gate-diagnostics-py3.11` / `ci-gate-diagnostics-py3.12`
- Release diagnostics: `release-diagnostics`

## Artifact-to-action map

| Artifact/file | What it represents | Look here first | If healthy, do this next | If failure/risk, do this next |
| --- | --- | --- | --- | --- |
| `build/release-preflight.json` | Release preflight decision | `ok`, then `failed_steps`, then `profile` | Continue release/package validation flow. | If `gate_fast` appears in `failed_steps`, open `build/gate-fast.json` next. |
| `build/gate-fast.json` | Fast gate decision and failing step IDs | `ok`, then first item in `failed_steps`, then `profile` | Continue normal PR flow. | Fix first failing step category, rerun, and re-check artifact. |
| `build/security-enforce.json` | Security threshold posture | `ok`, `counts`, `exceeded` | Keep current threshold posture. | Remediate findings or adjust thresholds with explicit follow-up. |

## Canonical review order

1. Download CI artifacts (`ci-gate-diagnostics-py*`; for tags also `release-diagnostics`).
2. Open `build/release-preflight.json` first.
3. If needed, open `build/gate-fast.json` second.
4. Open `build/security-enforce.json` for policy/budget context.
5. Only then deep-dive into raw logs.

## Copy-paste evidence snippet (PR or release discussion)

```md
### Evidence (artifact-first)
- `build/release-preflight.json`: `ok=<value>`, `failed_steps=<value>`, `profile=<value>`
- `build/gate-fast.json`: `ok=<value>`, `failed_steps=<value>`, `profile=<value>`
- `build/security-enforce.json`: `ok=<value>`, `counts=<value>`, `exceeded=<value>`

Decision: <go / no-go / conditional> based on artifact fields above.
```

For full troubleshooting depth, continue to [adoption-troubleshooting.md](adoption-troubleshooting.md).
