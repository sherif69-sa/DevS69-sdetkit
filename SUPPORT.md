# Support

This project is maintained in public and provided without a contractual SLA.
Support is best-effort through the public issue tracker and project docs.

## Before opening an issue

1. Use an isolated environment (recommended): virtualenv or `pipx`.
2. Confirm your runtime is **Python 3.11+**.
3. Re-run the canonical release-confidence path:
   - `python -m sdetkit gate fast --format json --stable-json --out build/gate-fast.json`
   - `python -m sdetkit gate release --format json --out build/release-preflight.json`
   - `python -m sdetkit doctor`

If the problem persists, open an issue with the artifacts below.

## Where to get help

- **Install/runtime problems:** open a GitHub issue and label it as install/runtime.
- **Docs problems:** open a GitHub issue and label it as documentation.
- **Release-confidence / gate interpretation questions:** open a GitHub issue and include the gate artifacts so maintainers can interpret the same evidence.
- **Bug reports vs feature requests:**
  - Use **Bug report** when behavior is incorrect or inconsistent with docs.
  - Use **Feature request** when behavior is working as documented but you want new capability.

Project issue tracker:
- https://github.com/sherif69-sa/DevS69-sdetkit/issues

## What to include in every support issue

Please include:

- What you tried.
- Expected behavior.
- Actual behavior.
- Minimal reproduction steps.

### Attach these artifacts

When possible, attach these files/outputs directly to the issue:

- `build/gate-fast.json`
- `build/release-preflight.json`
- output of `python -m sdetkit doctor`
- environment details:
  - Python version (`python --version`)
  - OS + version
  - install method (for example `pip install ...` in venv, or `pipx install ...`)

These details make support triage significantly faster and reduce back-and-forth.

## Stability and support boundaries

Support expectations follow documented surface tiers:

- **Public / stable:** strongest compatibility and support expectations; safest dependency targets for adopters.
- **Advanced but supported:** supported in production, but ergonomics/docs/integration edges may iterate faster.
- **Experimental / incubator:** opt-in, best-effort continuity; validate in your own repository/CI before depending on it.

See also:
- `docs/versioning-and-support.md`
- `docs/stability-levels.md`
- `docs/command-surface.md`

## Private contact

For private inquiries (including commercial licensing permissions), use one of the channels below:
- LinkedIn: https://www.linkedin.com/in/sherif-atef-b1077a124/
- Email: sherif.atef6300@gmail.com

## GitHub dependency snapshot submission failures

If your workflow uses `actions/component-detection-dependency-submission-action` and fails with:

- `HttpError: An error occurred while processing your request. Please try again later.`
- `Failed to submit snapshot`

this is usually a transient GitHub Dependency Graph API-side failure (the component scan can still succeed).

Recommended mitigations:

1. Ensure job permissions include:
   - `contents: read`
   - `dependency-graph: write`
2. Add an exponential-backoff retry around the submission step.
3. Keep the detector category/filter constrained (for Python: `detectorsCategories: Python`, `detectorsFilter: PipReport`) to reduce payload size and execution time.
4. Keep `snapshot-sha` and `snapshot-ref` aligned to the triggering commit/ref.

If the failure is intermittent, re-running the workflow usually succeeds once GitHub API capacity recovers.
