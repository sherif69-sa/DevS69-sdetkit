<div class="hero-panel" markdown>

# SDET Bootcamp (sdetkit)

A practical, production-ready toolkit for SDET workflows — with clean CLI ergonomics, diagnostics, API automation, and repository safety checks.

</div>

<div class="quick-jump" markdown>

[⚡ Fast start](#fast-start) · [🧭 Repo tour](repo-tour.md) · [🛠 CLI commands](cli.md) · [🩺 Doctor checks](doctor.md) · [🤝 Contribute](contributing.md)

</div>

## Why teams use this project

<div class="grid cards" markdown>

- **Reliable local + CI workflows**
  Move from laptop validation to pipeline checks with consistent scripts and quality gates.

- **Focused command-line experience**
  Use purpose-built commands for health checks, API calls, cassette workflows, and patch-safe operations.

- **Designed for maintainability**
  Organized modules, explicit docs, and test coverage make extension safer and faster.

</div>

## Fast start

```bash
python3 -m venv .venv
./.venv/bin/python -m pip install -r requirements-test.txt -r requirements-docs.txt -e .
bash scripts/check.sh all
```

!!! tip "Choose your starting point"
    New to the project? Start with **Repo tour**, then run **CLI**, then execute **Doctor**.

## Navigate by goal

### Run commands quickly

<div class="grid cards" markdown>

- [**CLI**](cli.md)
  Command reference and practical usage patterns.

- [**Doctor**](doctor.md)
  Environment and repository diagnostics with actionable recommendations.

- [**Repo audit**](repo-audit.md)
  Safety-focused checks and guided remediations.

</div>

### Integrate and automate

<div class="grid cards" markdown>

- [**API**](api.md)
  Programmatic interfaces and API usage flows.

- [**n8n integration**](n8n.md)
  Automation patterns for workflow orchestration.

- [**Patch harness**](patch-harness.md)
  Controlled patch application and validation.

</div>

### Understand architecture and contribute

<div class="grid cards" markdown>

- [**Repo tour**](repo-tour.md)
  Visual orientation map and role-based pathways.

- [**Project structure**](project-structure.md)
  Repository layout and module roles.

- [**Design**](design.md)
  Engineering decisions, principles, and trade-offs.

- [**Contributing**](contributing.md) • [**Security**](security.md) • [**Releasing**](releasing.md)

</div>
