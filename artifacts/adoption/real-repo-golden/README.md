# Real repo adoption golden artifacts

These files are generated evidence from the fixture at
`examples/adoption/real-repo/`.

They are **golden reference artifacts** for documentation and CI replay checks,
not live CI outputs.

## Generation context

- Fixture path: `examples/adoption/real-repo/`
- Generated on: 2026-04-06 (UTC)
- Generated from commit: `d6f7aaa2`
- Tool invocation context: local repo checkout with `PYTHONPATH=src`

## Canonical commands used

```bash
cd examples/adoption/real-repo
PYTHONPATH=/workspace/DevS69-sdetkit/src python -m sdetkit gate fast --format json --stable-json --out build/gate-fast.json
PYTHONPATH=/workspace/DevS69-sdetkit/src python -m sdetkit gate release --format json --out build/release-preflight.json
PYTHONPATH=/workspace/DevS69-sdetkit/src python -m sdetkit doctor --format json --out build/doctor.json
```

## Notes

- `gate release` currently does not accept `--stable-json`; output is still
  deterministic for this fixture.
- `gate fast` and `gate release` are expected to report failures in this fixture,
  which is intentional and truthful for first-run adoption triage.
