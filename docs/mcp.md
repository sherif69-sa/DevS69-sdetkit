# Coding agents (MCP)

`sdetkit mcp` serves SDETKit to coding agents over the [Model Context Protocol](https://modelcontextprotocol.io/), so an agent can check its own work before it commits or opens a pull request: did the change pass the repository's tests, without weakening them?

It is a stdio server with eighteen tools (`verify_change`, `gate_fast`, `doctor`, `diagnose_failure`, `run_mutation`, `auto_fix`, `hunt_flakes`, `select_impacted_tests`, `manage_test_quarantine`, `evaluate_blast_radius`, `heal_workspace`, `inject_chaos`, `shard_test_suite`, `query_reliability_trends`, `classify_flake_risk`, `run_polyglot_tests`, `profile_performance_regression`, `audit_supply_chain_provenance`) and no extra dependencies.

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
| `rules` | Array of rules to apply: `all`, `format`, `imports`, `unused_imports`, `whitespace`, `lint` |
| `diff` | Whether to compute and include unified diff of proposed changes (`true` or `false`, default `false`) |

The tool safely separates deterministic mechanical errors (which can be auto-remediated via standard formatting and linting tools) from logic errors (such as assertion failures, division by zero, or syntax errors), which are marked as requiring human review and blocked from auto-applying. An AST syntax preservation guard automatically takes pre-fix snapshots and reverts changes if syntax integrity is broken.

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

### `select_impacted_tests`

Runs `sdetkit verify impact` to analyze changed files using AST dependency graph traversal. It selects the minimal set of directly and transitively impacted tests, allowing agents and developers to bypass unimpacted test files and drastically accelerate verification cycles.

| Argument | What it does |
| --- | --- |
| `repo_root` | Repository to check (default: the server's working directory) |
| `files` | Array of specific changed file paths to analyze (default: auto-detects uncommitted git changes) |
| `base` | Git base reference to diff against (e.g. `main`, `HEAD~1`) |
| `run` | Whether to execute the selected impacted tests immediately (`true` or `false`, default `false`) |

The tool outputs structured JSON and formatted markdown reporting changed files, directly impacted tests, transitively impacted tests, reduction percentage (e.g. 98% skipped), and the recommended exact `pytest` command.

### `manage_test_quarantine`

Runs `sdetkit quarantine` to isolate flaky or failing tests from blocking the main CI build. Manages quarantine TTL expirations, audits repository manifest integrity against deleted or renamed tests, emits drop-in pytest exclusion filters, executes shadow runs, and graduates stabilized tests.

| Argument | What it does |
| --- | --- |
| `action` | Required action: `add`, `list`, `audit`, `filter`, `shadow_run`, or `graduate` |
| `test_id` | Test node ID (e.g. `tests/test_api.py::test_case`) for `add` and `graduate` actions |
| `reason` | Description of why the test was quarantined |
| `ttl_days` | Time-to-live in days before quarantine expiration (default: `7`) |
| `owner` | Responsible engineer or team handle |
| `issue_url` | Tracking issue URL |
| `runs` | Number of verification iterations required to graduate (default: `10`) |
| `manifest_path` | Custom path to quarantine manifest JSON |

### `evaluate_blast_radius`

Runs `sdetkit blast-radius` to evaluate the architectural blast radius and fan-out risk of code changes using AST dependency graph reachability. It scores risk from 0 to 100%, measures transitive repository footprint, detects critical infrastructure and public surface exposure, and prescribes the optimal verification strategy.

| Argument | What it does |
| --- | --- |
| `repo_root` | Repository to check (default: the server's working directory) |
| `files` | Array of specific changed file paths to analyze (default: auto-detects uncommitted git changes) |
| `base` | Git base reference to diff against (e.g. `main`, `HEAD~1`) |

The tool outputs structured JSON and formatted markdown reporting the blast radius index, risk tier (`LOW`, `MEDIUM`, `HIGH`, `CRITICAL`), transitive reach, test defense density, and recommended verification command.

### `heal_workspace`

Runs `sdetkit heal` to autonomously diagnose errors, apply verified AST-guarded mechanical fixes (formatting drift, ruff lint), isolate proven flaky tests into quarantine, and run impact-guided verification tests to restore repository health.

| Argument | What it does |
| --- | --- |
| `repo_root` | Repository to check (default: the server's working directory) |
| `apply` | Whether to apply verified fixes and quarantine (`true` or `false`, default `false` / preview) |
| `verify` | Whether to run impacted test verification post-heal (`true` or `false`, default `true`) |
| `target_test` | Optional test ID to evaluate for flakiness and auto-quarantine |
| `log_text` | Raw error log or traceback to diagnose and heal |

The tool outputs structured JSON and formatted markdown reporting the healing status, actions taken, modified files, quarantine decisions, and verification proof.

### `inject_chaos`

Runs `sdetkit chaos` to stress-test target tests or test suites under controlled runtime chaos (latency jitter, microsecond thread preemption races, synthetic memory constraints, or transient socket resets) to expose concurrency race conditions and environmental flakiness before shipping.

| Argument | What it does |
| --- | --- |
| `repo_root` | Repository to check (default: the server's working directory) |
| `target` | Target test ID, file, or path to execute under chaos (default: all tests) |
| `profile` | Preset profile: `combined`, `latency`, `race`, `memory`, or `transient_error` (default: `combined`) |
| `latency_ms` | Latency delay in milliseconds injected into sleep and socket ops (default: `50`) |
| `jitter_ms` | Variance in milliseconds applied to latency (default: `25`) |
| `switch_interval_us` | Thread switch interval in microseconds to force aggressive thread interleaving (default: `10`) |
| `memory_mb` | Synthetic memory buffer overhead in megabytes (default: `0`) |
| `fault_rate` | Transient fault injection rate between `0.0` and `1.0` (default: `0.0`) |
| `runs` | Number of chaos iterations to execute (default: `3`) |

The tool outputs structured JSON and formatted markdown reporting resilience score, duration overhead, detected failure modes, and hardening recommendations.

### `shard_test_suite`

Runs `sdetkit shard` to partition test suites across parallel CI worker nodes using Longest Processing Time (LPT) duration-weighted balancing to eliminate straggler jobs and maximize throughput, with optional AST subtree cryptographic caching to skip unimpacted tests.

| Argument | What it does |
| --- | --- |
| `repo_root` | Repository to check (default: the server's working directory) |
| `nodes` | Total number of parallel worker nodes (default: `4`) |
| `index` | Target worker node index to allocate and query (`0` to `nodes-1`, default: `0`) |
| `use_cache` | Whether to enable AST subtree cryptographic caching to skip unimpacted tests (default: `false`) |
| `test_files` | Optional explicit array of test file paths to partition |

The tool outputs structured JSON and formatted markdown reporting cluster parallelism, balance efficiency percentage, duration benchmarks, and the exact `pytest` command for the selected worker node.

### `query_reliability_trends`

Runs `sdetkit trend` to query release reliability velocity indices (RVI), flake reduction, mutation score trajectories, quarantine graduation health, and quality drift trends over time.

| Argument | What it does |
| --- | --- |
| `repo_root` | Repository to check (default: the server's working directory) |
| `days` | Lookback window in days (default: `30`) |
| `metric` | Specific metric trajectory to isolate: `all`, `health`, `mutation`, `quarantine`, `rvi` (default: `all`) |

The tool outputs structured JSON and formatted markdown reporting the Reliability Velocity Index (0-100), trajectory direction (`IMPROVING`, `STABLE`, `DEGRADING`), and detailed metric delta breakdown.

### `classify_flake_risk`

Runs `sdetkit genome` to statically audit test source code or files using AST traversal to detect concurrency races, arbitrary sleeps, unmocked clocks, unseeded random, and global state leaks before execution.

| Argument | What it does |
| --- | --- |
| `repo_root` | Repository to check (default: the server's working directory) |
| `target` | Target test file or directory path to audit (default: `tests/`) |
| `max_risk` | Maximum allowable flake risk score before flagging error (default: `50`) |

The tool outputs structured JSON and formatted markdown reporting the Flake Risk Score (0-100), risk tier (`PRISTINE`, `LOW`, `MODERATE`, `HIGH`, `CRITICAL`), detected markers by line, and prescriptive auto-remediation recipes.

### `run_polyglot_tests`

Runs `sdetkit polyglot` to execute unified multi-language test suites across Python (`pytest`), Go (`go test -json`), JavaScript/TypeScript (`vitest`, `jest`, `node`), and Java (`maven`, `gradle`) projects, normalizing JUnit reports and yielding unified execution verdicts.

| Argument | What it does |
| --- | --- |
| `repo_root` | Repository to check (default: the server's working directory) |
| `target` | Target project directory or test path to run (default: discover from root) |
| `languages` | Optional list of languages to filter, e.g. `['python', 'go', 'javascript', 'java']` |
| `fail_fast` | Stop execution upon first failing project (default: `false`) |
| `timeout` | Timeout in seconds per runner (default: `120`) |

The tool outputs structured JSON and formatted markdown reporting the polyglot matrix results, per-project breakdown, duration, passed/failed counts, and tail diagnostics for failing projects.

### `profile_performance_regression`

Runs `sdetkit perf` to benchmark test execution latency, measure P50/P90/P99 percentiles across multiple iterations, and flag performance regressions against golden baselines.

| Argument | What it does |
| --- | --- |
| `repo_root` | Repository to check (default: the server's working directory) |
| `target` | Target test file, folder, or benchmark script (default: `tests/`) |
| `iterations` | Number of benchmark iterations to execute (default: `3`) |
| `baseline` | Path to golden performance baseline JSON report |
| `max_regression_percent` | Maximum allowable P50 latency increase percentage before error (default: `15.0`) |
| `save_baseline` | Path to save the generated report as a new golden baseline |
| `timeout` | Timeout in seconds per iteration (default: `60`) |

The tool outputs structured JSON and formatted markdown reporting latency distribution (Min, P50, P90, P99, Max, StdDev), delta comparison against baseline, and regression verdicts.

### `audit_supply_chain_provenance`

Runs `sdetkit provenance` to audit multi-ecosystem lockfiles (Python uv/poetry/pip, JavaScript package-lock.json, Go go.sum), enforce copyleft license compliance policies, detect typosquatting attacks and unpinned wildcards, and compute cryptographic SHA256 dependency tree provenance attestations.

| Argument | What it does |
| --- | --- |
| `repo_root` | Repository to check (default: the server's working directory) |
| `policy` | License policy enforcement level: `permissive` (default) or `allow-copyleft` |
| `allow_unpinned` | Allow unpinned dependencies without raising warnings (default: `false`) |

The tool outputs structured JSON and formatted markdown summarizing total dependency pins, permissive vs copyleft license breakdowns, cryptographic whole-tree SHA256 digests, and supply-chain findings.

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
