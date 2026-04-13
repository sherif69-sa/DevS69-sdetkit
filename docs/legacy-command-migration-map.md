# Legacy command migration map (compatibility -> preferred lanes)

Use this page when you inherit existing automation that still uses transition-era or legacy command families.

## Migration policy

1. Keep production automation running first (do not break working pipelines abruptly).
2. Prefer the public/stable canonical path for first-run and release-go/no-go decisions:
   - `python -m sdetkit gate fast`
   - `python -m sdetkit gate release`
   - `python -m sdetkit doctor`
3. Migrate in small batches and validate artifacts after each move.
4. Keep `python -m sdetkit --help --show-hidden` for inventory/debugging only.

## Quick mapping table

| If you currently run | Preferred target lane | Why |
|---|---|---|
| `sdetkit weekly-review-lane` / historical weekly closeout variants | `sdetkit weekly-review` (or `sdetkit playbooks`) | Keeps workflow intent while moving to maintained surfaces. |
| `sdetkit phase1-*` / `phase2-*` / `phase3-*` closeout commands | `sdetkit playbooks` + stable command families (`gate`, `doctor`, `report`, `evidence`) | Reduces dependency on transition-era naming. |
| `sdetkit *-closeout` command families | `sdetkit playbooks` or umbrella kits (`release`, `intelligence`, `integration`, `forensics`) | Preserves outcomes while using clearer capability groupings. |
| Legacy quality-only invocations without explicit release decision flow | `gate fast` -> `gate release` -> `doctor` | Aligns with canonical ship/no-ship contract. |
| Hidden inventory-driven discovery in day-to-day use | `sdetkit kits list` and public help surfaces | Lowers cognitive load for new operators. |

## Suggested migration sequence

### Step 1: Inventory

Capture current usage from CI/scripts:

```bash
python -m sdetkit --help --show-hidden
```

Preview a recommendation for one legacy command:

```bash
python -m sdetkit legacy migrate-hint phase1-hardening
python -m sdetkit legacy migrate-hint --format json phase1-hardening
python -m sdetkit legacy migrate-hint --all --format json
```

Use `--format json` for automation workflows; payloads include `schema_version`, mode metadata, and `deprecation_horizon`.

Scan your repo/scripts for legacy command usage:

```bash
python scripts/legacy_command_analyzer.py --format json
```

### Step 2: Route by intent

- Release decision intent -> canonical gate/doctor path.
- Capability exploration intent -> `sdetkit kits list`.
- Team/process rollout intent -> `sdetkit playbooks`.

### Step 3: Validate in one branch

Run the same checks before/after migration and compare output artifacts (`ok`, `failed_steps`, profile and recommendations).

### Step 4: Keep compatibility fallback briefly

For high-risk repos, keep old command wrappers for one release cycle and remove after stable evidence is confirmed.

## Notes

- This page is guidance, not a forced deprecation policy.
- Legacy commands remain available for compatibility and traceability.
