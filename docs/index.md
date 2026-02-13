<div class="hero-panel" markdown>

# DevS69 sdetkit

A practical, production-ready toolkit for SDET workflows — with clean CLI ergonomics, diagnostics, API automation, and repository safety checks.

<div class="hero-badges" markdown>

[![Release](https://img.shields.io/badge/release-v1.0.1-0ea5e9?logo=github)](https://github.com/sherif69-sa/DevS69-sdetkit/releases) [![Python](https://img.shields.io/badge/python-3.11%2B-2563eb?logo=python)](https://github.com/sherif69-sa/DevS69-sdetkit/blob/main/pyproject.toml) [![Docs](https://img.shields.io/badge/docs-material-success?logo=materialformkdocs)](https://sherif69-sa.github.io/DevS69-sdetkit/)

</div>

</div>

<div class="quick-jump" markdown>

[⚡ Fast start](#fast-start) · [🆕 What's new](#whats-new-in-v101) · [🧭 Repo tour](repo-tour.md) · [🛠 CLI commands](cli.md) · [🩺 Doctor checks](doctor.md) · [🤝 Contribute](contributing.md)

</div>

## Why teams use this project

<div class="grid cards" markdown>

- **Reliable local + CI workflows**
  Move from laptop validation to pipeline checks with consistent scripts and quality gates.

- **Focused command-line experience**
  Use purpose-built commands for health checks, API calls, cassette workflows, and patch-safe operations.

- **Designed for maintainability**
  Organized modules, explicit docs, and test coverage make extension safer and faster.

- **Enterprise-friendly safety baseline**
  Hardened defaults for policy checks, governance, and release hygiene reduce operational risk.

</div>

## What's new in v1.0.1

<div class="grid cards release-cards" markdown>

- **Stronger PR quality gate**
  CI now runs `sdetkit doctor --all` and `sdetkit repo check --profile enterprise` on every pull request.

- **Security and dependency discipline**
  Dependency lockfiles and pinned automation actions improve repeatability and supply-chain posture.

- **Safer template/bootstrap behavior**
  `repo init`/`repo apply` flow is more robust against non-UTF-8 preset template content.

</div>

!!! info "Need the full release history?"
    See [CHANGELOG.md](https://github.com/sherif69-sa/DevS69-sdetkit/blob/main/CHANGELOG.md) for version-by-version details.

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

## Recommended journeys

<div class="grid cards" markdown>

- **For new contributors**
  Read [Repo tour](repo-tour.md) → [Contributing](contributing.md) → [Policy & baselines](policy-and-baselines.md).

- **For release managers**
  Start with [Releasing](releasing.md) → [CI contract](ci-contract.md) → [Premium quality gate](premium-quality-gate.md).

- **For automation engineers**
  Follow [CLI](cli.md) → [API](api.md) → [GitHub Action](github-action.md) → [n8n](n8n.md).

</div>

## License

Free for personal/educational noncommercial use. Commercial use requires a paid license; see [license page](license.md).
