from __future__ import annotations

import argparse
import json
import os
import re
import sys
from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "sdetkit.adaptive.diagnosis.v1"
SEVERITY_SCORE = {"high": 30, "medium": 18, "low": 8, "info": 3}
SEVERITY_RANK = {"high": 0, "medium": 1, "low": 2, "info": 3}
CONFIDENCE_RANK = {"high": 0, "medium": 1, "low": 2}
SAFE_RUFF_FIXABLE_RULES = {"F401", "I001"}
SAFE_AUTO_FIX_CODES = {"PRE_COMMIT_FORMAT_DRIFT", "RUFF_FIXABLE_LINT"}
RUFF_RULE_RE = re.compile(r"\b([A-Z]\d{3})\b")
ABS_PATH_RE = re.compile(r"(?<![A-Za-z0-9_.-])(?:/[A-Za-z0-9_@%+=:,./-]+)+")
WIN_PATH_RE = re.compile(r"[A-Za-z]:\\\\[^\s`'\"]+")


@dataclass(frozen=True)
class FailureSignal:
    name: str
    pattern: re.Pattern[str]
    description: str


@dataclass(frozen=True)
class SeededScenario:
    code: str
    title: str
    signals: tuple[str, ...]
    keywords: tuple[str, ...]
    checks: tuple[str, ...]
    commands: tuple[str, ...]
    odds: tuple[str, ...] = ()
    tags: tuple[str, ...] = ()
    risk_band: str = "medium"
    prior_weight: int = 1


@dataclass(frozen=True)
class OddsAxis:
    name: str
    values: tuple[str, ...]


@dataclass(frozen=True)
class FailureMatrixFamily:
    name: str
    signals: tuple[str, ...]
    keywords: tuple[str, ...]
    check: str
    command: str
    risk_band: str = "medium"


MATRIX_ENVIRONMENTS = (
    "linux",
    "macos",
    "windows",
    "container",
    "github_actions",
    "gitlab_ci",
    "jenkins",
    "self_hosted",
    "arm64",
    "x86_64",
    "wsl",
    "docker_compose",
    "kubernetes",
    "air_gapped",
    "proxy_network",
    "readonly_workspace",
)

MATRIX_SYMPTOMS = (
    "assertion_delta",
    "fixture_missing",
    "import_missing",
    "timeout",
    "flaky_rerun",
    "permission_denied",
    "cache_stale",
    "lockfile_drift",
    "version_conflict",
    "schema_mismatch",
    "api_parity",
    "type_mismatch",
    "format_drift",
    "lint_unsafe",
    "coverage_drop",
    "docs_link",
    "network_timeout",
    "tls_proxy",
    "rate_limit",
    "disk_full",
    "timezone",
    "parallel_order",
    "artifact_missing",
    "release_duplicate",
)

MATRIX_FAMILIES = (
    FailureMatrixFamily(
        "pytest",
        ("pytest-node-failed", "pytest-failed-count", "assertion-error"),
        ("pytest", "failed", "assertionerror"),
        "Reproduce the first failing pytest node and inspect the assertion delta.",
        "PYTHONPATH=src python -m pytest -q <first-failing-test> -vv",
        "high",
    ),
    FailureMatrixFamily(
        "pytest_collection",
        ("pytest-error-count", "python-exception"),
        ("modulenotfounderror", "importerror while importing", "fixture"),
        "Run collection-only on the failing test file and repair imports/fixtures first.",
        "PYTHONPATH=src python -m pytest -q <failing-test-file> --collect-only",
        "high",
    ),
    FailureMatrixFamily(
        "ruff",
        ("ruff-check-failure",),
        ("ruff", "found", "fixable"),
        "Identify whether the Ruff rule is safe mechanical or requires review.",
        "PYTHONPATH=src python -m ruff check <touched-python-files>",
    ),
    FailureMatrixFamily(
        "format",
        ("ruff-format-failure",),
        ("ruff format", "would reformat", "files were modified"),
        "Run formatter locally and verify no product files changed unexpectedly.",
        "PYTHONPATH=src python -m ruff format --check <touched-python-files>",
    ),
    FailureMatrixFamily(
        "mypy",
        ("mypy-error",),
        ("mypy", "error:", "attr-defined", "arg-type", "union-attr"),
        "Open the first mypy error and fix the declared type/API contract.",
        "PYTHONPATH=src python -m mypy <module-or-package>",
    ),
    FailureMatrixFamily(
        "coverage",
        ("coverage-failure",),
        ("coverage", "fail under", "threshold"),
        "Find the missed file or branch that moved coverage below policy.",
        "PYTHONPATH=src python -m pytest --cov",
    ),
    FailureMatrixFamily(
        "package",
        ("package-manager-error", "python-exception"),
        ("pip", "npm err", "resolver", "wheel", "lockfile"),
        "Recreate dependency resolution from a clean environment before editing product code.",
        "python -m pip install -r requirements-test.txt -e .",
        "high",
    ),
    FailureMatrixFamily(
        "docs",
        ("error-prefix", "command-failed"),
        ("mkdocs", "docs", "link", "markdown"),
        "Build docs in strict mode and fix the first broken page/link.",
        "NO_MKDOCS_2_WARNING=1 python -m mkdocs build -q",
    ),
    FailureMatrixFamily(
        "git",
        ("command-failed",),
        ("git", "non-fast-forward", "rejected", "fetch first"),
        "Fetch/rebase before retrying push and rerun proof after rebase.",
        "git fetch origin <branch>",
    ),
    FailureMatrixFamily(
        "ci",
        ("ci-exit-code", "failed-steps"),
        ("exit code", "failed_steps", "workflow"),
        "Open the first failed CI step and map it back to the local proof command.",
        "python -m sdetkit adaptive dashboard --format json",
        "high",
    ),
    FailureMatrixFamily(
        "network",
        ("error-prefix", "command-failed"),
        ("timeout", "dns", "tls", "rate limit", "connection"),
        "Separate transient service/network failure from deterministic product failure.",
        "python -m pytest -q <network-marked-tests> -vv",
    ),
    FailureMatrixFamily(
        "runtime",
        ("python-exception",),
        ("python", "datetime.utc", "syntaxerror", "runtime"),
        "Verify the failing interpreter and supported Python compatibility lane.",
        "python --version",
        "high",
    ),
    FailureMatrixFamily(
        "cache",
        ("error-prefix", "command-failed"),
        ("cache", "artifact", "restore", "stale"),
        "Clear or rebuild cache before changing product code.",
        "PYTHONPATH=src python -m pytest -q --cache-clear",
    ),
    FailureMatrixFamily(
        "release",
        ("error-prefix", "command-failed"),
        ("release", "tag", "version", "twine", "duplicate"),
        "Compare version metadata, tags, and built artifacts before publishing.",
        "git tag --points-at HEAD",
        "high",
    ),
    FailureMatrixFamily(
        "security",
        ("gate-problems-found", "error-prefix"),
        ("secret", "token", "bandit", "policy"),
        "Treat security-policy failures as review-first and verify redaction before sharing logs.",
        "python -m sdetkit security --help",
        "high",
    ),
    FailureMatrixFamily(
        "dashboard",
        ("failed-steps", "error-prefix"),
        ("artifact", "dashboard", "json", "contract"),
        "Check local artifact contracts and regenerate deterministic dashboard evidence.",
        "python -m sdetkit adaptive dashboard --format json",
    ),
)


def _generated_scenario_matrix() -> tuple[SeededScenario, ...]:
    scenarios: list[SeededScenario] = []
    for family in MATRIX_FAMILIES:
        for environment in MATRIX_ENVIRONMENTS:
            for symptom in MATRIX_SYMPTOMS:
                code = f"MATRIX_{family.name}_{environment}_{symptom}".upper()
                title = (
                    f"{family.name.replace('_', ' ').title()} failure on "
                    f"{environment.replace('_', ' ')} with {symptom.replace('_', ' ')}"
                )
                scenarios.append(
                    SeededScenario(
                        code=code,
                        title=title,
                        signals=family.signals,
                        keywords=tuple(dict.fromkeys((*family.keywords, environment, symptom))),
                        checks=(
                            family.check,
                            f"Confirm whether environment={environment} changes reproduction.",
                            f"Use symptom={symptom} to choose the narrowest proof command.",
                        ),
                        commands=(family.command,),
                        odds=(environment, symptom, family.name),
                        tags=("generated-matrix", "real-world-scale"),
                        risk_band=family.risk_band,
                        prior_weight=1,
                    )
                )
    return tuple(sorted(scenarios, key=lambda scenario: scenario.code))


