# Starter work inventory

Use this page when you want a **real first contribution** without guessing where to start.

## How to use this inventory

1. Pick one contribution type below.
2. Keep it reviewable in one PR (usually a few files, no broad refactors).
3. Run the minimum checks listed in [First contribution quickstart](first-contribution-quickstart.md).

If you want to coordinate first, open a scoped proposal with `.github/ISSUE_TEMPLATE/feature_request.yml` and mark it as first-contribution sized.

## Starter contribution categories

### 1) Docs and examples alignment

**Good fit when:** command behavior has drifted from docs, or examples are hard to follow.

- Sync command flags/output between `README.md`, `docs/ready-to-use.md`, and `docs/cli.md`.
- Fix broken internal documentation links in `docs/`.
- Improve short “what to run next” guidance after quickstart steps.

### 2) Small, focused tests

**Good fit when:** behavior exists but one edge case is not covered.

- Add one targeted test in an existing `tests/test_*.py` file.
- Add a regression test for a command already documented in `docs/cli.md`.
- Improve assertion clarity (inputs/expected outputs) without changing product behavior.

### 3) Lint/type hygiene fixes

**Good fit when:** Ruff/mypy reports a localized issue.

- Resolve one lint warning in `src/` or `tests/` without behavior changes.
- Tighten a type annotation where return/input types are already implied by code.

### 4) Contributor-flow polish

**Good fit when:** contributor docs/templates are inconsistent.

- Align wording across `README.md`, `CONTRIBUTING.md`, and `docs/first-contribution-quickstart.md`.
- Improve issue-template prompts so maintainers get reproducible context faster.

## If no starter issue is available

You can still contribute safely:

1. Choose one category above.
2. Open a feature request with:
   - a narrow problem statement,
   - one-file or one-workflow scope,
   - objective acceptance criteria,
   - note that it is intended as a first contribution.
3. Wait for maintainer confirmation before implementing.

This keeps the contribution path real without creating placeholder/fake issues.
