from __future__ import annotations

import argparse
import ast
import datetime as dt
import difflib
import hashlib
import json
import math
import os
import re
import subprocess
import sys
import tomllib as _tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

from .atomicio import atomic_write_text
from .plugins import (
    Finding as PluginFinding,
)
from .plugins import (
    Fix,
    RuleMeta,
    load_rule_catalog,
    normalize_packs,
    select_rules,
)
from .security import SecurityError, safe_path

SKIP_DIRS: frozenset[str] = frozenset(
    {
        ".git",
        ".hg",
        ".svn",
        "__pycache__",
        ".mypy_cache",
        ".pytest_cache",
        ".ruff_cache",
        ".hypothesis",
        ".nox",
        ".tox",
        ".venv",
        "venv",
        "node_modules",
        "dist",
        "build",
    }
)

SKIP_FILES: frozenset[str] = frozenset({".coverage"})

BIDI_HIDDEN_CODEPOINTS: frozenset[str] = frozenset(
    {
        "\u200b",  # zero width space
        "\u200c",  # zero width non-joiner
        "\u200d",  # zero width joiner
        "\ufeff",  # zero width no-break space (BOM)
        "\u202a",  # LRE
        "\u202b",  # RLE
        "\u202c",  # PDF
        "\u202d",  # LRO
        "\u202e",  # RLO
        "\u2066",  # LRI
        "\u2067",  # RLI
        "\u2068",  # FSI
        "\u2069",  # PDI
    }
)

SECRET_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    (
        "auth_header",
        re.compile(
            r"(?i)\\b(?:authorization|x-api-key|api[_-]?key|token|password|cookie|set-cookie)\\b\\s*[:=]\\s*[^\\s]{4,}"
        ),
    ),
    ("aws_access_key", re.compile(r"\\bAKIA[0-9A-Z]{16}\\b")),
    (
        "aws_secret_key",
        re.compile(r"(?i)aws(.{0,20})?(?:secret|access).{0,5}[=:].{0,5}[A-Za-z0-9/+=]{40}"),
    ),
    (
        "private_key_header",
        re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    ),
    ("github_pat", re.compile(r"\bgh[pousr]_[A-Za-z0-9]{20,}\b")),
    ("jwt", re.compile(r"\beyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9._-]+\.[A-Za-z0-9._-]+\b")),
)

HIGH_ENTROPY_TOKEN = re.compile(r"\b[A-Za-z0-9+/=_-]{24,}\b")
SENSITIVE_WORDS = (
    "secret",
    "token",
    "password",
    "passwd",
    "api_key",
    "apikey",
    "auth",
    "credential",
)
WORKFLOW_USE_RE = re.compile(r"^\s*(?:-\s*)?uses:\s*([^\s]+)\s*$")
UNPINNED_DEP_RE = re.compile(r"^(?:[A-Za-z0-9_.-]+)(?:\[[^\]]+\])?\s*(?:>=|>|~=|\*|$)")
PRIVATE_KEY_FILES: frozenset[str] = frozenset({"id_rsa", "id_dsa"})
PRIVATE_KEY_SUFFIXES: tuple[str, ...] = (".pem", ".p12", ".pfx", ".key")
_UTC = getattr(dt, "UTC", dt.timezone.utc)  # noqa: UP017

DEFAULT_INIT_TEMPLATES: dict[str, str] = {
    "SECURITY.md": (
        "# Security Policy\n\n"
        "## Reporting a Vulnerability\n\n"
        "Please report suspected vulnerabilities privately to the maintainers. "
        "Include reproduction steps, impact, and any proof-of-concept details.\n\n"
        "## Response Expectations\n\n"
        "Maintainers acknowledge reports promptly and provide status updates until closure.\n"
    ),
    "CONTRIBUTING.md": (
        "# Contributing\n\n"
        "Thanks for helping improve this project.\n\n"
        "## Getting Started\n\n"
        "- Create a branch from the default branch.\n"
        "- Keep changes scoped and include tests.\n"
        "- Run local quality checks before opening a pull request.\n\n"
        "## Pull Requests\n\n"
        "- Explain what changed and why.\n"
        "- Reference related issues where relevant.\n"
        "- Ensure CI is green before requesting review.\n"
    ),
    "CODE_OF_CONDUCT.md": (
        "# Code of Conduct\n\n"
        "This project is committed to a respectful, harassment-free experience for everyone.\n\n"
        "## Expected Behavior\n\n"
        "- Be respectful and constructive.\n"
        "- Welcome diverse perspectives.\n"
        "- Focus on what is best for the community.\n\n"
        "## Reporting\n\n"
        "If you experience unacceptable behavior, contact the maintainers privately.\n"
    ),
    ".github/ISSUE_TEMPLATE/config.yml": (
        "blank_issues_enabled: false\n"
        "contact_links:\n"
        "  - name: Security report\n"
        "    url: https://example.invalid/security\n"
        "    about: Please report vulnerabilities privately and avoid public disclosure.\n"
    ),
    ".github/ISSUE_TEMPLATE/bug_report.yml": (
        "name: Bug report\n"
        "description: Report a reproducible defect.\n"
        'title: "bug: "\n'
        "labels: [bug]\n"
        "body:\n"
        "  - type: textarea\n"
        "    id: summary\n"
        "    attributes:\n"
        "      label: Summary\n"
        "      description: What happened?\n"
        "    validations:\n"
        "      required: true\n"
        "  - type: textarea\n"
        "    id: steps\n"
        "    attributes:\n"
        "      label: Steps to reproduce\n"
        "      description: Provide a minimal, deterministic reproduction.\n"
        "    validations:\n"
        "      required: true\n"
    ),
    ".github/ISSUE_TEMPLATE/feature_request.yml": (
        "name: Feature request\n"
        "description: Suggest an improvement.\n"
        'title: "feat: "\n'
        "labels: [enhancement]\n"
        "body:\n"
        "  - type: textarea\n"
        "    id: problem\n"
        "    attributes:\n"
        "      label: Problem statement\n"
        "      description: What problem are you trying to solve?\n"
        "    validations:\n"
        "      required: true\n"
        "  - type: textarea\n"
        "    id: proposal\n"
        "    attributes:\n"
        "      label: Proposed solution\n"
        "      description: Describe your preferred approach.\n"
    ),
    ".github/PULL_REQUEST_TEMPLATE.md": (
        "## Summary\n\n"
        "Describe the change and its motivation.\n\n"
        "## Validation\n\n"
        "- [ ] Tests added or updated\n"
        "- [ ] Local checks passed\n"
    ),
}

ENTERPRISE_INIT_TEMPLATES: dict[str, str] = {
    ".github/dependabot.yml": (
        "version: 2\n"
        "updates:\n"
        "  - package-ecosystem: pip\n"
        "    directory: /\n"
        "    schedule:\n"
        "      interval: weekly\n"
    ),
    ".github/workflows/quality.yml": (
        "name: quality\n"
        "on:\n"
        "  pull_request:\n"
        "  push:\n"
        "    branches: [main]\n"
        "jobs:\n"
        "  quality:\n"
        "    runs-on: ubuntu-latest\n"
        "    steps:\n"
        "      - uses: actions/checkout@v4\n"
        "      - uses: actions/setup-python@v5\n"
        "        with:\n"
        "          python-version: '3.11'\n"
        "      - name: Install\n"
        "        run: python -m pip install -e .\n"
        "      - name: Test\n"
        "        run: pytest\n"
    ),
    ".github/workflows/security.yml": (
        "name: security\n"
        "on:\n"
        "  pull_request:\n"
        "  push:\n"
        "    branches: [main]\n"
        "jobs:\n"
        "  checks:\n"
        "    runs-on: ubuntu-latest\n"
        "    steps:\n"
        "      - uses: actions/checkout@v4\n"
        "      - name: Secret-pattern sanity check\n"
        "        run: |\n"
        "          if grep -R --line-number --exclude-dir=.git --exclude-dir=.venv 'AKIA[0-9A-Z]\\{16\\}' .; then\n"
        "            echo 'Potential AWS key pattern detected'\n"
        "            exit 1\n"
        "          fi\n"
        "      - name: Python syntax check\n"
        "        run: python -m compileall -q src tests\n"
    ),
}


def _shannon_entropy(s: str) -> float:
    if not s:
        return 0.0
    counts = {ch: s.count(ch) for ch in set(s)}
    n = float(len(s))
    entropy = 0.0
    for count in counts.values():
        p = count / n
        entropy -= p * (0 if p == 0 else math.log2(p))
    return entropy


def _safe_snippet(line: str) -> str:
    if len(line) <= 10:
        return "<redacted>"
    return f"{line[:3]}...{line[-3:]}"


def _git_commit_sha(root: Path) -> str | None:
    try:
        proc = subprocess.run(
            ["git", "-C", str(root), "rev-parse", "HEAD"],
            check=False,
            capture_output=True,
            text=True,
        )
    except OSError:
        return None
    sha = proc.stdout.strip()
    return sha if proc.returncode == 0 and sha else None


def _changed_files(root: Path, base: str) -> set[str]:
    try:
        proc = subprocess.run(
            [
                "git",
                "-C",
                str(root),
                "diff",
                "--name-only",
                "--diff-filter=ACMRTUXB",
                f"{base}...HEAD",
            ],
            check=False,
            capture_output=True,
            text=True,
        )
    except OSError:
        return set()
    if proc.returncode != 0:
        return set()
    return {x.strip() for x in proc.stdout.splitlines() if x.strip()}


