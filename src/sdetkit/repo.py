from __future__ import annotations

import argparse
import ast
import concurrent.futures
import datetime as dt
import difflib
import hashlib
import html
import importlib.metadata as importlib_metadata
import importlib.resources as importlib_resources
import json
import math
import os
import re
import subprocess
import sys
import threading
import tomllib as _tomllib
import urllib.error
import urllib.parse
import urllib.request
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
    apply_pack_defaults,
    load_repo_audit_packs,
    load_rule_catalog,
    merge_packs,
    normalize_org_packs,
    normalize_packs,
    select_rules,
)
from .projects import ProjectsConfigError, discover_projects, resolve_project
from .report import build_run_record, diff_runs, load_run_record
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
        ".sdetkit",
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

REPO_PRESETS: frozenset[str] = frozenset({"enterprise_python"})


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
    owner: str = ""
    justification: str = ""
    created: str | None = None
    expires: str | None = None
    ticket: str | None = None


@dataclass(frozen=True)
class RepoAuditPolicy:
    profile: str
    fail_on: str
    baseline_path: str
    exclude_paths: tuple[str, ...]
    disable_rules: frozenset[str]
    severity_overrides: dict[str, str]
    org_packs: tuple[str, ...]
    allowlist: tuple[AllowlistRule, ...]
    org_pack_unknown: tuple[str, ...]
    lint_expiry_max_days: int


class RepoAuditConfigError(ValueError):
    pass


@dataclass(frozen=True)
class RepoFixProjectResult:
    name: str
    root: Path
    root_rel: str
    profile: str
    packs: tuple[str, ...]
    fixes: tuple[Fix, ...]
    edits: tuple[Any, ...]


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


def _tool_version() -> str:
    try:
        return importlib_metadata.version("sdetkit")
    except importlib_metadata.PackageNotFoundError:
        return "1.0.0"


