# Coding agents (MCP)

`sdetkit mcp` serves SDETKit to coding agents over the [Model Context Protocol](https://modelcontextprotocol.io/), so an agent can check its own work before it commits or opens a pull request: did the change pass the repository's tests, without weakening them?

It is a stdio server with seven tools (`verify_change`, `gate_fast`, `doctor`, `diagnose_failure`, `run_mutation`, `auto_fix`, `hunt_flakes`) and no extra dependencies.

## Add it to an agent

Claude Code:

```bash
claude mcp add sdetkit -- python -m sdetkit mcp
```

Any client that reads an MCP server list (Cursor, VS Code, Codex and others) takes the same command:

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

Use the interpreter SDETKit is installed in. The tools run in the folder the agent starts the server in, unless a call names `repo_root`.

## Tools

### `verify_change`

Runs [`sdetkit verify change`](verify-change.md). With no arguments it verifies the agent's uncommitted work against `HEAD`: modified files, staged files and new untracked files, built through a throwaway git index, so the repository's own index and working tree are not touched. Pass `head` (and `base`) to verify commits instead, or `patch` for a diff file.

| Argument | What it does |
| --- | --- |
| `repo_root` | Repository to check |
| `base`, `head` | Commits to compare, instead of the uncommitted work |
| `pr` | A GitHub pull request number, instead: its head from `origin`, from where it left the default branch (or from `base`); see [verify a change](verify-change.md) |
| `patch` | A diff file to verify on top of `base` |
| `pytest_args` | Arguments for the test runner, such as test paths |
| `project` | Folder whose tests run, in a repository of several projects (default: every project the change touches) |
| `runner` | `auto` (default), `pytest`, `vitest`, `jest`, `node`, `go`, `maven` or `gradle`; see [JavaScript and TypeScript](verify-change.md#javascript-and-typescript), [Go](verify-change.md#go) and [Java](verify-change.md#java) |
| `network` | `allow` (default) or `deny`: run the tests with no network but their own loopback; see [Without the network](verify-change.md#without-the-network) |
| `min_changed_coverage` | Percentage of the changed lines of code the tests must run, from 0 (default: reported only) to 100; see [Changed lines no test runs](verify-change.md#changed-lines-no-test-runs) |
| `mutate` | `true` alters the changed lines the tests run, one operator or constant at a time, and runs the tests on each mutant, to find the lines no test checks; see [Changed lines no test checks](verify-change.md#changed-lines-no-test-checks) |
| `max_mutants` | At most this many mutants (default 20) |
| `max_mutation_seconds` | Start no further mutant after this many seconds (default: no limit) |
| `min_mutation_score` | Percentage of the mutants the tests must catch, from 0 (default: reported only) to 100; setting it turns `mutate` on |

The result text is the same summary the [verify-change action](verify-change.md#in-github-actions) posts on a pull request. The structured result carries `status` (`VERIFIED`, `REVIEW`, `FAILED`, `NOT_RUN`), `verdict`, `reasons`, `next_action`, `findings`, `proving_tests`, the change's tests that fail without it, and `failures`: for a `FAILED` change, each broken test's failure message, so the agent can fix its work without running the tests again, `changed_lines`: the share of the changed lines of code the tests run and, per file, the lines no test runs, so the agent can add the tests they need, and with `mutate`, `mutation`: the share of mutants the tests catch and each surviving one (`path`, `line`, `before`, `after`, and `hint`: the test it asks for, such as *test the boundary: inputs where the two sides are equal*), a line the agent's tests run but do not check. When the tests pass, `next_action` also names up to three of those lines of each kind (`Then add tests for the changed lines no test runs (src/a.py:8-9) and the changed lines no test checks (src/a.py:2).`), so the agent's next step is the tests it is missing.

### `gate_fast`

Runs [`sdetkit gate fast`](gate-action.md) (the repository's lint, format, types and tests) and returns the verdict (`SHIP`, `REVIEW`, `NOT_RUN`, `NO_SHIP`), its reasons, the first failure with the command to run next, and the failed steps. `only` limits it to some steps, such as `ruff,pytest`.

### `doctor`

Runs [`sdetkit doctor`](doctor.md) to inspect repository health, environment, dependencies, configuration, and release readiness. It returns a health score, judgment summary, failed checks, recommendations, and prescriptive remediation next actions.

| Argument | What it does |
| --- | --- |
| `repo_root` | Repository to check (default: the server's working directory) |
| `release` | Run release-specific metadata and clean-tree validation |
| `repo` | Validate gate scripts, templates, and pre-commit hooks |
| `ci` | Verify CI workflows and security governance files |
| `deps` | Validate dependency consistency |
| `ascii` | Verify pure ASCII source files under `src/` and `tools/` |

### `diagnose_failure`

Runs [`sdetkit investigate failure`](adaptive-diagnosis.md) to inspect error logs, stack traces, and test failures using SDETKit's adaptive diagnosis cortex. It returns failure classification, root-cause summary, confidence level, reproduction commands, and prioritized next actions.

| Argument | What it does |
| --- | --- |
| `repo_root` | Repository to check (default: the server's working directory) |
| `log_text` | Raw text of a traceback, test failure, or CI log |
| `log_path` | Path to a text log file to diagnose (alternative to `log_text`) |

The tool outputs structured JSON and formatted markdown with reproduction commands and next actions, enabling coding agents to isolate and fix failing tests.

### `run_mutation`

Runs [`sdetkit verify mutation`](verify-change.md#changed-lines-no-test-checks) to synthesize mutants (altering operators and constants) across target source files or working-tree changes. Tests run against each mutant, proving whether the test suite actually asserts the code's behavior. Surviving mutants return line numbers, code diffs, and prescriptive test-writing hints.

| Argument | What it does |
| --- | --- |
| `repo_root` | Repository to check (default: the server's working directory) |
| `path` | Path to a source file or directory to mutate. If omitted, mutates working tree changes |
| `pytest_args` | Arguments for pytest, such as specific test paths |
| `max_mutants` | Maximum number of mutants to synthesize and test (default 20, max 200) |
| `min_mutation_score` | Required mutation score percentage (default 0: report only) |
| `max_mutation_seconds` | Time budget in seconds for mutation testing |

The tool outputs structured JSON and formatted markdown with killed vs surviving counts and exact test hints.

### `auto_fix`

Runs `sdetkit auto-fix` to diagnose failure logs or the current working tree for safe mechanical issues (such as `PRE_COMMIT_FORMAT_DRIFT` or `RUFF_FIXABLE_LINT`), plan safe remediation, and optionally apply fixes with proof verification.

| Argument | What it does |
| --- | --- |
| `repo_root` | Repository to check (default: the server's working directory) |
| `log_text` | Raw error log or traceback text to diagnose and fix |
| `log_path` | Path to a saved failure log file to diagnose and fix |
| `apply` | Whether to apply the verified safe fix (`true`) or dry-run preview (`false`, default) |

The tool safely separates deterministic mechanical errors (which can be auto-remediated via standard formatting tools) from logic errors (such as assertion failures, division by zero, or syntax errors), which are marked as requiring human review and blocked from auto-applying.

### `hunt_flakes`

Runs `sdetkit verify flake` to stress-test target tests over multiple randomized iterations, proving non-determinism, computing flake rates, and capturing execution duration variance and timing anomalies.

| Argument | What it does |
| --- | --- |
| `repo_root` | Repository to check (default: the server's working directory) |
| `target` | Target test file or test ID (e.g. `tests/test_api.py::test_case`) |
| `runs` | Number of test iterations to execute (2-100, default 5) |
| `shuffle` | Whether to randomize hash seeds and execution order (default: `true`) |
| `max_seconds` | Maximum total runtime budget in seconds for flake hunting |

The tool returns a verdict (`deterministic`, `flaky`, or `broken`), flake rate percentage, duration statistics (min, max, mean, stddev), identified flaky test IDs, and classified root causes (`TIMING_RACE`, `STATE_POLLUTION`, `UNKNOWN`).

## What to tell the agent

The server's instructions already ask agents to call `verify_change` before committing. To make it a rule, add a line to the agent's instructions file (`CLAUDE.md`, `AGENTS.md`):

```markdown
Before you commit or open a pull request, call the sdetkit `verify_change` tool and do not
proceed unless it reports VERIFIED, or explain each REVIEW finding. On FAILED, fix the
tests it lists under failures and call it again.
```

## Boundaries

- The tools run the repository's own tests and tools, as the agent's own commands would. Each runs in a subprocess, so nothing they print reaches the protocol stream.
- Nothing is committed, pushed, applied or merged. A tool call can take as long as the test suite; `--timeout-seconds` (default 1800) caps it.