@dataclass(frozen=True)
class Finding:
    check: str
    severity: str
    path: str
    line: int
    column: int
    code: str
    message: str
    confidence: str = "medium"
    remediation: str = ""
    snippet: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "check": self.check,
            "code": self.code,
            "severity": self.severity,
            "path": self.path,
            "line": self.line,
            "column": self.column,
            "message": self.message,
            "confidence": self.confidence,
            "remediation": self.remediation,
            "snippet": self.snippet,
        }


@dataclass(frozen=True)
class RepoAuditCheck:
    key: str
    title: str
    passed: bool
    details: tuple[str, ...]
    findings: tuple[Finding, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "key": self.key,
            "title": self.title,
            "status": "pass" if self.passed else "fail",
            "details": list(self.details),
        }


@dataclass(frozen=True)
class RepoInitChange:
    path: str
    action: str
    current: str
    desired: str


@dataclass(frozen=True)
class AllowlistRule:
    rule_id: str
    path: str
    contains: str | None = None


@dataclass(frozen=True)
class RepoAuditPolicy:
    profile: str
    fail_on: str
    baseline_path: str
    exclude_paths: tuple[str, ...]
    disable_rules: frozenset[str]
    severity_overrides: dict[str, str]
    allowlist: tuple[AllowlistRule, ...]


class RepoAuditConfigError(ValueError):
    pass


def _iter_files(root: Path) -> list[Path]:
    files: list[Path] = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(
            d
            for d in dirnames
            if d not in SKIP_DIRS and not d.endswith(".egg-info") and not d.startswith(".venv")
        )
        for fname in sorted(filenames):
            if fname in SKIP_FILES:
                continue
            p = Path(dirpath) / fname
            if p.is_file():
                files.append(p)
    files.sort(key=lambda x: x.relative_to(root).as_posix())
    return files


def _line_for_offset(text: str, offset: int) -> tuple[int, int]:
    prefix = text[:offset]
    line = prefix.count("\n") + 1
    last_nl = prefix.rfind("\n")
    col = offset + 1 if last_nl == -1 else offset - last_nl
    return line, col


def run_checks(
    root: Path,
    *,
    profile: str,
    changed_only: bool,
    diff_base: str,
    baseline: list[dict[str, Any]],
) -> list[Finding]:
    findings: list[Finding] = []
    only = _changed_files(root, diff_base) if changed_only else set()

    for path in _iter_files(root):
        rel = path.relative_to(root).as_posix()
        if only and rel not in only:
            continue
        try:
            data = path.read_bytes()
        except OSError as exc:
            findings.append(
                Finding("decode", "error", rel, 1, 1, "read_error", f"unable to read file: {exc}")
            )
            continue

        try:
            text = data.decode("utf-8")
        except UnicodeDecodeError as exc:
            findings.append(
                Finding(
                    "decode",
                    "error",
                    rel,
                    1,
                    1,
                    "utf8_decode",
                    f"invalid UTF-8 at byte {exc.start}: {exc.reason}",
                    remediation="re-encode file as UTF-8 text",
                )
            )
            continue

        if b"\r\n" in data and b"\n" in data.replace(b"\r\n", b""):
            findings.append(
                Finding(
                    "line_endings", "warn", rel, 1, 1, "mixed_eol", "mixed line endings detected"
                )
            )
        elif b"\r\n" in data:
            findings.append(
                Finding("line_endings", "warn", rel, 1, 1, "crlf_eol", "CRLF line endings detected")
            )
        elif b"\r" in data:
            findings.append(
                Finding(
                    "line_endings", "warn", rel, 1, 1, "cr_eol", "legacy CR line endings detected"
                )
            )

        lines = text.splitlines(keepends=True)
        for idx, text_row in enumerate(lines, start=1):
            content = text_row.rstrip("\r\n")
            stripped = content.rstrip(" \t")
            if content != stripped:
                findings.append(
                    Finding(
                        "trailing_whitespace",
                        "warn",
                        rel,
                        idx,
                        len(stripped) + 1,
                        "trailing_ws",
                        "trailing whitespace",
                        confidence="high",
                        remediation="remove trailing spaces/tabs",
                    )
                )

        if data and not data.endswith(b"\n"):
            findings.append(
                Finding(
                    "eof_newline",
                    "warn",
                    rel,
                    max(1, len(lines)),
                    1,
                    "missing_eof_nl",
                    "missing EOF newline",
                    confidence="high",
                    remediation="add a single newline at end-of-file",
                )
            )

        for i, ch in enumerate(text):
            if ch in BIDI_HIDDEN_CODEPOINTS:
                line, col = _line_for_offset(text, i)
                findings.append(
                    Finding(
                        "hidden_unicode",
                        "error",
                        rel,
                        line,
                        col,
                        "hidden_unicode",
                        f"hidden/bidi Unicode character U+{ord(ch):04X}",
                        confidence="high",
                        remediation="remove invisible bidi control characters",
                    )
                )

        for idx, text_line in enumerate(text.splitlines(), start=1):
            for label, pattern in SECRET_PATTERNS:
                if pattern.search(text_line):
                    findings.append(
                        Finding(
                            "secret_scan",
                            "error",
                            rel,
                            idx,
                            1,
                            label,
                            f"potential secret matched pattern: {label}",
                            confidence="high",
                            remediation="remove secret and load it from secure secret manager",
                            snippet=_safe_snippet(text_line),
                        )
                    )

            if any(w in text_line.lower() for w in SENSITIVE_WORDS):
                for tok in HIGH_ENTROPY_TOKEN.findall(text_line):
                    if _shannon_entropy(tok) >= 4.0:
                        findings.append(
                            Finding(
                                "secret_scan",
                                "error",
                                rel,
                                idx,
                                text_line.find(tok) + 1,
                                "high_entropy_secret",
                                "high-entropy token near sensitive keyword",
                                confidence="medium",
                                remediation="rotate and remove token from source",
                                snippet=_safe_snippet(tok),
                            )
                        )

            lower = text_line.lower().replace(" ", "")
            config_like = rel.endswith(
                (".env", ".ini", ".cfg", ".conf", ".toml", ".yaml", ".yml", ".json")
            )
            if config_like and ("debug=true" in lower or "allow_all_origins=true" in lower):
                findings.append(
                    Finding(
                        "config_hardening",
                        "warn",
                        rel,
                        idx,
                        1,
                        "dangerous_default",
                        "dangerous debug or allow-all default detected",
                        confidence="high",
                        remediation="disable debug and restrict origin permissions",
                    )
                )

        if profile == "enterprise" and rel.endswith(".py"):
            findings.extend(_scan_python_ast(rel, text))

        if (
            profile == "enterprise"
            and rel.startswith(".github/workflows/")
            and rel.endswith((".yml", ".yaml"))
        ):
            findings.extend(_scan_workflow(rel, text))

        if path.name in PRIVATE_KEY_FILES or path.suffix.lower() in PRIVATE_KEY_SUFFIXES:
            findings.append(
                Finding(
                    "config_leak",
                    "error",
                    rel,
                    1,
                    1,
                    "private_key_file",
                    "private key or certificate material committed",
                    confidence="high",
                    remediation="remove file from git history and rotate impacted credentials",
                )
            )

        if path.name in {".env", ".pypirc", ".npmrc", "config.json"}:
            findings.append(
                Finding(
                    "config_leak",
                    "error",
                    rel,
                    1,
                    1,
                    "sensitive_config_file",
                    "sensitive runtime config file committed",
                    confidence="medium",
                    remediation="avoid committing secrets-bearing config files",
                )
            )

    if profile == "enterprise":
        findings.extend(_scan_dependency_hygiene(root, only if changed_only else None))

    findings = _apply_baseline(findings, baseline)

    findings.sort(key=lambda f: (f.path, f.line, f.column, f.check, f.code, f.message))
    return findings


def _scan_python_ast(rel: str, text: str) -> list[Finding]:
    out: list[Finding] = []
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return out
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            name = ""
            if isinstance(node.func, ast.Name):
                name = node.func.id
            elif isinstance(node.func, ast.Attribute):
                name = f"{getattr(node.func.value, 'id', '')}.{node.func.attr}".lstrip(".")
            if name in {"eval", "exec", "pickle.loads", "yaml.load"}:
                out.append(
                    Finding(
                        "code_risk",
                        "error",
                        rel,
                        node.lineno,
                        node.col_offset + 1,
                        name.replace(".", "_"),
                        f"unsafe call: {name}",
                        remediation="use safer alternatives",
                    )
                )
            if name == "subprocess.run" or name == "subprocess.Popen":
                for kw in node.keywords:
                    if (
                        kw.arg == "shell"
                        and isinstance(kw.value, ast.Constant)
                        and kw.value.value is True
                    ):
                        out.append(
                            Finding(
                                "code_risk",
                                "error",
                                rel,
                                node.lineno,
                                node.col_offset + 1,
                                "subprocess_shell_true",
                                "subprocess with shell=True",
                                remediation="pass argv list and keep shell=False",
                            )
                        )
    return out


