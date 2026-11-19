"""`sdetkit mcp`: SDETKit as an MCP server, so a coding agent can check its own work.

It speaks the Model Context Protocol over stdio (one JSON-RPC 2.0 message per line) and offers
seventeen tools:

- ``verify_change`` runs ``sdetkit verify change`` on the agent's change: by default the
  uncommitted work in the repository, untracked files included, against HEAD. It answers
  VERIFIED, REVIEW, FAILED or NOT_RUN, with the findings (tests removed, emptied or skipped) and
  which of the change's tests fail without it; for FAILED, why each broken test fails.
- ``gate_fast`` runs ``sdetkit gate fast``: the repository's lint, format, types and tests, with
  one verdict and the first failure.
- ``doctor`` runs ``sdetkit doctor``: repository health, environment, dependencies, configuration,
  and release readiness checks with prescriptive remediation actions.
- ``diagnose_failure`` runs ``sdetkit investigate failure``: analyzes error outputs, tracebacks,
  or test logs using adaptive diagnosis, returning root-cause classification and reproduction commands.
- ``run_mutation`` runs ``sdetkit verify mutation``: synthesizes mutants on source code to detect
  gaps in test assertions, returning mutation score, surviving mutants, and prescriptive test hints.
- ``auto_fix`` runs ``sdetkit auto-fix``: plans and optionally executes verified safe mechanical fixes
  (formatting drift, ruff fixable lint) with automated proof verification.
- ``hunt_flakes`` runs ``sdetkit verify flake``: stress-tests target tests over multiple iterations
  to detect non-determinism, measure execution duration variance, and isolate timing races.
- ``select_impacted_tests`` runs ``sdetkit verify impact``: selects and optionally executes the
  minimal subset of directly and transitively impacted tests using AST dependency graph traversal.
- ``manage_test_quarantine`` runs ``sdetkit quarantine``: isolates flaky tests into TTL-governed
  quarantine, audits manifest integrity, emits pytest exclusion filters, and graduates stable tests.
- ``evaluate_blast_radius`` runs ``sdetkit blast-radius``: computes architectural fan-out,
  critical infrastructure risk, public surface exposure, and test defense density to deliver
  a 0-100% blast radius index and prescriptive release strategy.
- ``heal_workspace`` runs ``sdetkit heal``: autonomously diagnoses errors, applies verified
  AST-guarded mechanical fixes, quarantines proven flakes, and verifies health via impacted tests.
- ``inject_chaos`` runs ``sdetkit chaos``: stress-tests test resilience and exposes concurrency races
  via injected latency, microsecond thread preemption, memory pressure, and socket fault resets.
- ``shard_test_suite`` runs ``sdetkit shard``: partitions tests across parallel workers using
  duration-weighted balancing to eliminate CI stragglers and AST subtree caching.
- ``query_reliability_trends`` runs ``sdetkit trend``: queries release reliability velocity indices (RVI),
  flake reduction, mutation score trajectories, and quality drift trends over time.
- ``classify_flake_risk`` runs ``sdetkit genome``: statically audits test ASTs to detect concurrency
  races, arbitrary sleeps, unmocked clocks, unseeded random, and global state leaks before execution.
- ``run_polyglot_tests`` runs ``sdetkit polyglot``: executes multi-language test suites across
  Python, Go, JavaScript/TypeScript, and Java projects, yielding normalized matrix verdicts.
- ``profile_performance_regression`` runs ``sdetkit perf``: benchmarks execution latency, P50/P90/P99
  percentiles, and flags performance regressions against golden baselines.
- ``audit_supply_chain_provenance`` runs ``sdetkit provenance``: audits multi-ecosystem dependency
  lockfiles (Python, JS, Go), checks copyleft license compliance, flags typosquatting, and computes
  cryptographic SHA256 provenance attestations.

Each tool runs SDETKit in a subprocess, so nothing a check prints can reach the protocol stream.
The tools run the repository's own tests and tools, as the agent's own commands would.
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any, TextIO

from sdetkit.versioning import tool_version

JsonObject = dict[str, Any]

# Newest first. The tools use nothing that changed between these revisions.
PROTOCOL_VERSIONS = ("2025-11-25", "2025-06-18", "2025-03-26", "2024-11-05")
SERVER_NAME = "sdetkit"
DEFAULT_TIMEOUT_SECONDS = 1800

PARSE_ERROR = -32700
INVALID_REQUEST = -32600
METHOD_NOT_FOUND = -32601
INVALID_PARAMS = -32602

_REPO_ROOT = {
    "type": "string",
    "description": "Repository to check (default: the server's working directory).",
}
TOOLS: list[JsonObject] = [
    {
        "name": "verify_change",
        "title": "Verify a change",
        "description": (
            "Run the repository's tests before and after a change in a temporary clone and check "
            "that no test was removed, emptied, skipped or configured away. With no `head` or "
            "`patch`, it verifies the uncommitted work (untracked files included) against HEAD: "
            "call it before you commit or open a pull request. Answers VERIFIED, REVIEW, FAILED "
            "or NOT_RUN, the reasons, which of the change's tests fail without it and, for "
            "FAILED, why each broken test fails, and which changed lines of code no test runs. "
            "The repository's working tree is not modified."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "repo_root": _REPO_ROOT,
                "base": {
                    "type": "string",
                    "description": "Commit the change starts from (with `head` or `patch`).",
                },
                "head": {
                    "type": "string",
                    "description": "Commit or branch holding the change.",
                },
                "pr": {
                    "type": "integer",
                    "minimum": 1,
                    "description": "A GitHub pull request to verify, by number: its head from "
                    "origin, from where it left the default branch (or from `base`).",
                },
                "patch": {
                    "type": "string",
                    "description": "Path of a unified diff to verify on top of `base`.",
                },
                "pytest_args": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Arguments for the test runner, such as test paths.",
                },
                "project": {
                    "type": "string",
                    "description": "Folder of the repository whose tests run, in a repository "
                    "of several projects (web/ with its package.json, svc/ with its go.mod). "
                    "Default: every project the change touches, in one report.",
                },
                "runner": {
                    "type": "string",
                    "enum": [
                        "auto",
                        "pytest",
                        "vitest",
                        "jest",
                        "node",
                        "go",
                        "maven",
                        "gradle",
                    ],
                    "description": "Test runner (default auto: pytest in a Python project, "
                    "otherwise the one package.json uses, otherwise go test with a go.mod, otherwise Maven or Gradle).",
                },
                "network": {
                    "type": "string",
                    "enum": ["allow", "deny"],
                    "description": "deny runs the tests with no network but their own loopback "
                    "(Linux network namespace); use it for code you do not trust yet.",
                },
                "min_changed_coverage": {
                    "type": "number",
                    "minimum": 0,
                    "maximum": 100,
                    "description": "Percentage of the changed lines of code the tests must run "
                    "(pytest, go test, jest, vitest, node --test, Maven, Gradle); below it the status "
                    "is REVIEW. "
                    "Default 0: only reported.",
                },
                "mutate": {
                    "type": "boolean",
                    "description": "Also alter the changed lines the tests run, one operator or "
                    "constant at a time, and run the tests on each: a mutant every test passes "
                    "with is a changed line no test checks. Each mutant runs the tests again.",
                },
                "max_mutation_seconds": {
                    "type": "number",
                    "exclusiveMinimum": 0,
                    "description": "Start no further mutant after this many seconds (default: "
                    "no limit); the result says how many did not run.",
                },
                "max_mutants": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": 200,
                    "description": "At most this many mutants (default 20).",
                },
                "min_mutation_score": {
                    "type": "number",
                    "minimum": 0,
                    "maximum": 100,
                    "description": "Percentage of the mutants the tests must catch; below it "
                    "the status is REVIEW. Setting it turns `mutate` on. Default 0: only reported.",
                },
            },
            "additionalProperties": False,
        },
    },
    {
        "name": "gate_fast",
        "title": "Run the fast quality gate",
        "description": (
            "Run the repository's own checks (ruff, mypy, pytest, and other test suites it "
            "configures) and return one verdict (SHIP, REVIEW, NOT_RUN or NO_SHIP), the first "
            "failure and the command to run next."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "repo_root": _REPO_ROOT,
                "only": {
                    "type": "string",
                    "description": "Comma-separated steps to run, for example `ruff,pytest`.",
                },
            },
            "additionalProperties": False,
        },
    },
    {
        "name": "doctor",
        "title": "Run repository health and readiness checks",
        "description": (
            "Run SDETKit repository doctor checks: inspect environment, dependencies, "
            "configuration, security files, and repo readiness. Returns a health score, "
            "judgment summary, failed checks, recommendations, and prescriptive next actions."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "repo_root": _REPO_ROOT,
                "release": {
                    "type": "boolean",
                    "description": "Run release-specific metadata and clean-tree validation.",
                },
                "repo": {
                    "type": "boolean",
                    "description": "Validate gate scripts, templates, and pre-commit hooks.",
                },
                "ci": {
                    "type": "boolean",
                    "description": "Verify CI workflows and security governance files.",
                },
                "deps": {
                    "type": "boolean",
                    "description": "Validate dependency consistency.",
                },
                "ascii": {
                    "type": "boolean",
                    "description": "Verify pure ASCII source files under src/ and tools/.",
                },
            },
            "additionalProperties": False,
        },
    },
    {
        "name": "diagnose_failure",
        "title": "Diagnose failure logs with adaptive test intelligence",
        "description": (
            "Analyze test failure outputs, tracebacks, or CI logs using SDETKit's adaptive "
            "diagnosis cortex. Returns classified failure signals, root-cause summary, "
            "proof reproduction commands, and a prioritized remediation plan."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "repo_root": _REPO_ROOT,
                "log_text": {
                    "type": "string",
                    "description": "Raw test failure text or traceback to diagnose.",
                },
                "log_path": {
                    "type": "string",
                    "description": "Path to a text log file to diagnose (alternative to `log_text`).",
                },
            },
            "additionalProperties": False,
        },
    },
    {
        "name": "run_mutation",
        "title": "Run mutation testing on source code to find gaps in test assertions",
        "description": (
            "Synthesize mutants (altering comparison, arithmetic, logic, boolean, negation, "
            "and return operators) on target files or working tree changes, run tests against "
            "each mutant, and report mutation score, surviving mutants, and prescriptive test hints."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "repo_root": _REPO_ROOT,
                "path": {
                    "type": "string",
                    "description": (
                        "Path to a file or folder to mutate. If omitted, mutates working tree change."
                    ),
                },
                "pytest_args": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Arguments for pytest, such as specific test file paths.",
                },
                "max_mutants": {
                    "type": "integer",
                    "description": "Maximum number of mutants to synthesize and test (1-200, default 20).",
                },
                "min_mutation_score": {
                    "type": "integer",
                    "description": "Required mutation score percentage (0-100, default 0).",
                },
                "max_mutation_seconds": {
                    "type": "number",
                    "description": "Maximum runtime budget in seconds for mutation testing.",
                },
            },
            "additionalProperties": False,
        },
    },
    {
        "name": "auto_fix",
        "title": "Automatically remediate safe mechanical issues (format drift, fixable lint)",
        "description": (
            "Diagnose failure logs or the working tree for safe mechanical issues "
            "(PRE_COMMIT_FORMAT_DRIFT, RUFF_FIXABLE_LINT), plan safe remediation, "
            "and optionally apply fixes with proof verification."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "repo_root": {
                    "type": "string",
                    "description": "Root directory of the repository (default: current workspace).",
                },
                "log_text": {
                    "type": "string",
                    "description": "Raw error log or traceback text to diagnose and fix.",
                },
                "log_path": {
                    "type": "string",
                    "description": "Relative path to a saved failure log file.",
                },
                "apply": {
                    "type": "boolean",
                    "description": "Whether to apply the verified safe fix (default: false / dry-run preview).",
                },
                "rules": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": (
                        "Specific remediation rules to apply: 'all', 'format', 'imports', "
                        "'unused_imports', 'whitespace', 'lint'."
                    ),
                },
                "diff": {
                    "type": "boolean",
                    "description": "Whether to include unified diff of changes in output (default: false).",
                },
            },
            "additionalProperties": False,
        },
    },
    {
        "name": "hunt_flakes",
        "title": "Hunt flaky tests, prove test non-determinism, and measure duration variance",
        "description": (
            "Stress-test target tests over multiple randomized iterations to mathematically "
            "detect and prove test non-determinism (flake rate), timing races, and state pollution."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "repo_root": _REPO_ROOT,
                "target": {
                    "type": "string",
                    "description": "Target test file or test ID (e.g. tests/test_api.py::test_case).",
                },
                "runs": {
                    "type": "integer",
                    "description": "Number of test iterations to execute (2-100, default 5).",
                },
                "shuffle": {
                    "type": "boolean",
                    "description": "Whether to randomize hash seeds and execution order (default: true).",
                },
                "max_seconds": {
                    "type": "number",
                    "description": "Maximum total runtime budget in seconds for flake hunting.",
                },
            },
            "additionalProperties": False,
        },
    },
    {
        "name": "select_impacted_tests",
        "title": "Predict and select impacted tests via AST dependency graph traversal",
        "description": (
            "Analyze code changes or working tree diffs using AST dependency graph "
            "traversal to select the minimal set of directly and transitively impacted "
            "tests, skipping unimpacted tests to drastically accelerate verification."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "repo_root": _REPO_ROOT,
                "files": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Specific changed file paths to analyze (default: detects uncommitted git changes).",
                },
                "base": {
                    "type": "string",
                    "description": "Git base reference to diff against (e.g. main, HEAD~1).",
                },
                "run": {
                    "type": "boolean",
                    "description": "Whether to execute the selected impacted tests immediately (default: false).",
                },
            },
            "additionalProperties": False,
        },
    },
    {
        "name": "manage_test_quarantine",
        "title": "Manage test quarantine, TTL expirations, shadow test runs, and flake graduation",
        "description": (
            "Isolate non-deterministic flaky tests into a policy-governed quarantine manifest, "
            "generate pytest exclusion filters, audit quarantine health and TTL expirations, "
            "execute shadow runs without blocking CI, and graduate stabilized tests after verification."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "repo_root": _REPO_ROOT,
                "action": {
                    "type": "string",
                    "enum": [
                        "add",
                        "list",
                        "audit",
                        "filter",
                        "shadow_run",
                        "graduate",
                    ],
                    "description": "Quarantine action: add, list, audit, filter, shadow_run, or graduate.",
                },
                "test_id": {
                    "type": "string",
                    "description": "Test ID (e.g. tests/test_api.py::test_case) for add or graduate actions.",
                },
                "reason": {
                    "type": "string",
                    "description": "Reason for quarantining the test.",
                },
                "ttl_days": {
                    "type": "integer",
                    "description": "Time-to-live in days before quarantine expires (default: 7).",
                },
                "owner": {
                    "type": "string",
                    "description": "Responsible engineer or team handle.",
                },
                "issue_url": {
                    "type": "string",
                    "description": "Tracking bug/issue URL.",
                },
                "classification": {
                    "type": "string",
                    "description": "Failure cause classification (e.g. TIMING_RACE, STATE_POLLUTION).",
                },
                "mode": {
                    "type": "string",
                    "enum": ["k", "ignore"],
                    "description": "Pytest exclusion mode for filter action (default: k).",
                },
                "runs": {
                    "type": "integer",
                    "description": "Number of consecutive iterations required for graduation (default: 10).",
                },
                "manifest_path": {
                    "type": "string",
                    "description": "Custom path to quarantine manifest JSON.",
                },
            },
            "required": ["action"],
            "additionalProperties": False,
        },
    },
    {
        "name": "evaluate_blast_radius",
        "title": "Score architectural blast radius, fan-out risk, and test strategy",
        "description": (
            "Analyze code changes or working tree diffs using AST dependency graph "
            "reachability to score architectural blast radius, measure transitive fan-out, "
            "detect critical infrastructure modifications, and prescribe the optimal verification strategy."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "repo_root": _REPO_ROOT,
                "files": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Specific changed file paths to analyze (default: detects uncommitted git changes).",
                },
                "base": {
                    "type": "string",
                    "description": "Git base reference to diff against (e.g. main, HEAD~1).",
                },
            },
            "additionalProperties": False,
        },
    },
    {
        "name": "heal_workspace",
        "title": "Autonomously heal workspace errors, apply mechanical fixes, and quarantine flakes",
        "description": (
            "Diagnose workspace failures or error logs, apply verified AST-guarded mechanical fixes "
            "(format drift, ruff lint), isolate proven flaky tests into quarantine, and run "
            "impact-guided verification tests to restore repository to a clean SHIP state."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "repo_root": _REPO_ROOT,
                "apply": {
                    "type": "boolean",
                    "description": "Whether to apply verified fixes and quarantine (default: false / preview).",
                },
                "verify": {
                    "type": "boolean",
                    "description": "Whether to run impacted test verification post-heal (default: true).",
                },
                "target_test": {
                    "type": "string",
                    "description": "Optional test ID to evaluate for flakiness and auto-quarantine.",
                },
                "log_text": {
                    "type": "string",
                    "description": "Raw error log or traceback to diagnose and heal.",
                },
            },
            "additionalProperties": False,
        },
    },
    {
        "name": "inject_chaos",
        "title": "Inject runtime chaos to stress-test resilience and concurrency races",
        "description": (
            "Stress-test target tests or test suites under controlled runtime chaos (latency jitter, "
            "extreme thread preemption races, synthetic memory constraints, or transient socket resets) "
            "to expose concurrency race conditions and environmental flakiness before shipping."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "repo_root": _REPO_ROOT,
                "target": {
                    "type": "string",
                    "description": "Target test ID, file, or path to execute under chaos (default: all tests).",
                },
                "profile": {
                    "type": "string",
                    "enum": [
                        "combined",
                        "latency",
                        "race",
                        "memory",
                        "transient_error",
                    ],
                    "description": "Chaos injection profile preset (default: combined).",
                },
                "latency_ms": {
                    "type": "integer",
                    "description": "Latency delay in milliseconds injected into sleep and socket ops (default: 50).",
                },
                "jitter_ms": {
                    "type": "integer",
                    "description": "Variance in milliseconds applied to latency (default: 25).",
                },
                "switch_interval_us": {
                    "type": "integer",
                    "description": "Thread switch interval in microseconds to force thread interleaving (default: 10).",
                },
                "memory_mb": {
                    "type": "integer",
                    "description": "Synthetic memory buffer overhead in megabytes (default: 0).",
                },
                "fault_rate": {
                    "type": "number",
                    "description": "Transient fault injection rate between 0.0 and 1.0 (default: 0.0).",
                },
                "runs": {
                    "type": "integer",
                    "description": "Number of chaos iterations to execute (default: 3).",
                },
            },
            "additionalProperties": False,
        },
    },
    {
        "name": "shard_test_suite",
        "title": "Partition test suite across parallel nodes using duration-weighted balancing and caching",
        "description": (
            "Partition test suites across parallel CI worker nodes using Longest Processing Time (LPT) "
            "duration-weighted balancing to eliminate straggler jobs and maximize throughput, with optional "
            "AST subtree cryptographic caching to skip unimpacted tests."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "repo_root": _REPO_ROOT,
                "nodes": {
                    "type": "integer",
                    "description": "Total number of parallel worker nodes (default: 4).",
                },
                "index": {
                    "type": "integer",
                    "description": "Target worker node index to allocate and query (0 to nodes-1, default: 0).",
                },
                "use_cache": {
                    "type": "boolean",
                    "description": "Whether to enable AST subtree cryptographic caching to skip unimpacted tests (default: false).",
                },
                "test_files": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Optional explicit subset of test files to partition.",
                },
            },
            "additionalProperties": False,
        },
    },
    {
        "name": "query_reliability_trends",
        "title": "Query release reliability velocity indices, drift trajectories, and telemetry trends",
        "description": (
            "Query release reliability velocity indices (RVI), flake reduction, "
            "mutation score trajectories, quarantine graduation health, and quality drift trends over time."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "repo_root": _REPO_ROOT,
                "days": {
                    "type": "integer",
                    "description": "Lookback window in days (default: 30).",
                },
                "metric": {
                    "type": "string",
                    "enum": ["all", "health", "mutation", "quarantine", "rvi"],
                    "description": "Specific metric trajectory to isolate (default: all).",
                },
            },
            "additionalProperties": False,
        },
    },
    {
        "name": "classify_flake_risk",
        "title": "Statically classify test flakiness risk, anti-patterns, and concurrency smells via AST analysis",
        "description": (
            "Statically audit test source code or files using AST traversal to detect concurrency races, "
            "arbitrary sleeps, unmocked clocks, unseeded random, and global state leaks before execution."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "repo_root": _REPO_ROOT,
                "target": {
                    "type": "string",
                    "description": "Target test file or directory path to audit (default: tests/).",
                },
                "max_risk": {
                    "type": "integer",
                    "description": "Maximum allowable flake risk score before flagging error (default: 50).",
                },
            },
            "additionalProperties": False,
        },
    },
    {
        "name": "run_polyglot_tests",
        "title": "Execute multi-language test suites across Python, Go, JS/TS, and Java projects",
        "description": (
            "Execute multi-language test runner matrix across Python, Go, JavaScript/TypeScript, "
            "and Java projects, normalizing JUnit reports and yielding unified execution verdicts."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "repo_root": _REPO_ROOT,
                "target": {
                    "type": "string",
                    "description": "Target project directory or test path to run (default: discover from root).",
                },
                "languages": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Optional list of languages to filter (e.g. ['python', 'go', 'javascript', 'java']).",
                },
                "fail_fast": {
                    "type": "boolean",
                    "description": "Stop execution upon first failing project (default: false).",
                },
                "timeout": {
                    "type": "integer",
                    "description": "Timeout in seconds per runner (default: 120).",
                },
            },
            "additionalProperties": False,
        },
    },
    {
        "name": "profile_performance_regression",
        "title": "Profile execution latency, P50/P90/P99 percentiles, and performance regressions",
        "description": (
            "Benchmark test execution latency and percentiles across multiple iterations, "
            "detect performance regressions against golden baselines, and isolate runtime bottlenecks."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "repo_root": _REPO_ROOT,
                "target": {
                    "type": "string",
                    "description": "Target test file, folder, or benchmark script (default: tests/).",
                },
                "iterations": {
                    "type": "integer",
                    "description": "Number of benchmark iterations to run (default: 3).",
                },
                "baseline": {
                    "type": "string",
                    "description": "Optional path to golden performance baseline JSON report.",
                },
                "max_regression_percent": {
                    "type": "number",
                    "description": "Maximum allowable P50 latency increase percentage before error (default: 15.0).",
                },
                "save_baseline": {
                    "type": "string",
                    "description": "Optional path to save current profile as new golden baseline.",
                },
                "timeout": {
                    "type": "integer",
                    "description": "Timeout in seconds per iteration (default: 60).",
                },
            },
            "additionalProperties": False,
        },
    },
    {
        "name": "audit_supply_chain_provenance",
        "title": "Audit supply-chain lockfiles, license compliance, and provenance attestations",
        "description": (
            "Audit multi-ecosystem dependency lockfiles (Python uv/poetry/pip, JS package-lock, Go go.sum), "
            "enforce copyleft license compliance policies, detect unpinned wildcards and typosquatting attacks, "
            "and compute cryptographic SHA256 dependency tree provenance attestations."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "repo_root": _REPO_ROOT,
                "policy": {
                    "type": "string",
                    "enum": ["permissive", "allow-copyleft"],
                    "description": "License policy enforcement level (default: permissive).",
                },
                "allow_unpinned": {
                    "type": "boolean",
                    "description": "Allow unpinned dependencies without raising warnings (default: false).",
                },
            },
            "additionalProperties": False,
        },
    },
]


class ToolError(ValueError):
    """Arguments a tool cannot run with."""


def _sdetkit(args: list[str], *, cwd: Path, timeout: int) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "sdetkit", *args],
        cwd=cwd,
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
        shell=False,
    )


def _repo_root(arguments: Mapping[str, Any], cwd: Path) -> Path:
    root = (cwd / str(arguments.get("repo_root") or ".")).resolve()
    if not root.is_dir():
        raise ToolError(f"repo_root is not a directory: {root}")
    return root


def _strings(arguments: Mapping[str, Any], key: str) -> list[str]:
    value = arguments.get(key) or []
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise ToolError(f"{key} must be a list of strings")
    return value


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8") if path.is_file() else ""


def _percent(value: Any, name: str = "min_changed_coverage") -> float:
    if value is None:
        return 0.0
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not 0 <= value <= 100:
        raise ToolError(f"{name} must be a number from 0 to 100")
    return float(value)


def _mutation_args(arguments: Mapping[str, Any]) -> list[str]:
    mutate = arguments.get("mutate")
    if mutate is not None and not isinstance(mutate, bool):
        raise ToolError("mutate must be true or false")
    limit = arguments.get("max_mutants")
    if limit is not None and (
        isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 200
    ):
        raise ToolError("max_mutants must be a whole number from 1 to 200")
    score = _percent(arguments.get("min_mutation_score"), "min_mutation_score")
    seconds = arguments.get("max_mutation_seconds")
    if seconds is not None and (
        isinstance(seconds, bool) or not isinstance(seconds, (int, float)) or seconds <= 0
    ):
        raise ToolError("max_mutation_seconds must be a number above 0")
    return [
        *(["--mutate"] if mutate else []),
        *(["--max-mutants", str(limit)] if limit is not None else []),
        *(["--max-mutation-seconds", str(seconds)] if seconds is not None else []),
        *(["--min-mutation-score", str(score)] if score else []),
    ]


def _mutation(mutation: Mapping[str, Any] | None) -> JsonObject | None:
    """The mutants an agent acts on: the score, and the changed lines no test checks."""

    if not mutation:
        return None
    return {
        "ran": bool(mutation.get("ran")),
        "score": mutation.get("score"),
        "survived": [
            {key: item.get(key, "") for key in ("path", "line", "before", "after", "hint")}
            for item in mutation.get("mutants", [])
            if item["outcome"] == "survived"
        ],
        "reason": mutation.get("reason", ""),
    }


def _changed_lines(coverage: Mapping[str, Any]) -> JsonObject:
    """The changed-line coverage an agent acts on: the share, and the lines no test runs."""

    return {
        "measured": bool(coverage.get("measured")),
        "percent": coverage.get("percent"),
        "not_run": {
            item["path"]: item["not_run"] for item in coverage.get("files", []) if item["not_run"]
        },
        "reason": coverage.get("reason", ""),
    }


def verify_change_tool(arguments: Mapping[str, Any], *, cwd: Path, timeout: int) -> JsonObject:
    root = _repo_root(arguments, cwd)
    head, patch, base = (str(arguments.get(key) or "") for key in ("head", "patch", "base"))
    pr = arguments.get("pr")
    if pr is not None and (isinstance(pr, bool) or not isinstance(pr, int) or pr < 1):
        raise ToolError("pr must be a pull request number")
    if sum(bool(value) for value in (head, patch, pr)) > 1:
        raise ToolError("give one of `head`, `patch` or `pr`")
    if base and not (head or patch or pr):
        raise ToolError(
            "`base` needs `head`, `patch` or `pr`; without them the uncommitted work is used"
        )
    with tempfile.TemporaryDirectory(prefix="sdetkit-mcp-") as temp_dir:
        out = Path(temp_dir)
        source = (
            ["--head", head]
            if head
            else (["--patch", patch] if patch else ["--pr", str(pr)] if pr else ["--working-tree"])
        )
        args = [
            "verify",
            "change",
            *source,
            *(["--base", base] if base else []),
            "--runner",
            str(arguments.get("runner") or "auto"),
            *(["--project", str(arguments["project"])] if arguments.get("project") else []),
            "--network",
            str(arguments.get("network") or "allow"),
            "--min-changed-coverage",
            str(_percent(arguments.get("min_changed_coverage"))),
            *_mutation_args(arguments),
            "--repo-root",
            str(root),
            "--out-dir",
            str(out / "report"),
            "--summary-out",
            str(out / "summary.md"),
            "--format",
            "json",
            "--",
            *_strings(arguments, "pytest_args"),
        ]
        completed = _sdetkit(args, cwd=root, timeout=timeout)
        summary = _read(out / "summary.md").strip()
        try:
            report = json.loads(completed.stdout)
        except ValueError:
            report = {}
    status = str(report.get("status") or "NOT_RUN")
    text = summary or completed.stderr.strip() or f"sdetkit exited with {completed.returncode}"
    return {
        "text": text,
        "structured": {
            "status": status,
            "verdict": (report.get("verdict") or {}).get("decision", "NOT_RUN"),
            "reasons": report.get("reasons", [completed.stderr.strip()] if not report else []),
            "next_action": report.get("next_action", ""),
            "projects": [
                {key: item.get(key) for key in ("project", "runner", "status", "reasons")}
                for item in report.get("projects") or []
            ],
            "proving_tests": ((report.get("tests") or {}).get("proof") or {}).get("proving", []),
            "findings": [finding.get("code") for finding in report.get("findings", [])],
            "failures": (report.get("tests") or {}).get("failures", {}),
            "changed_lines": _changed_lines(report.get("changed_coverage") or {}),
            "mutation": _mutation(report.get("mutation")),
        },
        "error": not report,
    }


def gate_fast_tool(arguments: Mapping[str, Any], *, cwd: Path, timeout: int) -> JsonObject:
    root = _repo_root(arguments, cwd)
    only = str(arguments.get("only") or "")
    with tempfile.TemporaryDirectory(prefix="sdetkit-mcp-") as temp_dir:
        out = Path(temp_dir)
        args = [
            "gate",
            "fast",
            "--root",
            str(root),
            "--format",
            "json",
            "--out",
            str(out / "gate-fast.json"),
            "--summary-out",
            str(out / "summary.md"),
            *(["--only", only] if only else []),
        ]
        completed = _sdetkit(args, cwd=root, timeout=timeout)
        summary = _read(out / "summary.md").strip()
        try:
            payload = json.loads(_read(out / "gate-fast.json") or "{}")
        except ValueError:
            payload = {}
    verdict = payload.get("verdict") or {}
    text = summary or completed.stderr.strip() or f"sdetkit exited with {completed.returncode}"
    return {
        "text": text,
        "structured": {
            "verdict": verdict.get("decision", "NOT_RUN"),
            "reasons": verdict.get("reasons", []),
            "next_action": payload.get("next_action", {}),
            "failed_steps": payload.get("failed_steps", []),
        },
        "error": not payload,
    }


def doctor_tool(arguments: Mapping[str, Any], *, cwd: Path, timeout: int) -> JsonObject:
    root = _repo_root(arguments, cwd)
    for flag in ("release", "repo", "ci", "deps", "ascii"):
        val = arguments.get(flag)
        if val is not None and not isinstance(val, bool):
            raise ToolError(f"{flag} must be true or false")
    with tempfile.TemporaryDirectory(prefix="sdetkit-mcp-") as temp_dir:
        out = Path(temp_dir)
        json_out = out / "doctor.json"
        args = [
            "doctor",
            "--format",
            "json",
            "--out",
            str(json_out),
            *(["--release"] if arguments.get("release") else []),
            *(["--repo"] if arguments.get("repo") else []),
            *(["--ci"] if arguments.get("ci") else []),
            *(["--deps"] if arguments.get("deps") else []),
            *(["--ascii"] if arguments.get("ascii") else []),
        ]
        completed = _sdetkit(args, cwd=root, timeout=timeout)
        try:
            payload = json.loads(_read(json_out) or completed.stdout or "{}")
        except ValueError:
            payload = {}
    ok = bool(payload.get("ok"))
    score = payload.get("score")
    judgment = payload.get("judgment") or {}
    next_action = payload.get("next_action") or {}
    failed_checks = (payload.get("quality") or {}).get("failed_check_ids", [])
    status_label = "PASS" if ok else "FAIL"
    text = (
        f"### SDETKit doctor: {status_label} (score: {score}%)\n\n"
        f"**Judgment**: {judgment.get('summary', 'No summary')}\n"
        f"**Next move**: {(judgment.get('top_judgment') or {}).get('next_move', 'No immediate action required.')}\n"
    )
    if failed_checks:
        text += f"\n**Failed checks**: {', '.join(failed_checks)}\n"
    if next_action.get("next_command"):
        text += f"**Next command**: `{next_action['next_command']}`\n"
    if completed.stderr.strip():
        text += f"\n```\n{completed.stderr.strip()}\n```"
    return {
        "text": text.strip(),
        "structured": {
            "ok": ok,
            "score": score,
            "failed_checks": failed_checks,
            "judgment": {
                "status": judgment.get("status", ""),
                "severity": judgment.get("severity", ""),
                "summary": judgment.get("summary", ""),
                "next_move": (judgment.get("top_judgment") or {}).get("next_move", ""),
            },
            "recommendations": payload.get("recommendations", []),
            "next_action": next_action,
        },
        "error": not ok,
    }


def diagnose_failure_tool(arguments: Mapping[str, Any], *, cwd: Path, timeout: int) -> JsonObject:
    root = _repo_root(arguments, cwd)
    log_text = arguments.get("log_text")
    log_path = arguments.get("log_path")
    if bool(log_text) == bool(log_path):
        raise ToolError("give exactly one of `log_text` or `log_path`")
    if log_text is not None and not isinstance(log_text, str):
        raise ToolError("log_text must be a string")
    if log_path is not None and not isinstance(log_path, str):
        raise ToolError("log_path must be a string")

    with tempfile.TemporaryDirectory(prefix="sdetkit-mcp-") as temp_dir:
        out = Path(temp_dir)
        if log_text is not None:
            target_log = out / "failure.log"
            target_log.write_text(log_text, encoding="utf-8")
        else:
            target_log = (root / str(log_path)).resolve()
            if not target_log.is_file():
                raise ToolError(f"log_path does not exist: {target_log}")

        args = [
            "investigate",
            "failure",
            "--log",
            str(target_log),
            "--format",
            "json",
        ]
        completed = _sdetkit(args, cwd=root, timeout=timeout)
        try:
            payload = json.loads(completed.stdout or "{}")
        except ValueError:
            payload = {}

    ok = bool(payload.get("ok", True)) and bool(payload)
    classification = payload.get("classification") or "UNKNOWN_FAILURE"
    summary = payload.get("summary") or "Failure analysis unavailable"
    confidence = payload.get("confidence") or "medium"
    proof_commands = payload.get("proof_commands") or []
    next_actions = payload.get("next_actions") or []
    safe_to_auto_fix = bool(payload.get("safe_to_auto_fix"))

    text = (
        f"### SDETKit failure diagnosis: {classification}\n\n"
        f"**Summary**: {summary}\n"
        f"**Confidence**: {confidence} | **Safe to auto-fix**: {safe_to_auto_fix}\n"
    )
    if proof_commands:
        cmds = "\n".join(f"- `{cmd}`" for cmd in proof_commands)
        text += f"\n**Proof commands**:\n{cmds}\n"
    if next_actions:
        actions = "\n".join(f"- {action}" for action in next_actions)
        text += f"\n**Next actions**:\n{actions}\n"
    if completed.stderr.strip():
        text += f"\n```\n{completed.stderr.strip()}\n```"

    return {
        "text": text.strip(),
        "structured": payload,
        "error": not ok,
    }


def run_mutation_tool(arguments: Mapping[str, Any], *, cwd: Path, timeout: int) -> JsonObject:
    root = _repo_root(arguments, cwd)
    target_path = arguments.get("path")
    if target_path is not None and not isinstance(target_path, str):
        raise ToolError("path must be a string")
    limit = arguments.get("max_mutants")
    if limit is not None and (
        isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 200
    ):
        raise ToolError("max_mutants must be a whole number from 1 to 200")
    score = _percent(arguments.get("min_mutation_score"), "min_mutation_score")
    seconds = arguments.get("max_mutation_seconds")
    if seconds is not None and (
        isinstance(seconds, bool) or not isinstance(seconds, (int, float)) or seconds <= 0
    ):
        raise ToolError("max_mutation_seconds must be a number above 0")

    with tempfile.TemporaryDirectory(prefix="sdetkit-mcp-") as temp_dir:
        out = Path(temp_dir)
        json_out = out / "mutation.json"
        args = [
            "verify",
            "mutation",
            "--repo-root",
            str(root),
            "--format",
            "json",
            "--out",
            str(json_out),
            *(["--path", str(target_path)] if target_path else []),
            *(["--max-mutants", str(limit)] if limit is not None else []),
            *(["--min-mutation-score", str(score)] if score else []),
            *(["--max-mutation-seconds", str(seconds)] if seconds is not None else []),
            "--",
            *_strings(arguments, "pytest_args"),
        ]
        completed = _sdetkit(args, cwd=root, timeout=timeout)
        try:
            payload = json.loads(_read(json_out) or completed.stdout or "{}")
        except ValueError:
            payload = {}

    ok = bool(payload.get("ok", True)) and bool(payload)
    from sdetkit.mutation_cli import render_markdown

    text = render_markdown(payload) if payload else completed.stderr.strip()
    return {
        "text": text.strip() or f"sdetkit exited with {completed.returncode}",
        "structured": payload,
        "error": not ok,
    }


def auto_fix_tool(arguments: Mapping[str, Any], *, cwd: Path, timeout: int) -> JsonObject:
    root = _repo_root(arguments, cwd)
    log_text = arguments.get("log_text")
    log_path = arguments.get("log_path")
    apply_val = arguments.get("apply")
    if apply_val is not None and not isinstance(apply_val, bool):
        raise ToolError("apply must be a boolean")
    apply_fix = bool(apply_val)

    rules_val = arguments.get("rules")
    if rules_val is not None:
        if isinstance(rules_val, list):
            if not all(isinstance(r, str) for r in rules_val):
                raise ToolError("rules must be an array of strings")
            rules_str = ",".join(rules_val)
        elif isinstance(rules_val, str):
            rules_str = rules_val
        else:
            raise ToolError("rules must be an array of strings or comma-separated string")
    else:
        rules_str = None

    diff_val = arguments.get("diff")
    if diff_val is not None and not isinstance(diff_val, bool):
        raise ToolError("diff must be a boolean")
    include_diff = bool(diff_val)

    if log_text is not None and not isinstance(log_text, str):
        raise ToolError("log_text must be a string")
    if log_path is not None and not isinstance(log_path, str):
        raise ToolError("log_path must be a string")

    with tempfile.TemporaryDirectory(prefix="sdetkit-mcp-") as temp_dir:
        out = Path(temp_dir)
        json_out = out / "auto-fix.json"
        args = [
            "auto-fix",
            "--repo-root",
            str(root),
            "--format",
            "json",
            "--out",
            str(json_out),
            *(["--apply"] if apply_fix else ["--dry-run"]),
        ]
        if rules_str:
            args.extend(["--rules", rules_str])
        if include_diff:
            args.append("--diff")
        if log_text is not None:
            target_log = out / "failure.log"
            target_log.write_text(log_text, encoding="utf-8")
            args.extend(["--log", str(target_log)])
        elif log_path is not None:
            target_log = (root / str(log_path)).resolve()
            if not target_log.is_file():
                raise ToolError(f"log_path does not exist: {target_log}")
            args.extend(["--log", str(target_log)])

        completed = _sdetkit(args, cwd=root, timeout=timeout)
        try:
            payload = json.loads(_read(json_out) or completed.stdout or "{}")
        except ValueError:
            payload = {}

    ok = bool(payload.get("ok", True)) and bool(payload)
    from sdetkit.auto_fix import render_markdown as render_auto_fix_markdown

    text = (
        render_auto_fix_markdown(payload, dry_run=not apply_fix)
        if payload
        else completed.stderr.strip()
    )
    return {
        "text": text.strip() or f"sdetkit exited with {completed.returncode}",
        "structured": payload,
        "error": not ok,
    }


def hunt_flakes_tool(arguments: Mapping[str, Any], *, cwd: Path, timeout: int) -> JsonObject:
    root = _repo_root(arguments, cwd)
    target = arguments.get("target")
    runs = arguments.get("runs")
    if runs is not None:
        if not isinstance(runs, int) or runs < 2 or runs > 100:
            raise ToolError("runs must be an integer between 2 and 100")
    else:
        runs = 5
    shuffle = bool(arguments.get("shuffle", True))
    max_seconds = arguments.get("max_seconds")
    if max_seconds is not None and not isinstance(max_seconds, (int, float)):
        raise ToolError("max_seconds must be a number above 0")

    from sdetkit.flake_hunter import hunt_flakes, render_markdown

    payload = hunt_flakes(
        root=root,
        target=str(target) if target else None,
        runs=runs,
        shuffle=shuffle,
        timeout=timeout,
        max_seconds=float(max_seconds) if max_seconds is not None else None,
    )
    md = render_markdown(payload)
    return {
        "text": md,
        "structured": payload,
        "error": not payload.get("ok", True),
    }


def select_impacted_tests_tool(
    arguments: Mapping[str, Any], *, cwd: Path, timeout: int
) -> JsonObject:
    root = _repo_root(arguments, cwd)
    files_val = arguments.get("files")
    if files_val is not None:
        if not isinstance(files_val, list) or not all(isinstance(f, str) for f in files_val):
            raise ToolError("files must be an array of strings")
        files = files_val
    else:
        files = None

    base_val = arguments.get("base")
    if base_val is not None and not isinstance(base_val, str):
        raise ToolError("base must be a string")
    base = base_val

    run_val = arguments.get("run")
    if run_val is not None and not isinstance(run_val, bool):
        raise ToolError("run must be a boolean")
    should_run = bool(run_val)

    from sdetkit.dependency_map import (
        analyze_impact,
        render_markdown,
        run_impacted_tests,
    )

    report = analyze_impact(root, files=files, base=base)
    exec_res = None
    if should_run and report.get("all_impacted_tests"):
        exec_res = run_impacted_tests(report, root=root, timeout=timeout)

    md = render_markdown(report, exec_res)
    payload = {**report, "execution": exec_res} if exec_res else report
    error = bool(exec_res and not exec_res.get("ok"))
    return {
        "text": md,
        "structured": payload,
        "error": error,
    }


def manage_test_quarantine_tool(
    arguments: Mapping[str, Any], *, cwd: Path, timeout: int
) -> JsonObject:
    root = _repo_root(arguments, cwd)
    action = str(arguments.get("action") or "").lower().strip()
    if action not in {
        "add",
        "list",
        "audit",
        "filter",
        "shadow_run",
        "shadow-run",
        "graduate",
    }:
        raise ToolError("action must be one of: add, list, audit, filter, shadow_run, graduate")

    from sdetkit.flake_hunter import (
        add_to_quarantine,
        audit_quarantine,
        filter_quarantine,
        graduate_test,
        list_quarantine,
        render_quarantine_audit_markdown,
        render_quarantine_list_markdown,
        shadow_run_quarantine,
    )

    manifest_path = arguments.get("manifest_path")
    if manifest_path is not None and not isinstance(manifest_path, str):
        raise ToolError("manifest_path must be a string")

    if action == "add":
        test_id = str(arguments.get("test_id") or "").strip()
        if not test_id:
            raise ToolError("test_id is required for add action")
        reason = str(arguments.get("reason") or "")
        ttl_days = int(arguments.get("ttl_days") or 7)
        owner = str(arguments.get("owner") or "")
        issue_url = str(arguments.get("issue_url") or "")
        classification = str(arguments.get("classification") or "UNKNOWN")
        res = add_to_quarantine(
            root,
            test_id,
            reason=reason,
            ttl_days=ttl_days,
            owner=owner,
            issue_url=issue_url,
            classification=classification,
            manifest_path=manifest_path,
        )
        md = (
            f"### Quarantined Test Added\n\n"
            f"- **Test:** `{test_id}`\n"
            f"- **TTL:** `{ttl_days}d` (Expires: `{res['expires_at']}`)\n"
            f"- **Owner:** `{owner or 'unassigned'}`\n"
            f"- **File Exists:** `{res['file_exists']}`"
        )
        return {"text": md, "structured": res, "error": False}

    if action == "list":
        status_filter = arguments.get("status")
        res = list_quarantine(
            root,
            manifest_path=manifest_path,
            status_filter=str(status_filter) if status_filter else None,
        )
        md = render_quarantine_list_markdown(res)
        return {"text": md, "structured": res, "error": False}

    if action == "audit":
        res = audit_quarantine(root, manifest_path=manifest_path)
        md = render_quarantine_audit_markdown(res)
        return {
            "text": md,
            "structured": res,
            "error": bool(res.get("health_score", 100) < 60),
        }

    if action == "filter":
        mode = str(arguments.get("mode") or "k")
        res = filter_quarantine(root, manifest_path=manifest_path, mode=mode)
        args_str = res.get("pytest_args", "")
        md = (
            f"### Quarantine Pytest Filter\n\n"
            f"Active quarantined tests: `{res['active_count']}`\n\n"
            f"```bash\n{args_str}\n```"
        )
        return {"text": md, "structured": res, "error": False}

    if action in ("shadow_run", "shadow-run"):
        res = shadow_run_quarantine(root, manifest_path=manifest_path, timeout=timeout)
        md = f"### Quarantine Shadow Run\n\n{res.get('message', '')}"
        return {"text": md, "structured": res, "error": False}

    if action == "graduate":
        test_id = str(arguments.get("test_id") or "").strip()
        if not test_id:
            raise ToolError("test_id is required for graduate action")
        runs = int(arguments.get("runs") or 10)
        res = graduate_test(root, test_id, runs=runs, manifest_path=manifest_path)
        md = f"### Quarantine Graduation: {res.get('message', '')}"
        return {
            "text": md,
            "structured": res,
            "error": not res.get("graduated", False),
        }

    return {"text": "Unknown action", "structured": {}, "error": True}


def evaluate_blast_radius_tool(
    arguments: Mapping[str, Any], *, cwd: Path, timeout: int
) -> JsonObject:
    root = _repo_root(arguments, cwd)
    files_val = arguments.get("files")
    if files_val is not None:
        if not isinstance(files_val, list) or not all(isinstance(f, str) for f in files_val):
            raise ToolError("files must be an array of strings")
        files = files_val
    else:
        files = None

    base_val = arguments.get("base")
    if base_val is not None and not isinstance(base_val, str):
        raise ToolError("base must be a string")
    base = base_val

    from sdetkit.dependency_map import (
        evaluate_blast_radius,
        render_blast_radius_markdown,
    )

    report = evaluate_blast_radius(root, files=files, base=base)
    md = render_blast_radius_markdown(report)
    is_error = bool(report.get("risk_tier") == "CRITICAL")
    return {
        "text": md,
        "structured": report,
        "error": is_error,
    }


def heal_workspace_tool(arguments: Mapping[str, Any], *, cwd: Path, timeout: int) -> JsonObject:
    root = _repo_root(arguments, cwd)
    apply = bool(arguments.get("apply", False))
    verify = bool(arguments.get("verify", True))
    target_test_val = arguments.get("target_test")
    if target_test_val is not None and not isinstance(target_test_val, str):
        raise ToolError("target_test must be a string")
    target_test = target_test_val
    log_text_val = arguments.get("log_text")
    if log_text_val is not None and not isinstance(log_text_val, str):
        raise ToolError("log_text must be a string")
    log_text = log_text_val

    from sdetkit.auto_fix import heal_workspace, render_heal_markdown

    report = heal_workspace(
        root,
        apply=apply,
        verify=verify,
        target_test=target_test,
        log_text=log_text,
        timeout=timeout,
    )
    md = render_heal_markdown(report)
    is_error = report.get("verdict") in ("NO_SHIP", "REVIEW_REQUIRED")
    return {
        "text": md,
        "structured": report,
        "error": is_error,
    }


def inject_chaos_tool(arguments: Mapping[str, Any], *, cwd: Path, timeout: int) -> JsonObject:
    root = _repo_root(arguments, cwd)
    target_val = arguments.get("target")
    if target_val is not None and not isinstance(target_val, str):
        raise ToolError("target must be a string")
    target = target_val

    profile = str(arguments.get("profile") or "combined")
    if profile not in ("combined", "latency", "race", "memory", "transient_error"):
        raise ToolError("profile must be one of: combined, latency, race, memory, transient_error")

    latency_ms = arguments.get("latency_ms", 50)
    if not isinstance(latency_ms, int) or latency_ms < 0:
        raise ToolError("latency_ms must be a non-negative integer")

    jitter_ms = arguments.get("jitter_ms", 25)
    if not isinstance(jitter_ms, int) or jitter_ms < 0:
        raise ToolError("jitter_ms must be a non-negative integer")

    switch_interval_us = arguments.get("switch_interval_us", 10)
    if not isinstance(switch_interval_us, int) or switch_interval_us < 0:
        raise ToolError("switch_interval_us must be a non-negative integer")

    memory_mb = arguments.get("memory_mb", 0)
    if not isinstance(memory_mb, int) or memory_mb < 0:
        raise ToolError("memory_mb must be a non-negative integer")

    fault_rate = arguments.get("fault_rate", 0.0)
    if not isinstance(fault_rate, (int, float)) or not 0.0 <= fault_rate <= 1.0:
        raise ToolError("fault_rate must be a number between 0.0 and 1.0")

    runs = arguments.get("runs", 3)
    if not isinstance(runs, int) or runs < 1:
        raise ToolError("runs must be a positive integer")

    from sdetkit.flake_hunter import inject_chaos, render_chaos_markdown

    report = inject_chaos(
        root,
        target=target,
        profile=profile,
        latency_ms=latency_ms,
        jitter_ms=jitter_ms,
        switch_interval_us=switch_interval_us,
        memory_mb=memory_mb,
        fault_rate=float(fault_rate),
        runs=runs,
        timeout=timeout,
    )
    md = render_chaos_markdown(report)
    is_error = report.get("verdict") in ("BRITTLE", "BROKEN_BASELINE")
    return {
        "text": md,
        "structured": report,
        "error": is_error,
    }


def shard_test_suite_tool(arguments: Mapping[str, Any], *, cwd: Path, timeout: int) -> JsonObject:
    root = _repo_root(arguments, cwd)
    nodes = arguments.get("nodes", 4)
    if not isinstance(nodes, int) or nodes < 1:
        raise ToolError("nodes must be a positive integer")

    index_val = arguments.get("index")
    if index_val is not None and (not isinstance(index_val, int) or index_val < 0):
        raise ToolError("index must be a non-negative integer")
    index = index_val

    use_cache = bool(arguments.get("use_cache", False))

    test_files_val = arguments.get("test_files")
    if test_files_val is not None:
        if not isinstance(test_files_val, list) or not all(
            isinstance(f, str) for f in test_files_val
        ):
            raise ToolError("test_files must be a list of strings")
    test_files = test_files_val

    from sdetkit.dependency_map import render_shard_markdown, shard_test_suite

    report = shard_test_suite(
        root,
        nodes=nodes,
        index=index,
        test_files=test_files,
        use_cache=use_cache,
    )
    md = render_shard_markdown(report)
    return {
        "text": md,
        "structured": report,
        "error": False,
    }


def query_reliability_trends_tool(
    arguments: Mapping[str, Any], *, cwd: Path, timeout: int
) -> JsonObject:
    root = _repo_root(arguments, cwd)
    days = arguments.get("days", 30)
    if not isinstance(days, int) or days < 1:
        raise ToolError("days must be a positive integer")

    metric = str(arguments.get("metric", "all")).lower()
    if metric not in ("all", "health", "mutation", "quarantine", "rvi"):
        raise ToolError("metric must be one of: all, health, mutation, quarantine, rvi")

    with tempfile.TemporaryDirectory(prefix="sdetkit-mcp-") as temp_dir:
        out = Path(temp_dir)
        json_out = out / "trend.json"
        summary_out = out / "summary.md"
        args = [
            "trend",
            "--root",
            str(root),
            "--days",
            str(days),
            "--format",
            "json",
            "--out",
            str(json_out),
            "--summary-out",
            str(summary_out),
        ]
        completed = _sdetkit(args, cwd=root, timeout=timeout)
        try:
            payload = json.loads(_read(json_out) or completed.stdout or "{}")
        except ValueError:
            payload = {}
        summary = _read(summary_out).strip() or completed.stdout.strip() or completed.stderr.strip()

    return {
        "text": summary,
        "structured": payload,
        "error": not payload,
    }


def classify_flake_risk_tool(
    arguments: Mapping[str, Any], *, cwd: Path, timeout: int
) -> JsonObject:
    root = _repo_root(arguments, cwd)
    target_val = arguments.get("target")
    if target_val is not None and not isinstance(target_val, str):
        raise ToolError("target must be a string")
    target = target_val

    max_risk_val = arguments.get("max_risk", 50)
    if (
        isinstance(max_risk_val, bool)
        or not isinstance(max_risk_val, int)
        or not 0 <= max_risk_val <= 100
    ):
        raise ToolError("max_risk must be a whole number between 0 and 100")
    max_risk = max_risk_val

    with tempfile.TemporaryDirectory(prefix="sdetkit-mcp-") as temp_dir:
        out = Path(temp_dir)
        json_out = out / "genome.json"
        summary_out = out / "summary.md"
        args = [
            "genome",
            "--root",
            str(root),
            "--max-risk",
            str(max_risk),
            "--format",
            "json",
            "--out",
            str(json_out),
            "--summary-out",
            str(summary_out),
            *([target] if target else []),
        ]
        completed = _sdetkit(args, cwd=root, timeout=timeout)
        try:
            payload = json.loads(_read(json_out) or completed.stdout or "{}")
        except ValueError:
            payload = {}
        summary = _read(summary_out).strip() or completed.stdout.strip() or completed.stderr.strip()

    return {
        "text": summary,
        "structured": payload,
        "error": not payload or bool(payload.get("verdict") == "REJECT"),
    }


def run_polyglot_tests_tool(arguments: Mapping[str, Any], *, cwd: Path, timeout: int) -> JsonObject:
    root = _repo_root(arguments, cwd)
    target_val = arguments.get("target")
    if target_val is not None and not isinstance(target_val, str):
        raise ToolError("target must be a string")
    target = target_val

    langs_val = arguments.get("languages")
    languages_arg: list[str] = []
    if langs_val is not None:
        if isinstance(langs_val, list):
            if not all(isinstance(x, str) for x in langs_val):
                raise ToolError("languages must be a list of strings")
            languages_arg = ["--languages", ",".join(langs_val)]
        elif isinstance(langs_val, str):
            languages_arg = ["--languages", langs_val]
        else:
            raise ToolError("languages must be a string or list of strings")

    fail_fast = bool(arguments.get("fail_fast", False))
    runner_timeout = int(arguments.get("timeout", min(timeout, 120)))

    with tempfile.TemporaryDirectory(prefix="sdetkit-mcp-") as temp_dir:
        out = Path(temp_dir)
        json_out = out / "polyglot.json"
        summary_out = out / "summary.md"
        args = [
            "polyglot",
            "--root",
            str(root),
            "--timeout",
            str(runner_timeout),
            "--format",
            "json",
            "--out",
            str(json_out),
            "--summary-out",
            str(summary_out),
            *(["--fail-fast"] if fail_fast else []),
            *languages_arg,
            *([target] if target else []),
        ]
        completed = _sdetkit(args, cwd=root, timeout=timeout)
        try:
            payload = json.loads(_read(json_out) or completed.stdout or "{}")
        except ValueError:
            payload = {}
        summary = _read(summary_out).strip() or completed.stdout.strip() or completed.stderr.strip()

    return {
        "text": summary,
        "structured": payload,
        "error": not payload or bool(payload.get("verdict") == "FAIL"),
    }


def profile_performance_regression_tool(
    arguments: Mapping[str, Any], *, cwd: Path, timeout: int
) -> JsonObject:
    root = _repo_root(arguments, cwd)
    target_val = arguments.get("target")
    if target_val is not None and not isinstance(target_val, str):
        raise ToolError("target must be a string")
    target = target_val or "tests/"

    iterations_val = arguments.get("iterations", 3)
    if (
        isinstance(iterations_val, bool)
        or not isinstance(iterations_val, int)
        or not 1 <= iterations_val <= 50
    ):
        raise ToolError("iterations must be a whole number between 1 and 50")
    iterations = iterations_val

    max_reg_val = arguments.get("max_regression_percent", 15.0)
    if isinstance(max_reg_val, bool) or not isinstance(max_reg_val, (int, float)):
        raise ToolError("max_regression_percent must be a number")
    max_regression = float(max_reg_val)

    baseline_val = arguments.get("baseline")
    if baseline_val is not None and not isinstance(baseline_val, str):
        raise ToolError("baseline must be a string path")

    save_baseline_val = arguments.get("save_baseline")
    if save_baseline_val is not None and not isinstance(save_baseline_val, str):
        raise ToolError("save_baseline must be a string path")

    runner_timeout = int(arguments.get("timeout", min(timeout, 60)))

    with tempfile.TemporaryDirectory(prefix="sdetkit-mcp-") as temp_dir:
        out = Path(temp_dir)
        json_out = out / "perf.json"
        summary_out = out / "summary.md"
        args = [
            "perf",
            "--root",
            str(root),
            "--iterations",
            str(iterations),
            "--max-regression",
            str(max_regression),
            "--timeout",
            str(runner_timeout),
            "--format",
            "json",
            "--out",
            str(json_out),
            "--summary-out",
            str(summary_out),
            *(["--baseline", baseline_val] if baseline_val else []),
            *(["--save-baseline", save_baseline_val] if save_baseline_val else []),
            target,
        ]
        completed = _sdetkit(args, cwd=root, timeout=timeout)
        try:
            payload = json.loads(_read(json_out) or completed.stdout or "{}")
        except ValueError:
            payload = {}
        summary = _read(summary_out).strip() or completed.stdout.strip() or completed.stderr.strip()

    return {
        "text": summary,
        "structured": payload,
        "error": not payload or bool(payload.get("verdict") in ("REGRESSION", "FAIL")),
    }


def audit_supply_chain_provenance_tool(
    arguments: Mapping[str, Any], *, cwd: Path, timeout: int
) -> JsonObject:
    root = _repo_root(arguments, cwd)
    policy_val = arguments.get("policy", "permissive")
    if policy_val not in ("permissive", "allow-copyleft"):
        raise ToolError("policy must be 'permissive' or 'allow-copyleft'")

    allow_unpinned = bool(arguments.get("allow_unpinned", False))

    with tempfile.TemporaryDirectory(prefix="sdetkit-mcp-") as temp_dir:
        out = Path(temp_dir)
        json_out = out / "provenance.json"
        summary_out = out / "summary.md"
        args = [
            "provenance",
            str(root),
            "--policy",
            policy_val,
            "--format",
            "json",
            "--out",
            str(json_out),
            "--summary-out",
            str(summary_out),
            *(["--allow-unpinned"] if allow_unpinned else []),
        ]
        completed = _sdetkit(args, cwd=root, timeout=timeout)
        try:
            payload = json.loads(_read(json_out) or completed.stdout or "{}")
        except ValueError:
            payload = {}
        summary = _read(summary_out).strip() or completed.stdout.strip() or completed.stderr.strip()

    return {
        "text": summary,
        "structured": payload,
        "error": not payload or bool(payload.get("verdict") == "FAIL"),
    }


HANDLERS: dict[str, Callable[..., JsonObject]] = {
    "verify_change": verify_change_tool,
    "gate_fast": gate_fast_tool,
    "doctor": doctor_tool,
    "diagnose_failure": diagnose_failure_tool,
    "run_mutation": run_mutation_tool,
    "auto_fix": auto_fix_tool,
    "hunt_flakes": hunt_flakes_tool,
    "select_impacted_tests": select_impacted_tests_tool,
    "manage_test_quarantine": manage_test_quarantine_tool,
    "evaluate_blast_radius": evaluate_blast_radius_tool,
    "heal_workspace": heal_workspace_tool,
    "inject_chaos": inject_chaos_tool,
    "shard_test_suite": shard_test_suite_tool,
    "query_reliability_trends": query_reliability_trends_tool,
    "classify_flake_risk": classify_flake_risk_tool,
    "run_polyglot_tests": run_polyglot_tests_tool,
    "profile_performance_regression": profile_performance_regression_tool,
    "audit_supply_chain_provenance": audit_supply_chain_provenance_tool,
}


def _result(request_id: Any, result: JsonObject) -> JsonObject:
    return {"jsonrpc": "2.0", "id": request_id, "result": result}


def _error(request_id: Any, code: int, message: str) -> JsonObject:
    return {
        "jsonrpc": "2.0",
        "id": request_id,
        "error": {"code": code, "message": message},
    }


class Server:
    """One MCP session: answers requests, ignores notifications."""

    def __init__(self, *, cwd: Path, timeout: int = DEFAULT_TIMEOUT_SECONDS) -> None:
        self.cwd = cwd
        self.timeout = timeout

    def handle(self, message: Any) -> JsonObject | None:
        if not isinstance(message, dict) or message.get("jsonrpc") != "2.0":
            return _error(None, INVALID_REQUEST, "not a JSON-RPC 2.0 message")
        method = message.get("method")
        if "id" not in message:
            return None  # a notification, such as notifications/initialized
        request_id = message["id"]
        params = message.get("params") or {}
        if method == "initialize":
            requested = str(params.get("protocolVersion") or "")
            version = requested if requested in PROTOCOL_VERSIONS else PROTOCOL_VERSIONS[0]
            return _result(
                request_id,
                {
                    "protocolVersion": version,
                    "capabilities": {"tools": {"listChanged": False}},
                    "serverInfo": {"name": SERVER_NAME, "version": tool_version()},
                    "instructions": (
                        "Call verify_change before you commit or open a pull request: it checks "
                        "that your change passes the repository's tests without weakening them. "
                        "Call gate_fast to run the fast quality gate, doctor to check repository "
                        "health and readiness, diagnose_failure to analyze failure logs, "
                        "run_mutation to check assertion thoroughness, auto_fix to "
                        "remediate safe mechanical issues, hunt_flakes to prove test determinism, "
                        "and select_impacted_tests to accelerate test execution via AST test impact analysis, "
                        "manage_test_quarantine to isolate, audit, and graduate flaky tests, "
                        "evaluate_blast_radius to score architectural blast radius, transitive reach, and risk tier, "
                        "heal_workspace to autonomously repair mechanical drift, quarantine flakes, and prove workspace health, "
                        "inject_chaos to stress-test resilience against concurrency races and runtime latency, "
                        "shard_test_suite to balance test execution across parallel workers with duration-weighted sharding, "
                        "query_reliability_trends to track release reliability velocity and drift trajectories, "
                        "classify_flake_risk to audit test smells and static flake anti-patterns before execution, "
                        "run_polyglot_tests to execute unified multi-language test suites across Python, Go, JS/TS, and Java projects, "
                        "profile_performance_regression to profile latency regressions and execution benchmarks across commits, "
                        "and audit_supply_chain_provenance to audit lockfile integrity, license policies, and supply-chain attestations. "
                        "When a tool answers FAILED, its output says why each check failed."
                    ),
                },
            )
        if method == "ping":
            return _result(request_id, {})
        if method == "tools/list":
            return _result(request_id, {"tools": TOOLS})
        if method == "tools/call":
            return self._call(request_id, params)
        return _error(request_id, METHOD_NOT_FOUND, f"unknown method: {method}")

    def _call(self, request_id: Any, params: Mapping[str, Any]) -> JsonObject:
        name = params.get("name")
        handler = HANDLERS.get(str(name))
        if handler is None:
            return _error(request_id, INVALID_PARAMS, f"unknown tool: {name}")
        arguments = params.get("arguments") or {}
        if not isinstance(arguments, dict):
            return _error(request_id, INVALID_PARAMS, "arguments must be an object")
        try:
            outcome = handler(arguments, cwd=self.cwd, timeout=self.timeout)
        except (ToolError, OSError, subprocess.TimeoutExpired) as exc:
            return _result(
                request_id,
                {"content": [{"type": "text", "text": str(exc)}], "isError": True},
            )
        return _result(
            request_id,
            {
                "content": [{"type": "text", "text": outcome["text"]}],
                "structuredContent": outcome["structured"],
                "isError": bool(outcome["error"]),
            },
        )


def serve(stdin: TextIO, stdout: TextIO, *, cwd: Path, timeout: int) -> None:
    server = Server(cwd=cwd, timeout=timeout)
    for line in stdin:
        if not line.strip():
            continue
        try:
            message = json.loads(line)
        except ValueError:
            response: JsonObject | None = _error(None, PARSE_ERROR, "invalid JSON")
        else:
            response = server.handle(message)
        if response is not None:
            stdout.write(json.dumps(response, separators=(",", ":")) + "\n")
            stdout.flush()


def main(argv: list[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(
        prog="sdetkit mcp",
        description=(
            "Serve SDETKit to coding agents over the Model Context Protocol (stdio): the "
            "verify_change, gate_fast, doctor, diagnose_failure, run_mutation, auto_fix, "
            "hunt_flakes, select_impacted_tests, manage_test_quarantine, evaluate_blast_radius, "
            "heal_workspace, inject_chaos, shard_test_suite, query_reliability_trends, classify_flake_risk, run_polyglot_tests, profile_performance_regression, and audit_supply_chain_provenance tools. "
            "Add it to an agent, for example `claude mcp add sdetkit -- python -m sdetkit mcp`."
        ),
    )
    parser.add_argument(
        "--timeout-seconds",
        type=int,
        default=DEFAULT_TIMEOUT_SECONDS,
        help="Longest a tool may run",
    )
    args = parser.parse_args(argv)
    serve(sys.stdin, sys.stdout, cwd=Path.cwd(), timeout=args.timeout_seconds)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
