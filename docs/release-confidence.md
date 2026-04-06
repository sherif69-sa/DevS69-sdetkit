# Release confidence with SDETKit (canonical explainer)

DevS69 SDETKit gives engineering teams deterministic release go/no-go decisions with machine-readable evidence, using one repeatable command path from local to CI.

## What release confidence means in this repo

Release confidence means a repository can answer **"Is this ready to ship?"** with repeatable command outcomes plus structured artifacts, not only ad hoc terminal interpretation.

## Canonical command path (primary)

```bash
python -m sdetkit gate fast --format json --stable-json --out build/gate-fast.json
python -m sdetkit gate release --format json --stable-json --out build/release-preflight.json
python -m sdetkit doctor
```

## Canonical proof contract (local and CI)

Invariant path:
- Local run uses the same gate path as CI evidence review: `gate fast` -> `gate release` -> `doctor`.
- CI preserves the same JSON decision objects as artifacts.

Invariant artifacts:

```text
build/
├── gate-fast.json
└── release-preflight.json
```

Invariant fields for first triage:
- `ok`
- `failed_steps`
- `profile`

Go/no-go support model:
- `ok` gives deterministic pass/fail.
- `failed_steps` gives first remediation targets.
- `profile` confirms which lane produced the result.

## Primary vs optional

### Primary (use first)
- `gate fast`
- `gate release`
- `doctor`
- JSON artifacts in `build/` for review decisions
- CI artifact decoder: [CI artifact walkthrough](ci-artifact-walkthrough.md)

### Optional (use later)
- Team rollout documents and stricter CI layers
- Broader command families (intelligence/integration/forensics)
- Advanced references and integrations

## Local and CI stay aligned

- Local developer run: execute canonical commands directly.
- CI run: execute same core commands and upload JSON outputs.
- Review: use artifact fields as source-of-truth before log deep-dives.

Canonical CI rollout details: [Recommended CI flow](recommended-ci-flow.md).

## What this does not try to be

- Not a replacement for every underlying lint/test/security tool.
- Not an attempt to maximize command surface area for first-time users.
- Not a claim that every repo needs full enterprise policy layers on day one.

SDETKit focuses first on deterministic release-confidence decisions and evidence clarity.

## Related pages by need

- Install and first run: [install.md](install.md), [ready-to-use.md](ready-to-use.md)
- Ultra-fast proof: [blank-repo-to-value-60-seconds.md](blank-repo-to-value-60-seconds.md)
- Evidence and comparison: [before-after-evidence-example.md](before-after-evidence-example.md), [evidence-showcase.md](evidence-showcase.md)
- Fit decision: [decision-guide.md](decision-guide.md)
- Boundary policy: [stability-levels.md](stability-levels.md)