def _scan_workflow(rel: str, text: str) -> list[Finding]:
    out: list[Finding] = []
    for idx, line in enumerate(text.splitlines(), start=1):
        m = WORKFLOW_USE_RE.match(line)
        if m:
            uses = m.group(1)
            if "@" in uses and re.search(r"@[0-9a-f]{40}$", uses) is None:
                out.append(
                    Finding(
                        "gha_hardening",
                        "warn",
                        rel,
                        idx,
                        1,
                        "unpinned_action",
                        "GitHub Action is not pinned to full commit SHA",
                        remediation="pin action with @<40-char-SHA>",
                    )
                )
        lower = line.lower()
        if "pull_request_target" in lower:
            out.append(
                Finding(
                    "gha_hardening",
                    "error",
                    rel,
                    idx,
                    1,
                    "pull_request_target",
                    "pull_request_target requires strict hardening",
                    remediation="prefer pull_request unless privileged flow is required",
                )
            )
        if "permissions: write-all" in lower:
            out.append(
                Finding(
                    "gha_hardening",
                    "error",
                    rel,
                    idx,
                    1,
                    "write_all_permissions",
                    "workflow uses write-all permissions",
                    remediation="use least privilege permissions block",
                )
            )
        if "curl" in lower and "|" in lower and "bash" in lower:
            out.append(
                Finding(
                    "gha_hardening",
                    "error",
                    rel,
                    idx,
                    1,
                    "curl_bash",
                    "curl|bash pattern in workflow",
                    remediation="download, verify checksum/signature, then execute",
                )
            )
    return out


def _scan_dependency_hygiene(root: Path, only: set[str] | None) -> list[Finding]:
    out: list[Finding] = []
    has_py_manifest = (root / "pyproject.toml").exists() or (root / "requirements.txt").exists()
    has_node_manifest = (root / "package.json").exists()
    if has_py_manifest and not ((root / "poetry.lock").exists() or (root / "uv.lock").exists()):
        if only is None or "pyproject.toml" in only or "requirements.txt" in only:
            out.append(
                Finding(
                    "dependency_hygiene",
                    "warn",
                    "pyproject.toml",
                    1,
                    1,
                    "missing_python_lockfile",
                    "Python manifest found without lockfile",
                    remediation="add poetry.lock or uv.lock for deterministic installs",
                )
            )
    if has_node_manifest and not any(
        (root / x).exists() for x in ("package-lock.json", "pnpm-lock.yaml", "yarn.lock")
    ):
        if only is None or "package.json" in only:
            out.append(
                Finding(
                    "dependency_hygiene",
                    "warn",
                    "package.json",
                    1,
                    1,
                    "missing_node_lockfile",
                    "Node manifest found without lockfile",
                    remediation="commit a Node lockfile",
                )
            )

    req = root / "requirements.txt"
    if req.exists() and (only is None or "requirements.txt" in only):
        for i, line in enumerate(
            req.read_text(encoding="utf-8", errors="ignore").splitlines(), start=1
        ):
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            if UNPINNED_DEP_RE.match(stripped):
                out.append(
                    Finding(
                        "dependency_hygiene",
                        "warn",
                        "requirements.txt",
                        i,
                        1,
                        "unpinned_dependency",
                        "dependency is not pinned to exact version",
                        remediation="pin with == exact version",
                    )
                )
    return out


def _load_baseline(path: Path | None) -> list[dict[str, Any]]:
    if path is None or not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    if isinstance(data, list):
        return [x for x in data if isinstance(x, dict)]
    return []


def _apply_baseline(findings: list[Finding], baseline: list[dict[str, Any]]) -> list[Finding]:
    if not baseline:
        return findings
    active: list[dict[str, Any]] = []
    today = dt.date.today()
    for item in baseline:
        exp = item.get("expires")
        if isinstance(exp, str):
            try:
                if dt.date.fromisoformat(exp) < today:
                    continue
            except ValueError:
                pass
        active.append(item)

    out: list[Finding] = []
    for finding in findings:
        matched = False
        for item in active:
            if item.get("path") and item.get("path") != finding.path:
                continue
            if item.get("check") and item.get("check") != finding.check:
                continue
            if item.get("code") and item.get("code") != finding.code:
                continue
            matched = True
            break
        if not matched:
            out.append(finding)
    return out


def _severity_rank(level: str) -> int:
    return {"info": 0, "warn": 1, "error": 2}.get(level, 2)


def _score(findings: list[Finding]) -> int:
    if not findings:
        return 100
    weights = {"warn": 5, "error": 20}
    penalty = sum(weights.get(f.severity, 20) for f in findings)
    return max(0, 100 - min(100, penalty))


def _report_payload(
    root: Path, findings: list[Finding], *, profile: str, policy_text: str | None
) -> dict[str, Any]:
    counts = {"info": 0, "warn": 0, "error": 0}
    by_check: dict[str, int] = {}
    for f in findings:
        counts[f.severity] = counts.get(f.severity, 0) + 1
        by_check[f.check] = by_check.get(f.check, 0) + 1
    policy_hash = hashlib.sha256((policy_text or "").encode("utf-8")).hexdigest()
    return {
        "root": str(root),
        "metadata": {
            "tool": "sdetkit",
            "version": "0.2.8",
            "profile": profile,
            "git_commit": _git_commit_sha(root),
            "generated_at_utc": dt.datetime.now(_UTC).isoformat()
            if profile == "enterprise"
            else "",
            "policy_hash": policy_hash,
        },
        "summary": {
            "counts": {k: counts[k] for k in sorted(counts)},
            "by_check": {k: by_check[k] for k in sorted(by_check)},
            "findings": len(findings),
            "score": _score(findings),
            "ok": not findings,
        },
        "findings": [f.to_dict() for f in findings],
    }


def _to_sarif(payload: dict[str, Any]) -> dict[str, Any]:
    def _sarif_uri(path: str) -> str:
        normalized = path.replace("\\", "/")
        while normalized.startswith("./"):
            normalized = normalized[2:]
        if re.match(r"^[A-Za-z]:/", normalized):
            normalized = normalized[3:]
        normalized = normalized.lstrip("/")
        return normalized or "."

    rules: dict[str, dict[str, Any]] = {}
    results: list[dict[str, Any]] = []
    for item in payload["findings"]:
        rid = str(
            item.get("rule_id")
            or f"{item.get('check', 'repo_audit')}/{item.get('code', 'unknown')}"
        )
        if rid not in rules:
            rules[rid] = {
                "id": rid,
                "name": rid,
                "shortDescription": {"text": str(item.get("message", rid))},
                "help": {"text": str(item.get("remediation", item.get("message", "")))},
            }
        results.append(
            {
                "ruleId": rid,
                "level": (
                    "error"
                    if item["severity"] == "error"
                    else "warning"
                    if item["severity"] == "warn"
                    else "note"
                ),
                "message": {"text": item["message"]},
                "properties": {
                    "pack": item.get("pack", "core"),
                    "fixable": bool(item.get("fixable", False)),
                },
                "locations": [
                    {
                        "physicalLocation": {
                            "artifactLocation": {"uri": _sarif_uri(str(item.get("path") or "."))},
                            "region": {
                                "startLine": item.get("line", 1),
                                "startColumn": item.get("column", 1),
                            },
                        }
                    }
                ],
            }
        )
    rules_list = [rules[key] for key in sorted(rules)]
    return {
        "$schema": "https://json.schemastore.org/sarif-2.1.0.json",
        "version": "2.1.0",
        "runs": [
            {
                "tool": {"driver": {"name": "sdetkit", "rules": rules_list}},
                "results": results,
            }
        ],
    }


def _generate_sbom(root: Path) -> dict[str, Any]:
    components: list[dict[str, str]] = []
    pyproject = root / "pyproject.toml"
    if pyproject.exists():
        text = pyproject.read_text(encoding="utf-8", errors="ignore")
        for dep in re.findall(r"[\"\']([A-Za-z0-9_.-]+)(?:[^\"\']*)[\"\']", text):
            if dep.lower() in {"project", "dependencies", "name", "x"}:
                continue
            components.append({"type": "library", "name": dep, "purl": f"pkg:pypi/{dep}"})
    package_json = root / "package.json"
    if package_json.exists():
        try:
            pj = json.loads(package_json.read_text(encoding="utf-8"))
        except ValueError:
            pj = {}
        deps = pj.get("dependencies", {})
        if isinstance(deps, dict):
            for name in sorted(deps):
                components.append({"type": "library", "name": name, "purl": f"pkg:npm/{name}"})

    return {
        "bomFormat": "CycloneDX",
        "specVersion": "1.5",
        "version": 1,
        "metadata": {"component": {"type": "application", "name": root.name}},
        "components": components,
    }