ODDS_EXPANSION_AXES = (
    OddsAxis(
        "runner", ("github-hosted", "self-hosted", "container", "local-wsl", "macos", "windows")
    ),
    OddsAxis("python", ("3.10", "3.11", "3.12", "3.13", "pypy", "pre-release")),
    OddsAxis("architecture", ("x86_64", "arm64", "musllinux", "manylinux")),
    OddsAxis(
        "dependency_state",
        (
            "fresh-lock",
            "stale-lock",
            "resolver-backtrack",
            "missing-extra",
            "yanked-wheel",
            "sdist-build",
        ),
    ),
    OddsAxis(
        "filesystem",
        (
            "case-sensitive",
            "case-insensitive",
            "long-path",
            "permission-denied",
            "mounted-volume",
            "readonly",
        ),
    ),
    OddsAxis(
        "network",
        (
            "offline",
            "rate-limited",
            "tls-proxy",
            "dns-flake",
            "api-timeout",
            "eventual-consistency",
        ),
    ),
    OddsAxis("test_shape", ("unit", "integration", "async", "snapshot", "property", "mutation")),
    OddsAxis(
        "state", ("empty-db", "dirty-cache", "clock-skew", "timezone", "locale", "parallel-order")
    ),
    OddsAxis(
        "change_type", ("api-contract", "typing", "formatting", "dependency", "workflow", "docs")
    ),
)


FAILURE_LIKE_SIGNAL_DB = (
    FailureSignal(
        "explicit-failed", re.compile(r"\bFAILED\b"), "A tool emitted an explicit FAILED marker."
    ),
    FailureSignal("traceback", re.compile(r"\bTraceback\b"), "Python emitted a traceback."),
    FailureSignal(
        "assertion-error", re.compile(r"\bAssertionError\b"), "A behavior assertion failed."
    ),
    FailureSignal(
        "error-prefix", re.compile(r"\b[Ee]rror:"), "A tool emitted an error-prefixed line."
    ),
    FailureSignal(
        "ci-exit-code",
        re.compile(r"Process completed with exit code (?!0\b)\d+"),
        "The CI step ended with a non-zero process exit code.",
    ),
    FailureSignal(
        "gate-problems-found",
        re.compile(r"gate: problems found", re.IGNORECASE),
        "A quality gate reported problems found.",
    ),
    FailureSignal("fail-token", re.compile(r"\bFAIL\b"), "A tool emitted an explicit FAIL token."),
    FailureSignal(
        "failed-steps",
        re.compile(r"\bfailed_steps\b", re.IGNORECASE),
        "Structured evidence included failed_steps.",
    ),
    FailureSignal(
        "ruff-format-failure",
        re.compile(
            r"ruff format.*(?:failed|would reformat|files were modified)",
            re.IGNORECASE | re.DOTALL,
        ),
        "Ruff format reported formatting drift or a failed format check.",
    ),
    FailureSignal(
        "ruff-check-failure",
        re.compile(
            r"(?:^.*ruff check.*failed.*$|^Found [1-9]\d* errors?\.)", re.IGNORECASE | re.MULTILINE
        ),
        "Ruff check reported lint errors.",
    ),
    FailureSignal(
        "mypy-error",
        re.compile(
            r"(?:^.*mypy.*failed.*$|^.+:\d+:\s+error:|^Found [1-9]\d* errors? in \d+ files?)",
            re.IGNORECASE | re.MULTILINE,
        ),
        "Mypy reported type-checking errors.",
    ),
    FailureSignal(
        "pytest-failures-section",
        re.compile(r"=+ FAILURES =+"),
        "Pytest printed a FAILURES section.",
    ),
    FailureSignal(
        "pytest-failed-count",
        re.compile(r"\b(?!0\s+failed)\d+\s+failed\b", re.IGNORECASE),
        "Pytest reported one or more failed tests.",
    ),
    FailureSignal(
        "pytest-error-count",
        re.compile(r"\b(?!0\s+errors?)\d+\s+errors?\b", re.IGNORECASE),
        "Pytest reported one or more erroring tests.",
    ),
    FailureSignal(
        "pytest-node-failed",
        re.compile(r"FAILED\s+[^\s]+::"),
        "Pytest reported a failed node id.",
    ),
    FailureSignal(
        "python-exception",
        re.compile(r"\b(?:[A-Z][A-Za-z]+Error|Exception):"),
        "A Python exception class appeared with details.",
    ),
    FailureSignal(
        "command-failed",
        re.compile(r"\bcommand failed\b", re.IGNORECASE),
        "A command wrapper reported failure.",
    ),
    FailureSignal(
        "coverage-failure",
        re.compile(r"(?:coverage.*(?:fail|under)|fail under)", re.IGNORECASE),
        "The coverage gate reported a threshold failure.",
    ),
    FailureSignal(
        "package-manager-error",
        re.compile(r"\b(?:npm ERR!|pnpm ERR!|yarn (?:run )?v?\d+.*error)", re.IGNORECASE),
        "A package manager emitted an error marker.",
    ),
)


BUILTIN_SCENARIO_PACK = "data/adaptive_scenarios.json"
SCENARIO_PACK_SCHEMA_VERSION = "sdetkit.adaptive.scenario_pack.v1"
SCENARIO_PACK_REPORT_SCHEMA_VERSION = "sdetkit.adaptive.scenario_pack_report.v1"
APPROVED_OVERRIDE_TAG = "override-approved"
VALID_RISK_BANDS = {"low", "medium", "high"}
REQUIRED_SCENARIO_FIELDS = {
    "code",
    "title",
    "signals",
    "keywords",
    "checks",
    "commands",
    "risk_band",
    "prior_weight",
}


def _package_file(rel_path: str) -> Path:
    return Path(__file__).resolve().parent / rel_path


def _as_str_tuple(value: Any, field: str, code: str) -> tuple[str, ...]:
    if not isinstance(value, list) or not value:
        raise ValueError(f"scenario {code}: {field} must be a non-empty list")
    out: list[str] = []
    for item in value:
        if not isinstance(item, str) or not item.strip():
            raise ValueError(f"scenario {code}: {field} must contain non-empty strings")
        text = item.strip()
        if text not in out:
            out.append(text)
    return tuple(out)


def _as_optional_str_tuple(value: Any, field: str, code: str) -> tuple[str, ...]:
    if value is None:
        return ()
    if not isinstance(value, list):
        raise ValueError(f"scenario {code}: {field} must be a list when provided")
    out: list[str] = []
    for item in value:
        if not isinstance(item, str) or not item.strip():
            raise ValueError(f"scenario {code}: {field} must contain non-empty strings")
        text = item.strip()
        if text not in out:
            out.append(text)
    return tuple(out)


