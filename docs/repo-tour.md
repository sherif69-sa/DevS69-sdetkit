# Repo tour (visual orientation)

This page is the fastest way to understand where to go next depending on your goal.

## 1) Big-picture flow

```text
Readme -> Setup -> CLI usage -> Diagnostics -> Safe repo checks -> Contribution/release
   |         |         |             |                |                 |
 README   docs/cli   doctor.md   repo-audit.md   patch-harness.md   contributing.md
```

## 2) Choose your path

<div class="grid cards" markdown>

- [**I’m evaluating the project as a candidate**](#candidate-path)
  Jump through architecture, quality gates, and practical CLI outcomes.

- [**I’m onboarding as a contributor**](#contributor-path)
  Follow setup, standards, and contribution workflow in the right order.

- [**I need commands right now**](#operator-path)
  Go directly to executable examples and diagnostics commands.

</div>

## Candidate path

1. Read [project structure](project-structure.md) to map modules quickly.
2. Review [design principles](design.md) to understand trade-offs.
3. Check [doctor](doctor.md) + [repo audit](repo-audit.md) for real quality mechanics.
4. Scan [ROADMAP](https://github.com/sherif69-sa/sdet_bootcamp/blob/main/ROADMAP.md) for direction and maturity indicators.

## Contributor path

1. Start with [contributing](contributing.md).
2. Run [CLI guide](cli.md) examples to validate your local setup.
3. Execute [doctor checks](doctor.md) before opening changes.
4. Use [patch harness](patch-harness.md) when applying structured updates.
5. Follow [releasing](releasing.md) for versioning and release flow.

## Operator path

### Most-used commands

```bash
./.venv/bin/sdetkit --help
./.venv/bin/sdetkit doctor --all
./.venv/bin/sdetkit apiget https://example.com/api --expect dict
./.venv/bin/sdetkit repo check . --profile enterprise --format json
```

### Deep-dive references

- [CLI command guide](cli.md)
- [API docs](api.md)
- [n8n integration](n8n.md)
- [Security notes](security.md)

## 3) Repo artifact map

| Area | Purpose | First file to open |
|---|---|---|
| `src/sdetkit/` | Product code (CLI + library modules) | `src/sdetkit/cli.py` |
| `tests/` | Regression + behavior checks | `tests/test_cli_sdetkit.py` |
| `docs/` | User + engineering documentation | `docs/index.md` |
| `tools/` | Patch and utility helpers | `tools/patch_harness.py` |
| `scripts/` | Environment/bootstrap/check wrappers | `scripts/check.sh` |

---

Need a top-level jump list? Return to [docs home](index.md) or [README](https://github.com/sherif69-sa/sdet_bootcamp/blob/main/README.md).