def _render(payload: dict[str, Any], fmt: str) -> str:
    if fmt == "json":
        return json.dumps(payload, ensure_ascii=True, sort_keys=True, indent=2) + "\n"
    if fmt == "sarif":
        return json.dumps(_to_sarif(payload), ensure_ascii=True, sort_keys=True, indent=2) + "\n"
    if fmt == "md":
        lines = [
            "# sdetkit repo check report",
            "",
            f"- root: `{payload['root']}`",
            f"- score: {payload['summary']['score']}",
            f"- findings: {payload['summary']['findings']}",
            "",
            "## Findings",
        ]
        for item in payload["findings"]:
            lines.append(
                f"- `{item['severity']}` `{item['check']}` `{item['path']}:{item['line']}:{item['column']}` - {item['message']}"
            )
        return "\n".join(lines) + "\n"

    lines = [
        f"repo: {payload['root']}",
        f"score: {payload['summary']['score']}",
        f"findings: {payload['summary']['findings']}",
    ]
    for item in payload["findings"]:
        lines.append(
            f"[{item['severity']}] {item['path']}:{item['line']}:{item['column']} {item['check']}/{item['code']} {item['message']}"
        )
    return "\n".join(lines) + "\n"


def _needs_fail(findings: list[Finding], fail_on: str | None, min_score: int | None) -> bool:
    if min_score is not None and _score(findings) < min_score:
        return True
    if fail_on is None:
        return bool(findings)
    threshold = _severity_rank(fail_on)
    return any(_severity_rank(f.severity) >= threshold for f in findings)


def _fix_text(text: str, *, eol: str | None) -> str:
    lines = text.splitlines(keepends=True)
    out: list[str] = []
    for line in lines:
        eol_part = ""
        content = line
        if line.endswith("\r\n"):
            content = line[:-2]
            eol_part = "\r\n"
        elif line.endswith("\n"):
            content = line[:-1]
            eol_part = "\n"
        elif line.endswith("\r"):
            content = line[:-1]
            eol_part = "\r"
        content = content.rstrip(" \t")
        if eol is None:
            out.append(content + eol_part)
        elif eol == "lf":
            out.append(content + ("\n" if eol_part else ""))
        else:
            out.append(content + ("\r\n" if eol_part else ""))

    fixed = "".join(out)
    if fixed and not fixed.endswith("\n") and not fixed.endswith("\r\n"):
        fixed += "\n" if eol != "crlf" else "\r\n"
    return fixed


def _apply_fixes(root: Path, *, check: bool, dry_run: bool, diff: bool, eol: str | None) -> int:
    changed = 0
    for path in _iter_files(root):
        rel = path.relative_to(root).as_posix()
        try:
            original_bytes = path.read_bytes()
            original = original_bytes.decode("utf-8")
        except (OSError, UnicodeDecodeError):
            continue

        fixed = _fix_text(original, eol=eol)
        if fixed == original:
            continue

        changed += 1
        if diff or check or dry_run:
            d = difflib.unified_diff(
                original.splitlines(keepends=True),
                fixed.splitlines(keepends=True),
                fromfile=f"a/{rel}",
                tofile=f"b/{rel}",
            )
            sys.stdout.write("".join(d))

        if not check and not dry_run:
            atomic_write_text(path, fixed)

    if check:
        return 1 if changed else 0
    if dry_run:
        return 0
    return 0


def _resolve_root(user_path: str, *, allow_absolute: bool) -> Path:
    base = Path.cwd().resolve()
    try:
        return safe_path(base, user_path, allow_absolute=allow_absolute)
    except SecurityError:
        raise


def _init_templates(profile: str) -> dict[str, str]:
    templates = dict(DEFAULT_INIT_TEMPLATES)
    if profile == "enterprise":
        templates.update(ENTERPRISE_INIT_TEMPLATES)
    return dict(sorted(templates.items()))


def _plan_repo_init(
    root: Path, *, profile: str, force: bool
) -> tuple[list[RepoInitChange], list[str]]:
    changes: list[RepoInitChange] = []
    conflicts: list[str] = []
    for rel, desired in _init_templates(profile).items():
        target = safe_path(root, rel, allow_absolute=False)
        if not target.exists():
            changes.append(RepoInitChange(path=rel, action="create", current="", desired=desired))
            continue
        try:
            current = target.read_text(encoding="utf-8")
        except OSError:
            conflicts.append(rel)
            continue
        if current == desired:
            continue
        if not force:
            conflicts.append(rel)
            continue
        changes.append(RepoInitChange(path=rel, action="update", current=current, desired=desired))
    return changes, sorted(conflicts)


def _print_repo_init_plan(changes: list[RepoInitChange], *, apply: bool) -> None:
    mode = "apply" if apply else "dry-run"
    if not changes:
        print(f"repo init ({mode}): no changes")
        return
    for change in changes:
        print(f"{change.action.upper():<6} {change.path}")
    creates = sum(1 for item in changes if item.action == "create")
    updates = sum(1 for item in changes if item.action == "update")
    print(f"repo init ({mode}): {len(changes)} planned (create={creates}, update={updates})")


def _print_repo_init_diff(changes: list[RepoInitChange]) -> None:
    for change in changes:
        diff = difflib.unified_diff(
            change.current.splitlines(keepends=True),
            change.desired.splitlines(keepends=True),
            fromfile=f"a/{change.path}",
            tofile=f"b/{change.path}",
        )
        sys.stdout.write("".join(diff))


def _run_repo_init(root: Path, *, profile: str, apply: bool, force: bool, diff: bool) -> int:
    changes, conflicts = _plan_repo_init(root, profile=profile, force=force)
    if conflicts:
        for rel in conflicts:
            print(f"refusing to overwrite existing file: {rel} (use --force)", file=sys.stderr)
        return 2
    _print_repo_init_plan(changes, apply=apply)
    if diff and changes:
        _print_repo_init_diff(changes)
    if not apply:
        return 0
    for change in changes:
        target = safe_path(root, change.path, allow_absolute=False)
        target.parent.mkdir(parents=True, exist_ok=True)
        atomic_write_text(target, change.desired)
    print(f"repo init: wrote {len(changes)} file(s)")
    return 0


def _plan_repo_fix_audit(
    root: Path,
    *,
    profile: str,
    packs: tuple[str, ...],
    policy: RepoAuditPolicy,
    allow_absolute_path: bool,
    force: bool,
) -> tuple[list[Fix], list[str], dict[str, Any]]:
    payload = run_repo_audit(root, profile=profile, packs=packs)
    baseline_path = safe_path(root, policy.baseline_path, allow_absolute=allow_absolute_path)
    baseline_doc = _load_repo_baseline(baseline_path)
    actionable, suppression = _apply_repo_audit_policy(
        list(payload.get("findings", [])), policy, baseline_doc.get("entries", [])
    )
    by_rule: dict[str, list[PluginFinding]] = {}
    for item in actionable:
        rule_id = str(item.get("rule_id") or _repo_rule_id(item))
        by_rule.setdefault(rule_id, []).append(
            PluginFinding(
                rule_id=rule_id,
                severity=str(item.get("severity", "warn")),
                message=str(item.get("message", "")),
                path=str(item.get("path", ".")),
                line=int(item.get("line", 1)),
                details={
                    "pack": item.get("pack", "core"),
                    "fixable": bool(item.get("fixable", False)),
                    "fingerprint": item.get("fingerprint", ""),
                },
                fingerprint=str(item.get("fingerprint", "")),
            )
        )

    catalog = load_rule_catalog()
    fixer_map = catalog.fixer_map()
    fixes: list[Fix] = []
    conflicts: list[str] = []
    for rule_id in sorted(by_rule):
        fixer = fixer_map.get(rule_id)
        if fixer is None:
            continue
        generated = fixer.fix(root, by_rule[rule_id], {"profile": profile, "packs": packs})
        for fix in generated:
            if not force and not fix.safe:
                continue
            approved_changes = []
            for edit in fix.changes:
                target = root / edit.path
                if (
                    target.exists()
                    and target.read_text(encoding="utf-8") != edit.old_text
                    and not force
                ):
                    conflicts.append(edit.path)
                    continue
                approved_changes.append(edit)
            if approved_changes:
                fixes.append(
                    Fix(
                        rule_id=fix.rule_id,
                        description=fix.description,
                        safe=fix.safe,
                        changes=tuple(approved_changes),
                    )
                )

    fixes.sort(key=lambda item: (item.rule_id, item.description))
    conflicts = sorted(set(conflicts))
    return (
        fixes,
        conflicts,
        {"payload": payload, "suppression": suppression, "actionable": actionable},
    )


def _print_fix_plan(fixes: list[Fix], *, apply: bool) -> None:
    mode = "apply" if apply else "dry-run"
    if not fixes:
        print(f"repo fix-audit ({mode}): no changes")
        return
    for fix in fixes:
        for edit in fix.changes:
            print(f"PLAN  {fix.rule_id:<36} {edit.path}")
    print(f"repo fix-audit ({mode}): {sum(len(f.changes) for f in fixes)} file change(s)")


def _unified_diff_for_edit(path: str, old_text: str, new_text: str) -> str:
    return "".join(
        difflib.unified_diff(
            old_text.splitlines(keepends=True),
            new_text.splitlines(keepends=True),
            fromfile=f"a/{path}",
            tofile=f"b/{path}",
            lineterm="",
        )
    )


