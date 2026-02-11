````markdown
# SDET Bootcamp (sdetkit)

A practical repo for production-style SDET workflows:
- CLI exercises
- quality gates (ruff/mypy/pytest/coverage/docs)
- testable modules for katas and tasks

## Start

```bash
python3 -m venv .venv
./.venv/bin/python -m pip install -r requirements-test.txt -r requirements-docs.txt -e .
bash scripts/check.sh all
````

## Pages

* CLI: cli.md
* Doctor: doctor.md
* Patch harness: patch-harness.md
* n8n integration: n8n.md
* Project structure: project-structure.md
* Roadmap: roadmap.md
* Contributing: contributing.md

- [Repo Audit and Safe Fixes](repo-audit.md)
