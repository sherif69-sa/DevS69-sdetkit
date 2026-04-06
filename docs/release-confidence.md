# Release confidence with SDETKit (canonical explainer)

DevS69 SDETKit gives engineering teams deterministic release go/no-go decisions with machine-readable evidence, using one repeatable command path from local to CI.

## What release confidence means in this repo

Release confidence means a repository can answer **"Is this ready to ship?"** with repeatable command outcomes plus structured artifacts, not only ad hoc terminal interpretation.

## Canonical command path (primary)

```bash
python -m sdetkit gate fast
python -m sdetkit gate release
python -m sdetkit doctor
```

These are the primary commands for first-time adoption and ongoing release checks.

## Primary vs optional

### Primary (use first)
- `gate fast`
- `gate release`
- `doctor`
- JSON artifacts in `build/` for review decisions

### Optional (use when needed)
- Team rollout documents and CI policy layers
- Broader command families (intelligence/integration/forensics)
- Advanced references and integrations

## Why artifacts matter

Artifact files provide machine-readable decision objects that reviewers can inspect consistently.

Typical first artifacts:

```text
build/
├── gate-fast.json
└── release-preflight.json
```

Inspect `ok`, `failed_steps`, and `profile` first.

For concrete representative artifacts in this repo, use [Evidence showcase](evidence-showcase.md).

## Local and CI stay aligned

The same command path is used locally and in CI, so teams avoid one-off script behavior drift:

- Local developer run: execute canonical commands directly.
- CI run: execute same commands, upload JSON outputs as artifacts.
- Review: use artifact fields as source-of-truth for go/no-go decisions.

For implementation details, continue with [Recommended CI flow](recommended-ci-flow.md).

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
