# CI artifact walkthrough (core release-confidence path)

Use this page when a CI run is finished and you need the fastest **artifact-first** review path.

This is the **canonical page for evidence/artifact interpretation**.

Grounded in this repository's documented workflow/artifacts:

- `ci-gate-diagnostics` upload bundle (`build/gate-fast.json`, `build/security-enforce.json`)
- `release-diagnostics` upload bundle (`build/release-preflight.json`)

For full troubleshooting depth, continue to [adoption-troubleshooting.md](adoption-troubleshooting.md).

## Artifact-to-action map

| Artifact/file | What it represents | Look here first | If healthy, do this next | If failure/risk, do this next |
| --- | --- | --- | --- | --- |
| `build/gate-fast.json` | Fast PR-safe gate result (`gate fast`) and first failing step list | `ok`, then `failed_steps` (first item), then matching `steps[]` entry (`id`, `rc`) | Keep PR flow unchanged; move to `build/security-enforce.json` for threshold posture. | Fix the first failed step category (lint/type/tests/doctor/templates), rerun fast gate, then re-check artifact. |
| `build/security-enforce.json` | Security budget enforcement result (`security enforce`) with current counts vs limits | `ok`, `counts`, `exceeded`, `limits` | Keep current thresholds; proceed with stricter `main`/release checks. | Remediate findings or temporarily tune budget with explicit follow-up to ratchet down. |
| `build/release-preflight.json` | Release metadata preflight state used in tag/release workflows | `ok`, `version`, `tag`, `pyproject`, `changelog` (and summary fields when present) | Continue to package validation/publish flow for the same tag. | Fix tag/version/changelog mismatch first, rerun preflight, then continue release checks. |

## Recommended review order

1. Download artifacts from the workflow run: `ci-gate-diagnostics` and (for tag builds) `release-diagnostics`.
2. Open `build/gate-fast.json` first for fastest actionable failure.
3. Open `build/security-enforce.json` second for policy/budget posture.
4. On release/tag runs, open `build/release-preflight.json` before checking later packaging logs.

This order keeps review focused on deterministic go/no-go evidence before log-deep-dives.
