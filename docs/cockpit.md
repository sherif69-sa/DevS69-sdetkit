# Quality Cockpit and Test Radar

`sdetkit cockpit` (aliases: `sdetkit radar`, `sdetkit scan`) provides an instant 360-degree quality intelligence dashboard for human developers and AI coding agents. In a single command running in seconds, it audits repository readiness, verifies working-tree cleanliness, confirms native MCP tool availability, evaluates assertion mutation coverage, and synthesizes a definitive release confidence verdict (`SHIP`, `REVIEW`, or `NO_SHIP`).

```bash
# 360-degree quality cockpit terminal dashboard
python -m sdetkit cockpit

# Instant Zero-to-Value repository scan
python -m sdetkit scan

# Continuous live terminal watch mode (re-evaluates on file changes)
python -m sdetkit cockpit --watch

# Generate standalone offline interactive HTML report
python -m sdetkit cockpit --html quality-radar.html

# Emit GitHub-flavored Markdown for CI summaries
python -m sdetkit cockpit --step-summary

# Emit machine-readable radar telemetry
python -m sdetkit cockpit --format json
```

## Zero-to-Value Radar View

```text
==============================================================================
 * DEVS69 SDETKIT 2.0 * QUALITY COCKPIT & TEST RADAR
==============================================================================
 WORKSPACE : DevS69-sdetkit (git: main @ 5b2b409)
 RUNTIME   : Python 3.12.8 | Surfaces: Python, C/C++
 HEALTH    : 100/100 [ SHIP ]
==============================================================================
 [ RADAR DIMENSIONS & QUALITY HEALTH ]
   [OK] Doctor Health Score    : 100% (ASCII & dependency integrity)
   [OK] Native MCP Server      : 12 tools registered on stdio
   [OK] Assertion Mutation     : Active (6 AST mutation operators)
   [OK] Security & Secrets     : Clean (zero unapproved secret leaks)
   [OK] Working Tree Drift     : Clean (no unasserted format drift)
------------------------------------------------------------------------------
 [ MCP AGENT SUPER-BRIDGE ]
   Tools: verify_change, gate_fast, doctor, diagnose_failure, run_mutation, auto_fix, hunt_flakes, select_impacted_tests, manage_test_quarantine, evaluate_blast_radius, heal_workspace, inject_chaos
   Agent Connect Command: claude mcp add sdetkit -- python -m sdetkit mcp
------------------------------------------------------------------------------
 [ VERDICT & ACTION ]
   VERDICT    : [ SHIP ]
   NEXT STEP  : Repository is in prime state. All baseline checks green.
==============================================================================
```

## The Five Radar Dimensions

| Dimension | Engine | What It Asserts |
| :--- | :--- | :--- |
| **Doctor Health** | `sdetkit doctor` | Scans repository hygiene, dependency consistency, CI workflows, and verifies pure ASCII source compliance under `src/` and `tools/`. |
| **MCP Agent Readiness** | `sdetkit.mcp_server` | Verifies that all 12 zero-dependency MCP stdio tools (`verify_change`, `gate_fast`, `doctor`, `diagnose_failure`, `run_mutation`, `auto_fix`, `hunt_flakes`, `select_impacted_tests`, `manage_test_quarantine`, `evaluate_blast_radius`, `heal_workspace`, `inject_chaos`) are operational. |
| **Assertion Mutation** | `sdetkit.changed_mutation` | Checks active AST mutation operators (condition negation, comparison inversion, call replacement, boundary shift) to catch logic gaps where tests pass without asserting behavior. |
| **Security & Secrets** | `sdetkit.gates.security_gate` | Audits code for hardcoded secrets and risky execution paths against the repository's vetted security baseline. |
| **Safe Remediation Drift** | `sdetkit.auto_fix` | Classifies uncommitted working tree changes into clean, safe-to-auto-fix (format or lint drift), or human review required. |

## AI Coding Agent Super-Bridge

Modern AI coding agents (Claude Code, Cursor, Codex, Gemini CLI) excel when provided with explicit quality invariants and native tool execution boundaries.

### 1. View Ready-to-Use Agent Configuration
To display recommended configuration snippets for Claude Code, Cursor, and generic coding agents:

```bash
python -m sdetkit cockpit --agent-config
```

### 2. Scaffold Agent Instruction Files
To scaffold `CLAUDE.md`, `AGENTS.md`, and `.mcp.json` directly into your workspace:

```bash
python -m sdetkit cockpit --init-agent
```

This generates:
- **`CLAUDE.md`**: Directs Claude Code to run `verify_change` and `gate_fast` before committing.
- **`AGENTS.md`**: Provides immutable quality invariants for all autonomous coding assistants.
- **`.mcp.json`**: Standard MCP server registration:
  ```json
  {
    "mcpServers": {
      "sdetkit": {
        "command": "python",
        "args": ["-m", "sdetkit", "mcp"]
      }
    }
  }
  ```

## CLI Reference

| Flag | Purpose |
| :--- | :--- |
| `--repo-root <dir>` | Target repository directory (default: current working directory `.`) |
| `--format {text,json,md,html}` | Output format (default: `text` formatted ASCII dashboard) |
| `--html <path>` | Write standalone interactive HTML quality dashboard to file |
| `--step-summary` | Append GitHub-flavored Markdown radar card to `$GITHUB_STEP_SUMMARY` |
| `--watch` | Live terminal watch mode (re-evaluates radar on file change) |
| `--scan` | Deep scan mode: includes security scan and dependency checks |
| `--out <path>` | Write radar telemetry output to specified file |
| `--agent-config` | Print AI agent configuration templates to stdout |
| `--init-agent` | Write `CLAUDE.md`, `AGENTS.md`, and `.mcp.json` into the repository |
| `--force` | Overwrite existing agent files when running `--init-agent` |
| `--ascii` | Enforce pure ASCII character discipline in terminal output |

### Exit Status Codes
- `0`: Repository health score is nominal and verdict is `SHIP`.
- `1`: Radar detected issues requiring human review (`REVIEW`) or blocking issues (`NO_SHIP`).
