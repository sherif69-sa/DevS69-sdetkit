# DevS69 SDETKit

SDETKit is an umbrella **SDET / QA / release confidence platform** with deterministic CLI workflows and machine-readable artifacts.

## Umbrella kits

- **Release Confidence Kit** (`sdetkit release ...`): gate, doctor, security, repo audit, and evidence lanes.
- **Test Intelligence Kit** (`sdetkit intelligence ...`): flake classification, deterministic env capture, changed-scope impact summary, and mutation governance.
- **Integration Assurance Kit** (`sdetkit integration ...`): profile-driven environment/service readiness contracts.
- **Failure Forensics Kit** (`sdetkit forensics ...`, experimental): run compare and deterministic repro bundle generation.

List kits:

```bash
python -m sdetkit kits list --format json
```

## Hero journeys (start here)

```bash
python -m sdetkit release gate fast
python -m sdetkit release gate release
python -m sdetkit intelligence flake classify --history examples/kits/intelligence/flake-history.json
python -m sdetkit integration check --profile examples/kits/integration/profile.json
python -m sdetkit forensics compare --from examples/kits/forensics/run-a.json --to examples/kits/forensics/run-b.json
```

## Backward compatibility

Existing stable commands remain supported (`gate`, `doctor`, `security`, `repo`, `evidence`, `report`, etc.). Kit commands are additive product grouping aliases.

## Docs

- Architecture note: `docs/architecture/umbrella-kits.md`
- Kit pages:
  - `docs/kits/release-confidence.md`
  - `docs/kits/test-intelligence.md`
  - `docs/kits/integration-assurance.md`
  - `docs/kits/failure-forensics.md`
