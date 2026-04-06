# Sample outputs (exploratory, non-canonical examples)

This page is exploratory and non-canonical.

For canonical first-proof and CI evidence interpretation, use:
- [Blank repo to value in 60 seconds](blank-repo-to-value-60-seconds.md)
- [CI artifact walkthrough](ci-artifact-walkthrough.md)
- [Evidence showcase](evidence-showcase.md)

## Scope note

- These examples are shape-oriented and explanatory.
- Do not treat this page as the source of truth for go/no-go decisions.
- Use real run artifacts (`build/*.json`) from your local run or CI upload for decision-making.

## Example 1: `gate fast` shape

```bash
python -m sdetkit gate fast --format json --stable-json --out build/gate-fast.json
```

Look for:
- `ok`
- `failed_steps`
- `profile`

## Example 2: `security enforce` shape

```bash
python -m sdetkit security enforce --format json --max-error 0 --max-warn 0 --max-info 0 --out build/security-enforce.json
```

Look for:
- `ok`
- `counts`
- `exceeded`

## Example 3: `gate release` shape

```bash
python -m sdetkit gate release --format json --stable-json --out build/release-preflight.json
```

Look for:
- `ok`
- `failed_steps`
- `profile`

## Decision reminder

For PR and release decisions, cite fields from your real artifacts and link the uploaded files.