def _scenario_from_row(row: Any, *, source: Path) -> SeededScenario:
    if not isinstance(row, dict):
        raise ValueError(f"scenario pack {source}: each scenario must be an object")
    missing = sorted(REQUIRED_SCENARIO_FIELDS.difference(row))
    raw_code = row.get("code", "UNKNOWN")
    code = raw_code.strip() if isinstance(raw_code, str) else "UNKNOWN"
    if missing:
        raise ValueError(f"scenario {code}: missing required fields: {', '.join(missing)}")
    if not code or not re.fullmatch(r"[A-Z0-9_]+", code):
        raise ValueError(f"scenario {code}: code must be uppercase snake case")
    title = row.get("title")
    if not isinstance(title, str) or not title.strip():
        raise ValueError(f"scenario {code}: title must be a non-empty string")
    risk_band = row.get("risk_band")
    if risk_band not in VALID_RISK_BANDS:
        raise ValueError(f"scenario {code}: risk_band must be one of low, medium, high")
    prior_weight = row.get("prior_weight")
    if not isinstance(prior_weight, int) or isinstance(prior_weight, bool) or prior_weight < 1:
        raise ValueError(f"scenario {code}: prior_weight must be a positive integer")
    return SeededScenario(
        code=code,
        title=title.strip(),
        signals=_as_str_tuple(row.get("signals"), "signals", code),
        keywords=_as_str_tuple(row.get("keywords"), "keywords", code),
        checks=_as_str_tuple(row.get("checks"), "checks", code),
        commands=_as_str_tuple(row.get("commands"), "commands", code),
        odds=_as_optional_str_tuple(row.get("odds"), "odds", code),
        tags=_as_optional_str_tuple(row.get("tags"), "tags", code),
        risk_band=str(risk_band),
        prior_weight=prior_weight,
    )


def load_scenario_pack(path: Path) -> tuple[SeededScenario, ...]:
    """Load and validate a versioned adaptive scenario pack."""
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"scenario pack {path}: root must be an object")
    if payload.get("schema_version") != SCENARIO_PACK_SCHEMA_VERSION:
        raise ValueError(
            f"scenario pack {path}: schema_version must be {SCENARIO_PACK_SCHEMA_VERSION}"
        )
    rows = payload.get("scenarios")
    if not isinstance(rows, list) or not rows:
        raise ValueError(f"scenario pack {path}: scenarios must be a non-empty list")
    scenarios = [_scenario_from_row(row, source=path) for row in rows]
    codes = [scenario.code for scenario in scenarios]
    duplicate_codes = sorted(code for code, count in Counter(codes).items() if count > 1)
    if duplicate_codes:
        raise ValueError(
            f"scenario pack {path}: duplicate scenario codes: {', '.join(duplicate_codes)}"
        )
    return tuple(sorted(scenarios, key=lambda scenario: scenario.code))


def merge_scenario_packs(*packs: Sequence[SeededScenario]) -> tuple[SeededScenario, ...]:
    """Merge packs deterministically, allowing later packs to override by scenario code."""
    merged: dict[str, SeededScenario] = {}
    for pack in packs:
        for scenario in pack:
            merged[scenario.code] = scenario
    return tuple(merged[code] for code in sorted(merged))


def _scenario_layer_name(path: Path, index: int) -> str:
    if index == 0:
        return "builtin"
    normalized = path.as_posix()
    if normalized.endswith(".sdetkit/adaptive/scenarios.json"):
        return "repo-local"
    return f"overlay-{index}"


def _scenario_layer_paths(root: Path | None = None) -> list[Path]:
    return [_package_file(BUILTIN_SCENARIO_PACK), *_default_layer_paths(root)]


def _scenario_layer_metadata(
    *, path: Path, index: int, scenarios: Sequence[SeededScenario]
) -> dict[str, Any]:
    codes = [scenario.code for scenario in scenarios]
    return {
        "index": index,
        "source": _scenario_layer_name(path, index),
        "path": str(path),
        "scenario_count": len(scenarios),
        "codes": codes,
    }


def layered_scenario_pack_report(
    root: Path | None = None, *, require_override_approval: bool = False
) -> dict[str, Any]:
    """Return deterministic scenario pack layer metadata and merged scenario codes.

    Overrides are allowed for normal loading so existing local packs remain compatible.
    Governance checks can set ``require_override_approval`` to reject overrides unless the
    replacing scenario carries the explicit ``override-approved`` tag.
    """
    merged: dict[str, SeededScenario] = {}
    seen_sources: dict[str, str] = {}
    layers: list[dict[str, Any]] = []
    overrides: list[dict[str, Any]] = []
    for index, path in enumerate(_scenario_layer_paths(root)):
        scenarios = load_scenario_pack(path)
        source = _scenario_layer_name(path, index)
        layers.append(_scenario_layer_metadata(path=path, index=index, scenarios=scenarios))
        for scenario in scenarios:
            previous_source = seen_sources.get(scenario.code)
            if previous_source is not None:
                approved = APPROVED_OVERRIDE_TAG in scenario.tags
                override = {
                    "code": scenario.code,
                    "previous_source": previous_source,
                    "source": source,
                    "approved": approved,
                    "approval_tag": APPROVED_OVERRIDE_TAG if approved else "",
                }
                overrides.append(override)
                if require_override_approval and not approved:
                    raise ValueError(
                        f"scenario {scenario.code}: override from {source} requires "
                        f"{APPROVED_OVERRIDE_TAG} tag"
                    )
            merged[scenario.code] = scenario
            seen_sources[scenario.code] = source
    merged_codes = sorted(merged)
    return {
        "schema_version": SCENARIO_PACK_REPORT_SCHEMA_VERSION,
        "ok": True,
        "layer_count": len(layers),
        "scenario_count": len(merged_codes),
        "layers": layers,
        "overrides": sorted(overrides, key=lambda row: (row["code"], row["source"])),
        "merged_codes": merged_codes,
        "override_policy": {
            "require_override_approval": require_override_approval,
            "approval_tag": APPROVED_OVERRIDE_TAG,
        },
    }


def validate_layered_scenario_packs(root: Path | None = None) -> dict[str, Any]:
    """Validate layered packs using governance override policy."""
    return layered_scenario_pack_report(root, require_override_approval=True)


def _default_layer_paths(root: Path | None = None) -> list[Path]:
    base = root or Path.cwd()
    env_paths = [
        Path(item)
        for item in os.environ.get("SDETKIT_ADAPTIVE_SCENARIO_PACKS", "").split(os.pathsep)
        if item
    ]
    candidates = [base / ".sdetkit" / "adaptive" / "scenarios.json", *env_paths]
    return [path for path in candidates if path.exists()]


def load_layered_scenarios(root: Path | None = None) -> tuple[SeededScenario, ...]:
    """Load built-in scenarios plus repo/org/private overlay packs in deterministic order."""
    packs = [SEEDED_SCENARIO_DB, *[load_scenario_pack(path) for path in _default_layer_paths(root)]]
    return merge_scenario_packs(*packs)


CURATED_SCENARIO_DB = load_scenario_pack(_package_file(BUILTIN_SCENARIO_PACK))
GENERATED_SCENARIO_DB = _generated_scenario_matrix()
SEEDED_SCENARIO_DB = merge_scenario_packs(CURATED_SCENARIO_DB, GENERATED_SCENARIO_DB)


def _as_int(value: Any) -> int:
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, (int, float)):
        return int(value)
    if isinstance(value, str) and value.strip().lstrip("-").isdigit():
        return int(value.strip())
    return 0