def _run_repo_fix_audit(
    root: Path,
    *,
    profile: str,
    packs: tuple[str, ...],
    policy: RepoAuditPolicy,
    dry_run: bool,
    apply: bool,
    force: bool,
    show_diff: bool,
    patch_path: str | None,
    allow_absolute_path: bool,
) -> int:
    fixes, conflicts, _ = _plan_repo_fix_audit(
        root,
        profile=profile,
        packs=packs,
        policy=policy,
        allow_absolute_path=allow_absolute_path,
        force=force,
    )
    if conflicts:
        for rel in conflicts:
            print(f"refusing to overwrite existing file: {rel} (use --force)", file=sys.stderr)
        return 2

    _print_fix_plan(fixes, apply=apply)
    all_edits = sorted([edit for fix in fixes for edit in fix.changes], key=lambda item: item.path)
    patch_data = "".join(
        _unified_diff_for_edit(edit.path, edit.old_text, edit.new_text) for edit in all_edits
    )

    if show_diff and patch_data:
        sys.stdout.write(patch_data)
    if patch_path:
        patch_target = safe_path(root, patch_path, allow_absolute=allow_absolute_path)
        if patch_target.exists() and not force:
            print("refusing to overwrite existing patch output (use --force)", file=sys.stderr)
            return 2
        atomic_write_text(patch_target, patch_data.replace("\r\n", "\n"))

    if dry_run or not apply:
        return 0

    for edit in all_edits:
        target = safe_path(root, edit.path, allow_absolute=False)
        target.parent.mkdir(parents=True, exist_ok=True)
        atomic_write_text(target, edit.new_text.replace("\r\n", "\n"))
    print(f"repo fix-audit: wrote {len(all_edits)} file(s)")
    return 0


def _audit_oss_readiness(root: Path) -> RepoAuditCheck:
    required = (
        "README.md",
        "LICENSE",
        "CONTRIBUTING.md",
        "CODE_OF_CONDUCT.md",
        "SECURITY.md",
        "CHANGELOG.md",
    )
    missing = [name for name in required if not (root / name).exists()]
    if not missing:
        return RepoAuditCheck(
            key="oss_readiness",
            title="OSS readiness files",
            passed=True,
            details=("All required governance files are present.",),
        )
    return RepoAuditCheck(
        key="oss_readiness",
        title="OSS readiness files",
        passed=False,
        details=tuple(f"Missing: {name}" for name in missing),
        findings=tuple(
            Finding(
                check="repo_audit",
                severity="error",
                path=name,
                line=1,
                column=1,
                code="missing_required_file",
                message=f"required OSS readiness file is missing: {name}",
                confidence="high",
                remediation="add the missing governance file",
            )
            for name in missing
        ),
    )


def _audit_ci_security_workflows(root: Path) -> RepoAuditCheck:
    workflows_dir = root / ".github" / "workflows"
    workflow_files: list[str] = []
    if workflows_dir.exists() and workflows_dir.is_dir():
        workflow_files = sorted(
            p.name for p in workflows_dir.iterdir() if p.is_file() and p.suffix in {".yml", ".yaml"}
        )

    ci_present = any("ci" in name for name in workflow_files)
    security_present = any(
        "security" in name or "codeql" in name or "dependabot" in name for name in workflow_files
    )
    details = [
        "Discovered workflows: " + (", ".join(workflow_files) if workflow_files else "none"),
        f"CI workflow present: {'yes' if ci_present else 'no'}",
        f"Security workflow present: {'yes' if security_present else 'no'}",
    ]
    findings: list[Finding] = []
    if not ci_present:
        findings.append(
            Finding(
                check="repo_audit",
                severity="error",
                path=".github/workflows",
                line=1,
                column=1,
                code="missing_ci_workflow",
                message="no CI workflow detected under .github/workflows",
                confidence="high",
                remediation="add a CI workflow file (e.g. ci.yml)",
            )
        )
    if not security_present:
        findings.append(
            Finding(
                check="repo_audit",
                severity="error",
                path=".github/workflows",
                line=1,
                column=1,
                code="missing_security_workflow",
                message="no security workflow detected under .github/workflows",
                confidence="high",
                remediation="add a security workflow file (e.g. security.yml)",
            )
        )
    return RepoAuditCheck(
        key="ci_security_workflows",
        title="CI and security workflow presence",
        passed=ci_present and security_present,
        details=tuple(details),
        findings=tuple(findings),
    )


def _audit_python_tooling(root: Path) -> RepoAuditCheck:
    checks = {
        "pyproject.toml": (root / "pyproject.toml").exists(),
        "noxfile.py": (root / "noxfile.py").exists(),
        "quality.sh": (root / "quality.sh").exists(),
        "requirements-test.txt": (root / "requirements-test.txt").exists(),
    }
    missing = [name for name, present in checks.items() if not present]
    details = tuple(
        f"{name}: {'present' if present else 'missing'}" for name, present in sorted(checks.items())
    )
    findings = tuple(
        Finding(
            check="repo_audit",
            severity="error",
            path=name,
            line=1,
            column=1,
            code="missing_python_tooling",
            message=f"required Python tooling file is missing: {name}",
            confidence="high",
            remediation="add the missing tooling file or adjust project standards",
        )
        for name in missing
    )
    return RepoAuditCheck(
        key="python_tooling",
        title="Python tooling config presence",
        passed=len(missing) == 0,
        details=details,
        findings=findings,
    )


def _audit_repo_hygiene(root: Path) -> RepoAuditCheck:
    checks = {
        ".gitignore": (root / ".gitignore").exists(),
        "tests/": (root / "tests").is_dir(),
        "docs/": (root / "docs").is_dir(),
    }
    large_files: list[str] = []
    for p in _iter_files(root):
        try:
            size = p.stat().st_size
        except OSError:
            continue
        if size > 5 * 1024 * 1024:
            large_files.append(f"{p.relative_to(root).as_posix()} ({size} bytes)")

    details = [
        f"{name}: {'present' if present else 'missing'}" for name, present in sorted(checks.items())
    ]
    if large_files:
        details.extend(f"Large tracked file: {item}" for item in sorted(large_files))
    else:
        details.append("No files larger than 5 MiB detected.")
    findings: list[Finding] = []
    for name, present in sorted(checks.items()):
        if not present:
            findings.append(
                Finding(
                    check="repo_audit",
                    severity="error",
                    path=name.rstrip("/"),
                    line=1,
                    column=1,
                    code="missing_repo_hygiene_item",
                    message=f"required repository hygiene item is missing: {name}",
                    confidence="high",
                    remediation="add the missing repository hygiene file/directory",
                )
            )
    for item in sorted(large_files):
        findings.append(
            Finding(
                check="repo_audit",
                severity="warn",
                path=item.split(" ", 1)[0],
                line=1,
                column=1,
                code="large_tracked_file",
                message=f"tracked file exceeds 5 MiB: {item}",
                confidence="high",
                remediation="move binaries to artifacts/storage and keep source repo lean",
            )
        )

    return RepoAuditCheck(
        key="repo_hygiene",
        title="Basic repository hygiene",
        passed=all(checks.values()) and not large_files,
        details=tuple(details),
        findings=tuple(findings),
    )


def _plugin_finding_to_dict(finding: PluginFinding, meta: RuleMeta) -> dict[str, Any]:
    normalized = finding.with_fingerprint()
    path = normalized.path or "."
    details = dict(normalized.details or {})
    pack = str(details.get("pack") or "core")
    return {
        "check": "repo_audit",
        "code": normalized.rule_id,
        "rule_id": normalized.rule_id,
        "severity": normalized.severity,
        "path": path,
        "line": normalized.line or 1,
        "column": 1,
        "message": normalized.message,
        "confidence": "high",
        "remediation": meta.description,
        "snippet": "",
        "fingerprint": normalized.fingerprint,
        "pack": pack,
        "fixable": bool(meta.supports_fix),
    }


def run_repo_audit(
    root: Path, *, profile: str = "default", packs: tuple[str, ...] | None = None
) -> dict[str, Any]:
    catalog = load_rule_catalog()
    selected_packs = packs or normalize_packs(profile, None)
    selected_rules = select_rules(catalog, selected_packs)

    findings: list[dict[str, Any]] = []
    checks: list[dict[str, Any]] = []
    context: dict[str, Any] = {"profile": profile, "packs": selected_packs}
    for loaded in selected_rules:
        rule_findings = loaded.plugin.run(root, context)
        checks.append(
            {
                "key": loaded.meta.id,
                "title": loaded.meta.title,
                "status": "pass" if not rule_findings else "fail",
                "details": [loaded.meta.description],
                "pack": next(
                    (t.split(":", 1)[1] for t in loaded.meta.tags if t.startswith("pack:")), "core"
                ),
                "supports_fix": loaded.meta.supports_fix,
            }
        )
        for finding in rule_findings:
            findings.append(_plugin_finding_to_dict(finding, loaded.meta))

    counts = {"info": 0, "warn": 0, "error": 0}
    for finding_item in findings:
        sev = str(finding_item.get("severity", "error"))
        counts[sev] = counts.get(sev, 0) + 1

    checks.sort(key=lambda x: str(x["key"]))
    findings.sort(
        key=lambda x: (str(x.get("path", "")), str(x.get("rule_id", "")), str(x.get("message", "")))
    )
    return {
        "schema_version": "1.1.0",
        "root": str(root),
        "summary": {
            "checks": len(checks),
            "passed": sum(1 for item in checks if item["status"] == "pass"),
            "failed": sum(1 for item in checks if item["status"] == "fail"),
            "ok": not findings,
            "counts": {k: counts[k] for k in sorted(counts)},
            "findings": len(findings),
            "packs": list(selected_packs),
        },
        "checks": checks,
        "findings": findings,
    }


