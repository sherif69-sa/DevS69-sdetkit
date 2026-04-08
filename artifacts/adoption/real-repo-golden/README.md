# Real repo adoption golden artifacts

These files are generated evidence from the fixture at
`examples/adoption/real-repo/`.

They are **golden reference artifacts** for documentation and CI replay checks,
not live CI outputs.

## Canonical file set

- `gate-fast.json`
- `release-preflight.json`
- `doctor.json`
- `gate-fast.rc`
- `release-preflight.rc`
- `doctor.rc`
- `adoption-proof-summary.json`

## Generation context

- Fixture path: `examples/adoption/real-repo/`
- Generated on: 2026-04-08 (UTC)
- Tool invocation context: local repo checkout with editable install (`python -m pip install -e .`)

## Canonical commands used

```bash
cd examples/adoption/real-repo
python -m sdetkit gate fast --format json --stable-json --out build/gate-fast.json ; echo $? > build/gate-fast.rc
python -m sdetkit gate release --format json --out build/release-preflight.json ; echo $? > build/release-preflight.rc
python -m sdetkit doctor --format json --out build/doctor.json ; echo $? > build/doctor.rc
python ../../../scripts/real_repo_adoption_projection.py --fixture-root . --repo-root ../../.. --build-dir build --out build/adoption-proof-summary.json
```

## Truth notes

- `gate release` intentionally omits `--stable-json` because command support differs from `gate fast`.
- `gate fast` and `gate release` are expected to fail in this fixture; this is intentional first-run triage evidence, not a broken replay lane.
- `doctor` is expected to succeed while reporting actionable quality checks.