def _config_hash(*, profile: str, packs: tuple[str, ...]) -> str:
    payload = {"packs": list(packs), "profile": profile}
    doc = json.dumps(payload, ensure_ascii=True, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(doc.encode("utf-8")).hexdigest()


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


class _FileInventoryCache:
    def __init__(self, cache_dir: Path) -> None:
        self._path = cache_dir / "inventory.json"
        self._lock = threading.Lock()
        self._entries: dict[str, dict[str, Any]] = {}
        self._dirty = False
        self._loaded = False

    def _load(self) -> None:
        if self._loaded:
            return
        self._loaded = True
        if not self._path.exists():
            return
        try:
            payload = json.loads(self._path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return
        if isinstance(payload, dict) and int(payload.get("schema_version", 0)) != 1:
            return
        entries = payload.get("entries") if isinstance(payload, dict) else None
        if isinstance(entries, dict):
            self._entries = {str(k): dict(v) for k, v in entries.items() if isinstance(v, dict)}

    def digest_for(self, root: Path, rel_path: str) -> str | None:
        with self._lock:
            self._load()
        target = root / rel_path
        key = rel_path.replace("\\", "/")
        if not target.exists():
            return None
        try:
            stat = target.stat()
            mtime = int(stat.st_mtime_ns)
            size = int(stat.st_size)
        except OSError:
            return None
        cached = self._entries.get(key)
        if cached and cached.get("mtime_ns") == mtime and cached.get("size") == size:
            digest = cached.get("digest")
            if isinstance(digest, str) and digest:
                return digest
        try:
            digest = _sha256_bytes(target.read_bytes())
        except OSError:
            return None
        self._entries[key] = {"mtime_ns": mtime, "size": size, "digest": digest}
        self._dirty = True
        return digest

    def save(self) -> None:
        with self._lock:
            if not self._dirty:
                return
        self._path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "schema_version": 1,
            "entries": {k: self._entries[k] for k in sorted(self._entries)},
        }
        atomic_write_text(
            self._path, json.dumps(payload, ensure_ascii=True, sort_keys=True, indent=2) + "\n"
        )


RUN_CACHE_SCHEMA_VERSION = 1
REPO_AUDIT_RULESET_VERSION = "1"


def _repo_fingerprint(root: Path, inventory: _FileInventoryCache) -> str:
    material: list[dict[str, str | None]] = []
    for path in _iter_files(root):
        rel = path.relative_to(root).as_posix()
        material.append({"path": rel, "digest": inventory.digest_for(root, rel)})
    payload = json.dumps(material, ensure_ascii=True, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _run_cache_file(cache_dir: Path, key: str) -> Path:
    return cache_dir / "runs" / f"{key}.json"


def _run_cache_key(
    *,
    profile: str,
    packs: tuple[str, ...],
    repo_fingerprint: str,
    changed_only: bool,
    since_ref: str,
    include_untracked: bool,
    include_staged: bool,
) -> str:
    material = {
        "profile": profile,
        "packs": list(packs),
        "repo_fingerprint": repo_fingerprint,
        "ruleset_version": REPO_AUDIT_RULESET_VERSION,
        "changed_only": changed_only,
        "since_ref": since_ref,
        "include_untracked": include_untracked,
        "include_staged": include_staged,
    }
    payload = json.dumps(material, ensure_ascii=True, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _load_run_cache(cache_dir: Path, key: str) -> dict[str, Any] | None:
    target = _run_cache_file(cache_dir, key)
    if not target.exists():
        return None
    try:
        payload = json.loads(target.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if not isinstance(payload, dict):
        return None
    if int(payload.get("schema_version", 0)) != RUN_CACHE_SCHEMA_VERSION:
        return None
    cached = payload.get("payload")
    return cached if isinstance(cached, dict) else None


def _store_run_cache(cache_dir: Path, key: str, payload: dict[str, Any]) -> None:
    target = _run_cache_file(cache_dir, key)
    target.parent.mkdir(parents=True, exist_ok=True)
    atomic_write_text(
        target,
        json.dumps(
            {"schema_version": RUN_CACHE_SCHEMA_VERSION, "payload": payload},
            ensure_ascii=True,
            sort_keys=True,
            indent=2,
        )
        + "\n",
    )


class RepoRuleExecutionContext:
    def __init__(
        self, root: Path, inventory: _FileInventoryCache, changed: set[str] | None = None
    ) -> None:
        self._root = root
        self._inventory = inventory
        self._deps: set[str] = set()
        self.changed_files = set(changed or set())

    def track_file(self, path: str | Path) -> None:
        rel = Path(path).as_posix() if not isinstance(path, Path) else path.as_posix()
        rel = rel.lstrip("/") or "."
        self._deps.add(rel)

    def read_text(self, path: str | Path, *, encoding: str = "utf-8") -> str:
        rel = Path(path).as_posix() if not isinstance(path, Path) else path.as_posix()
        self.track_file(rel)
        target = self._root / rel
        return target.read_text(encoding=encoding)

    def dependency_manifest(self) -> dict[str, str | None]:
        manifest: dict[str, str | None] = {}
        for rel in sorted(self._deps):
            manifest[rel] = self._inventory.digest_for(self._root, rel)
        return manifest


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
    generated_at = ""
    if profile == "enterprise":
        source_date_epoch = os.environ.get("SOURCE_DATE_EPOCH")
        if source_date_epoch:
            try:
                generated_at = dt.datetime.fromtimestamp(int(source_date_epoch), tz=_UTC).strftime(
                    "%Y-%m-%dT%H:%M:%SZ"
                )
            except ValueError:
                generated_at = dt.datetime.now(_UTC).isoformat()
        else:
            generated_at = dt.datetime.now(_UTC).isoformat()

    return {
        "root": str(root),
        "metadata": {
            "tool": "sdetkit",
            "version": "1.0.0",
            "profile": profile,
            "git_commit": _git_commit_sha(root),
            "generated_at_utc": generated_at,
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

    def _as_int(value: Any, default: int = 1) -> int:
        if isinstance(value, int):
            return value
        try:
            return int(str(value))
        except (TypeError, ValueError):
            return default

    rules: dict[str, dict[str, Any]] = {}
    results: list[dict[str, Any]] = []
    for item in payload["findings"]:
        rid = str(
            item.get("rule_id")
            or f"{item.get('check', 'repo_audit')}/{item.get('code', 'unknown')}"
        )
        if rid not in rules:
            tags = item.get("rule_tags", [])
            if not isinstance(tags, list):
                tags = []
            rules[rid] = {
                "id": rid,
                "name": str(item.get("rule_title") or rid),
                "shortDescription": {
                    "text": str(item.get("rule_title") or item.get("message", rid))
                },
                "help": {"text": str(item.get("rule_description") or item.get("remediation", ""))},
                "properties": {"tags": tags, "pack": item.get("pack", "core")},
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
                    "suppression_status": item.get("suppression_status"),
                    "suppression_reason": item.get("suppression_reason"),
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
    results.sort(
        key=lambda item: (
            str(item.get("ruleId", "")),
            str(item.get("level", "")),
            str(
                item.get("locations", [{}])[0]
                .get("physicalLocation", {})
                .get("artifactLocation", {})
                .get("uri", "")
            ),
            _as_int(
                item.get("locations", [{}])[0]
                .get("physicalLocation", {})
                .get("region", {})
                .get("startLine", 1)
            ),
            _as_int(
                item.get("locations", [{}])[0]
                .get("physicalLocation", {})
                .get("region", {})
                .get("startColumn", 1)
            ),
            str(item.get("message", {}).get("text", "")),
        )
    )
    rules_list = [rules[key] for key in sorted(rules)]
    summary = payload.get("summary") if isinstance(payload, dict) else None
    run_properties: dict[str, Any] = {}
    if isinstance(summary, dict):
        incremental = summary.get("incremental")
        if isinstance(incremental, dict):
            run_properties["incremental"] = incremental
        cache = summary.get("cache")
        if isinstance(cache, dict):
            run_properties["cache"] = cache
    run_doc: dict[str, Any] = {
        "tool": {"driver": {"name": "sdetkit", "rules": rules_list}},
        "results": results,
    }
    if run_properties:
        run_doc["properties"] = run_properties
    return {
        "$schema": "https://json.schemastore.org/sarif-2.1.0.json",
        "version": "2.1.0",
        "runs": [run_doc],
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


def _stable_finding_sort_key(item: dict) -> tuple:
    sev = str(item.get("severity") or item.get("level") or item.get("status") or "").lower()
    rank = {"error": 3, "warn": 2, "warning": 2, "info": 1, "ok": 0}.get(sev, -1)

    path = str(item.get("path") or "")
    check = str(item.get("check") or "")
    code = str(item.get("code") or "")
    msg = str(item.get("message") or "")
    fp = str(item.get("fingerprint") or "")

    line = item.get("line")
    col = item.get("column") or item.get("col")

    def as_int(x) -> int:
        if isinstance(x, int):
            return x
        try:
            return int(str(x))
        except Exception:
            return 0

    return (-rank, path, as_int(line), as_int(col), check, code, msg, fp)


def _stable_sorted_findings(findings: list[dict]) -> list[dict]:
    return sorted(findings, key=_stable_finding_sort_key)


def _stable_sorted_details(details) -> list[dict]:
    if not isinstance(details, list):
        return []
    only = [d for d in details if isinstance(d, dict)]
    return sorted(only, key=_stable_finding_sort_key)


def _html_escape(x) -> str:
    import html as _html

    return _html.escape("" if x is None else str(x), quote=True)


def _render_findings_html(title: str, findings: list[dict]) -> str:
    rows = []
    for f in findings:
        rows.append(
            "<tr>"
            f"<td>{_html_escape(f.get('severity') or '')}</td>"
            f"<td>{_html_escape(f.get('check') or '')}</td>"
            f"<td>{_html_escape(f.get('path') or '')}</td>"
            f"<td>{_html_escape(f.get('line') or '')}</td>"
            f"<td>{_html_escape(f.get('column') or f.get('col') or '')}</td>"
            f"<td>{_html_escape(f.get('code') or '')}</td>"
            f"<td>{_html_escape(f.get('message') or '')}</td>"
            "</tr>"
        )

    return (
        "<!doctype html>"
        "<html><head><meta charset='utf-8'/>"
        f"<title>{_html_escape(title)}</title>"
        "<style>"
        "body{font-family:system-ui,Segoe UI,Roboto,Arial,sans-serif;margin:16px;}"
        "table{border-collapse:collapse;width:100%;}"
        "th,td{border:1px solid #ddd;padding:6px;vertical-align:top;}"
        "th{background:#f5f5f5;text-align:left;}"
        "code{white-space:pre-wrap;}"
        "</style>"
        "</head><body>"
        f"<h1>{_html_escape(title)}</h1>"
        f"<p>Findings: {len(findings)}</p>"
        "<table>"
        "<thead><tr>"
        "<th>severity</th><th>check</th><th>path</th><th>line</th><th>col</th><th>code</th><th>message</th>"
        "</tr></thead>"
        "<tbody>" + "".join(rows) + "</tbody></table>"
        "</body></html>"
    )


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

    if fmt == "html":
        stable = dict(payload)
        stable["findings"] = _stable_sorted_findings(list(payload.get("findings") or []))
        return _render_findings_html("sdetkit repo check", stable["findings"])

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


def _iter_template_files(node: Any) -> list[Any]:
    stack = [node]
    files: list[Any] = []
    while stack:
        current = stack.pop()
        if current.is_dir():
            children = list(current.iterdir())
            children.sort(key=lambda item: item.as_posix(), reverse=True)
            stack.extend(children)
            continue
        if current.is_file():
            files.append(current)
    return files


def _load_repo_preset_templates(preset: str) -> dict[str, str]:
    if preset not in REPO_PRESETS:
        raise ValueError(f"unsupported preset: {preset}")
    base = importlib_resources.files("sdetkit.templates").joinpath(preset)
    templates: dict[str, str] = {}
    for entry in _iter_template_files(base):
        if entry.name == "__init__.py":
            continue
        rel = entry.relative_to(base).as_posix()
        templates[rel] = entry.read_bytes().decode("utf-8", errors="replace")
    return templates


def _plan_repo_init(
    root: Path, *, preset: str, force: bool
) -> tuple[list[RepoInitChange], list[str]]:
    changes: list[RepoInitChange] = []
    conflicts: list[str] = []
    for rel, desired in _load_repo_preset_templates(preset).items():
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


def _print_repo_init_plan(changes: list[RepoInitChange], *, command: str, dry_run: bool) -> None:
    mode = "dry-run" if dry_run else "write"
    if not changes:
        print(f"repo {command} ({mode}): no changes")
        return
    for change in changes:
        print(f"{change.action.upper():<6} {change.path}")
    creates = sum(1 for item in changes if item.action == "create")
    updates = sum(1 for item in changes if item.action == "update")
    print(f"repo {command} ({mode}): {len(changes)} planned (create={creates}, update={updates})")


def _print_repo_init_diff(changes: list[RepoInitChange]) -> None:
    for change in changes:
        diff = difflib.unified_diff(
            change.current.splitlines(keepends=True),
            change.desired.splitlines(keepends=True),
            fromfile=f"a/{change.path}",
            tofile=f"b/{change.path}",
        )
        sys.stdout.write("".join(diff))


def _run_repo_init(
    root: Path, *, preset: str, command: str, dry_run: bool, force: bool, diff: bool
) -> int:
    changes, conflicts = _plan_repo_init(root, preset=preset, force=force)
    if conflicts and command == "init":
        for rel in conflicts:
            print(f"refusing to overwrite existing file: {rel} (use --force)", file=sys.stderr)
        return 2
    if conflicts and command == "apply":
        for rel in conflicts:
            print(f"SKIP   {rel}")
    _print_repo_init_plan(changes, command=command, dry_run=dry_run)
    if diff and changes:
        _print_repo_init_diff(changes)
    if dry_run:
        return 0
    for change in changes:
        target = safe_path(root, change.path, allow_absolute=False)
        target.parent.mkdir(parents=True, exist_ok=True)
        atomic_write_text(target, change.desired)
    print(f"repo {command}: wrote {len(changes)} file(s)")
    return 0


def _plan_repo_fix_audit(
    root: Path,
    *,
    profile: str,
    packs: tuple[str, ...],
    policy: RepoAuditPolicy,
    allow_absolute_path: bool,
    force: bool,
    changed_only: bool,
    since_ref: str,
    include_untracked: bool,
    include_staged: bool,
    require_git: bool,
    cache_dir: str,
    no_cache: bool,
    cache_stats: bool,
    jobs: int,
) -> tuple[list[Fix], list[str], dict[str, Any]]:
    payload = run_repo_audit(
        root,
        profile=profile,
        packs=packs,
        changed_only=changed_only,
        since_ref=since_ref,
        include_untracked=include_untracked,
        include_staged=include_staged,
        require_git=require_git,
        cache_dir=cache_dir,
        no_cache=no_cache,
        cache_stats=cache_stats,
        jobs=jobs,
    )
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
    changed_only: bool,
    since_ref: str,
    include_untracked: bool,
    include_staged: bool,
    require_git: bool,
    cache_dir: str,
    no_cache: bool,
    cache_stats: bool,
    jobs: int,
) -> int:
    fixes, conflicts, _ = _plan_repo_fix_audit(
        root,
        profile=profile,
        packs=packs,
        policy=policy,
        allow_absolute_path=allow_absolute_path,
        force=force,
        changed_only=changed_only,
        since_ref=since_ref,
        include_untracked=include_untracked,
        include_staged=include_staged,
        require_git=require_git,
        cache_dir=cache_dir,
        no_cache=no_cache,
        cache_stats=cache_stats,
        jobs=jobs,
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


def _git_run(
    root: Path, args: list[str], *, env: dict[str, str] | None = None
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-C", str(root), *args],
        check=False,
        capture_output=True,
        text=True,
        env=env,
    )


def _git_current_branch(root: Path) -> str:
    proc = _git_run(root, ["rev-parse", "--abbrev-ref", "HEAD"])
    if proc.returncode != 0:
        raise ValueError(proc.stderr.strip() or "unable to determine current branch")
    branch = proc.stdout.strip()
    if not branch:
        raise ValueError("unable to determine current branch")
    return branch


def _git_branch_exists(root: Path, branch: str) -> bool:
    proc = _git_run(root, ["show-ref", "--verify", "--quiet", f"refs/heads/{branch}"])
    return proc.returncode == 0


def _git_changed_files(root: Path) -> list[str]:
    proc = _git_run(root, ["status", "--porcelain"])
    if proc.returncode != 0:
        raise ValueError(proc.stderr.strip() or "unable to determine changed files")
    paths = set()
    for line in proc.stdout.splitlines():
        if not line:
            continue
        payload = line[3:] if len(line) >= 4 else line
        right = payload.split(" -> ")[-1].strip()
        if right:
            paths.add(right)
    return sorted(paths)


def _parse_remote_repo(url: str) -> str | None:
    value = url.strip()
    if value.endswith(".git"):
        value = value[:-4]
    if value.startswith("git@github.com:"):
        return value.split(":", 1)[1]
    parsed = urllib.parse.urlparse(value)
    if parsed.netloc.lower() != "github.com":
        return None
    path = parsed.path.strip("/")
    if path.count("/") < 1:
        return None
    return "/".join(path.split("/")[:2])


def _detect_repo_slug(root: Path, remote: str) -> str | None:
    proc = _git_run(root, ["remote", "get-url", remote])
    if proc.returncode != 0:
        return None
    return _parse_remote_repo(proc.stdout.strip())


def _deterministic_commit_message(
    *, rule_ids: list[str], file_count: int, provided: str | None
) -> str:
    if provided:
        return provided
    ids = ", ".join(sorted(set(rule_ids))) if rule_ids else "none"
    return f"chore(sdetkit): auto-fix repo audit ({file_count} files; rules: {ids})"


def _build_pr_body(
    *,
    profile: str | None,
    packs: list[str],
    rule_ids: list[str],
    changed_files: list[str],
    per_project: list[RepoFixProjectResult],
) -> str:
    lines = [
        "## What and why",
        "",
        "This PR was generated by `sdetkit repo pr-fix` to apply safe, deterministic repository-hygiene auto-fixes.",
        "",
        "## Summary",
        "",
        "| Item | Value |",
        "| --- | --- |",
        f"| Profile | `{profile or 'default'}` |",
        f"| Packs | `{', '.join(sorted(set(packs))) or 'core'}` |",
        f"| Rule IDs fixed | `{', '.join(sorted(set(rule_ids))) or 'none'}` |",
        f"| Files changed | `{len(changed_files)}` |",
        "",
        "## Safety",
        "",
        "These changes are generated from sdetkit fixers and are expected to touch template/config/workflow hygiene files only.",
        "",
        "## How to review",
        "",
        "1. Review commit diff files listed below (stable order).",
        "2. Re-run `sdetkit repo fix-audit --apply` and verify no additional changes (idempotency).",
        "3. Let existing CI checks validate generated outputs.",
        "",
        "### Changed files",
        "",
    ]
    lines.extend(f"- `{path}`" for path in sorted(changed_files))
    if per_project:
        lines.extend(["", "## Monorepo breakdown", ""])
        for project in per_project:
            project_rules = sorted({fix.rule_id for fix in project.fixes})
            lines.append(
                f"- `{project.name}` (`{project.root_rel}`): {len(project.edits)} file(s), rules: {', '.join(project_rules) or 'none'}"
            )
    lines.extend(
        [
            "",
            "## CI artifacts",
            "",
            "JSON/SARIF outputs can be produced by the existing audit workflow configuration for this repository.",
        ]
    )
    return "\n".join(lines) + "\n"


def _github_create_pr(
    *,
    repo_slug: str,
    token: str,
    head: str,
    base: str,
    title: str,
    body: str,
    draft: bool,
) -> dict[str, Any]:
    req = urllib.request.Request(
        f"https://api.github.com/repos/{repo_slug}/pulls",
        data=json.dumps(
            {"title": title, "body": body, "head": head, "base": base, "draft": draft}
        ).encode("utf-8"),
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {token}",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "sdetkit",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=20) as resp:
        return cast(dict[str, Any], json.loads(resp.read().decode("utf-8")))


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
        "rule_title": meta.title,
        "rule_description": meta.description,
        "rule_tags": list(meta.tags),
        "snippet": "",
        "fingerprint": normalized.fingerprint,
        "pack": pack,
        "fixable": bool(meta.supports_fix),
    }


def _git_available(root: Path) -> bool:
    proc = _git_run(root, ["rev-parse", "--is-inside-work-tree"])
    return proc.returncode == 0 and proc.stdout.strip() == "true"


def _git_name_only(root: Path, args: list[str]) -> set[str]:
    proc = _git_run(root, args)
    if proc.returncode != 0:
        raise ValueError(proc.stderr.strip() or "unable to collect changed files")
    return {x.strip() for x in proc.stdout.splitlines() if x.strip()}


def collect_git_changed_files(
    root: Path,
    *,
    since_ref: str,
    include_untracked: bool,
    include_staged: bool,
) -> set[str]:
    changed = set(_git_name_only(root, ["diff", "--name-only"]))
    if include_staged:
        changed.update(_git_name_only(root, ["diff", "--name-only", "--cached"]))
    try:
        changed.update(_git_name_only(root, ["diff", "--name-only", f"{since_ref}...HEAD"]))
    except ValueError:
        # Ignore failures when diffing from since_ref (e.g., invalid ref or no common base);
        # we still return files changed in the working tree, staged area, and untracked files.
        pass
    if include_untracked:
        changed.update(_git_name_only(root, ["ls-files", "--others", "--exclude-standard"]))
    return {x.replace("\\", "/") for x in changed}


def _rule_cache_file(cache_dir: Path, key: str) -> Path:
    return cache_dir / f"{key}.json"


def _rule_cache_key(
    *,
    rule_id: str,
    repo_root: Path,
    profile: str,
    packs: tuple[str, ...],
) -> str:
    repo_identity = repo_root.resolve(strict=False).as_posix()
    material = {
        "tool_version": _tool_version(),
        "ruleset_version": REPO_AUDIT_RULESET_VERSION,
        "rule_id": rule_id,
        "repo_root": repo_identity,
        "config": _config_hash(profile=profile, packs=packs),
        "packs": list(packs),
    }
    payload = json.dumps(material, ensure_ascii=True, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _load_cached_rule(cache_dir: Path, key: str) -> dict[str, Any] | None:
    target = _rule_cache_file(cache_dir, key)
    if not target.exists():
        return None
    try:
        payload = json.loads(target.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if not isinstance(payload, dict):
        return None
    if int(payload.get("schema_version", 0)) != 1:
        return None
    return payload


def _cache_valid(payload: dict[str, Any], manifest: dict[str, str | None]) -> bool:
    deps = payload.get("dependencies")
    if not isinstance(deps, dict):
        return False
    normalized = {str(k): (str(v) if isinstance(v, str) else None) for k, v in deps.items()}
    return normalized == manifest


def _store_rule_cache(
    cache_dir: Path,
    key: str,
    *,
    findings: list[dict[str, Any]],
    dependencies: dict[str, str | None],
) -> None:
    cache_dir.mkdir(parents=True, exist_ok=True)
    doc = {
        "schema_version": 1,
        "findings": findings,
        "dependencies": {k: dependencies[k] for k in sorted(dependencies)},
    }
    atomic_write_text(
        _rule_cache_file(cache_dir, key),
        json.dumps(doc, ensure_ascii=True, sort_keys=True, indent=2) + "\n",
    )


def run_repo_audit(
    root: Path,
    *,
    profile: str = "default",
    packs: tuple[str, ...] | None = None,
    changed_only: bool = False,
    since_ref: str = "HEAD~1",
    include_untracked: bool = True,
    include_staged: bool = True,
    require_git: bool = False,
    cache_dir: str = ".sdetkit/cache",
    no_cache: bool = False,
    cache_stats: bool = False,
    jobs: int = 1,
) -> dict[str, Any]:
    catalog = load_rule_catalog()
    selected_packs = packs or normalize_packs(profile, None)
    selected_rules = sorted(select_rules(catalog, selected_packs), key=lambda item: item.meta.id)

    changed_files: set[str] = set()
    incremental_used = False
    if changed_only:
        git_ok = _git_available(root)
        if not git_ok:
            if require_git:
                raise ValueError("git unavailable or current path is not a git repository")
        else:
            changed_files = collect_git_changed_files(
                root,
                since_ref=since_ref,
                include_untracked=include_untracked,
                include_staged=include_staged,
            )
            incremental_used = True

    cache_enabled = not no_cache
    cache_root = root / cache_dir
    inventory = _FileInventoryCache(cache_root)
    repo_fingerprint = _repo_fingerprint(root, inventory)
    run_cache_key = _run_cache_key(
        profile=profile,
        packs=selected_packs,
        repo_fingerprint=repo_fingerprint,
        changed_only=changed_only,
        since_ref=since_ref,
        include_untracked=include_untracked,
        include_staged=include_staged,
    )
    if cache_enabled:
        cached_run = _load_run_cache(cache_root, run_cache_key)
        if cached_run is not None:
            cached_summary = dict(cached_run.get("summary") or {})
            if cache_stats:
                cached_summary["cache"] = {"hit": True, "incremental_used": incremental_used}
            cached_run["summary"] = cached_summary
            inventory.save()
            return cached_run

    def run_one(loaded: Any) -> tuple[str, dict[str, Any], list[dict[str, Any]], int, int]:
        rule_id = loaded.meta.id
        pack_name = next(
            (t.split(":", 1)[1] for t in loaded.meta.tags if t.startswith("pack:")), "core"
        )
        key = _rule_cache_key(
            rule_id=rule_id, repo_root=root, profile=profile, packs=selected_packs
        )
        cached_doc = _load_cached_rule(cache_root, key) if cache_enabled else None

        if cached_doc is not None and changed_only and incremental_used:
            deps = cached_doc.get("dependencies")
            if isinstance(deps, dict):
                dep_paths = {str(item) for item in deps}
                if dep_paths and dep_paths.isdisjoint(changed_files):
                    cached_findings = [
                        x for x in cached_doc.get("findings", []) if isinstance(x, dict)
                    ]
                    check = {
                        "key": loaded.meta.id,
                        "title": loaded.meta.title,
                        "status": "pass" if not cached_findings else "fail",
                        "details": [loaded.meta.description],
                        "pack": pack_name,
                        "supports_fix": loaded.meta.supports_fix,
                    }
                    return rule_id, check, cached_findings, 1, 0

        exec_ctx = RepoRuleExecutionContext(root, inventory, changed_files)
        context: dict[str, Any] = {
            "profile": profile,
            "packs": selected_packs,
            "_exec_ctx": exec_ctx,
        }
        rule_findings = loaded.plugin.run(root, context)
        normalized_findings = [
            _plugin_finding_to_dict(finding, loaded.meta) for finding in rule_findings
        ]

        hit_count = 0
        miss_count = 0
        deps_manifest = exec_ctx.dependency_manifest()
        if cache_enabled and deps_manifest:
            if cached_doc is not None and _cache_valid(cached_doc, deps_manifest):
                normalized_findings = [
                    x for x in cached_doc.get("findings", []) if isinstance(x, dict)
                ]
                hit_count = 1
            else:
                _store_rule_cache(
                    cache_root, key, findings=normalized_findings, dependencies=deps_manifest
                )
                miss_count = 1

        check = {
            "key": loaded.meta.id,
            "title": loaded.meta.title,
            "status": "pass" if not normalized_findings else "fail",
            "details": [loaded.meta.description],
            "pack": pack_name,
            "supports_fix": loaded.meta.supports_fix,
        }
        return rule_id, check, normalized_findings, hit_count, miss_count

    max_workers = max(1, int(jobs))
    if max_workers == 1:
        results = [run_one(rule) for rule in selected_rules]
    else:
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = [executor.submit(run_one, rule) for rule in selected_rules]
            results = [future.result() for future in futures]

    checks: list[dict[str, Any]] = []
    findings: list[dict[str, Any]] = []
    cache_hits: dict[str, int] = {}
    cache_misses: dict[str, int] = {}
    for rule_id, check, rule_findings, hit_count, miss_count in sorted(
        results, key=lambda item: item[0]
    ):
        checks.append(check)
        findings.extend(rule_findings)
        if hit_count:
            cache_hits[rule_id] = cache_hits.get(rule_id, 0) + hit_count
        if miss_count:
            cache_misses[rule_id] = cache_misses.get(rule_id, 0) + miss_count

    counts = {"info": 0, "warn": 0, "error": 0}
    for finding_item in findings:
        sev = str(finding_item.get("severity", "error"))
        counts[sev] = counts.get(sev, 0) + 1

    checks.sort(key=lambda x: str(x["key"]))
    findings.sort(
        key=lambda x: (str(x.get("path", "")), str(x.get("rule_id", "")), str(x.get("message", "")))
    )
    inventory.save()

    summary: dict[str, Any] = {
        "checks": len(checks),
        "passed": sum(1 for item in checks if item["status"] == "pass"),
        "failed": sum(1 for item in checks if item["status"] == "fail"),
        "ok": not findings,
        "counts": {k: counts[k] for k in sorted(counts)},
        "findings": len(findings),
        "packs": list(selected_packs),
        "incremental": {"used": incremental_used, "changed_files": len(changed_files)},
    }
    if cache_stats:
        summary["cache"] = {
            "hit": False,
            "incremental_used": incremental_used,
            "hits": {k: cache_hits[k] for k in sorted(cache_hits)},
            "misses": {k: cache_misses[k] for k in sorted(cache_misses)},
        }
    payload = {
        "schema_version": "1.1.0",
        "root": str(root),
        "summary": summary,
        "checks": checks,
        "findings": findings,
    }
    if cache_enabled:
        _store_run_cache(cache_root, run_cache_key, payload)
    return payload


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
            "summary": payload.get("summary", {}),
        }
        return (
            json.dumps(_to_sarif(sarif_payload), ensure_ascii=True, sort_keys=True, indent=2) + "\n"
        )

    if fmt == "md":
        body = _render_repo_audit(payload, "text").rstrip("\n")
        return "```\n" + body + "\n```\n"

    if fmt == "html":
        body = _render_repo_audit(payload, "text").rstrip("\n")
        esc = html.escape(body)
        return (
            "<!doctype html>\n"
            '<html><head><meta charset="utf-8" />'
            "<title>sdetkit repo audit report</title></head>"
            "<body><pre>" + esc + "</pre></body></html>\n"
        )

    # AUDIT_MD_HTML_RENDER

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
                f"  - suppressed active allowlist: {policy_summary.get('suppressed_active', 0)}",
                f"  - expired allowlist matches: {policy_summary.get('suppressed_expired', 0)}",
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


def _render_repo_audit_aggregate(payload: dict[str, Any], fmt: str) -> str:
    if fmt == "json":
        return json.dumps(payload, ensure_ascii=True, sort_keys=True, indent=2) + "\n"
    if fmt == "sarif":
        runs: list[dict[str, Any]] = []
        for item in payload.get("projects", []):
            if not isinstance(item, dict):
                continue
            doc = _to_sarif({"findings": item.get("run_record", {}).get("findings", [])})
            run = dict(doc["runs"][0])
            run["automationDetails"] = {"id": str(item.get("name", "unknown"))}
            runs.append(run)
        return (
            json.dumps(
                {
                    "$schema": "https://json.schemastore.org/sarif-2.1.0.json",
                    "runs": runs,
                    "version": "2.1.0",
                },
                ensure_ascii=True,
                sort_keys=True,
                indent=2,
            )
            + "\n"
        )

    if fmt == "md":
        body = _render_repo_audit_aggregate(payload, "text").rstrip("\n")
        return "```\n" + body + "\n```\n"

    if fmt == "html":
        body = _render_repo_audit_aggregate(payload, "text").rstrip("\n")
        esc = html.escape(body)
        return (
            "<!doctype html>\n"
            '<html><head><meta charset="utf-8" />'
            "<title>sdetkit repo aggregate audit report</title></head>"
            "<body><pre>" + esc + "</pre></body></html>\n"
        )

    # AUDIT_AGG_MD_HTML_RENDER

    lines = [f"Repo aggregate audit: {payload.get('root', '.')}", ""]
    for item in payload.get("projects", []):
        if not isinstance(item, dict):
            continue
        summary = item.get("summary", {})
        lines.extend(
            [
                f"Project: {item.get('name')} ({item.get('root')})",
                f"  Findings: {summary.get('findings', 0)}",
                f"  Counts: warn={summary.get('counts', {}).get('warn', 0)} error={summary.get('counts', {}).get('error', 0)}",
                "",
            ]
        )
    totals = payload.get("totals", {})
    lines.append(
        f"Totals: findings={totals.get('findings', 0)} warn={totals.get('counts', {}).get('warn', 0)} error={totals.get('counts', {}).get('error', 0)}"
    )
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


def _project_root_relative(path: Path, *, repo_root: Path) -> str:
    try:
        rel = path.resolve(strict=False).relative_to(repo_root.resolve(strict=True))
    except ValueError:
        return path.name
    return rel.as_posix() or "."


def _aggregate_totals(project_runs: list[dict[str, Any]]) -> dict[str, Any]:
    counts = {"info": 0, "warn": 0, "error": 0}
    total_findings = 0
    total_actionable = 0
    for item in project_runs:
        summary = item.get("summary", {}) if isinstance(item, dict) else {}
        total_findings += int(summary.get("findings", 0))
        policy = summary.get("policy", {}) if isinstance(summary, dict) else {}
        total_actionable += int(policy.get("actionable", summary.get("findings", 0)))
        sev = summary.get("counts", {}) if isinstance(summary, dict) else {}
        for key in counts:
            counts[key] += int(sev.get(key, 0))
    return {
        "counts": {k: counts[k] for k in sorted(counts)},
        "findings": total_findings,
        "actionable": total_actionable,
    }


def _repo_audit_profile_defaults(profile: str) -> RepoAuditPolicy:
    return RepoAuditPolicy(
        profile=profile,
        fail_on="warn",
        baseline_path=".sdetkit/audit-baseline.json",
        exclude_paths=(),
        disable_rules=frozenset(),
        severity_overrides={},
        org_packs=(),
        allowlist=(),
        org_pack_unknown=(),
        lint_expiry_max_days=365,
    )


def _parse_iso_date(raw: str, *, field: str) -> dt.date:
    try:
        return dt.date.fromisoformat(raw)
    except ValueError as exc:
        raise RepoAuditConfigError(f"{field} must be ISO date YYYY-MM-DD") from exc


def _today_date() -> dt.date:
    env_today = os.environ.get("SDETKIT_TODAY")
    if env_today:
        return _parse_iso_date(env_today, field="SDETKIT_TODAY")
    return dt.date.today()


def _allowlist_status(rule: AllowlistRule, today: dt.date) -> str:
    if rule.expires is None:
        return "active"
    return (
        "expired" if _parse_iso_date(rule.expires, field="allowlist expires") < today else "active"
    )


def _normalized_allowlist_entry(rule: AllowlistRule, today: dt.date) -> dict[str, Any]:
    return {
        "rule_id": rule.rule_id,
        "path": rule.path,
        "contains": rule.contains,
        "owner": rule.owner,
        "justification": rule.justification,
        "created": rule.created,
        "expires": rule.expires,
        "ticket": rule.ticket,
        "status": _allowlist_status(rule, today),
    }


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
    cli_org_packs: list[str] | None,
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

    raw_org_packs = raw.get("org_packs")
    if raw_org_packs is not None and not isinstance(raw_org_packs, list):
        raise RepoAuditConfigError("org_packs must be a list of strings")
    org_packs = normalize_org_packs(raw_org_packs)

    raw_max_days = raw.get("lint_expiry_max_days", base.lint_expiry_max_days)
    if not isinstance(raw_max_days, int) or raw_max_days < 1:
        raise RepoAuditConfigError("lint_expiry_max_days must be a positive integer")

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
        owner = item.get("owner")
        justification = item.get("justification")
        created = item.get("created")
        expires = item.get("expires")
        ticket = item.get("ticket")
        if not isinstance(rule_id, str) or not isinstance(path, str):
            raise RepoAuditConfigError("allowlist entries require string rule_id and path")
        if contains is not None and not isinstance(contains, str):
            raise RepoAuditConfigError("allowlist contains must be a string when provided")
        for field_name, value in (
            ("owner", owner),
            ("justification", justification),
            ("created", created),
            ("expires", expires),
            ("ticket", ticket),
        ):
            if value is not None and not isinstance(value, str):
                raise RepoAuditConfigError(f"allowlist {field_name} must be a string")
        if isinstance(created, str):
            _parse_iso_date(created, field="allowlist created")
        if isinstance(expires, str):
            _parse_iso_date(expires, field="allowlist expires")
        allowlist.append(
            AllowlistRule(
                rule_id=rule_id,
                path=path,
                contains=contains,
                owner=(owner or "").strip(),
                justification=(justification or "").strip(),
                created=created,
                expires=expires,
                ticket=ticket,
            )
        )

    if cli_fail_on is not None:
        fail_on = cli_fail_on
    if cli_baseline is not None:
        baseline_path = cli_baseline
    if cli_excludes:
        exclude_paths = exclude_paths + tuple(cli_excludes)
    if cli_disable_rules:
        disable_rules.update(cli_disable_rules)
    if cli_org_packs:
        org_packs = normalize_org_packs(cli_org_packs)

    known_rule_ids = {item.meta.id for item in load_rule_catalog().rules}
    fail_on, severity_overrides, unknown_org = apply_pack_defaults(
        selected_org_packs=org_packs,
        available=load_repo_audit_packs(),
        base_fail_on=fail_on,
        base_severity_overrides=severity_overrides,
        known_rule_ids=known_rule_ids,
    )

    return RepoAuditPolicy(
        profile=profile,
        fail_on=fail_on,
        baseline_path=baseline_path,
        exclude_paths=tuple(exclude_paths),
        disable_rules=frozenset(disable_rules),
        severity_overrides=severity_overrides,
        org_packs=org_packs,
        allowlist=tuple(allowlist),
        org_pack_unknown=unknown_org,
        lint_expiry_max_days=raw_max_days,
    )


def _repo_rule_id(item: dict[str, Any]) -> str:
    explicit = item.get("rule_id")
    if isinstance(explicit, str) and explicit:
        return explicit
    return f"{item.get('check', 'repo_audit')}/{item.get('code', 'unknown')}"


def _effective_packs(policy: RepoAuditPolicy, pack_csv: str | None) -> tuple[str, ...]:
    return merge_packs(normalize_packs(policy.profile, pack_csv), policy.org_packs)


def _policy_lint(policy: RepoAuditPolicy, *, fail_on: str, fmt: str) -> tuple[int, str]:
    known_rule_ids = {item.meta.id for item in load_rule_catalog().rules}
    today = _today_date()
    warnings: list[dict[str, str]] = []
    errors: list[dict[str, str]] = []
    seen: set[tuple[str, str, str]] = set()
    for idx, item in enumerate(policy.allowlist, start=1):
        if not item.owner.strip():
            errors.append({"code": "missing_owner", "message": f"allowlist[{idx}] missing owner"})
        if not item.justification.strip():
            errors.append(
                {
                    "code": "missing_justification",
                    "message": f"allowlist[{idx}] missing justification",
                }
            )
        key = (item.rule_id, item.path, item.contains or "")
        if key in seen:
            warnings.append(
                {
                    "code": "duplicate_allowlist",
                    "message": f"allowlist[{idx}] duplicates rule/path/contains",
                }
            )
        seen.add(key)
        if item.expires:
            expires = _parse_iso_date(item.expires, field="allowlist expires")
            if expires < today:
                warnings.append(
                    {
                        "code": "expired_allowlist",
                        "message": f"allowlist[{idx}] expired on {item.expires}",
                    }
                )
            if (expires - today).days > policy.lint_expiry_max_days:
                warnings.append(
                    {
                        "code": "long_expiry",
                        "message": f"allowlist[{idx}] expires beyond threshold",
                    }
                )
    for rule_id in sorted(policy.disable_rules):
        if rule_id not in known_rule_ids:
            warnings.append(
                {
                    "code": "unknown_disable_rule",
                    "message": f"disable_rules contains unknown rule id: {rule_id}",
                }
            )
    for rule_id in sorted(policy.severity_overrides):
        if rule_id not in known_rule_ids:
            warnings.append(
                {
                    "code": "unknown_severity_override",
                    "message": f"severity_overrides contains unknown rule id: {rule_id}",
                }
            )
    for name in sorted(policy.org_pack_unknown):
        warnings.append({"code": "unknown_org_pack", "message": f"unknown org pack: {name}"})
    warnings.sort(key=lambda x: (x["code"], x["message"]))
    errors.sort(key=lambda x: (x["code"], x["message"]))
    payload = {
        "schema_version": "sdetkit.policy-lint.v1",
        "counts": {"errors": len(errors), "warnings": len(warnings)},
        "errors": errors,
        "warnings": warnings,
    }
    rendered = (
        json.dumps(payload, ensure_ascii=True, sort_keys=True, indent=2) + "\n"
        if fmt == "json"
        else "\n".join(["Policy lint", f"errors={len(errors)} warnings={len(warnings)}"]).rstrip()
        + "\n"
    )
    if fail_on == "warn" and (warnings or errors):
        return 1, rendered
    if fail_on == "error" and errors:
        return 1, rendered
    return 0, rendered


def _policy_export(policy: RepoAuditPolicy, *, include_expired: bool) -> dict[str, Any]:
    today = _today_date()
    entries = [_normalized_allowlist_entry(item, today) for item in policy.allowlist]
    if not include_expired:
        entries = [item for item in entries if item["status"] == "active"]
    entries.sort(key=lambda x: (x["rule_id"], x["path"], x.get("contains") or ""))
    return {
        "schema_version": "sdetkit.policy.v1",
        "today": today.isoformat(),
        "org_packs": list(policy.org_packs),
        "allowlist": entries,
    }


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
    expired: list[dict[str, str]] = []
    today = _today_date()
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
            if _allowlist_status(rule, today) == "expired":
                expired.append(
                    {
                        "fingerprint": item["fingerprint"],
                        "reason": "policy:allowlist:expired",
                        "expires": str(rule.expires or ""),
                    }
                )
                item["suppression_status"] = "expired_allowlist"
                item["suppression_reason"] = f"allowlist expired on {rule.expires}"
                allowlisted = False
                break
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
        "suppressed_active": sum(1 for x in suppressed if x["reason"] == "policy:allowlist"),
        "suppressed_expired": len(expired),
    }
    return actionable, {"counts": counts, "suppressed": suppressed, "expired": expired}


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
        "tool_version": "1.0.0",
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


def _to_posix_relpath(path: str) -> str:
    normalized = str(path).replace("\\", "/")
    while normalized.startswith("./"):
        normalized = normalized[2:]
    return normalized.lstrip("/") or "."


def _to_ide_diagnostics(findings: list[dict[str, Any]]) -> dict[str, Any]:
    diagnostics: list[dict[str, Any]] = []
    for item in findings:
        row: dict[str, Any] = {
            "path": _to_posix_relpath(str(item.get("path", "."))),
            "line": int(item.get("line") or 1),
            "severity": str(item.get("severity", "error")),
            "code": _repo_rule_id(item),
            "message": str(item.get("message", "")),
            "fixable": bool(item.get("fixable", False)),
        }
        col = item.get("column")
        if isinstance(col, int) and col > 0:
            row["col"] = col
        diagnostics.append(row)
    diagnostics.sort(
        key=lambda x: (
            str(x.get("path", "")),
            int(x.get("line", 1)),
            int(x.get("col", 0)),
            str(x.get("code", "")),
            str(x.get("message", "")),
        )
    )
    return {"schema_version": "sdetkit.ide.diagnostics.v1", "diagnostics": diagnostics}


def _build_precommit_entry(*, profile: str | None, pack: str, mode: str) -> str:
    args = ["sdetkit", "repo", "audit", "--pack", pack]
    if profile:
        args.extend(["--profile", profile])
    if mode == "changed-only":
        args.append("--changed-only")
    args.extend(["--fail-on", "error"])
    return " ".join(args)


def _precommit_hook_item(*, profile: str | None, pack: str, mode: str, indent: int = 6) -> str:
    pad = " " * indent
    entry = _build_precommit_entry(profile=profile, pack=pack, mode=mode)
    lines = [
        f"{pad}- id: sdetkit-repo-audit",
        f"{pad}  name: sdetkit repo audit",
        f"{pad}  entry: {entry}",
        f"{pad}  language: system",
        f"{pad}  pass_filenames: false",
    ]
    return "\n".join(lines)


def _default_precommit_config(*, profile: str | None, pack: str, mode: str) -> str:
    hook = _precommit_hook_item(profile=profile, pack=pack, mode=mode, indent=6)
    return f"repos:\n  - repo: local\n    hooks:\n{hook}\n"


def _update_precommit_yaml(
    existing: str, *, profile: str | None, pack: str, mode: str
) -> tuple[str, str]:
    normalized = existing.replace("\r\n", "\n")
    lines = normalized.split("\n")
    hook_idx = next(
        (
            i
            for i, line in enumerate(lines)
            if re.match(r"^\s*-\s+id:\s*sdetkit-repo-audit\s*$", line)
        ),
        None,
    )
    if hook_idx is not None:
        start = hook_idx
        indent = len(lines[hook_idx]) - len(lines[hook_idx].lstrip(" "))
        end = hook_idx + 1
        while end < len(lines):
            cur = lines[end]
            cur_indent = len(cur) - len(cur.lstrip(" "))
            if cur.strip() and cur_indent <= indent and cur.lstrip(" ").startswith("-"):
                break
            end += 1
        repl = _precommit_hook_item(profile=profile, pack=pack, mode=mode, indent=indent).split(
            "\n"
        )
        updated = "\n".join(lines[:start] + repl + lines[end:]).rstrip("\n") + "\n"
        return updated, "updated"

    repo_key_idx = next((i for i, line in enumerate(lines) if line.strip() == "repos:"), None)
    if repo_key_idx is None:
        raise ValueError("no top-level repos: section found")
    insert_at = len(lines)
    for idx in range(repo_key_idx + 1, len(lines)):
        line = lines[idx]
        if not line.strip() or line.lstrip(" ").startswith("#"):
            continue
        if not line.startswith(" ") and ":" in line:
            insert_at = idx
            break
    block = [
        "  - repo: local",
        "    hooks:",
        *_precommit_hook_item(profile=profile, pack=pack, mode=mode, indent=6).split("\n"),
    ]
    updated_lines = lines[:insert_at]
    if updated_lines and updated_lines[-1].strip():
        updated_lines.append("")
    updated_lines.extend(block)
    updated_lines.extend(lines[insert_at:])
    updated = "\n".join(updated_lines).rstrip("\n") + "\n"
    return updated, "added"


def _precommit_diff(before: str, after: str) -> str:
    if before == after:
        return ""
    return "\n".join(
        difflib.unified_diff(
            before.splitlines(),
            after.splitlines(),
            fromfile=".pre-commit-config.yaml(old)",
            tofile=".pre-commit-config.yaml(new)",
            lineterm="",
        )
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="sdetkit repo")
    sub = parser.add_subparsers(dest="repo_cmd", required=True)

    cp = sub.add_parser("check")
    cp.add_argument("path", nargs="?", default=".")
    cp.add_argument("--format", choices=["text", "json", "md", "sarif", "html"], default="text")
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
    ip.add_argument("--preset", choices=sorted(REPO_PRESETS), required=True)
    ip.add_argument("--root", default=".")
    ip.add_argument("--dry-run", action="store_true")
    ip.add_argument("--force", action="store_true")
    ip.add_argument("--diff", action="store_true")
    ip.add_argument("--allow-absolute-path", action="store_true")

    aply = sub.add_parser("apply")
    aply.add_argument("--preset", choices=sorted(REPO_PRESETS), required=True)
    aply.add_argument("--root", default=".")
    aply.add_argument("--dry-run", action="store_true")
    aply.add_argument("--force", action="store_true")
    aply.add_argument("--diff", action="store_true")
    aply.add_argument("--allow-absolute-path", action="store_true")

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
    ap.add_argument("--org-pack", action="append", default=[])
    ap.add_argument("--format", choices=["text", "json", "sarif", "md", "html"], default="text")
    ap.add_argument("--json-schema", choices=["legacy", "v1"], default="legacy")
    ap.add_argument("--output", "--out", dest="output", default=None)
    ap.add_argument("--fail-on", choices=["none", "warn", "error"], default=None)
    ap.add_argument("--config", default=None)
    ap.add_argument("--baseline", default=None)
    ap.add_argument("--update-baseline", action="store_true")
    ap.add_argument("--exclude", action="append", default=[])
    ap.add_argument("--disable-rule", action="append", default=[])
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--allow-absolute-path", action="store_true")
    ap.add_argument("--emit-run-record", default=None)
    ap.add_argument("--diff-against", default=None)
    ap.add_argument("--step-summary", action="store_true")
    ap.add_argument("--all-projects", action="store_true")
    ap.add_argument("--sort", action="store_true")
    ap.add_argument("--fail-strategy", choices=["overall", "per-project"], default="overall")

    ap.add_argument("--changed-only", action="store_true")
    ap.add_argument("--since-ref", default="HEAD~1")
    ap.add_argument("--include-untracked", action=argparse.BooleanOptionalAction, default=True)
    ap.add_argument("--include-staged", action=argparse.BooleanOptionalAction, default=True)
    ap.add_argument("--require-git", action="store_true")
    ap.add_argument("--cache-dir", default=".sdetkit/cache")
    ap.add_argument("--no-cache", action="store_true")
    ap.add_argument("--cache-stats", action="store_true")
    ap.add_argument("--jobs", type=int, default=1)
    ap.add_argument("--ide", choices=["vscode", "generic"], default=None)
    ap.add_argument("--ide-output", default=None)
    ap.add_argument("--include-suppressed", action="store_true")

    dp = sub.add_parser("dev")
    dsub = dp.add_subparsers(dest="dev_cmd", required=True)

    da = dsub.add_parser("audit")
    da.add_argument("path", nargs="?", default=".")
    da.add_argument("--allow-absolute-path", action="store_true")
    da.add_argument("--pack", default="core")
    da.add_argument("--profile", choices=["default", "enterprise"], default=None)
    da.add_argument("--mode", choices=["changed-only", "full"], default="changed-only")

    df = dsub.add_parser("fix")
    df.add_argument("path", nargs="?", default=".")
    df.add_argument("--allow-absolute-path", action="store_true")
    df.add_argument("--apply", action="store_true")
    df.add_argument("--diff", action="store_true")
    df.add_argument("--pack", default="core")
    df.add_argument("--profile", choices=["default", "enterprise"], default=None)
    df.add_argument("--mode", choices=["changed-only", "full"], default="changed-only")

    dpc = dsub.add_parser("precommit")
    dpcsub = dpc.add_subparsers(dest="precommit_cmd", required=True)
    dpc_install = dpcsub.add_parser("install")
    dpc_install.add_argument("path", nargs="?", default=".")
    dpc_install.add_argument("--profile", choices=["default", "enterprise"], default=None)
    dpc_install.add_argument("--pack", default="core")
    dpc_install.add_argument("--mode", choices=["changed-only", "full"], default="changed-only")
    dpc_install.add_argument("--apply", action="store_true")
    dpc_install.add_argument("--dry-run", action="store_true")
    dpc_install.add_argument("--force", action="store_true")
    dpc_install.add_argument("--diff", action="store_true")
    dpc_install.add_argument("--allow-absolute-path", action="store_true")

    projp = sub.add_parser("projects")
    projsub = projp.add_subparsers(dest="projects_cmd", required=True)
    projlist = projsub.add_parser("list")
    projlist.add_argument("path", nargs="?", default=".")
    projlist.add_argument("--json", action="store_true")
    projlist.add_argument("--sort", action="store_true")
    projlist.add_argument("--allow-absolute-path", action="store_true")

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
    fxap.add_argument("--org-pack", action="append", default=[])
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
    fxap.add_argument("--project", default=None)
    fxap.add_argument("--all-projects", action="store_true")
    fxap.add_argument("--sort", action="store_true")
    fxap.add_argument("--changed-only", action="store_true")
    fxap.add_argument("--since-ref", default="HEAD~1")
    fxap.add_argument("--include-untracked", action=argparse.BooleanOptionalAction, default=True)
    fxap.add_argument("--include-staged", action=argparse.BooleanOptionalAction, default=True)
    fxap.add_argument("--require-git", action="store_true")
    fxap.add_argument("--cache-dir", default=".sdetkit/cache")
    fxap.add_argument("--no-cache", action="store_true")
    fxap.add_argument("--cache-stats", action="store_true")
    fxap.add_argument("--jobs", type=int, default=1)

    prp = sub.add_parser("pr-fix")
    prp.add_argument("path", nargs="?", default=".")
    prp.add_argument("--profile", choices=["default", "enterprise"], default=None)
    prp.add_argument("--pack", default=None)
    prp.add_argument("--org-pack", action="append", default=[])
    prp.add_argument("--config", default=None)
    prp.add_argument("--baseline", default=None)
    prp.add_argument("--exclude", action="append", default=[])
    prp.add_argument("--disable-rule", action="append", default=[])
    prp.add_argument("--dry-run", action="store_true")
    prp.add_argument("--apply", action="store_true")
    prp.add_argument("--force", action="store_true")
    prp.add_argument("--diff", action="store_true")
    prp.add_argument("--patch", default=None)
    prp.add_argument("--allow-absolute-path", action="store_true")
    prp.add_argument("--project", default=None)
    prp.add_argument("--all-projects", action="store_true")
    prp.add_argument("--sort", action="store_true")
    prp.add_argument("--changed-only", action="store_true")
    prp.add_argument("--since-ref", default="HEAD~1")
    prp.add_argument("--include-untracked", action=argparse.BooleanOptionalAction, default=True)
    prp.add_argument("--include-staged", action=argparse.BooleanOptionalAction, default=True)
    prp.add_argument("--require-git", action="store_true")
    prp.add_argument("--cache-dir", default=".sdetkit/cache")
    prp.add_argument("--no-cache", action="store_true")
    prp.add_argument("--cache-stats", action="store_true")
    prp.add_argument("--jobs", type=int, default=1)

    prp.add_argument("--branch", default="sdetkit/fix-audit")
    prp.add_argument("--force-branch", action="store_true")
    prp.add_argument("--commit", dest="commit", action="store_true", default=None)
    prp.add_argument("--no-commit", dest="commit", action="store_false")
    prp.add_argument("--commit-message", default=None)
    prp.add_argument("--author", default=None)
    prp.add_argument("--base-ref", default=None)
    prp.add_argument("--open-pr", action="store_true")
    prp.add_argument("--remote", default="origin")
    prp.add_argument("--repo", default=None)
    prp.add_argument("--token-env", default="GITHUB_TOKEN")
    prp.add_argument("--title", default=None)
    prp.add_argument("--body", default=None)
    prp.add_argument("--body-file", default=None)
    prp.add_argument("--draft", action="store_true")
    prp.add_argument("--labels", default=None)

    pp = sub.add_parser("policy")
    psub = pp.add_subparsers(dest="policy_cmd", required=True)
    plint = psub.add_parser("lint")
    plint.add_argument("path", nargs="?", default=".")
    plint.add_argument("--config", default=None)
    plint.add_argument("--format", choices=["text", "json"], default="text")
    plint.add_argument("--fail-on", choices=["none", "warn", "error"], default="warn")
    plint.add_argument("--allow-absolute-path", action="store_true")
    pexport = psub.add_parser("export")
    pexport.add_argument("path", nargs="?", default=".")
    pexport.add_argument("--config", default=None)
    pexport.add_argument("--output", default=None)
    pexport.add_argument("--include-expired", action="store_true")
    pexport.add_argument("--allow-absolute-path", action="store_true")
    pexport.add_argument("--force", action="store_true")

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

    if ns.repo_cmd == "projects":
        try:
            projects_root = _resolve_root(ns.path, allow_absolute=bool(ns.allow_absolute_path))
            source, projects = discover_projects(projects_root, sort=bool(ns.sort))
        except (SecurityError, ProjectsConfigError, OSError, ValueError) as exc:
            print(str(exc), file=sys.stderr)
            return 2
        records = []
        for project in projects:
            resolved = resolve_project(projects_root, project)
            records.append(
                {
                    "name": resolved.name,
                    "root": resolved.root_rel,
                    "root_resolved": str(resolved.root),
                    "config": resolved.config_rel,
                    "config_resolved": str(resolved.config_path) if resolved.config_path else None,
                    "profile": resolved.profile,
                    "packs": list(resolved.packs),
                    "baseline": resolved.baseline_rel,
                    "exclude": list(resolved.exclude_paths),
                }
            )
        projects_payload = {"manifest": source, "projects": records}
        if ns.json:
            sys.stdout.write(
                json.dumps(projects_payload, ensure_ascii=True, sort_keys=True, indent=2) + "\n"
            )
            return 0
        if source:
            print(f"Manifest: {source}")
        for rec in records:
            print(f"- {rec['name']}: root={rec['root']} baseline={rec['baseline']}")
        return 0

    target_path = getattr(ns, "path", getattr(ns, "root", "."))
    try:
        root = _resolve_root(target_path, allow_absolute=bool(ns.allow_absolute_path))
    except SecurityError as exc:
        print(str(exc), file=sys.stderr)
        return 2

    if (
        getattr(ns, "changed_only", False)
        and getattr(ns, "require_git", False)
        and not _git_available(root)
    ):
        print(
            "--require-git requested but git is unavailable or path is not a git repository",
            file=sys.stderr,
        )
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
                cli_org_packs=None,
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
                root, profile=policy.profile, packs=_effective_packs(policy, None)
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
        resolved_fps = sorted(old_fps - new_fps)
        print(f"NEW: {len(new_only)} RESOLVED: {len(resolved_fps)} UNCHANGED: {len(unchanged)}")
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

    if ns.repo_cmd == "policy":
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
                cli_profile=None,
                cli_fail_on=None,
                cli_baseline=None,
                cli_excludes=None,
                cli_disable_rules=None,
                cli_org_packs=None,
                config_path=config_file,
            )
        except RepoAuditConfigError as exc:
            print(str(exc), file=sys.stderr)
            return 2

        if ns.policy_cmd == "lint":
            code, rendered = _policy_lint(policy, fail_on=ns.fail_on, fmt=ns.format)
            sys.stdout.write(rendered)
            return code

        rendered = (
            json.dumps(
                _policy_export(policy, include_expired=bool(ns.include_expired)),
                ensure_ascii=True,
                sort_keys=True,
                indent=2,
            )
            + "\n"
        )
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
        return 0

    if ns.repo_cmd == "dev":
        if ns.dev_cmd == "audit":
            args = [
                "audit",
                ns.path,
                "--pack",
                ns.pack,
                "--fail-on",
                "error",
                "--allow-absolute-path",
            ]
            if ns.profile:
                args.extend(["--profile", ns.profile])
            if ns.mode == "changed-only":
                args.append("--changed-only")
            return main(args)

        if ns.dev_cmd == "fix":
            args = [
                "fix-audit",
                ns.path,
                "--pack",
                ns.pack,
                "--allow-absolute-path",
            ]
            if ns.profile:
                args.extend(["--profile", ns.profile])
            if ns.mode == "changed-only":
                args.append("--changed-only")
            if ns.diff:
                args.append("--diff")
            if ns.apply:
                args.append("--apply")
            else:
                args.append("--dry-run")
            return main(args)

        if ns.dev_cmd == "precommit" and ns.precommit_cmd == "install":
            target_root = safe_path(root, ns.path, allow_absolute=bool(ns.allow_absolute_path))
            if not target_root.exists() or not target_root.is_dir():
                print(
                    f"target path does not exist or is not a directory: {ns.path}", file=sys.stderr
                )
                return 2
            target = target_root / ".pre-commit-config.yaml"
            before = target.read_text(encoding="utf-8") if target.exists() else ""
            creating = not target.exists()
            try:
                after = (
                    _default_precommit_config(profile=ns.profile, pack=ns.pack, mode=ns.mode)
                    if creating
                    else _update_precommit_yaml(
                        before,
                        profile=ns.profile,
                        pack=ns.pack,
                        mode=ns.mode,
                    )[0]
                )
            except ValueError as exc:
                if not ns.force:
                    print(
                        f"unable to merge existing .pre-commit-config.yaml: {exc}", file=sys.stderr
                    )
                    return 2
                after = _default_precommit_config(profile=ns.profile, pack=ns.pack, mode=ns.mode)

            changed = before.replace("\r\n", "\n") != after
            if ns.diff:
                diff = _precommit_diff(before.replace("\r\n", "\n"), after)
                if diff:
                    print(diff)
            print(
                f"precommit install plan: {'create' if creating else 'update'} {target.as_posix()}"
            )
            if not changed:
                print("precommit install: already up to date")
                return 0
            if ns.dry_run or not ns.apply:
                print("precommit install: dry-run (no changes written)")
                return 0
            atomic_write_text(target, after)
            print("precommit install: wrote .pre-commit-config.yaml")
            return 0

    if ns.repo_cmd == "audit":
        if ns.all_projects:
            try:
                source, projects = discover_projects(root, sort=bool(ns.sort))
            except (ProjectsConfigError, OSError, ValueError) as exc:
                print(str(exc), file=sys.stderr)
                return 2
            project_runs: list[dict[str, Any]] = []
            failures = 0
            for project in projects:
                resolved = resolve_project(root, project)
                config_file = resolved.config_path
                try:
                    policy = _resolve_repo_audit_policy(
                        resolved.root,
                        cli_profile=ns.profile or resolved.profile,
                        cli_fail_on=getattr(ns, "fail_on", None),
                        cli_baseline=ns.baseline or resolved.baseline_rel,
                        cli_excludes=list(resolved.exclude_paths) + list(ns.exclude or []),
                        cli_disable_rules=ns.disable_rule,
                        cli_org_packs=ns.org_pack,
                        config_path=config_file,
                    )
                except RepoAuditConfigError as exc:
                    print(str(exc), file=sys.stderr)
                    return 2
                if ns.pack:
                    packs = _effective_packs(policy, ns.pack)
                elif resolved.packs:
                    packs = merge_packs(tuple(resolved.packs), policy.org_packs)
                else:
                    packs = _effective_packs(policy, None)
                project_payload = run_repo_audit(
                    resolved.root,
                    profile=policy.profile,
                    packs=packs,
                    changed_only=bool(ns.changed_only),
                    since_ref=str(ns.since_ref),
                    include_untracked=bool(ns.include_untracked),
                    include_staged=bool(ns.include_staged),
                    require_git=bool(ns.require_git),
                    cache_dir=str(ns.cache_dir),
                    no_cache=bool(ns.no_cache),
                    cache_stats=bool(ns.cache_stats),
                    jobs=int(ns.jobs),
                )
                original_findings = [
                    x for x in project_payload.get("findings", []) if isinstance(x, dict)
                ]
                baseline_path = safe_path(
                    resolved.root, policy.baseline_path, allow_absolute=bool(ns.allow_absolute_path)
                )
                baseline_doc = _load_repo_baseline(baseline_path)
                actionable, suppression = _apply_repo_audit_policy(
                    original_findings, policy, baseline_doc.get("entries", [])
                )
                project_payload["findings"] = (
                    original_findings if ns.include_suppressed else actionable
                )
                counts = {"error": 0, "warn": 0, "info": 0}
                for finding in actionable:
                    sev = str(finding.get("severity", "error"))
                    counts[sev] = counts.get(sev, 0) + 1
                project_summary = cast(dict[str, Any], project_payload.get("summary", {}))
                project_summary["counts"] = {k: counts[k] for k in sorted(counts)}
                project_summary["findings"] = len(actionable)
                project_summary["policy"] = {
                    "total_findings": len(original_findings),
                    "suppressed_by_baseline": suppression["counts"]["baseline"],
                    "suppressed_by_policy": suppression["counts"]["policy"],
                    "suppressed_active": suppression["counts"]["suppressed_active"],
                    "suppressed_expired": suppression["counts"]["suppressed_expired"],
                    "actionable": len(actionable),
                }
                project_payload["summary"] = project_summary
                project_payload["suppressed"] = suppression["suppressed"]
                project_payload["suppressed_expired"] = suppression["expired"]
                run_record = build_run_record(
                    project_payload,
                    profile=policy.profile,
                    packs=packs,
                    fail_on=policy.fail_on,
                    repo_root=resolved.root_rel,
                    config_used=resolved.config_rel,
                    incremental_used=bool(
                        project_summary.get("incremental", {}).get("used", False)
                    ),
                    changed_file_count=int(
                        project_summary.get("incremental", {}).get("changed_files", 0)
                    ),
                    cache_summary=project_summary.get("cache")
                    if isinstance(project_summary.get("cache"), dict)
                    else None,
                )
                project_failed = _needs_fail_repo_audit(actionable, policy.fail_on)
                failures += int(project_failed)
                project_runs.append(
                    {
                        "name": resolved.name,
                        "root": resolved.root_rel,
                        "summary": project_payload.get("summary", {}),
                        "run_record": run_record,
                        "failed": project_failed,
                    }
                )
            aggregate = {
                "schema_version": "sdetkit.audit.aggregate.v1",
                "root": str(root),
                "manifest": source,
                "projects": project_runs,
                "totals": _aggregate_totals(project_runs),
                "deltas": {"new": 0, "resolved": 0, "unchanged": 0},
            }
            if ns.ide_output:
                diagnostics: list[dict[str, Any]] = []
                for item in project_runs:
                    run_record = item.get("run_record", {})
                    findings = (
                        run_record.get("findings", []) if isinstance(run_record, dict) else []
                    )
                    for finding_item in findings:
                        if not isinstance(finding_item, dict):
                            continue
                        rel_root = str(item.get("root", "")).strip("/")
                        finding_path = _to_posix_relpath(str(finding_item.get("path", ".")))
                        prefixed = dict(finding_item)
                        prefixed["path"] = (
                            f"{rel_root}/{finding_path}" if rel_root else finding_path
                        )
                        diagnostics.append(prefixed)
                ide_doc = _to_ide_diagnostics(diagnostics)
                ide_target = safe_path(
                    root, ns.ide_output, allow_absolute=bool(ns.allow_absolute_path)
                )
                if ide_target.exists() and not ns.force:
                    print(
                        "refusing to overwrite existing ide output (use --force)", file=sys.stderr
                    )
                    return 2
                atomic_write_text(
                    ide_target,
                    json.dumps(ide_doc, ensure_ascii=True, sort_keys=True, indent=2) + "\n",
                )
            rendered = _render_repo_audit_aggregate(aggregate, ns.format)
            if ns.output:
                out_path = safe_path(root, ns.output, allow_absolute=bool(ns.allow_absolute_path))
                if out_path.exists() and not ns.force:
                    print("refusing to overwrite existing output (use --force)", file=sys.stderr)
                    return 2
                atomic_write_text(out_path, rendered)
            else:
                sys.stdout.write(rendered)
            return 1 if failures > 0 else 0

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
                cli_org_packs=ns.org_pack,
                config_path=config_file,
            )
        except RepoAuditConfigError as exc:
            print(str(exc), file=sys.stderr)
            return 2
        packs = _effective_packs(policy, ns.pack)
        audit_payload = run_repo_audit(
            root,
            profile=policy.profile,
            packs=packs,
            changed_only=bool(ns.changed_only),
            since_ref=str(ns.since_ref),
            include_untracked=bool(ns.include_untracked),
            include_staged=bool(ns.include_staged),
            require_git=bool(ns.require_git),
            cache_dir=str(ns.cache_dir),
            no_cache=bool(ns.no_cache),
            cache_stats=bool(ns.cache_stats),
            jobs=int(ns.jobs),
        )
        original_findings = [x for x in audit_payload.get("findings", []) if isinstance(x, dict)]
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
        audit_payload["findings"] = original_findings if ns.include_suppressed else actionable
        counts = {"error": 0, "warn": 0, "info": 0}
        for finding in actionable:
            sev = str(finding.get("severity", "error"))
            counts[sev] = counts.get(sev, 0) + 1
        audit_summary = cast(dict[str, Any], audit_payload.get("summary", {}))
        audit_summary["counts"] = {k: counts[k] for k in sorted(counts)}
        audit_summary["findings"] = len(actionable)
        audit_summary["policy"] = {
            "total_findings": len(original_findings),
            "suppressed_by_baseline": suppression["counts"]["baseline"],
            "suppressed_by_policy": suppression["counts"]["policy"],
            "suppressed_active": suppression["counts"]["suppressed_active"],
            "suppressed_expired": suppression["counts"]["suppressed_expired"],
            "actionable": len(actionable),
        }
        audit_payload["summary"] = audit_summary
        audit_payload["suppressed"] = suppression["suppressed"]
        audit_payload["suppressed_expired"] = suppression["expired"]
        run_record = build_run_record(
            audit_payload,
            profile=policy.profile,
            packs=packs,
            fail_on=policy.fail_on,
            repo_root=str(root),
            config_used=ns.config,
            incremental_used=bool(audit_summary.get("incremental", {}).get("used", False)),
            changed_file_count=int(audit_summary.get("incremental", {}).get("changed_files", 0)),
            cache_summary=audit_summary.get("cache")
            if isinstance(audit_summary.get("cache"), dict)
            else None,
        )
        if ns.json_schema == "v1" and ns.format == "json":
            audit_payload = run_record

        diff_payload = None
        if ns.diff_against:
            try:
                previous = load_run_record(
                    safe_path(root, ns.diff_against, allow_absolute=bool(ns.allow_absolute_path))
                )
                diff_payload = diff_runs(previous, run_record)
                print(
                    "NEW: "
                    f"{diff_payload['counts']['new']} RESOLVED: {diff_payload['counts']['resolved']} "
                    f"UNCHANGED: {diff_payload['counts']['unchanged']}"
                )
            except (ValueError, OSError, SecurityError) as exc:
                print(str(exc), file=sys.stderr)
                return 2

        if ns.emit_run_record:
            try:
                run_target = safe_path(
                    root, ns.emit_run_record, allow_absolute=bool(ns.allow_absolute_path)
                )
                if run_target.exists() and not ns.force:
                    print("refusing to overwrite existing output (use --force)", file=sys.stderr)
                    return 2
                atomic_write_text(
                    run_target,
                    json.dumps(run_record, ensure_ascii=True, sort_keys=True, indent=2) + "\n",
                )
            except (SecurityError, OSError, ValueError) as exc:
                print(str(exc), file=sys.stderr)
                return 2

        if ns.step_summary:
            summary_path = os.environ.get("GITHUB_STEP_SUMMARY")
            if summary_path:
                actionable = [x for x in run_record.get("findings", []) if not x.get("suppressed")]
                actionable_sorted = sorted(
                    actionable,
                    key=lambda x: (
                        -_severity_rank(str(x.get("severity", "error"))),
                        str(x.get("rule_id", "")),
                        str(x.get("path", "")),
                    ),
                )
                lines = [
                    "## sdetkit repo audit summary",
                    "",
                    f"- total findings: {len(run_record.get('findings', []))}",
                    f"- suppressed: {run_record.get('aggregates', {}).get('counts_suppressed', 0)}",
                    f"- actionable: {len(actionable)}",
                ]
                if diff_payload is not None:
                    lines.append(f"- NEW: {diff_payload['counts']['new']}")
                    lines.append(f"- RESOLVED: {diff_payload['counts']['resolved']}")
                lines.extend(["", "### Top 10 actionable findings", ""])
                for item in actionable_sorted[:10]:
                    lines.append(
                        f"- [{item.get('severity')}] `{item.get('rule_id')}` `{item.get('path')}`: {item.get('message')}"
                    )
                lines.extend(["", "Run: sdetkit repo fix-audit --dry-run", ""])
                try:
                    with Path(summary_path).open("a", encoding="utf-8") as handle:
                        handle.write("\n".join(lines))
                except OSError as exc:
                    print(str(exc), file=sys.stderr)
                    return 2

        rendered = _render_repo_audit(audit_payload, ns.format)
        if ns.ide_output:
            try:
                ide_target = safe_path(
                    root, ns.ide_output, allow_absolute=bool(ns.allow_absolute_path)
                )
                if ide_target.exists() and not ns.force:
                    print(
                        "refusing to overwrite existing ide output (use --force)", file=sys.stderr
                    )
                    return 2
                ide_findings = original_findings if ns.include_suppressed else actionable
                atomic_write_text(
                    ide_target,
                    json.dumps(
                        _to_ide_diagnostics(ide_findings),
                        ensure_ascii=True,
                        sort_keys=True,
                        indent=2,
                    )
                    + "\n",
                )
            except (SecurityError, OSError, ValueError) as exc:
                print(str(exc), file=sys.stderr)
                return 2
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
        return 1 if _needs_fail_repo_audit(actionable, policy.fail_on) else 0

    if ns.repo_cmd == "fix-audit":
        if ns.dry_run and ns.apply:
            print("cannot use --dry-run and --apply together", file=sys.stderr)
            return 2
        if ns.project and ns.all_projects:
            print("cannot use --project with --all-projects", file=sys.stderr)
            return 2
        if ns.project or ns.all_projects:
            try:
                _, projects = discover_projects(root, sort=bool(ns.sort))
            except (ProjectsConfigError, OSError, ValueError) as exc:
                print(str(exc), file=sys.stderr)
                return 2
            selected = projects
            if ns.project:
                selected = [p for p in projects if p.name == ns.project]
                if not selected:
                    print(f"unknown project: {ns.project}", file=sys.stderr)
                    return 2
            exit_code = 0
            for project in selected:
                resolved = resolve_project(root, project)
                try:
                    policy = _resolve_repo_audit_policy(
                        resolved.root,
                        cli_profile=ns.profile or resolved.profile,
                        cli_fail_on="none",
                        cli_baseline=ns.baseline or resolved.baseline_rel,
                        cli_excludes=list(resolved.exclude_paths) + list(ns.exclude or []),
                        cli_disable_rules=ns.disable_rule,
                        cli_org_packs=ns.org_pack,
                        config_path=resolved.config_path,
                    )
                except RepoAuditConfigError as exc:
                    print(str(exc), file=sys.stderr)
                    return 2
                if ns.pack:
                    packs = _effective_packs(policy, ns.pack)
                elif resolved.packs:
                    packs = merge_packs(tuple(resolved.packs), policy.org_packs)
                else:
                    packs = _effective_packs(policy, None)
                rc = _run_repo_fix_audit(
                    resolved.root,
                    profile=policy.profile,
                    packs=packs,
                    policy=policy,
                    dry_run=bool(ns.dry_run) or not bool(ns.apply),
                    apply=bool(ns.apply),
                    force=bool(ns.force),
                    show_diff=bool(ns.diff),
                    patch_path=ns.patch,
                    allow_absolute_path=bool(ns.allow_absolute_path),
                    changed_only=bool(ns.changed_only),
                    since_ref=str(ns.since_ref),
                    include_untracked=bool(ns.include_untracked),
                    include_staged=bool(ns.include_staged),
                    require_git=bool(ns.require_git),
                    cache_dir=str(ns.cache_dir),
                    no_cache=bool(ns.no_cache),
                    cache_stats=bool(ns.cache_stats),
                    jobs=int(ns.jobs),
                )
                exit_code = max(exit_code, rc)
            return exit_code
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
                cli_org_packs=ns.org_pack,
                config_path=config_file,
            )
        except RepoAuditConfigError as exc:
            print(str(exc), file=sys.stderr)
            return 2
        packs = _effective_packs(policy, ns.pack)
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
            changed_only=bool(ns.changed_only),
            since_ref=str(ns.since_ref),
            include_untracked=bool(ns.include_untracked),
            include_staged=bool(ns.include_staged),
            require_git=bool(ns.require_git),
            cache_dir=str(ns.cache_dir),
            no_cache=bool(ns.no_cache),
            cache_stats=bool(ns.cache_stats),
            jobs=int(ns.jobs),
        )

    if ns.repo_cmd == "pr-fix":
        if ns.dry_run and ns.apply:
            print("cannot use --dry-run and --apply together", file=sys.stderr)
            return 2
        if ns.project and ns.all_projects:
            print("cannot use --project with --all-projects", file=sys.stderr)
            return 2
        if ns.body and ns.body_file:
            print("cannot use --body with --body-file", file=sys.stderr)
            return 2
        if ns.open_pr and not ns.apply:
            print("--open-pr requires --apply", file=sys.stderr)
            return 2

        project_results: list[RepoFixProjectResult] = []
        if ns.project or ns.all_projects:
            try:
                _, projects = discover_projects(root, sort=bool(ns.sort))
            except (ProjectsConfigError, OSError, ValueError) as exc:
                print(str(exc), file=sys.stderr)
                return 2
            selected = projects
            if ns.project:
                selected = [p for p in projects if p.name == ns.project]
                if not selected:
                    print(f"unknown project: {ns.project}", file=sys.stderr)
                    return 2
            for project in selected:
                resolved = resolve_project(root, project)
                try:
                    policy = _resolve_repo_audit_policy(
                        resolved.root,
                        cli_profile=ns.profile or resolved.profile,
                        cli_fail_on="none",
                        cli_baseline=ns.baseline or resolved.baseline_rel,
                        cli_excludes=list(resolved.exclude_paths) + list(ns.exclude or []),
                        cli_disable_rules=ns.disable_rule,
                        cli_org_packs=ns.org_pack,
                        config_path=resolved.config_path,
                    )
                except RepoAuditConfigError as exc:
                    print(str(exc), file=sys.stderr)
                    return 2
                if ns.pack:
                    packs = _effective_packs(policy, ns.pack)
                elif resolved.packs:
                    packs = merge_packs(tuple(resolved.packs), policy.org_packs)
                else:
                    packs = _effective_packs(policy, None)
                fixes, conflicts, _ = _plan_repo_fix_audit(
                    resolved.root,
                    profile=policy.profile,
                    packs=packs,
                    policy=policy,
                    allow_absolute_path=bool(ns.allow_absolute_path),
                    force=bool(ns.force),
                    changed_only=bool(ns.changed_only),
                    since_ref=str(ns.since_ref),
                    include_untracked=bool(ns.include_untracked),
                    include_staged=bool(ns.include_staged),
                    require_git=bool(ns.require_git),
                    cache_dir=str(ns.cache_dir),
                    no_cache=bool(ns.no_cache),
                    cache_stats=bool(ns.cache_stats),
                    jobs=int(ns.jobs),
                )
                if conflicts:
                    for rel in conflicts:
                        print(
                            f"refusing to overwrite existing file: {rel} (use --force)",
                            file=sys.stderr,
                        )
                    return 2
                edits = tuple(
                    sorted(
                        [edit for fix in fixes for edit in fix.changes], key=lambda item: item.path
                    )
                )
                project_results.append(
                    RepoFixProjectResult(
                        name=resolved.name,
                        root=resolved.root,
                        root_rel=resolved.root_rel,
                        profile=policy.profile,
                        packs=packs,
                        fixes=tuple(fixes),
                        edits=edits,
                    )
                )
        else:
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
                    cli_org_packs=ns.org_pack,
                    config_path=config_file,
                )
            except RepoAuditConfigError as exc:
                print(str(exc), file=sys.stderr)
                return 2
            packs = _effective_packs(policy, ns.pack)
            fixes, conflicts, _ = _plan_repo_fix_audit(
                root,
                profile=policy.profile,
                packs=packs,
                policy=policy,
                allow_absolute_path=bool(ns.allow_absolute_path),
                force=bool(ns.force),
                changed_only=bool(ns.changed_only),
                since_ref=str(ns.since_ref),
                include_untracked=bool(ns.include_untracked),
                include_staged=bool(ns.include_staged),
                require_git=bool(ns.require_git),
                cache_dir=str(ns.cache_dir),
                no_cache=bool(ns.no_cache),
                cache_stats=bool(ns.cache_stats),
                jobs=int(ns.jobs),
            )
            if conflicts:
                for rel in conflicts:
                    print(
                        f"refusing to overwrite existing file: {rel} (use --force)", file=sys.stderr
                    )
                return 2
            edits = tuple(
                sorted([edit for fix in fixes for edit in fix.changes], key=lambda item: item.path)
            )
            project_results.append(
                RepoFixProjectResult(
                    name="root",
                    root=root,
                    root_rel=".",
                    profile=policy.profile,
                    packs=packs,
                    fixes=tuple(fixes),
                    edits=edits,
                )
            )

        all_fixes = [fix for project in project_results for fix in project.fixes]
        _print_fix_plan(all_fixes, apply=bool(ns.apply))
        all_edits = sorted(
            [(project, edit) for project in project_results for edit in project.edits],
            key=lambda item: (item[0].root_rel, item[1].path),
        )
        patch_data = "".join(
            _unified_diff_for_edit(edit.path, edit.old_text, edit.new_text) for _, edit in all_edits
        )
        if ns.diff and patch_data:
            sys.stdout.write(patch_data)
        if ns.patch:
            patch_target = safe_path(root, ns.patch, allow_absolute=bool(ns.allow_absolute_path))
            if patch_target.exists() and not ns.force:
                print("refusing to overwrite existing patch output (use --force)", file=sys.stderr)
                return 2
            atomic_write_text(patch_target, patch_data.replace("\r\n", "\n"))
        if ns.dry_run or not ns.apply:
            return 0
        if not all_edits:
            print("no changes")
            return 0

        try:
            current_branch = _git_current_branch(root)
        except ValueError as exc:
            print(str(exc), file=sys.stderr)
            return 2
        base_ref = ns.base_ref or current_branch
        if _git_branch_exists(root, ns.branch):
            if not ns.force_branch:
                print(f"branch already exists: {ns.branch} (use --force-branch)", file=sys.stderr)
                return 2
            reset = _git_run(root, ["branch", "-f", ns.branch, base_ref])
            if reset.returncode != 0:
                print(reset.stderr.strip() or "unable to reset branch", file=sys.stderr)
                return 2
        else:
            created = _git_run(root, ["branch", ns.branch, base_ref])
            if created.returncode != 0:
                print(created.stderr.strip() or "unable to create branch", file=sys.stderr)
                return 2
        checked = _git_run(root, ["checkout", ns.branch])
        if checked.returncode != 0:
            print(checked.stderr.strip() or "unable to checkout branch", file=sys.stderr)
            return 2

        for project_result, edit in all_edits:
            target = safe_path(project_result.root, edit.path, allow_absolute=False)
            target.parent.mkdir(parents=True, exist_ok=True)
            atomic_write_text(target, edit.new_text.replace("\r\n", "\n"))

        changed_files = _git_changed_files(root)
        if not changed_files:
            print("no changes")
            return 0

        commit_enabled = bool(ns.apply) if ns.commit is None else bool(ns.commit)
        rule_ids = sorted({fix.rule_id for fix in all_fixes})
        if commit_enabled:
            add_proc = _git_run(root, ["add", "."])
            if add_proc.returncode != 0:
                print(add_proc.stderr.strip() or "unable to stage changes", file=sys.stderr)
                return 2
            commit_message = _deterministic_commit_message(
                rule_ids=rule_ids,
                file_count=len(changed_files),
                provided=ns.commit_message,
            )
            env = os.environ.copy()
            source_date_epoch = os.environ.get("SOURCE_DATE_EPOCH")
            if source_date_epoch:
                env["GIT_AUTHOR_DATE"] = source_date_epoch
                env["GIT_COMMITTER_DATE"] = source_date_epoch
            cmd = ["commit", "-m", commit_message]
            if ns.author:
                cmd.extend(["--author", ns.author])
            commit_proc = _git_run(root, cmd, env=env)
            if commit_proc.returncode != 0:
                print(commit_proc.stderr.strip() or "unable to create commit", file=sys.stderr)
                return 2

        if not ns.open_pr:
            print(f"repo pr-fix: branch ready at {ns.branch}")
            return 0

        token = os.environ.get(ns.token_env)
        if not token:
            print(f"missing GitHub token in environment variable: {ns.token_env}", file=sys.stderr)
            return 2
        push_proc = _git_run(root, ["push", "-u", ns.remote, ns.branch])
        if push_proc.returncode != 0:
            print(push_proc.stderr.strip() or "unable to push branch", file=sys.stderr)
            return 2
        repo_slug = ns.repo or _detect_repo_slug(root, ns.remote)
        if not repo_slug:
            print(
                "unable to determine GitHub repository slug (use --repo OWNER/NAME)",
                file=sys.stderr,
            )
            return 2
        if ns.body_file:
            body_text = Path(ns.body_file).read_text(encoding="utf-8")
        elif ns.body:
            body_text = ns.body
        else:
            body_text = _build_pr_body(
                profile=ns.profile,
                packs=[pack for project in project_results for pack in project.packs],
                rule_ids=rule_ids,
                changed_files=changed_files,
                per_project=project_results if (ns.project or ns.all_projects) else [],
            )
        title = ns.title or f"sdetkit: auto-fix repo audit ({len(changed_files)} files)"
        try:
            pr_resp = _github_create_pr(
                repo_slug=repo_slug,
                token=token,
                head=ns.branch,
                base=base_ref,
                title=title,
                body=body_text,
                draft=bool(ns.draft),
            )
        except urllib.error.HTTPError as exc:
            print(f"GitHub PR creation failed: {exc.code}", file=sys.stderr)
            return 2
        except urllib.error.URLError as exc:
            print(f"GitHub PR creation failed: {exc.reason}", file=sys.stderr)
            return 2
        if ns.labels:
            labels = [item.strip() for item in ns.labels.split(",") if item.strip()]
            if labels:
                issue_url = (
                    f"https://api.github.com/repos/{repo_slug}/issues/{pr_resp.get('number')}"
                )
                req = urllib.request.Request(
                    issue_url,
                    data=json.dumps({"labels": labels}).encode("utf-8"),
                    headers={
                        "Accept": "application/vnd.github+json",
                        "Authorization": f"Bearer {token}",
                        "X-GitHub-Api-Version": "2022-11-28",
                        "User-Agent": "sdetkit",
                        "Content-Type": "application/json",
                    },
                    method="PATCH",
                )
                with urllib.request.urlopen(req, timeout=20):
                    pass
        print(f"Opened PR: {pr_resp.get('html_url', '')}")
        return 0

    if ns.repo_cmd in {"init", "apply"}:
        return _run_repo_init(
            root,
            preset=ns.preset,
            command=ns.repo_cmd,
            dry_run=bool(ns.dry_run),
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
