# Repo tour (release-confidence orientation)

Use this page to map the repository quickly without losing the core story.

## 1) Core flow first

```text
Install -> gate fast -> gate release -> doctor -> artifact review -> team/CI rollout
```

Canonical commands:

```bash
python -m sdetkit gate fast
python -m sdetkit gate release
python -m sdetkit doctor
```

## 2) Where to start by goal

- **Evaluating fit quickly**
  - [Start here](index.md)
  - [Blank repo to value in 60 seconds](blank-repo-to-value-60-seconds.md)
  - [Decision guide](decision-guide.md)

- **Onboarding to guided execution**
  - [Install](install.md)
  - [First run quickstart](ready-to-use.md)
  - [Release confidence](release-confidence.md)

- **Reviewing proof and behavior change**
  - [Before/after evidence example](before-after-evidence-example.md)
  - [Evidence showcase](evidence-showcase.md)

## 3) Repository map

| Area | Purpose | First file to open |
|---|---|---|
| `src/sdetkit/` | Product code (CLI + library modules) | `src/sdetkit/cli.py` |
| `tests/` | Regression + behavior checks | `tests/test_cli_sdetkit.py` |
| `docs/` | User + engineering documentation | `docs/index.md` |
| `scripts/` | Environment/bootstrap/check wrappers | `scripts/check.sh` |
| `artifacts/` | Generated evidence packs | `artifacts/` |

## 4) Secondary and advanced references

Advanced command families, integrations, and reference pages are intentionally secondary to the release-confidence first-run path.

Use [CLI reference](cli.md) only after the core command path is stable.