def _as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _safe(value: Any, limit: int = 500) -> str:
    text = str(value or "").replace("\r", " ").replace("\n", " ").strip()
    text = WIN_PATH_RE.sub("<path>", ABS_PATH_RE.sub("<path>", text))
    text = re.sub(r"secret-[A-Za-z0-9_.-]+", "<redacted>", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "…"


def _safe_list(values: Sequence[Any], limit: int = 6) -> list[str]:
    out: list[str] = []
    for value in values:
        text = _safe(value, 260)
        if text and text not in out:
            out.append(text)
        if len(out) >= limit:
            break
    return out


def _operator_guidance(
    *,
    code: str,
    diagnosis: str,
    fixes: Sequence[str],
    commands: Sequence[str],
    files: Sequence[str],
) -> dict[str, Any]:
    safe_to_auto_fix = code in SAFE_AUTO_FIX_CODES
    safe_fixes = _safe_list(fixes, 5)
    safe_commands = _safe_list(commands, 5)
    safe_files = _safe_list(files, 8)
    return {
        "what_is_going_on": _safe(diagnosis, 700),
        "what_to_fix_first": safe_fixes[0]
        if safe_fixes
        else "Start with the first concrete failing line in the captured evidence.",
        "how_to_fix": safe_fixes,
        "how_to_verify": safe_commands,
        "affected_files": safe_files,
        "automation_boundary": (
            "safe_mechanical_fix_allowed_after_proof"
            if safe_to_auto_fix
            else "review_first_no_auto_mutation"
        ),
        "why_this_is_not_random": (
            "Not random: generated from matched failure signals, affected files, and proof commands "
            "in the current evidence; unknown or unsafe failures stay review-first."
        ),
    }


def _diag(
    code: str,
    severity: str,
    confidence: str,
    title: str,
    diagnosis: str,
    why: str,
    evidence: Sequence[Any],
    fixes: Sequence[str],
    commands: Sequence[str],
    risk: str,
    signal: str,
    *,
    repeat_count: int = 0,
    files: Sequence[str] = (),
) -> dict[str, Any]:
    safe_fixes = _safe_list(fixes, 8)
    safe_commands = _safe_list(commands, 8)
    safe_files = _safe_list(files, 8)
    return {
        "code": code,
        "severity": severity,
        "confidence": confidence,
        "title": _safe(title, 160),
        "diagnosis": _safe(diagnosis, 900),
        "why_developers_miss_it": _safe(why, 900),
        "evidence": _safe_list(evidence, 8),
        "recommended_fix": safe_fixes,
        "proof_commands": safe_commands,
        "risk_if_ignored": _safe(risk, 500),
        "learning_signal": _safe(signal, 160),
        "repeat_count": max(0, repeat_count),
        "affected_files": safe_files,
        "operator_guidance": _operator_guidance(
            code=code,
            diagnosis=diagnosis,
            fixes=safe_fixes,
            commands=safe_commands,
            files=safe_files,
        ),
    }


def _file_mentions(text: str) -> list[str]:
    found = re.findall(r"[A-Za-z0-9_.-]+(?:/[A-Za-z0-9_.-]+)+\.py", text)
    return _safe_list([path for path in found if not path.startswith(("http/", "https/"))], 8)


def _ruff_rule_codes(text: str) -> list[str]:
    codes: list[str] = []
    for code in RUFF_RULE_RE.findall(text):
        if code not in codes:
            codes.append(code)
    return codes[:12]


def _failure_like_signals(text: str) -> list[FailureSignal]:
    return [signal for signal in FAILURE_LIKE_SIGNAL_DB if signal.pattern.search(text)]


def _scenario_calibration_map(
    adaptive_history: dict[str, Any] | None = None,
) -> dict[str, dict[str, Any]]:
    history = _as_dict(adaptive_history)
    rows = _as_list(history.get("top_recurring_scenarios"))
    out: dict[str, dict[str, Any]] = {}
    for row in rows:
        item = _as_dict(row)
        code = str(item.get("code", "")).strip()
        if code:
            out[code] = _as_dict(item.get("calibration"))
    return out


def _calibration_score(calibration: dict[str, Any]) -> int:
    if not calibration:
        return 0
    actions = {str(value) for value in _as_list(calibration.get("actions"))}
    score = _as_int(calibration.get("confidence_delta")) * 2
    risk_delta = _as_int(calibration.get("risk_delta"))
    if risk_delta > 0:
        score += min(4, max(1, risk_delta // 8))
    elif risk_delta < 0:
        score -= min(4, max(1, abs(risk_delta) // 8))
    if "promote" in actions:
        score += 4
    if "increase_risk" in actions:
        score += 2
    if "demote" in actions:
        score -= 8
    if "lower_confidence" in actions:
        score -= 3
    return score


def _candidate_calibration_evidence(
    candidates: Sequence[SeededScenario], calibration_by_code: dict[str, dict[str, Any]]
) -> str:
    parts: list[str] = []
    for scenario in candidates[:4]:
        calibration = calibration_by_code.get(scenario.code, {})
        if not calibration:
            continue
        parts.append(
            f"{scenario.code}:{calibration.get('primary_action', 'observe')}:"
            f"confidence_delta={_as_int(calibration.get('confidence_delta'))}:"
            f"risk_delta={_as_int(calibration.get('risk_delta'))}"
        )
    return "candidate_calibration=" + ";".join(parts) if parts else ""


def _looks_failure_like(text: str) -> bool:
    return bool(_failure_like_signals(text))


def _has_failure_signal(text: str, name: str) -> bool:
    return any(signal.name == name for signal in _failure_like_signals(text))


def _failure_like_evidence(text: str, adaptive_history: dict[str, Any] | None = None) -> list[str]:
    signals = _failure_like_signals(text)
    calibration_by_code = _scenario_calibration_map(adaptive_history)
    evidence = ["matched_failure_signals=" + ",".join(signal.name for signal in signals[:6])]
    evidence.extend(signal.description for signal in signals[:3])
    candidates = _candidate_scenarios(text, signals, calibration_by_code=calibration_by_code)
    if candidates:
        evidence.append(
            "candidate_scenarios=" + ",".join(scenario.code for scenario in candidates[:4])
        )
        evidence.append(_candidate_odds_evidence(candidates))
        calibration_evidence = _candidate_calibration_evidence(candidates, calibration_by_code)
        if calibration_evidence:
            evidence.append(calibration_evidence)
    return evidence


def _candidate_scenarios(
    text: str,
    signals: Sequence[FailureSignal] | None = None,
    *,
    limit: int = 4,
    calibration_by_code: dict[str, dict[str, Any]] | None = None,
) -> list[SeededScenario]:
    lower = text.lower()
    signal_names = {signal.name for signal in (signals or _failure_like_signals(text))}
    scored: list[tuple[int, str, SeededScenario]] = []
    for scenario in SEEDED_SCENARIO_DB:
        signal_hits = len(signal_names.intersection(scenario.signals))
        keyword_hits = sum(1 for keyword in scenario.keywords if keyword.lower() in lower)
        odds_hits = sum(1 for odd in scenario.odds if odd.lower() in lower)
        score = signal_hits * 3 + keyword_hits + odds_hits + max(0, scenario.prior_weight - 1)
        if score and "generated-matrix" in scenario.tags:
            score = max(1, score - 2)
        elif score:
            score += 20
        score += _calibration_score(_as_dict((calibration_by_code or {}).get(scenario.code)))
        if score:
            scored.append((-score, scenario.code, scenario))
    scored.sort()
    return [scenario for _, _, scenario in scored[:limit]]


def _odds_space_size() -> int:
    total = max(1, len(SEEDED_SCENARIO_DB)) * max(1, len(FAILURE_LIKE_SIGNAL_DB))
    for axis in ODDS_EXPANSION_AXES:
        total *= max(1, len(axis.values))
    return total


def _candidate_odds_evidence(candidates: Sequence[SeededScenario]) -> str:
    parts = [
        f"{scenario.code}:{scenario.risk_band}:prior={scenario.prior_weight}"
        for scenario in candidates[:4]
    ]
    return "candidate_odds=" + ";".join(parts)


def _candidate_checks(
    text: str, limit: int = 5, adaptive_history: dict[str, Any] | None = None
) -> list[str]:
    checks: list[str] = []
    for scenario in _candidate_scenarios(
        text, calibration_by_code=_scenario_calibration_map(adaptive_history)
    ):
        checks.append(f"Check candidate {scenario.code}: {scenario.checks[0]}")
        for check in scenario.checks[1:2]:
            checks.append(check)
        if len(checks) >= limit:
            break
    checks.append(
        "If no candidate fits, inspect the first actionable traceback or failing command manually."
    )
    return checks[:limit]


def _candidate_commands(
    text: str, limit: int = 4, adaptive_history: dict[str, Any] | None = None
) -> list[str]:
    commands: list[str] = []
    for scenario in _candidate_scenarios(
        text, calibration_by_code=_scenario_calibration_map(adaptive_history)
    ):
        for command in scenario.commands:
            if command not in commands:
                commands.append(command)
            if len(commands) >= limit:
                return commands
    return commands or ["python -m pre_commit run -a"]


def _seeded_scenario_evidence() -> list[str]:
    return [
        f"seeded_scenario_count={len(SEEDED_SCENARIO_DB)}",
        f"curated_scenario_count={len(CURATED_SCENARIO_DB)}",
        f"generated_matrix_scenario_count={len(GENERATED_SCENARIO_DB)}",
        f"seeded_odds_space_size={_odds_space_size()}",
        "seeded_scenario_examples="
        + ",".join(scenario.code for scenario in SEEDED_SCENARIO_DB[:5]),
    ]


def _is_safe_ruff_fixable_lint(text: str, codes: Sequence[str]) -> bool:
    lower = text.lower()
    if not codes:
        return False
    if any(code not in SAFE_RUFF_FIXABLE_RULES for code in codes):
        return False
    return (
        "fixable" in lower
        or "[*]" in text
        or "remove unused import" in lower
        or "import block is un-sorted" in lower
    )


def _append_ruff_lint(text: str, files: Sequence[str], diagnoses: list[dict[str, Any]]) -> None:
    codes = _ruff_rule_codes(text)
    if files and _is_safe_ruff_fixable_lint(text, codes):
        targets = " ".join(files)
        rule_text = ", ".join(codes)
        diagnoses.append(
            _diag(
                "RUFF_FIXABLE_LINT",
                "medium",
                "high",
                "Ruff fixable lint can be mechanically remediated",
                f"Ruff reported fixable mechanical lint ({rule_text}) in known files.",
                "Developers often fix the visible import by hand and miss that Ruff can apply this narrow class safely.",
                ["ruff fixable lint", f"ruff_rules={rule_text}", "safe_rules=F401,I001"],
                [
                    "Run ruff check --fix on affected files.",
                    "Run ruff format on affected files.",
                    "Re-run Ruff check and format check.",
                ],
                [
                    f"PYTHONPATH=src python -m ruff check {targets}",
                    f"PYTHONPATH=src python -m ruff format --check {targets}",
                ],
                "The PR stays red for a mechanical lint issue that the autopilot can safely prove.",
                "ruff-fixable-lint",
                files=files,
            )
        )
        return
    _append_static("RUFF_LINT_FAILURE", "Ruff lint contract failed", files, diagnoses)


def _append_local_investigation(
    text: str, files: Sequence[str], diagnoses: list[dict[str, Any]]
) -> bool:
    lower = text.lower()

    if "missing test dependencies" in lower or (
        "modulenotfounderror" in lower
        and any(name in lower for name in ("hypothesis", "yaml", "pytest", "respx", "httpx"))
    ):
        diagnoses.append(
            _diag(
                "MISSING_TEST_DEPENDENCY",
                "medium",
                "high",
                "Test dependency is missing",
                "The test run failed before exercising product behavior because a required test dependency is unavailable.",
                "Developers often chase product code when collection failed because the environment is incomplete.",
                ["missing test dependency"],
                ["Install the declared test requirements and rerun the same focused test command."],
                ["python -m pip install -r requirements-test.txt"],
                "The failure can be misclassified as product logic when the test environment is incomplete.",
                "missing-test-dependency",
                files=files,
            )
        )
        return True

    if (
        "cannot import name 'utc' from 'datetime'" in lower
        or "cannot import name 'utc' from datetime" in lower
    ):
        diagnoses.append(
            _diag(
                "PYTHON_RUNTIME_COMPATIBILITY",
                "high",
                "high",
                "Python runtime compatibility issue detected",
                "The log shows use of datetime.UTC on a Python runtime that does not provide that symbol.",
                "Developers often reproduce on a newer interpreter and miss older supported runtime lanes.",
                ["datetime.UTC import failed"],
                [
                    "Replace the runtime-specific import with a compatibility-safe fallback and rerun supported Python lanes."
                ],
                ["python --version", "python -m pytest -q"],
                "Supported older Python versions can remain broken even when newer CI lanes pass.",
                "python-runtime-compatibility",
                files=files,
            )
        )
        return True

    if "/mnt/c/" in lower and any(
        token in lower
        for token in ("pip", "venv", "site-packages", "keyboardinterrupt", "slow", "stuck")
    ):
        diagnoses.append(
            _diag(
                "LOCAL_ENVIRONMENT_FRICTION",
                "medium",
                "high",
                "Local WSL filesystem friction detected",
                "The log suggests Python packaging or virtualenv work is running from the Windows-mounted filesystem.",
                "Developers often debug package tooling when the real issue is filesystem friction under WSL.",
                ["wsl-mounted-filesystem", "python environment operation"],
                [
                    "Move the active clone or virtualenv to the native WSL filesystem and rerun the same command."
                ],
                ["cp -a /mnt/c/<repo> ~/<repo>", "python -m venv .venv"],
                "Local environment friction can hide the real product signal and waste debugging time.",
                "local-environment-friction",
                files=files,
            )
        )
        return True

    if "takes no arguments" in lower and (
        "init_" in text or "__init__" in text or "test double" in lower or "mock" in lower
    ):
        diagnoses.append(
            _diag(
                "BROKEN_TEST_DOUBLE",
                "medium",
                "high",
                "Test double constructor is broken",
                "The failure appears to happen before product code runs because a local test double cannot be instantiated.",
                "Developers often treat this as product behavior until the traceback shows the fake object failed first.",
                ["test double instantiation failed"],
                ["Fix the test double constructor and rerun the focused test slice."],
                ["python -m pytest -q <focused-test>"],
                "A broken test harness can send the investigation toward the wrong product area.",
                "broken-test-double",
                files=files,
            )
        )
        return True

    if (
        "attributeerror" in lower
        and ("object has no attribute" in lower or "has no attribute" in lower)
        and any(token in lower for token in ("async", "sync", "client", "helper", "parity"))
    ):
        diagnoses.append(
            _diag(
                "MISSING_PUBLIC_API_PARITY",
                "high",
                "high",
                "Missing public API parity detected",
                "A public surface appears to be missing a method or helper that an adjacent sync/async/client surface provides.",
                "Developers often verify one public path and miss that a paired async or helper API is incomplete.",
                ["attribute missing on public API surface"],
                [
                    "Add the missing public API parity and focused regression coverage for both surfaces."
                ],
                ["python -m pytest -q <focused-parity-test>"],
                "Users can hit runtime AttributeError even though the sibling public API works.",
                "missing-public-api-parity",
                files=files,
            )
        )
        return True

    if "rejected" in lower and ("fetch first" in lower or "non-fast-forward" in lower):
        diagnoses.append(
            _diag(
                "GIT_BRANCH_DIVERGED",
                "medium",
                "high",
                "Git branch diverged from remote",
                "The push was rejected because the remote branch contains work not present locally.",
                "Developers often retry the push instead of rebasing onto the updated remote branch.",
                ["push rejected", "fetch first"],
                ["Fetch the remote branch, rebase locally, rerun proof, then push again."],
                ["git fetch origin <branch>", "git rebase origin/<branch>", "git push"],
                "A force push or stale branch can overwrite remote fixes or bot updates.",
                "git-branch-diverged",
                files=files,
            )
        )
        return True

    if "successfully rebased" in lower and "origin/" in lower:
        diagnoses.append(
            _diag(
                "REMOTE_BRANCH_DRIFT",
                "medium",
                "high",
                "Remote branch drift was resolved locally",
                "The local branch had to be rebased on a newer remote branch before pushing.",
                "Bot or remote updates can land between local proof and push.",
                ["remote branch updated", "local rebase succeeded"],
                ["Rerun proof after rebase before pushing."],
                ["python -m pre_commit run -a", "git push"],
                "Proof from before the rebase may no longer describe the pushed branch.",
                "remote-branch-drift",
                files=files,
            )
        )
        return True

    if "product logic failure" in lower or "deterministic product behavior failure" in lower:
        diagnoses.append(
            _diag(
                "PRODUCT_LOGIC_FAILURE",
                "high",
                "medium",
                "Product behavior failure requires review",
                "The log explicitly identifies a deterministic product behavior or contract failure.",
                "Developers often look for environment causes after a real behavior assertion has already identified the failing contract.",
                ["deterministic product behavior failure"],
                [
                    "Reproduce the focused failing behavior and inspect the product contract before broad rewrites."
                ],
                ["PYTHONPATH=src python -m pytest -q <focused-test>"],
                "A real behavior regression can be merged if it is mislabeled as infrastructure noise.",
                "product-logic-failure",
                files=files,
            )
        )
        return True

    return False


def _failure_snippets(text: str, *, limit: int = 5) -> list[str]:
    snippets: list[str] = []
    marker = re.compile(
        r"(FAILED|FAILURES|AssertionError|Traceback|Error:|error:|ruff|mypy|ModuleNotFoundError|ImportError|Process completed with exit code|Found [1-9])",
        re.IGNORECASE,
    )
    for line in text.splitlines():
        cleaned = _safe(line, 260)
        if not cleaned or not marker.search(cleaned):
            continue
        if cleaned not in snippets:
            snippets.append(cleaned)
        if len(snippets) >= limit:
            break
    return snippets


def _attach_log_context(diagnoses: list[dict[str, Any]], start_index: int, text: str) -> None:
    snippets = _failure_snippets(text)
    if not snippets:
        return
    for diagnosis in diagnoses[start_index:]:
        guidance = _as_dict(diagnosis.get("operator_guidance"))
        guidance["observed_failure_lines"] = snippets
        guidance["matched_from_current_log"] = True
        diagnosis["operator_guidance"] = guidance
        evidence = _as_list(diagnosis.get("evidence"))
        for index, snippet in enumerate(snippets[:3], start=1):
            item = f"observed_failure_line_{index}={snippet}"
            if item not in evidence:
                evidence.append(item)
        diagnosis["evidence"] = _safe_list(evidence, 8)


GREEN_QUALITY_GATE_TOKENS = (
    "quality.sh cov passed",
    "quality gate passed",
    "coverage gate are green",
    "lint + tests + coverage gate are green",
    "gate fast: ok",
    "checks: lint + tests + coverage gate are green",
)

REVIEW_FIRST_ADVISORY_TOKENS = (
    "adaptive diagnosis",
    "unknown_review_required",
    "failure needs human review",
    "sdetkit will keep this review-first",
    "current evidence is not safe for automatic remediation",
    "auto-fix status",
    "check candidate coverage_gate_regression",
)

HARD_FAILURE_TOKENS_IN_GREEN_GATE_CONTEXT = (
    "process completed with exit code",
    "gate fast: fail",
    "quality.sh cov failed",
    "coverage failed",
    "fail under",
    "failed_steps:",
    "[fail]",
    "traceback",
    "assertionerror",
    "error:",
    "command failed",
)


def _has_green_quality_gate_signal(text: str) -> bool:
    lowered = text.lower()
    return any(token in lowered for token in GREEN_QUALITY_GATE_TOKENS)


def _has_hard_failure_signal_in_green_context(text: str) -> bool:
    lowered = text.lower()
    return any(token in lowered for token in HARD_FAILURE_TOKENS_IN_GREEN_GATE_CONTEXT)


def _has_review_first_advisory_signal(text: str) -> bool:
    lowered = text.lower()
    return any(token in lowered for token in REVIEW_FIRST_ADVISORY_TOKENS)


def _looks_green_quality_advisory(text: str) -> bool:
    if not _has_green_quality_gate_signal(text):
        return False
    if _has_hard_failure_signal_in_green_context(text):
        return False
    return _has_review_first_advisory_signal(text)


def _append_log(
    text: str, diagnoses: list[dict[str, Any]], adaptive_history: dict[str, Any] | None = None
) -> None:
    start_index = len(diagnoses)
    lower = text.lower()
    files = _file_mentions(text)
    handled_local = _append_local_investigation(text, files, diagnoses)
    formatted = _format_count(text)
    if formatted:
        evidence = ["ruff-format modified files", f"reformatted_file_count={formatted}"]
        if "pytest" in lower and ("passed" in lower or "rc=0" in lower):
            evidence.append("pytest evidence appears green")
        diagnoses.append(
            _diag(
                "PRE_COMMIT_FORMAT_DRIFT",
                "medium",
                "high",
                "Formatter drift blocked pre-commit",
                f"ruff-format reformatted {formatted} file(s) during the quality gate.",
                "Developers often see green tests and miss hooks that mutate files.",
                evidence,
                [
                    "Run ruff format on touched files.",
                    "Re-run format check and targeted pytest.",
                ],
                ["PYTHONPATH=src python -m ruff format --check <touched-python-files>"],
                "CI stays red even though product behavior may already be correct.",
                "formatting-drift-after-green-tests",
                files=files,
            )
        )
    if "mypy" in lower and "error:" in lower:
        _append_static("MYPY_TYPE_CONTRACT_DRIFT", "Type contract drift detected", files, diagnoses)
    if "ruff" in lower and not formatted and _has_failure_signal(text, "ruff-check-failure"):
        _append_ruff_lint(text, files, diagnoses)
    if "modulenotfounderror" in lower or "importerror while importing" in lower:
        _append_pytest(
            text,
            "PYTEST_IMPORT_FAILURE",
            "Pytest import or collection failed",
            files,
            diagnoses,
        )
    elif not handled_local and ("assertionerror" in lower or re.search(r"FAILED\s+[^\s]+::", text)):
        _append_pytest(
            text,
            "PYTEST_ASSERTION_FAILURE",
            "Targeted test behavior failed",
            files,
            diagnoses,
        )
    if not diagnoses and _looks_failure_like(text) and not _looks_green_quality_advisory(text):
        diagnoses.append(
            _diag(
                "UNKNOWN_REVIEW_REQUIRED",
                "high",
                "medium",
                "Failure needs human review",
                "The provided log contains failure-like text but did not match a known adaptive diagnosis family.",
                "Unknown failures should not be guessed into a safe-fix route.",
                _failure_like_evidence(text, adaptive_history),
                _candidate_checks(text, adaptive_history=adaptive_history),
                _candidate_commands(text, adaptive_history=adaptive_history),
                "Unclassified failures can be unsafe to automate.",
                "unknown-review-required",
                files=files,
            )
        )
    _attach_log_context(diagnoses, start_index, text)


def _format_count(text: str) -> int:
    match = re.search(r"(\d+)\s+files?\s+reformatted", text)
    if match:
        return _as_int(match.group(1))
    return 1 if "files were modified by this hook" in text or "file reformatted" in text else 0


def _first_test(text: str) -> str:
    for pattern in (r"FAILED\s+([^\s]+::[^\s]+)", r"(tests/[\w./-]+\.py::[\w\[\]-]+)"):
        match = re.search(pattern, text)
        if match:
            return _safe(match.group(1), 180)
    return "unknown test"


def _append_static(
    code: str, title: str, files: Sequence[str], diagnoses: list[dict[str, Any]]
) -> None:
    diagnoses.append(
        _diag(
            code,
            "medium",
            "medium",
            title,
            f"{title}; inspect the first failing line before broad rewrites.",
            "Static-quality failures are often hidden inside larger gate output.",
            [title],
            ["Fix the first reported contract violation."],
            ["PYTHONPATH=src python -m ruff check <touched-python-files>"],
            "The branch remains blocked at static quality.",
            code.lower().replace("_", "-"),
            files=files,
        )
    )


def _append_pytest(
    text: str,
    code: str,
    title: str,
    files: Sequence[str],
    diagnoses: list[dict[str, Any]],
) -> None:
    test = _first_test(text)
    diagnoses.append(
        _diag(
            code,
            "high",
            "high" if code == "PYTEST_IMPORT_FAILURE" else "medium",
            title,
            f"Pytest reported a failure near {test}; use the first failing test as the fix anchor.",
            "Large CI logs can hide the first useful traceback under repeated summary output.",
            ["pytest failure", f"first_failed_test={test}"],
            ["Reproduce the first failing test only."],
            [f"PYTHONPATH=src python -m pytest -q {test}"],
            "A behavior regression can be merged behind otherwise green checks.",
            "pytest-failure",
            files=files,
        )
    )


def _append_mission(bundle: dict[str, Any], diagnoses: list[dict[str, Any]]) -> None:
    if not bundle:
        return
    decision = str(bundle.get("decision", "")).upper()
    failed = _as_int(bundle.get("failed_step_count"))
    steps = [_as_dict(step) for step in _as_list(bundle.get("steps"))]
    failed_steps = [
        str(step.get("id") or step.get("name") or "unknown")
        for step in steps
        if step.get("status") == "failed" or _as_int(step.get("rc")) != 0
    ]
    if decision == "NO_SHIP" or failed:
        evidence = [f"decision={decision or 'unknown'}", f"failed_step_count={failed}"]
        if failed_steps:
            evidence.append("failed_steps=" + ", ".join(failed_steps[:6]))
        diagnoses.append(
            _diag(
                "MISSION_CONTROL_NO_SHIP",
                "high",
                "high" if failed_steps else "medium",
                "Mission Control marked the run as no-ship",
                "Mission Control found a release-blocking run state across evidence sources.",
                "Developers often inspect one failing command and miss the higher-level decision.",
                evidence,
                ["Start with the first failed Mission Control step."],
                ["PYTHONPATH=src python -m sdetkit mission-control --execute --doctor-cortex"],
                "A no-ship decision can be bypassed if the team only checks local unit tests.",
                "mission-control-no-ship",
            )
        )
    if not _as_list(bundle.get("findings")) and not _as_list(bundle.get("artifacts")):
        diagnoses.append(
            _diag(
                "EVIDENCE_ARTIFACT_MISSING",
                "low",
                "medium",
                "Mission evidence is thin",
                "The Mission Control payload does not expose findings or artifacts that explain the run.",
                "Reviewers need durable artifacts, not only an exit code.",
                ["no findings or artifacts were present in the provided bundle"],
                ["Write a JSON and Markdown evidence bundle for the run."],
                ["PYTHONPATH=src python -m sdetkit mission-control --execute"],
                "Future reviewers lose context needed to diagnose repeated failures.",
                "mission-evidence-gap",
            )
        )


def _doctor_counts(record: dict[str, Any]) -> tuple[int, int] | None:
    cortex = _as_dict(record.get("doctor_cortex"))
    if not cortex or cortex.get("enabled") is False:
        return None
    diagnosis = _as_dict(cortex.get("diagnosis"))
    prescriptions = _as_dict(cortex.get("prescriptions"))
    return (
        _as_int(cortex.get("diagnosis_count", diagnosis.get("diagnosis_count", 0))),
        _as_int(cortex.get("prescription_count", prescriptions.get("prescription_count", 0))),
    )


def _append_history(records: list[dict[str, Any]], diagnoses: list[dict[str, Any]]) -> None:
    if not records:
        if not diagnoses:
            return
        diagnoses.append(
            _diag(
                "MISSION_CONTROL_HISTORY_MISSING",
                "low",
                "high",
                "Mission Control history is not available yet",
                "No Mission Control ledger records were available, so recurrence cannot be assessed.",
                "A single run cannot show whether the issue is new, repeated, or worsening.",
                ["ledger_record_count=0"],
                ["Enable Mission Control ledger writes for future runs."],
                ["PYTHONPATH=src python -m sdetkit mission-control --append-ledger"],
                "The kit cannot separate one-time noise from repeated release friction.",
                "mission-history-missing",
            )
        )
        return
    decisions = Counter(str(row.get("decision", "UNKNOWN")).upper() for row in records)
    no_ship = decisions.get("NO_SHIP", 0)
    failed_runs = sum(1 for row in records if _as_int(row.get("failed_step_count")) > 0)
    if no_ship >= 2 or failed_runs >= 2:
        diagnoses.append(_repeated_history(records, no_ship, failed_runs))
    counts = [sample for row in records if (sample := _doctor_counts(row))]
    if len(counts) >= 2:
        _append_doctor_trend(counts[-2], counts[-1], diagnoses)


def _repeated_history(
    records: Sequence[dict[str, Any]], no_ship: int, failed_runs: int
) -> dict[str, Any]:
    return _diag(
        "MISSION_CONTROL_REPEATED_FAILURE_PATTERN",
        "high",
        "high",
        "Repeated release friction detected in history",
        f"History shows {no_ship} NO_SHIP decision(s) and {failed_runs} failed run(s).",
        "Developers usually inspect the latest run; repeated patterns need ledger comparison.",
        [f"ledger_record_count={len(records)}", f"no_ship_count={no_ship}"],
        ["Treat the repeated failing gate as a stabilization task."],
        ["PYTHONPATH=src python -m sdetkit mission-control history"],
        "The same release blocker is likely to return.",
        "repeated-release-friction",
        repeat_count=max(no_ship, failed_runs),
    )


def _append_doctor_trend(
    previous: tuple[int, int], latest: tuple[int, int], diagnoses: list[dict[str, Any]]
) -> None:
    for kind, before, after in (
        ("DIAGNOSIS", previous[0], latest[0]),
        ("PRESCRIPTION", previous[1], latest[1]),
    ):
        if after <= before:
            continue
        noun = kind.lower()
        diagnoses.append(
            _diag(
                f"DOCTOR_CORTEX_{kind}_REGRESSION",
                "medium",
                "high",
                f"Doctor Cortex {noun} count increased",
                f"Doctor Cortex {noun} count increased from {before} to {after}.",
                "A release can look acceptable while diagnostic debt grows across runs.",
                [f"{noun}_delta={after - before}"],
                [f"Inspect the newest Doctor Cortex {noun} output."],
                ["PYTHONPATH=src python -m sdetkit doctor --format json"],
                "Remediation effort can grow quietly until it blocks release.",
                f"doctor-cortex-{noun}-regression",
            )
        )


def _append_adaptive(history: dict[str, Any], diagnoses: list[dict[str, Any]]) -> None:
    if not history:
        return
    runs = _as_int(history.get("run_count", history.get("runs", 0)))
    if runs <= 0:
        diagnoses.append(
            _diag(
                "LEARNING_DB_EMPTY",
                "low",
                "high",
                "Adaptive memory is initialized but empty",
                "Adaptive memory has no run-specific records yet, but SDETKit starts with a seeded scenario database for common CI and quality failures.",
                "Developers often treat an empty run history as zero intelligence even when a tested scenario catalog can guide the first investigation.",
                ["adaptive_run_count=0", *_seeded_scenario_evidence()],
                [
                    "Use the seeded scenario database to classify the first failing signal before adding project-specific memory.",
                    "Populate adaptive memory after meaningful runs so local patterns can outrank generic candidates.",
                ],
                ["PYTHONPATH=src python -m sdetkit adaptive history --format operator-json"],
                "Recommendations remain weaker without prior context.",
                "adaptive-memory-empty",
            )
        )
    else:
        diagnoses.append(
            _diag(
                "KNOWN_ADAPTIVE_PATTERN_AVAILABLE",
                "info",
                "medium",
                "Adaptive memory has reusable context",
                "Adaptive memory contains prior context for this investigation.",
                "Developers rarely remember every prior hotspot after many small PRs.",
                [f"adaptive_run_count={runs}"],
                ["Compare current changed files with adaptive history."],
                ["PYTHONPATH=src python -m sdetkit adaptive history --format operator-json"],
                "Prior context may be ignored and investigation work repeated.",
                "adaptive-context",
                repeat_count=runs,
            )
        )


def _risk_score(diagnoses: Sequence[dict[str, Any]]) -> int:
    score = 0
    for item in diagnoses:
        score += SEVERITY_SCORE.get(str(item.get("severity", "info")), 3)
        score += {"high": 5, "medium": 2}.get(str(item.get("confidence", "low")), 0)
        score += min(_as_int(item.get("repeat_count")), 5) * 2
    return min(100, score)


def _rank(item: dict[str, Any]) -> tuple[int, int, int, str]:
    return (
        SEVERITY_RANK.get(str(item.get("severity", "info")), 9),
        CONFIDENCE_RANK.get(str(item.get("confidence", "low")), 9),
        -_as_int(item.get("repeat_count")),
        str(item.get("code", "")),
    )


def analyze_evidence(
    *,
    log_text: str = "",
    mission_control: dict[str, Any] | None = None,
    ledger_records: Sequence[dict[str, Any]] | None = None,
    adaptive_history: dict[str, Any] | None = None,
) -> dict[str, Any]:
    diagnoses: list[dict[str, Any]] = []
    if log_text:
        _append_log(log_text, diagnoses, _as_dict(adaptive_history))
    _append_mission(_as_dict(mission_control), diagnoses)
    _append_history(list(ledger_records or []), diagnoses)
    _append_adaptive(_as_dict(adaptive_history), diagnoses)
    diagnoses = sorted(diagnoses, key=_rank)
    return _payload(diagnoses, _status_for(diagnoses))


def _status_for(diagnoses: Sequence[dict[str, Any]]) -> str:
    if any(item.get("severity") == "high" for item in diagnoses):
        return "needs_fix"
    if any(str(item.get("code", "")) in SAFE_AUTO_FIX_CODES for item in diagnoses):
        return "needs_fix"
    if _risk_score(diagnoses) >= 30:
        return "needs_attention"
    return "monitor" if diagnoses else "clear"


def _payload(diagnoses: list[dict[str, Any]], status: str) -> dict[str, Any]:
    confidence = "low"
    if any(item.get("confidence") == "high" for item in diagnoses):
        confidence = "high"
    elif diagnoses:
        confidence = "medium"
    summary = "No adaptive diagnosis signals were found in the provided evidence."
    if diagnoses:
        verb = (
            "Fix this before release signoff"
            if status == "needs_fix"
            else "Keep collecting evidence"
        )
        summary = f"Primary issue: {diagnoses[0]['title']}. {verb}."
    return {
        "schema_version": SCHEMA_VERSION,
        "ok": status in {"clear", "monitor"},
        "status": status,
        "risk_score": _risk_score(diagnoses),
        "confidence": confidence,
        "summary": _safe(summary, 500),
        "diagnosis_count": len(diagnoses),
        "diagnoses": diagnoses,
        "fix_plan": [
            {
                "code": item["code"],
                "title": item["title"],
                "safe_to_auto_fix": item["code"] in SAFE_AUTO_FIX_CODES,
                "recommended_fix": item["recommended_fix"][:4],
                "proof_commands": item["proof_commands"][:4],
            }
            for item in diagnoses[:5]
        ],
        "scenario_database": {
            "curated_scenario_count": len(CURATED_SCENARIO_DB),
            "generated_matrix_scenario_count": len(GENERATED_SCENARIO_DB),
            "total_scenario_count": len(SEEDED_SCENARIO_DB),
            "failure_signal_count": len(FAILURE_LIKE_SIGNAL_DB),
            "odds_space_size": _odds_space_size(),
            "generation_strategy": "curated_pack_plus_deterministic_real_world_failure_matrix",
        },
        "learning_updates": [
            {
                "signal": item["learning_signal"],
                "code": item["code"],
                "confidence": item["confidence"],
            }
            for item in diagnoses
        ],
    }


def render_text(payload: dict[str, Any]) -> str:
    lines = [
        f"schema_version={payload['schema_version']}",
        f"ok={str(payload['ok']).lower()}",
        f"status={payload['status']}",
        f"risk_score={payload['risk_score']}",
        f"confidence={payload['confidence']}",
        f"summary={payload['summary']}",
        f"diagnosis_count={payload['diagnosis_count']}",
    ]
    for item in _as_list(payload.get("diagnoses"))[:5]:
        row = _as_dict(item)
        lines.append(
            f"diagnosis={row.get('code')}|{row.get('severity')}|{row.get('confidence')}|{row.get('title')}"
        )
    return "\n".join(_safe(line, 600) for line in lines) + "\n"


def _diagnosis_markdown(row: dict[str, Any]) -> list[str]:
    lines = [
        f"### {row.get('title', 'Untitled diagnosis')}",
        "",
        f"- Code: {row.get('code', 'UNKNOWN')}",
        f"- Severity: {row.get('severity', 'unknown')}",
        f"- Confidence: {row.get('confidence', 'unknown')}",
        f"- Repeat count: {row.get('repeat_count', 0)}",
        "",
        str(row.get("diagnosis", "")),
        "",
        "Why developers miss it:",
        str(row.get("why_developers_miss_it", "")),
        "",
        "Evidence:",
    ]
    lines += [f"- {value}" for value in _as_list(row.get("evidence"))]
    guidance = _as_dict(row.get("operator_guidance"))
    if guidance:
        lines += ["", "Operator guidance:"]
        lines += [
            f"- What is going on: {guidance.get('what_is_going_on', '')}",
            f"- Fix first: {guidance.get('what_to_fix_first', '')}",
            f"- Automation boundary: {guidance.get('automation_boundary', '')}",
            f"- Why this is not random: {guidance.get('why_this_is_not_random', '')}",
        ]
        observed = _as_list(guidance.get("observed_failure_lines"))
        if observed:
            lines += ["- Observed failure lines:"]
            lines += [f"  - `{value}`" for value in observed[:5]]
    lines += ["", "Recommended fix:"]
    lines += [f"- {value}" for value in _as_list(row.get("recommended_fix"))]
    lines += ["", "Proof commands:"]
    lines += [f"- `{value}`" for value in _as_list(row.get("proof_commands"))]
    lines += ["", f"Risk if ignored: {row.get('risk_if_ignored', '')}", ""]
    return lines


def render_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# Adaptive Diagnosis Intelligence",
        "",
        f"- Status: {payload['status']}",
        f"- OK: {str(payload['ok']).lower()}",
        f"- Risk score: {payload['risk_score']}",
        f"- Confidence: {payload['confidence']}",
        f"- Summary: {payload['summary']}",
        "",
        "## Diagnoses",
        "",
    ]
    for item in _as_list(payload.get("diagnoses")):
        lines.extend(_diagnosis_markdown(_as_dict(item)))
    if not _as_list(payload.get("diagnoses")):
        lines.append("- none")
    return "\n".join(_safe(line, 900) if line else "" for line in lines) + "\n"


def _load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"expected JSON object in {path}")
    return payload


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    records: list[dict[str, Any]] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"invalid JSONL at line {line_number}: {exc}") from exc
        if isinstance(payload, dict):
            records.append(payload)
    return records


def _render(payload: dict[str, Any], output_format: str) -> str:
    if output_format == "json":
        return json.dumps(payload, indent=2, sort_keys=True) + "\n"
    if output_format == "md":
        return render_markdown(payload)
    return render_text(payload)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m sdetkit.adaptive_diagnosis")
    parser.add_argument("--mission-control", default="")
    parser.add_argument("--ledger", default="")
    parser.add_argument("--adaptive-history", default="")
    parser.add_argument("--log", action="append", default=[])
    parser.add_argument("--format", choices=["text", "json", "md"], default="text")
    parser.add_argument("--out", default="")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(list(argv if argv is not None else sys.argv[1:]))
    try:
        log_text = "\n".join(
            Path(path).read_text(encoding="utf-8", errors="replace") for path in args.log
        )
        payload = analyze_evidence(
            log_text=log_text,
            mission_control=_load_json(Path(args.mission_control))
            if args.mission_control
            else None,
            ledger_records=_load_jsonl(Path(args.ledger)) if args.ledger else [],
            adaptive_history=_load_json(Path(args.adaptive_history))
            if args.adaptive_history
            else None,
        )
        rendered = _render(payload, str(args.format))
        if args.out:
            out_path = Path(args.out)
            out_path.parent.mkdir(parents=True, exist_ok=True)
            out_path.write_text(rendered, encoding="utf-8")
        else:
            sys.stdout.write(rendered)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"error={exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
