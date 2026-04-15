# Role-based quickstarts (Phase 1 skeleton)

These quickstarts provide role-specific entry points for the top-tier transformation.

## Quickstart set

- [Release owner quickstart](quickstart-role-release-owner.md)
- [Platform engineer quickstart](quickstart-role-platform-engineer.md)
- [QA governance quickstart](quickstart-role-qa-governance.md)

## Shared baseline (all roles)

Run the canonical path before role-specific checks:

```bash
python -m sdetkit gate fast --format json --stable-json --out build/gate-fast.json
python -m sdetkit gate release --format json --out build/release-preflight.json
python -m sdetkit doctor --format json --out build/doctor.json
```

## Week-1 rollout checklist

- [ ] Assign one named owner per role.
- [ ] Capture one successful evidence run per role.
- [ ] Link each role run into the top-tier dashboard weekly closeout.
