# Repo adoption scan

`adopt-scan` is the repo-level entrypoint for adopting SDETKit in a real company repository. It inventories the repo, detects likely stacks and CI/docs/test contracts, reports adoption gaps, and gives the exact commands to establish release-confidence evidence.

## Command

```bash
python -m sdetkit adopt-scan . --format json --out build/sdetkit-adopt-scan.json
```

## What it detects

- Python, JavaScript/TypeScript, docs, Docker, GitHub Actions, GitLab CI, tests, README, and license surfaces.
- Missing CI contract, missing tests, missing Python project metadata, missing test dependency contract, missing docs build contract, missing README, and missing license/compliance policy.
- Recommended first commands for `gate fast`, `gate release`, `doctor`, `review`, pytest, Ruff, MkDocs, and the adaptive dashboard when gaps exist.

## How teams use it

1. Run `adopt-scan` on every repo before rollout.
2. Fix high-severity adoption gaps first, especially missing tests and missing CI.
3. Publish the recommended JSON artifacts in CI.
4. Use the adaptive dashboard and diagnosis output for evidence-based remediation rather than random fixes.
