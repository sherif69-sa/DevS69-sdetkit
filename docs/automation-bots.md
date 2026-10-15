# Automation bots and maintenance control loop

This page lists the GitHub Actions workflows that keep this repository maintained, and the local commands that reproduce what they check. Every workflow listed here exists under `.github/workflows/`.

## Workflows

| Workflow | Runs on | What it does |
| --- | --- | --- |
| `ci.yml` (CI) | push, pull request | Fast and full CI lanes, wheel smoke installs, repo audit |
| `quality.yml` (Quality) | pull request, schedule | Pre-commit, whole-package coverage, critical-spine and quality-truth checks |
| `security.yml` (Security) | push, pull request, schedule | CodeQL analysis of the Python code |
| `osv-scanner.yml` | push, pull request, schedule | OSV vulnerability scan of dependencies |
| `dependency-audit.yml` | push, pull request, schedule | `pip-audit` of the declared dependencies |
| `dependency-review.yml` | pull request | GitHub dependency review of added or changed dependencies |
| `dependency-auto-merge.yml` | pull request | Auto-merge policy for dependency-update pull requests; refreshes `uv.lock` on Dependabot pull requests |
| `pre-commit-autoupdate.yml` | schedule | Opens a pull request that updates pre-commit hook versions |
| `maintenance-autopilot.yml` | pull request, schedule | Runs `tools/maintenance_autopilot.py` and uploads its evidence (a required check) |
| `repo-audit.yml` | push, pull request | Runs the SDETKit repo audit action |
| `enforce-branch-protection.yml` | push, pull request, schedule | Checks that `main` keeps its branch protection |
| `legacy-required-status-bridge.yml` | pull request, workflow run | Publishes the `ci` required status from the CI workflow's result |
| `first-proof.yml` | push, pull request | Runs the first-proof path on Python 3.10 to 3.13 |
| `adoption-real-repo-canonical.yml` | pull request | Replays the canonical real-repository adoption evidence |
| `release-candidate.yml` | push, pull request | Builds and qualifies the candidate wheel and sdist |
| `release.yml` | tag push | Publishes to PyPI through Trusted Publishing |
| `versioning.yml` | push, pull request | Checks that `CHANGELOG.md` has the current version |
| `sbom.yml` | push | Generates a software bill of materials |
| `docs-link-check.yml` | push, pull request | Validates Markdown links |
| `pages.yml` | push | Builds and publishes the documentation site |
| `mutation-tests.yml` | schedule | Mutation testing |

## Reproduce the checks locally

```bash
python -m sdetkit gate fast
python -m sdetkit gate release
python -m sdetkit maintenance --format md
python -m sdetkit maintenance --include-check github_automation_check --format json
python -m sdetkit intelligence upgrade-audit --format json --used-in-repo-only --top 10
bash quality.sh ci
```

When a CI job fails, save its log and run the remediation loop on it; see [Remediation loop](remediation-loop.md):

```bash
python -m sdetkit diagnose run --log build/ci-logs/<job>/ci_log.txt --prove
```

## Weekly maintainer flow

1. Clear failing required checks (`ci`, `maintenance-autopilot`) on open pull requests first.
2. Triage new CodeQL, OSV and `pip-audit` findings; fix high-severity ones before anything else.
3. Review the pre-commit autoupdate and dependency-update pull requests.
4. Check the latest `maintenance-autopilot` evidence for drift.
5. Record follow-up work in `docs/roadmap.md`.