def list_repo_rules(
    *, profile: str = "default", packs: tuple[str, ...] | None = None
) -> list[dict[str, Any]]:
    catalog = load_rule_catalog()
    selected_packs = packs or normalize_packs(profile, None)
    selected_rules = select_rules(catalog, selected_packs)
    rules = []
    for loaded in selected_rules:
        pack = next((t.split(":", 1)[1] for t in loaded.meta.tags if t.startswith("pack:")), "core")
        rules.append(
            {
                "rule_id": loaded.meta.id,
                "title": loaded.meta.title,
                "description": loaded.meta.description,
                "severity": loaded.meta.default_severity,
                "pack": pack,
                "tags": list(loaded.meta.tags),
                "fixable": loaded.meta.supports_fix,
            }
        )
    rules.sort(key=lambda x: str(x["rule_id"]))
    return rules


def _render_repo_audit(payload: dict[str, Any], fmt: str) -> str:
    if fmt == "json":
        return json.dumps(payload, ensure_ascii=True, sort_keys=True, indent=2) + "\n"
    if fmt == "sarif":
        sarif_payload = {
            "findings": payload.get("findings", []),
        }
        return (
            json.dumps(_to_sarif(sarif_payload), ensure_ascii=True, sort_keys=True, indent=2) + "\n"
        )

    lines = [
        f"Repo audit: {payload['root']}",
        (
            "Result: PASS"
            if payload["summary"]["ok"]
            else f"Result: FAIL ({payload['summary']['failed']} checks failed)"
        ),
        (f"Checks: {payload['summary']['passed']}/{payload['summary']['checks']} passed"),
        (
            "Findings: "
            f"{payload['summary']['findings']} (warn={payload['summary']['counts']['warn']}, "
            f"error={payload['summary']['counts']['error']})"
        ),
        "",
    ]
    policy_summary = payload.get("summary", {}).get("policy")
    if isinstance(policy_summary, dict):
        lines.extend(
            [
                "Suppression summary:",
                f"  - total findings: {policy_summary.get('total_findings', 0)}",
                f"  - suppressed by baseline: {policy_summary.get('suppressed_by_baseline', 0)}",
                f"  - suppressed by policy: {policy_summary.get('suppressed_by_policy', 0)}",
                f"  - actionable: {policy_summary.get('actionable', payload['summary']['findings'])}",
                "",
            ]
        )
    for item in payload["checks"]:
        icon = "PASS" if item["status"] == "pass" else "FAIL"
        lines.append(f"[{icon}] {item['title']} ({item['key']})")
        for detail in item["details"]:
            lines.append(f"  - {detail}")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def _needs_fail_repo_audit(findings: list[dict[str, Any]], fail_on: str) -> bool:
    if fail_on == "none":
        return False
    if fail_on == "error":
        return any(str(item.get("severity")) == "error" for item in findings)
    return any(
        _severity_rank(str(item.get("severity", "error"))) >= _severity_rank("warn")
        for item in findings
    )


def _repo_audit_profile_defaults(profile: str) -> RepoAuditPolicy:
    return RepoAuditPolicy(
        profile=profile,
        fail_on="warn",
        baseline_path=".sdetkit/audit-baseline.json",
        exclude_paths=(),
        disable_rules=frozenset(),
        severity_overrides={},
        allowlist=(),
    )


