# SDETKit architecture map (contributor and maintainer guide)

This document is the authoritative architectural blueprint of SDETKit v2.0.0. It defines how subsystems are layered, how AI coding agents interact with gates over MCP, how evidence circulates deterministically, and where contributors should introduce changes.

---

## 1. Stable first path (the public contract)

The platform front door is intentionally narrow, deterministic, and stable:

1. `python -m sdetkit gate fast` &mdash; Fast commit-time quality gate (doctor, ci_templates, ruff, format, mypy, targeted pytest).
2. `python -m sdetkit gate release` &mdash; Release preflight gate (`doctor_release`, `code_scanning` SARIF, `gate_fast`).
3. `python -m sdetkit doctor` &mdash; Diagnostics, environment readiness, and prescriptive remediation.

Any change that could impact first-time contributor adoption must validate this stable path first.

---

## 2. Six-layer platform architecture

```
+------------------------------------------------------------------------+
| 6. Consumption & Agent Layer: CLI, MCP Server (stdio), Review APIs    |
+------------------------------------------------------------------------+
                                    |
+------------------------------------------------------------------------+
| 5. Judgment & Decision Engine: SHIP/NO-SHIP, Verdicts (sdetkit.verdict)|
+------------------------------------------------------------------------+
                                    |
+------------------------------------------------------------------------+
| 4. Deterministic Evidence Lake: SARIF, Doctor Cortex, Release Artifacts|
+------------------------------------------------------------------------+
                                    |
+------------------------------------------------------------------------+
| 3. Fix-Safety & Verification: change_verifier, protected patch harness |
+------------------------------------------------------------------------+
                                    |
+------------------------------------------------------------------------+
| 2. Quality Gates & Orchestration: gate profiles, doctor, checks engine |
+------------------------------------------------------------------------+
                                    |
+------------------------------------------------------------------------+
| 1. Polyglot Adapters: Python, Go, Java, TypeScript/JS, C++            |
+------------------------------------------------------------------------+
```

### Layer 1: Polyglot adoption surface & test adapters
- **Python**: `pytest`, `unittest`, `hypothesis`, standard lockfiles (`uv.lock`, `requirements.txt`).
- **Go**: `sdetkit.go_tests` runner, `go test`, module dependency mapping.
- **Java**: `sdetkit.java_tests` runner, Gradle/Maven topology parsing.
- **JavaScript / TypeScript**: `sdetkit.js_tests` runner, Vitest/Jest regex adapters (`sdetkit.failure_vector_adapters`).
- **C++**: `sdetkit.failure_vector_cpp` failure extraction and sanitizer output parsing.
- **CI Adapters**: GitHub Actions, GitLab CI, Jenkins, Tekton (`templates/ci`).

### Layer 2: Quality gates & checks orchestration
- `sdetkit.gate`: Orchestrates execution profiles (`fast`, `release`, `strict`, `adoption`).
- `sdetkit.checks`: Profile-driven checks framework with dependency ordering and bounded timeouts.
- `sdetkit.doctor`: Prescriptive readiness scanner covering metadata, dependencies, security files, and repo layout.

### Layer 3: Fix-safety & patch verification harness
- `sdetkit.change_verifier`: Verifies code modifications to ensure tests were not weakened or deleted.
- `sdetkit.changed_mutation`: Generates surgical AST/line mutations against modified code to ensure changed lines are thoroughly tested.
- `sdetkit.changed_coverage`: Strict line-by-line coverage enforcement for PR diffs.
- `sdetkit.protected_verifier` & `sdetkit.patch`: Path-traversal and symlink escape rejection, file size boundaries, and atomic application.

### Layer 4: Deterministic evidence circuit
- **Machine-readable contracts**: `sdetkit.verdict.v1`, `sdetkit.doctor.v2`, `sdetkit.judgment.v1`.
- **Security & scan formats**: SARIF 2.1.0 output for GitHub Advanced Security / GitLab integration.
- **Release preflight bundles**: Written to `build/release-preflight.json` with SHA-256 provenance and clean tree attestation.

### Layer 5: Judgment & decision engine
- Translates disparate evidence into unified `SHIP` / `REVIEW` / `NO-SHIP` decisions.
- Ranked confidence scoring with contradiction resolution and prescriptive next actions.

### Layer 6: AI coding agent & operator interfaces
- **Model Context Protocol (MCP)**: Native stdio server (`sdetkit.mcp_server`) exposing `verify_change` and `gate_fast` directly to autonomous coding agents (Claude Code, Gemini CLI, Antigravity).
- **CLI Router**: `sdetkit.cli` entrypoint with subcommands (`gate`, `doctor`, `verify`, `diagnose`, `mission-control`).
- **Operator Summaries**: Markdown and ANSI console outputs optimized for human operators and pull request review bots.

---

## 3. Command-surface tiers

- **Public / stable**: Canonical release-confidence flows (`gate fast`, `gate release`, `doctor`) and their machine-readable artifact contracts.
- **Advanced but supported**: Deep operational lanes (`verify change`, `diagnose`, `mission-control`, `adoption-surface`, `readiness`).
- **Legacy / historical**: Shims and historical entrypoints preserved for backwards compatibility (`kvcli`, `apigetcli`).

---

## 4. Cross-platform engineering invariants

1. **Pure ASCII source code**: All source code under `src/` and `tools/` must contain only valid ASCII bytes (< 0x80). Non-ASCII characters in docstrings, regexes, or UI templates must use standard unicode escape sequences (e.g. `\u2014`, `\u2026`, `\u276F`). Enforced by `python -m sdetkit doctor --ascii`.
2. **Symlink and filesystem resilience**: The codebase must operate reliably across Linux, macOS, and Windows. Symlink directories (such as `templates/ci`) must provide clean NTFS junction / skip-worktree fallback without dirtying Git status or breaking path traversal.
3. **Clean diff & typing standards**: Strict type safety via `mypy`, lint compliance via `ruff`, and zero unchecked exception leaks.

---

## 5. Plugin & notification extension points

- **Entry point discovery**: Registered via `project.entry-points` in `pyproject.toml` (e.g. `sdetkit.notify_adapters` for `stdout`, `telegram`, `whatsapp`).
- **Resilience-first loading**: Plugin failures are isolated with graceful fallbacks so an unavailable plugin never crashes core gates.

---

## 6. Where to read next

- Product overview: [Documentation hub](../index.md)
- Top-tier upgrade roadmap: [docs/top-tier-upgrade-cycle-plan.md](../top-tier-upgrade-cycle-plan.md)
- CLI reference: [docs/cli.md](../cli.md)
- Stability policy: [docs/stability-levels.md](../stability-levels.md)
