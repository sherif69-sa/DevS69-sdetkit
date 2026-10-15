# Evidence showcase: real-output proof anchor from this repository

Use this page as the canonical real-output anchor for artifact shape and interpretation language.

For first-time adoption, start with [Blank repo to value in 60 seconds](blank-repo-to-value-60-seconds.md). For decode order, use [CI artifact walkthrough](ci-artifact-walkthrough.md).

## Source-of-truth context

- These excerpts come from actual generated outputs captured in this repository's documented workflow.
- They are not customer data, synthetic benchmarks, or fabricated screenshots.
- Values (counts, failing steps) are context-dependent and can differ by branch, time, and repo state.

## Evidence scenario (context)

Scenario used for this evidence set:
- Run `gate fast`
- Run strict `security enforce`
- Run `gate release`

Commands used:

```bash
mkdir -p build
python -m sdetkit gate fast --format json --out build/gate-fast.json
python -m sdetkit security enforce --format json --out build/security-enforce.json --max-error 0 --max-warn 0 --max-info 0
python -m sdetkit gate release --format json --out build/release-preflight.json
```

Observed exit codes in this captured run:
- `gate fast`: `2`
- `security enforce`: `1`
- `gate release`: `2`

## Artifact files produced

```text
build/
├── gate-fast.json
├── security-enforce.json
└── release-preflight.json
```

## Artifact excerpts and reviewer decision sentence

### `build/gate-fast.json`

```json
{
  "failed_steps": [
    "ruff",
    "ruff_format"
  ],
  "ok": false,
  "profile": "fast"
}
```

Reviewer decision sentence:
- "Fast gate is not ready to merge: `ok=false`; first remediation target is `ruff`."

### `build/security-enforce.json`

```json
{
  "counts": {
    "error": 0,
    "info": 131,
    "total": 131,
    "warn": 0
  },
  "exceeded": [
    {
      "count": 131,
      "limit": 0,
      "metric": "info"
    }
  ],
  "ok": false
}
```

Reviewer decision sentence:
- "Security budget failed on `info` (`131 > 0`); release stays blocked until threshold or findings are addressed."

### `build/release-preflight.json`

```json
{
  "failed_steps": [
    "gate_fast"
  ],
  "ok": false,
  "profile": "release"
}
```

Reviewer decision sentence:
- "Release preflight is not ready: `ok=false`; blocker is nested `gate_fast`."

## Canonical inspect order

1. Open `build/release-preflight.json` first.
2. If `gate_fast` failed, open `build/gate-fast.json`.
3. If policy is relevant, open `build/security-enforce.json` (`counts`, `exceeded`).
4. Use raw logs only after artifact-level triage.

## How teams should reference these artifacts

- Upload JSON files as CI artifacts.
- In PR summaries and release discussions, cite fields (`ok`, `failed_steps`, `counts`, `exceeded`) rather than long log excerpts.
- Keep artifact links in decision threads so go/no-go reasoning stays auditable.

## Caution on context and time

This is a repository-specific captured run. Treat the structure as canonical and the values as situational.

## Related pages

- Behavior comparison: [Before/after evidence example](before-after-evidence-example.md)
- Product model: [Release confidence](release-confidence.md)
- Canonical decoder: [CI artifact walkthrough](ci-artifact-walkthrough.md)

Secondary references (after core proof path):
- [SDETKit vs ad hoc](sdetkit-vs-ad-hoc.md)
- [Repo cleanup plan](repo-cleanup-plan.md)
- [Repo health dashboard](repo-health-dashboard.md)