def _load_repo_audit_config(root: Path, config_path: Path | None) -> dict[str, Any]:
    candidate = root / "pyproject.toml" if config_path is None else config_path
    if not candidate.exists():
        return {}
    try:
        data = cast(Any, _tomllib).loads(candidate.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise RepoAuditConfigError(f"unable to parse repo audit config: {exc}") from exc
    if not isinstance(data, dict):
        return {}
    tool = data.get("tool")
    if not isinstance(tool, dict):
        return {}
    sdetkit = tool.get("sdetkit")
    if not isinstance(sdetkit, dict):
        return {}
    cfg = sdetkit.get("repo_audit")
    if cfg is None:
        return {}
    if not isinstance(cfg, dict):
        raise RepoAuditConfigError("[tool.sdetkit.repo_audit] must be a TOML table")
    return cfg


def _as_str_list(value: Any, *, field: str) -> tuple[str, ...]:
    if value is None:
        return ()
    if not isinstance(value, list) or any(not isinstance(x, str) for x in value):
        raise RepoAuditConfigError(f"config field '{field}' must be a list of strings")
    return tuple(value)


def _resolve_repo_audit_policy(
    root: Path,
    *,
    cli_profile: str | None,
    cli_fail_on: str | None,
    cli_baseline: str | None,
    cli_excludes: list[str] | None,
    cli_disable_rules: list[str] | None,
    config_path: Path | None,
) -> RepoAuditPolicy:
    raw = _load_repo_audit_config(root, config_path)
    profile = cli_profile or str(raw.get("profile") or "default")
    if profile not in {"default", "enterprise"}:
        raise RepoAuditConfigError("profile must be 'default' or 'enterprise'")
    base = _repo_audit_profile_defaults(profile)

    fail_on = str(raw.get("fail_on") or base.fail_on)
    if fail_on not in {"none", "warn", "error"}:
        raise RepoAuditConfigError("fail_on must be one of: none, warn, error")

    baseline_path = str(raw.get("baseline_path") or base.baseline_path)
    exclude_paths = tuple(base.exclude_paths) + _as_str_list(
        raw.get("exclude_paths"), field="exclude_paths"
    )
    disable_rules = set(base.disable_rules)
    disable_rules.update(_as_str_list(raw.get("disable_rules"), field="disable_rules"))

    raw_overrides = raw.get("severity_overrides") or {}
    if not isinstance(raw_overrides, dict):
        raise RepoAuditConfigError("severity_overrides must be a map")
    severity_overrides = dict(base.severity_overrides)
    for rule_id, level in raw_overrides.items():
        if not isinstance(rule_id, str) or not isinstance(level, str):
            raise RepoAuditConfigError("severity_overrides keys and values must be strings")
        if level not in {"info", "warn", "error"}:
            raise RepoAuditConfigError("severity_overrides values must be info|warn|error")
        severity_overrides[rule_id] = level

    raw_allowlist = raw.get("allowlist") or []
    if not isinstance(raw_allowlist, list):
        raise RepoAuditConfigError("allowlist must be a list")
    allowlist: list[AllowlistRule] = []
    for item in raw_allowlist:
        if not isinstance(item, dict):
            raise RepoAuditConfigError("allowlist entries must be tables")
        rule_id = item.get("rule_id")
        path = item.get("path")
        contains = item.get("contains")
        if not isinstance(rule_id, str) or not isinstance(path, str):
            raise RepoAuditConfigError("allowlist entries require string rule_id and path")
        if contains is not None and not isinstance(contains, str):
            raise RepoAuditConfigError("allowlist contains must be a string when provided")
        allowlist.append(AllowlistRule(rule_id=rule_id, path=path, contains=contains))

    if cli_fail_on is not None:
        fail_on = cli_fail_on
    if cli_baseline is not None:
        baseline_path = cli_baseline
    if cli_excludes:
        exclude_paths = exclude_paths + tuple(cli_excludes)
    if cli_disable_rules:
        disable_rules.update(cli_disable_rules)

    return RepoAuditPolicy(
        profile=profile,
        fail_on=fail_on,
        baseline_path=baseline_path,
        exclude_paths=tuple(exclude_paths),
        disable_rules=frozenset(disable_rules),
        severity_overrides=severity_overrides,
        allowlist=tuple(allowlist),
    )


def _repo_rule_id(item: dict[str, Any]) -> str:
    explicit = item.get("rule_id")
    if isinstance(explicit, str) and explicit:
        return explicit
    return f"{item.get('check', 'repo_audit')}/{item.get('code', 'unknown')}"


def _repo_finding_fingerprint(item: dict[str, Any]) -> str:
    normalized = str(item.get("path", ".")).replace("\\", "/").lstrip("/")
    payload = "|".join([_repo_rule_id(item), normalized, str(item.get("message", ""))])
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _finding_matches_glob(path: str, pattern: str) -> bool:
    return Path(path).match(pattern)


def _apply_repo_audit_policy(
    findings: list[dict[str, Any]],
    policy: RepoAuditPolicy,
    baseline_entries: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    baseline_fingerprints = {
        str(item.get("fingerprint"))
        for item in baseline_entries
        if isinstance(item, dict) and isinstance(item.get("fingerprint"), str)
    }
    actionable: list[dict[str, Any]] = []
    suppressed: list[dict[str, str]] = []
    for finding in findings:
        item = dict(finding)
        rule_id = _repo_rule_id(item)
        item["rule_id"] = rule_id
        item["fingerprint"] = _repo_finding_fingerprint(item)
        aliases = {rule_id, str(item.get("code", "")), f"repo_audit/{item.get('code', '')}"}
        for key in sorted(aliases):
            if key in policy.severity_overrides:
                item["severity"] = policy.severity_overrides[key]
                break
        if any(_finding_matches_glob(str(item.get("path", "")), g) for g in policy.exclude_paths):
            suppressed.append(
                {"fingerprint": item["fingerprint"], "reason": "policy:exclude_paths"}
            )
            continue
        if any(alias in policy.disable_rules for alias in aliases):
            suppressed.append(
                {"fingerprint": item["fingerprint"], "reason": "policy:disable_rules"}
            )
            continue
        allowlisted = False
        for rule in policy.allowlist:
            if rule.rule_id not in aliases:
                continue
            if not _finding_matches_glob(str(item.get("path", "")), rule.path):
                continue
            if rule.contains and rule.contains not in str(item.get("message", "")):
                continue
            allowlisted = True
            break
        if allowlisted:
            suppressed.append({"fingerprint": item["fingerprint"], "reason": "policy:allowlist"})
            continue
        if item["fingerprint"] in baseline_fingerprints:
            suppressed.append({"fingerprint": item["fingerprint"], "reason": "baseline"})
            continue
        actionable.append(item)
    actionable.sort(
        key=lambda x: (str(x.get("path", "")), str(x.get("rule_id", "")), str(x.get("message", "")))
    )
    suppressed.sort(key=lambda x: (x["reason"], x["fingerprint"]))
    counts = {
        "baseline": sum(1 for x in suppressed if x["reason"] == "baseline"),
        "policy": sum(1 for x in suppressed if x["reason"].startswith("policy:")),
    }
    return actionable, {"counts": counts, "suppressed": suppressed}


def _baseline_entries_from_findings(findings: list[dict[str, Any]]) -> list[dict[str, Any]]:
    entries = []
    for item in findings:
        entries.append(
            {
                "rule_id": _repo_rule_id(item),
                "path": str(item.get("path", ".")),
                "fingerprint": _repo_finding_fingerprint(item),
                "severity": str(item.get("severity", "error")),
                "message_key": str(item.get("message", "")),
            }
        )
    entries.sort(key=lambda x: (x["path"], x["rule_id"], x["fingerprint"]))
    return entries


def _load_repo_baseline(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"schema_version": "1.0", "entries": []}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise RepoAuditConfigError(f"unable to read baseline: {exc}") from exc
    if not isinstance(data, dict):
        raise RepoAuditConfigError("baseline must be a JSON object")
    entries = data.get("entries", [])
    if not isinstance(entries, list):
        raise RepoAuditConfigError("baseline entries must be a list")
    normalized = [x for x in entries if isinstance(x, dict)]
    return {
        "schema_version": str(data.get("schema_version", "1.0")),
        "created_at": data.get("created_at"),
        "tool_version": data.get("tool_version"),
        "entries": normalized,
    }


def _write_repo_baseline(path: Path, entries: list[dict[str, Any]]) -> None:
    payload = {
        "schema_version": "1.0",
        "tool_version": "0.2.8",
        "entries": entries,
    }
    atomic_write_text(path, json.dumps(payload, ensure_ascii=True, sort_keys=True, indent=2) + "\n")


def _baseline_diff(old_entries: list[dict[str, Any]], new_entries: list[dict[str, Any]]) -> str:
    old_lines = [f"{x['rule_id']}|{x['path']}|{x['fingerprint']}" for x in old_entries]
    new_lines = [f"{x['rule_id']}|{x['path']}|{x['fingerprint']}" for x in new_entries]
    diff = list(
        difflib.unified_diff(
            old_lines, new_lines, fromfile="baseline(old)", tofile="baseline(new)", lineterm=""
        )
    )
    if len(diff) <= 12:
        return "\n".join(diff)
    return "\n".join(diff[:12] + [f"... ({len(diff) - 12} more lines)"])


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="sdetkit repo")
    sub = parser.add_subparsers(dest="repo_cmd", required=True)

    cp = sub.add_parser("check")
    cp.add_argument("path", nargs="?", default=".")
    cp.add_argument("--format", choices=["text", "json", "md", "sarif"], default="text")
    cp.add_argument("--out", default=None)
    cp.add_argument("--force", action="store_true")
    cp.add_argument("--allow-absolute-path", action="store_true")
    cp.add_argument("--fail-on", choices=["info", "warn", "error"], default=None)
    cp.add_argument("--min-score", type=int, default=None)
    cp.add_argument("--profile", choices=["default", "enterprise"], default="default")
    cp.add_argument("--changed-only", action="store_true")
    cp.add_argument("--diff-base", default="origin/main")
    cp.add_argument("--baseline", default=None)
    cp.add_argument("--policy", default=None)
    cp.add_argument("--sbom-out", default=None)

    fp = sub.add_parser("fix")
    fp.add_argument("path", nargs="?", default=".")
    fp.add_argument("--check", action="store_true")
    fp.add_argument("--dry-run", action="store_true")
    fp.add_argument("--diff", action="store_true")
    fp.add_argument("--eol", choices=["lf", "crlf"], default=None)
    fp.add_argument("--force", action="store_true")
    fp.add_argument("--allow-absolute-path", action="store_true")

    ip = sub.add_parser("init")
    ip.add_argument("path", nargs="?", default=".")
    ip.add_argument("--profile", choices=["default", "enterprise"], default="default")
    ip.add_argument("--dry-run", action="store_true")
    ip.add_argument("--apply", action="store_true")
    ip.add_argument("--force", action="store_true")
    ip.add_argument("--diff", action="store_true")
    ip.add_argument("--allow-absolute-path", action="store_true")

    bp = sub.add_parser("baseline")
    bsub = bp.add_subparsers(dest="baseline_cmd", required=True)

    bcreate = bsub.add_parser("create")
    bcreate.add_argument("path", nargs="?", default=".")
    bcreate.add_argument("--profile", choices=["default", "enterprise"], default=None)
    bcreate.add_argument("--output", default=None)
    bcreate.add_argument("--exclude", action="append", default=[])
    bcreate.add_argument("--config", default=None)
    bcreate.add_argument("--allow-absolute-path", action="store_true")

    bcheck = bsub.add_parser("check")
    bcheck.add_argument("path", nargs="?", default=".")
    bcheck.add_argument("--baseline", default=None)
    bcheck.add_argument("--fail-on", choices=["none", "warn", "error"], default=None)
    bcheck.add_argument("--update", action="store_true")
    bcheck.add_argument("--diff", action="store_true")
    bcheck.add_argument("--profile", choices=["default", "enterprise"], default=None)
    bcheck.add_argument("--config", default=None)
    bcheck.add_argument("--allow-absolute-path", action="store_true")

    ap = sub.add_parser("audit")
    ap.add_argument("path", nargs="?", default=".")
    ap.add_argument("--profile", choices=["default", "enterprise"], default=None)
    ap.add_argument("--pack", default=None)
    ap.add_argument("--format", choices=["text", "json", "sarif"], default="text")
    ap.add_argument("--output", "--out", dest="output", default=None)
    ap.add_argument("--fail-on", choices=["none", "warn", "error"], default=None)
    ap.add_argument("--config", default=None)
    ap.add_argument("--baseline", default=None)
    ap.add_argument("--update-baseline", action="store_true")
    ap.add_argument("--exclude", action="append", default=[])
    ap.add_argument("--disable-rule", action="append", default=[])
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--allow-absolute-path", action="store_true")

    rules_parser = sub.add_parser("rules")
    rules_sub = rules_parser.add_subparsers(dest="rules_cmd", required=True)
    rules_list = rules_sub.add_parser("list")
    rules_list.add_argument("--profile", choices=["default", "enterprise"], default="default")
    rules_list.add_argument("--pack", default=None)
    rules_list.add_argument("--json", action="store_true")

    fxap = sub.add_parser("fix-audit")
    fxap.add_argument("path", nargs="?", default=".")
    fxap.add_argument("--profile", choices=["default", "enterprise"], default=None)
    fxap.add_argument("--pack", default=None)
    fxap.add_argument("--config", default=None)
    fxap.add_argument("--baseline", default=None)
    fxap.add_argument("--exclude", action="append", default=[])
    fxap.add_argument("--disable-rule", action="append", default=[])
    fxap.add_argument("--dry-run", action="store_true")
    fxap.add_argument("--apply", action="store_true")
    fxap.add_argument("--force", action="store_true")
    fxap.add_argument("--diff", action="store_true")
    fxap.add_argument("--patch", default=None)
    fxap.add_argument("--allow-absolute-path", action="store_true")

    ns = parser.parse_args(argv)

    if ns.repo_cmd == "rules":
        packs = normalize_packs(ns.profile, ns.pack)
        rules = list_repo_rules(profile=ns.profile, packs=packs)
        if ns.json:
            sys.stdout.write(
                json.dumps(
                    {"profile": ns.profile, "packs": list(packs), "rules": rules},
                    ensure_ascii=True,
                    sort_keys=True,
                    indent=2,
                )
                + "\n"
            )
        else:
            for rule in rules:
                print(
                    f"{rule['rule_id']:<36} [{rule['pack']}] sev={rule['severity']} fixable={'yes' if rule['fixable'] else 'no'}"
                )
        return 0

    try:
        root = _resolve_root(ns.path, allow_absolute=bool(ns.allow_absolute_path))
    except SecurityError as exc:
        print(str(exc), file=sys.stderr)
        return 2

    if ns.repo_cmd == "check":
        policy_text = None
        if ns.policy:
            try:
                policy_path = safe_path(
                    root, ns.policy, allow_absolute=bool(ns.allow_absolute_path)
                )
                policy_text = policy_path.read_text(encoding="utf-8")
            except (SecurityError, OSError):
                policy_text = None
        baseline_path = None
        if ns.baseline:
            try:
                baseline_path = safe_path(
                    root, ns.baseline, allow_absolute=bool(ns.allow_absolute_path)
                )
            except SecurityError:
                baseline_path = None
        findings = run_checks(
            root,
            profile=ns.profile,
            changed_only=bool(ns.changed_only),
            diff_base=str(ns.diff_base),
            baseline=_load_baseline(baseline_path),
        )
        payload = _report_payload(root, findings, profile=ns.profile, policy_text=policy_text)
        rendered = _render(payload, ns.format)
        if ns.sbom_out:
            try:
                sbom_path = safe_path(
                    root, ns.sbom_out, allow_absolute=bool(ns.allow_absolute_path)
                )
                if sbom_path.exists() and not ns.force:
                    print(
                        "refusing to overwrite existing SBOM output (use --force)", file=sys.stderr
                    )
                    return 2
                atomic_write_text(
                    sbom_path,
                    json.dumps(_generate_sbom(root), ensure_ascii=True, sort_keys=True, indent=2)
                    + "\n",
                )
            except (SecurityError, OSError, ValueError) as exc:
                print(str(exc), file=sys.stderr)
                return 2
        sys.stdout.write(rendered)
        if ns.out:
            try:
                out_path = safe_path(root, ns.out, allow_absolute=bool(ns.allow_absolute_path))
                if out_path.exists() and not ns.force:
                    print("refusing to overwrite existing output (use --force)", file=sys.stderr)
                    return 2
                atomic_write_text(out_path, rendered)
            except (SecurityError, OSError, ValueError) as exc:
                print(str(exc), file=sys.stderr)
                return 2
        return 1 if _needs_fail(findings, ns.fail_on, ns.min_score) else 0

    if ns.repo_cmd == "baseline":
        config_file = None
        if ns.config:
            try:
                config_file = safe_path(
                    root, ns.config, allow_absolute=bool(ns.allow_absolute_path)
                )
            except SecurityError as exc:
                print(str(exc), file=sys.stderr)
                return 2
        try:
            policy = _resolve_repo_audit_policy(
                root,
                cli_profile=ns.profile,
                cli_fail_on=getattr(ns, "fail_on", None),
                cli_baseline=ns.baseline
                if getattr(ns, "baseline", None)
                else getattr(ns, "output", None),
                cli_excludes=getattr(ns, "exclude", None),
                cli_disable_rules=None,
                config_path=config_file,
            )
        except RepoAuditConfigError as exc:
            print(str(exc), file=sys.stderr)
            return 2

        try:
            baseline_target = safe_path(
                root,
                (ns.output or policy.baseline_path)
                if ns.baseline_cmd == "create"
                else (ns.baseline or policy.baseline_path),
                allow_absolute=bool(ns.allow_absolute_path),
            )
        except SecurityError as exc:
            print(str(exc), file=sys.stderr)
            return 2
        try:
            findings_payload = run_repo_audit(
                root, profile=policy.profile, packs=normalize_packs(policy.profile, None)
            )
            actionable_findings, _ = _apply_repo_audit_policy(
                findings_payload.get("findings", []), policy, []
            )
            entries = _baseline_entries_from_findings(actionable_findings)
            previous = _load_repo_baseline(baseline_target)
        except RepoAuditConfigError as exc:
            print(str(exc), file=sys.stderr)
            return 2
        if ns.baseline_cmd == "create":
            _write_repo_baseline(baseline_target, entries)
            print(f"baseline created: {baseline_target.relative_to(root).as_posix()}")
            return 0

        old_entries = [x for x in previous.get("entries", []) if isinstance(x, dict)]
        old_fps = {str(x.get("fingerprint")) for x in old_entries}
        new_fps = {str(x.get("fingerprint")) for x in entries}
        unchanged = sorted(old_fps & new_fps)
        new_only = sorted(new_fps - old_fps)
        resolved = sorted(old_fps - new_fps)
        print(f"NEW: {len(new_only)} RESOLVED: {len(resolved)} UNCHANGED: {len(unchanged)}")
        if ns.diff:
            print(_baseline_diff(old_entries, entries))
        if ns.update:
            _write_repo_baseline(baseline_target, entries)
        if policy.fail_on != "none":
            threshold = _severity_rank(policy.fail_on)
            new_items = [x for x in entries if str(x.get("fingerprint")) in set(new_only)]
            if any(_severity_rank(str(x.get("severity", "error"))) >= threshold for x in new_items):
                return 1
        return 0

    if ns.repo_cmd == "audit":
        config_file = None
        if ns.config:
            try:
                config_file = safe_path(
                    root, ns.config, allow_absolute=bool(ns.allow_absolute_path)
                )
            except SecurityError as exc:
                print(str(exc), file=sys.stderr)
                return 2
        try:
            policy = _resolve_repo_audit_policy(
                root,
                cli_profile=ns.profile,
                cli_fail_on=getattr(ns, "fail_on", None),
                cli_baseline=ns.baseline,
                cli_excludes=ns.exclude,
                cli_disable_rules=ns.disable_rule,
                config_path=config_file,
            )
        except RepoAuditConfigError as exc:
            print(str(exc), file=sys.stderr)
            return 2
        packs = normalize_packs(policy.profile, ns.pack)
        payload = run_repo_audit(root, profile=policy.profile, packs=packs)
        original_findings = list(payload.get("findings", []))
        try:
            baseline_path = safe_path(
                root,
                policy.baseline_path,
                allow_absolute=bool(ns.allow_absolute_path),
            )
        except SecurityError as exc:
            print(str(exc), file=sys.stderr)
            return 2
        baseline_doc = _load_repo_baseline(baseline_path)
        actionable, suppression = _apply_repo_audit_policy(
            original_findings, policy, baseline_doc.get("entries", [])
        )
        if ns.update_baseline:
            _write_repo_baseline(baseline_path, _baseline_entries_from_findings(original_findings))
        payload["findings"] = actionable
        counts = {"error": 0, "warn": 0, "info": 0}
        for finding in actionable:
            sev = str(finding.get("severity", "error"))
            counts[sev] = counts.get(sev, 0) + 1
        payload["summary"]["counts"] = {k: counts[k] for k in sorted(counts)}
        payload["summary"]["findings"] = len(actionable)
        payload["summary"]["policy"] = {
            "total_findings": len(original_findings),
            "suppressed_by_baseline": suppression["counts"]["baseline"],
            "suppressed_by_policy": suppression["counts"]["policy"],
            "actionable": len(actionable),
        }
        payload["suppressed"] = suppression["suppressed"]
        rendered = _render_repo_audit(payload, ns.format)
        if ns.output:
            try:
                out_path = safe_path(root, ns.output, allow_absolute=bool(ns.allow_absolute_path))
                if out_path.exists() and not ns.force:
                    print("refusing to overwrite existing output (use --force)", file=sys.stderr)
                    return 2
                atomic_write_text(out_path, rendered)
            except (SecurityError, OSError, ValueError) as exc:
                print(str(exc), file=sys.stderr)
                return 2
        else:
            sys.stdout.write(rendered)
        return 1 if _needs_fail_repo_audit(payload.get("findings", []), policy.fail_on) else 0

    if ns.repo_cmd == "fix-audit":
        if ns.dry_run and ns.apply:
            print("cannot use --dry-run and --apply together", file=sys.stderr)
            return 2
        config_file = None
        if ns.config:
            try:
                config_file = safe_path(
                    root, ns.config, allow_absolute=bool(ns.allow_absolute_path)
                )
            except SecurityError as exc:
                print(str(exc), file=sys.stderr)
                return 2
        try:
            policy = _resolve_repo_audit_policy(
                root,
                cli_profile=ns.profile,
                cli_fail_on="none",
                cli_baseline=ns.baseline,
                cli_excludes=ns.exclude,
                cli_disable_rules=ns.disable_rule,
                config_path=config_file,
            )
        except RepoAuditConfigError as exc:
            print(str(exc), file=sys.stderr)
            return 2
        packs = normalize_packs(policy.profile, ns.pack)
        return _run_repo_fix_audit(
            root,
            profile=policy.profile,
            packs=packs,
            policy=policy,
            dry_run=bool(ns.dry_run) or not bool(ns.apply),
            apply=bool(ns.apply),
            force=bool(ns.force),
            show_diff=bool(ns.diff),
            patch_path=ns.patch,
            allow_absolute_path=bool(ns.allow_absolute_path),
        )

    if ns.repo_cmd == "init":
        if ns.dry_run and ns.apply:
            print("cannot use --dry-run and --apply together", file=sys.stderr)
            return 2
        return _run_repo_init(
            root,
            profile=ns.profile,
            apply=bool(ns.apply),
            force=bool(ns.force),
            diff=bool(ns.diff),
        )

    if ns.check and ns.dry_run:
        print("cannot use --check and --dry-run together", file=sys.stderr)
        return 2
    try:
        return _apply_fixes(
            root,
            check=bool(ns.check),
            dry_run=bool(ns.dry_run),
            diff=bool(ns.diff),
            eol=ns.eol,
        )
    except OSError as exc:
        print(str(exc), file=sys.stderr)
        return 2
