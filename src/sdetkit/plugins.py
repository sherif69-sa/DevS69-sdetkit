from __future__ import annotations

import hashlib
import importlib.metadata as importlib_metadata
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol


@dataclass(frozen=True)
class RuleMeta:
    id: str
    title: str
    description: str
    default_severity: str
    tags: tuple[str, ...] = ()
    supports_fix: bool = False


@dataclass(frozen=True)
class Finding:
    rule_id: str
    severity: str
    message: str
    path: str | None = None
    line: int | None = None
    details: dict[str, Any] | None = None
    fingerprint: str = ""

    def with_fingerprint(self) -> Finding:
        if self.fingerprint:
            return self
        normalized = (self.path or ".").replace("\\", "/").lstrip("/")
        payload = "|".join((self.rule_id, normalized, self.message))
        digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()
        return Finding(
            rule_id=self.rule_id,
            severity=self.severity,
            message=self.message,
            path=self.path,
            line=self.line,
            details=self.details,
            fingerprint=digest,
        )


@dataclass(frozen=True)
class FileEdit:
    path: str
    old_text: str
    new_text: str


@dataclass(frozen=True)
class Fix:
    rule_id: str
    description: str
    changes: tuple[FileEdit, ...]
    safe: bool = True


class AuditRule(Protocol):
    @property
    def meta(self) -> RuleMeta:
        raise NotImplementedError

    def run(self, repo_root: Path, context: dict[str, Any]) -> list[Finding]:
        pass


class Fixer(Protocol):
    @property
    def rule_id(self) -> str:
        pass

    def fix(self, repo_root: Path, findings: list[Finding], context: dict[str, Any]) -> list[Fix]:
        pass


@dataclass(frozen=True)
class LoadedRule:
    meta: RuleMeta
    plugin: AuditRule
    source: str = "builtin"


@dataclass(frozen=True)
class LoadedFixer:
    rule_id: str
    plugin: Fixer
    source: str = "builtin"


@dataclass(frozen=True)
class RuleCatalog:
    rules: tuple[LoadedRule, ...]
    fixers: tuple[LoadedFixer, ...]

    def fixer_map(self) -> dict[str, Fixer]:
        return {item.rule_id: item.plugin for item in self.fixers}


@dataclass(frozen=True)
class LoadedPack:
    pack_name: str
    rule_ids: tuple[str, ...]
    defaults: dict[str, Any]
    source: str = "builtin"


CORE_PACK = "core"
ENTERPRISE_PACK = "enterprise"
SECURITY_PACK = "security"
KNOWN_PACKS: tuple[str, ...] = (CORE_PACK, ENTERPRISE_PACK, SECURITY_PACK)
DEFAULT_PACKS_BY_PROFILE: dict[str, tuple[str, ...]] = {
    "default": (CORE_PACK,),
    "enterprise": (CORE_PACK, ENTERPRISE_PACK),
}


TEMPLATE_SECURITY = (
    "# Security Policy\n\n"
    "## Reporting a Vulnerability\n\n"
    "Please report vulnerabilities privately to project maintainers with reproduction details and impact.\n"
)
TEMPLATE_COC = (
    "# Code of Conduct\n\n"
    "This project is committed to a respectful, inclusive environment for everyone.\n"
)
TEMPLATE_CONTRIB = (
    "# Contributing\n\n"
    "## Getting started\n\n"
    "- Create a feature branch.\n"
    "- Keep changes focused and add tests.\n"
    "- Run local checks before opening a pull request.\n"
)
TEMPLATE_ISSUE_CONFIG = (
    "blank_issues_enabled: false\n"
    "contact_links:\n"
    "  - name: Security report\n"
    "    url: https://example.invalid/security\n"
    "    about: Report vulnerabilities privately.\n"
)
TEMPLATE_PR = (
    "## Summary\n\n"
    "Describe what changed and why.\n\n"
    "## Validation\n\n"
    "- [ ] Tests updated\n"
    "- [ ] Local checks passed\n"
)
TEMPLATE_DEPENDABOT = (
    "version: 2\n"
    "updates:\n"
    "  - package-ecosystem: pip\n"
    "    directory: /\n"
    "    schedule:\n"
    "      interval: weekly\n"
)
TEMPLATE_CODEOWNERS = "# Default owners\n* @org/team\n"
TEMPLATE_PRE_COMMIT = (
    "repos:\n"
    "  - repo: https://github.com/pre-commit/pre-commit-hooks\n"
    "    rev: v4.6.0\n"
    "    hooks:\n"
    "      - id: check-yaml\n"
    "      - id: end-of-file-fixer\n"
    "      - id: trailing-whitespace\n"
)
TEMPLATE_REPO_AUDIT_WORKFLOW = (
    "name: repo-audit\n"
    "on:\n"
    "  pull_request:\n"
    "  push:\n"
    "    branches: [main]\n"
    "jobs:\n"
    "  audit:\n"
    "    runs-on: ubuntu-latest\n"
    "    steps:\n"
    "      - uses: actions/checkout@v4\n"
    "      - uses: actions/setup-python@v5\n"
    "        with:\n"
    "          python-version: '3.11'\n"
    "      - run: python -m pip install -e .\n"
    "      - run: sdetkit repo audit . --format json\n"
)


@dataclass(frozen=True)
class _MissingFileRule:
    meta: RuleMeta
    rel_path: str

    def run(self, repo_root: Path, context: dict[str, Any]) -> list[Finding]:
        exec_ctx = context.get("_exec_ctx")
        if exec_ctx is not None and hasattr(exec_ctx, "track_file"):
            exec_ctx.track_file(self.rel_path)
        target = repo_root / self.rel_path
        if target.exists():
            return []
        return [
            Finding(
                rule_id=self.meta.id,
                severity=self.meta.default_severity,
                message=f"missing required file: {self.rel_path}",
                path=self.rel_path,
                line=1,
                details={
                    "pack": _pack_from_tags(self.meta.tags),
                    "fixable": self.meta.supports_fix,
                },
            ).with_fingerprint()
        ]


@dataclass(frozen=True)
class _SecuritySecretsRule:
    meta: RuleMeta

    def run(self, repo_root: Path, context: dict[str, Any]) -> list[Finding]:
        exec_ctx = context.get("_exec_ctx")
        findings: list[Finding] = []
        allow_fixture_prefixes = ("tests/fixtures/", "test/fixtures/")
        key_names = {"id_rsa", "id_dsa"}
        key_suffixes = (".pem", ".key")
        for path in sorted(repo_root.rglob("*"), key=lambda p: p.as_posix()):
            if not path.is_file():
                continue
            rel = path.relative_to(repo_root).as_posix()
            if rel.startswith(".git/"):
                continue
            if exec_ctx is not None and hasattr(exec_ctx, "track_file"):
                exec_ctx.track_file(rel)
            name = path.name
            lower = name.lower()
            is_fixture = any(rel.startswith(prefix) for prefix in allow_fixture_prefixes)

            env_like = (
                lower == ".env"
                or (lower.startswith(".env.") and lower != ".env.example")
                or lower == ".envrc"
            )
            key_like = lower in key_names or lower.endswith(key_suffixes)

            if env_like:
                findings.append(
                    Finding(
                        rule_id=self.meta.id,
                        severity="warn",
                        message="potential secret file committed to repository",
                        path=rel,
                        line=1,
                        details={
                            "pack": _pack_from_tags(self.meta.tags),
                            "fixture_allowlisted": is_fixture,
                            "fixable": self.meta.supports_fix,
                        },
                    ).with_fingerprint()
                )
                continue

            if key_like and not is_fixture:
                findings.append(
                    Finding(
                        rule_id=self.meta.id,
                        severity="error",
                        message="private key material-like filename committed to repository",
                        path=rel,
                        line=1,
                        details={
                            "pack": _pack_from_tags(self.meta.tags),
                            "fixture_allowlisted": is_fixture,
                            "fixable": self.meta.supports_fix,
                        },
                    ).with_fingerprint()
                )
        return findings


@dataclass(frozen=True)
class _SecurityFixtureAllowlistRule:
    meta: RuleMeta

    def run(self, repo_root: Path, context: dict[str, Any]) -> list[Finding]:
        exec_ctx = context.get("_exec_ctx")
        findings: list[Finding] = []
        allow_fixture_prefixes = ("tests/fixtures/", "test/fixtures/")
        key_names = {"id_rsa", "id_dsa"}
        key_suffixes = (".pem", ".key")
        for path in sorted(repo_root.rglob("*"), key=lambda p: p.as_posix()):
            if not path.is_file():
                continue
            rel = path.relative_to(repo_root).as_posix()
            if exec_ctx is not None and hasattr(exec_ctx, "track_file"):
                exec_ctx.track_file(rel)
            if not any(rel.startswith(prefix) for prefix in allow_fixture_prefixes):
                continue
            lower = path.name.lower()
            if lower in key_names or lower.endswith(key_suffixes):
                findings.append(
                    Finding(
                        rule_id=self.meta.id,
                        severity=self.meta.default_severity,
                        message="fixture allowlist matched key-like filename; verify it is sanitized",
                        path=rel,
                        line=1,
                        details={"pack": _pack_from_tags(self.meta.tags), "fixable": False},
                    ).with_fingerprint()
                )
        return findings


@dataclass(frozen=True)
class _SecurityCodeownersRule:
    meta: RuleMeta

    def run(self, repo_root: Path, context: dict[str, Any]) -> list[Finding]:
        exec_ctx = context.get("_exec_ctx")
        candidates = ("CODEOWNERS", ".github/CODEOWNERS", "docs/CODEOWNERS")
        for rel in candidates:
            if exec_ctx is not None and hasattr(exec_ctx, "track_file"):
                exec_ctx.track_file(rel)
            if (repo_root / rel).exists():
                return []
        return [
            Finding(
                rule_id=self.meta.id,
                severity=self.meta.default_severity,
                message="missing CODEOWNERS file in supported locations",
                path=".github/CODEOWNERS",
                line=1,
                details={
                    "pack": _pack_from_tags(self.meta.tags),
                    "fixable": self.meta.supports_fix,
                },
            ).with_fingerprint()
        ]


@dataclass(frozen=True)
class _SecurityWorkflowRule:
    meta: RuleMeta

    def run(self, repo_root: Path, context: dict[str, Any]) -> list[Finding]:
        workflows_dir = repo_root / ".github" / "workflows"
        exec_ctx = context.get("_exec_ctx")
        findings: list[Finding] = []
        if exec_ctx is not None and hasattr(exec_ctx, "track_file"):
            exec_ctx.track_file(".github/workflows")
        if not workflows_dir.exists() or not workflows_dir.is_dir():
            return findings

        floating_refs = {"main", "master", "latest", "head"}
        sha_ref = re.compile(r"^[0-9a-f]{40}$")
        tag_ref = re.compile(r"^v?\d+(?:\.\d+){0,3}$")

        for wf in sorted(workflows_dir.iterdir(), key=lambda p: p.as_posix()):
            if not wf.is_file() or wf.suffix not in {".yml", ".yaml"}:
                continue
            rel = wf.relative_to(repo_root).as_posix()
            if exec_ctx is not None and hasattr(exec_ctx, "track_file"):
                exec_ctx.track_file(rel)
            lines = wf.read_text(encoding="utf-8", errors="ignore").splitlines()
            saw_permissions = False
            for idx, raw in enumerate(lines, start=1):
                stripped = raw.strip()
                if stripped.startswith("permissions:"):
                    saw_permissions = True
                if "uses:" not in stripped:
                    continue
                _, rhs = stripped.split("uses:", 1)
                spec = rhs.strip().strip("\"'")
                if "@" not in spec:
                    continue
                ref = spec.rsplit("@", 1)[1].strip()
                low = ref.lower()
                if low in floating_refs and self.meta.id == "SEC_GH_ACTIONS_PINNING":
                    findings.append(
                        Finding(
                            rule_id=self.meta.id,
                            severity=self.meta.default_severity,
                            message="workflow action uses floating reference; pin to tag or commit SHA",
                            path=rel,
                            line=idx,
                            details={
                                "pack": _pack_from_tags(self.meta.tags),
                                "ref": ref,
                                "fixable": False,
                            },
                        ).with_fingerprint()
                    )
                    continue
                if sha_ref.match(ref) or tag_ref.match(ref):
                    continue

            if not saw_permissions and self.meta.id == "SEC_GH_PERMISSIONS_MISSING":
                findings.append(
                    Finding(
                        rule_id=self.meta.id,
                        severity=self.meta.default_severity,
                        message="workflow missing permissions block; define least-privilege permissions",
                        path=rel,
                        line=1,
                        details={"pack": _pack_from_tags(self.meta.tags), "fixable": False},
                    ).with_fingerprint()
                )
        return findings


@dataclass(frozen=True)
class _SecurityPythonHygieneRule:
    meta: RuleMeta

    def run(self, repo_root: Path, context: dict[str, Any]) -> list[Finding]:
        exec_ctx = context.get("_exec_ctx")
        if exec_ctx is not None and hasattr(exec_ctx, "track_file"):
            exec_ctx.track_file("pyproject.toml")
        has_pyproject = (repo_root / "pyproject.toml").exists()
        has_python = has_pyproject or any(repo_root.rglob("*.py"))
        if self.meta.id == "SEC_PY_DEPENDENCY_FILES_MISSING":
            req_candidates = [
                p.relative_to(repo_root).as_posix()
                for p in sorted(repo_root.glob("requirements*.txt"), key=lambda p: p.as_posix())
            ]
            if exec_ctx is not None and hasattr(exec_ctx, "track_file"):
                exec_ctx.track_file("requirements.txt")
                for req in req_candidates:
                    exec_ctx.track_file(req)
            if not has_python:
                return []
            if has_pyproject or req_candidates:
                return []
            return [
                Finding(
                    rule_id=self.meta.id,
                    severity=self.meta.default_severity,
                    message="python project missing dependency declaration file",
                    path="pyproject.toml",
                    line=1,
                    details={"pack": _pack_from_tags(self.meta.tags), "fixable": False},
                ).with_fingerprint()
            ]
        if self.meta.id == "SEC_PY_PRECOMMIT_MISSING":
            target = ".pre-commit-config.yaml"
            if exec_ctx is not None and hasattr(exec_ctx, "track_file"):
                exec_ctx.track_file(target)
            if not has_python or (repo_root / target).exists():
                return []
            return [
                Finding(
                    rule_id=self.meta.id,
                    severity=self.meta.default_severity,
                    message="missing .pre-commit-config.yaml for python hygiene checks",
                    path=target,
                    line=1,
                    details={"pack": _pack_from_tags(self.meta.tags), "fixable": True},
                ).with_fingerprint()
            ]
        if self.meta.id == "SEC_PY_BANDIT_CONFIG_HINT":
            bandit_targets = (".bandit", "pyproject.toml", "bandit.yaml", "bandit.yml")
            if exec_ctx is not None and hasattr(exec_ctx, "track_file"):
                for rel in bandit_targets:
                    exec_ctx.track_file(rel)
            has_bandit = (
                (repo_root / ".bandit").exists()
                or (repo_root / "bandit.yaml").exists()
                or (repo_root / "bandit.yml").exists()
            )
            if not has_bandit and has_pyproject:
                text = (repo_root / "pyproject.toml").read_text(encoding="utf-8", errors="ignore")
                has_bandit = "[tool.bandit" in text
            if not has_python or has_bandit:
                return []
            return [
                Finding(
                    rule_id=self.meta.id,
                    severity=self.meta.default_severity,
                    message="optional bandit configuration not found",
                    path="pyproject.toml",
                    line=1,
                    details={"pack": _pack_from_tags(self.meta.tags), "fixable": False},
                ).with_fingerprint()
            ]
        return []


@dataclass(frozen=True)
class _MissingFileFixer:
    rule_id: str
    rel_path: str
    content: str
    safe: bool = True

    def fix(self, repo_root: Path, findings: list[Finding], context: dict[str, Any]) -> list[Fix]:
        if not findings:
            return []
        target = repo_root / self.rel_path
        current = target.read_text(encoding="utf-8") if target.exists() else ""
        if current == self.content:
            return []
        return [
            Fix(
                rule_id=self.rule_id,
                description=f"create {self.rel_path}",
                safe=self.safe,
                changes=(FileEdit(path=self.rel_path, old_text=current, new_text=self.content),),
            )
        ]


def _pack_from_tags(tags: tuple[str, ...]) -> str:
    for tag in tags:
        if tag.startswith("pack:"):
            return tag.split(":", 1)[1]
    return CORE_PACK


def builtin_rules() -> list[AuditRule]:
    return [
        _MissingFileRule(
            meta=RuleMeta(
                id="CORE_MISSING_SECURITY_MD",
                title="SECURITY.md exists",
                description="Repository should publish a security reporting policy.",
                default_severity="error",
                tags=("pack:core", "governance"),
                supports_fix=True,
            ),
            rel_path="SECURITY.md",
        ),
        _MissingFileRule(
            meta=RuleMeta(
                id="CORE_MISSING_CODE_OF_CONDUCT_MD",
                title="CODE_OF_CONDUCT.md exists",
                description="Repository should define contributor conduct expectations.",
                default_severity="error",
                tags=("pack:core", "governance"),
                supports_fix=True,
            ),
            rel_path="CODE_OF_CONDUCT.md",
        ),
        _MissingFileRule(
            meta=RuleMeta(
                id="CORE_MISSING_CONTRIBUTING_MD",
                title="CONTRIBUTING.md exists",
                description="Repository should explain how to contribute.",
                default_severity="warn",
                tags=("pack:core", "governance"),
                supports_fix=True,
            ),
            rel_path="CONTRIBUTING.md",
        ),
        _MissingFileRule(
            meta=RuleMeta(
                id="CORE_MISSING_ISSUE_TEMPLATE_CONFIG",
                title="Issue template config exists",
                description="Repository should define issue template defaults.",
                default_severity="warn",
                tags=("pack:core", "github"),
                supports_fix=True,
            ),
            rel_path=".github/ISSUE_TEMPLATE/config.yml",
        ),
        _MissingFileRule(
            meta=RuleMeta(
                id="CORE_MISSING_PR_TEMPLATE",
                title="PR template exists",
                description="Repository should provide a pull request template.",
                default_severity="warn",
                tags=("pack:core", "github"),
                supports_fix=True,
            ),
            rel_path=".github/PULL_REQUEST_TEMPLATE.md",
        ),
        _MissingFileRule(
            meta=RuleMeta(
                id="SEC_GH_DEPENDABOT_MISSING",
                title="Dependabot config exists",
                description="Repository should configure dependency update automation.",
                default_severity="warn",
                tags=("pack:enterprise", "pack:security", "dependencies"),
                supports_fix=True,
            ),
            rel_path=".github/dependabot.yml",
        ),
        _SecuritySecretsRule(
            meta=RuleMeta(
                id="SEC_SECRETS_ENV_IN_REPO",
                title="Secret-like files are not committed",
                description=(
                    "Detects likely secret-bearing files such as .env variants and private-key "
                    "filename patterns, with fixture allowlist handling."
                ),
                default_severity="warn",
                tags=("pack:security", "secrets"),
                supports_fix=False,
            )
        ),
        _SecurityCodeownersRule(
            meta=RuleMeta(
                id="SEC_GH_CODEOWNERS_MISSING",
                title="CODEOWNERS exists",
                description="Repository should define code ownership coverage.",
                default_severity="warn",
                tags=("pack:security", "github"),
                supports_fix=True,
            )
        ),
        _MissingFileRule(
            meta=RuleMeta(
                id="SEC_GH_SECURITY_MD_MISSING",
                title="SECURITY.md exists",
                description="Repository should provide a security disclosure policy.",
                default_severity="warn",
                tags=("pack:security", "github"),
                supports_fix=True,
            ),
            rel_path="SECURITY.md",
        ),
        _SecurityWorkflowRule(
            meta=RuleMeta(
                id="SEC_GH_ACTIONS_PINNING",
                title="GitHub Actions are pinned",
                description="Workflow actions should avoid floating refs such as @main/@master.",
                default_severity="warn",
                tags=("pack:security", "github", "actions"),
                supports_fix=False,
            )
        ),
        _SecurityWorkflowRule(
            meta=RuleMeta(
                id="SEC_GH_PERMISSIONS_MISSING",
                title="GitHub Actions permissions declared",
                description="Workflow files should declare permissions blocks for least privilege.",
                default_severity="warn",
                tags=("pack:security", "github", "actions"),
                supports_fix=False,
            )
        ),
        _SecurityPythonHygieneRule(
            meta=RuleMeta(
                id="SEC_PY_DEPENDENCY_FILES_MISSING",
                title="Python dependency file present",
                description="Python repos should include pyproject.toml or requirements*.txt.",
                default_severity="warn",
                tags=("pack:security", "python"),
                supports_fix=False,
            )
        ),
        _SecurityPythonHygieneRule(
            meta=RuleMeta(
                id="SEC_PY_PRECOMMIT_MISSING",
                title="pre-commit config present",
                description="Python repos should include a baseline pre-commit configuration.",
                default_severity="warn",
                tags=("pack:security", "python"),
                supports_fix=True,
            )
        ),
        _SecurityPythonHygieneRule(
            meta=RuleMeta(
                id="SEC_PY_BANDIT_CONFIG_HINT",
                title="Bandit config hint",
                description="Informational hint when no bandit configuration is found.",
                default_severity="info",
                tags=("pack:security", "python"),
                supports_fix=False,
            )
        ),
        _SecurityFixtureAllowlistRule(
            meta=RuleMeta(
                id="SEC_SECRETS_TEST_FIXTURES_ALLOW",
                title="Fixture secret filename allowlist",
                description="Allows test fixture paths while still warning on key-like filenames.",
                default_severity="warn",
                tags=("pack:security", "secrets"),
                supports_fix=False,
            )
        ),
        _MissingFileRule(
            meta=RuleMeta(
                id="ENT_REPO_AUDIT_WORKFLOW_MISSING",
                title="Repo audit workflow exists",
                description="Repository should run sdetkit repo audit in CI.",
                default_severity="warn",
                tags=("pack:enterprise", "ci"),
                supports_fix=True,
            ),
            rel_path=".github/workflows/repo-audit.yml",
        ),
    ]


def builtin_fixers() -> list[Fixer]:
    return [
        _MissingFileFixer("CORE_MISSING_SECURITY_MD", "SECURITY.md", TEMPLATE_SECURITY),
        _MissingFileFixer("CORE_MISSING_CODE_OF_CONDUCT_MD", "CODE_OF_CONDUCT.md", TEMPLATE_COC),
        _MissingFileFixer("CORE_MISSING_CONTRIBUTING_MD", "CONTRIBUTING.md", TEMPLATE_CONTRIB),
        _MissingFileFixer(
            "CORE_MISSING_ISSUE_TEMPLATE_CONFIG",
            ".github/ISSUE_TEMPLATE/config.yml",
            TEMPLATE_ISSUE_CONFIG,
        ),
        _MissingFileFixer(
            "CORE_MISSING_PR_TEMPLATE", ".github/PULL_REQUEST_TEMPLATE.md", TEMPLATE_PR
        ),
        _MissingFileFixer(
            "SEC_GH_DEPENDABOT_MISSING", ".github/dependabot.yml", TEMPLATE_DEPENDABOT
        ),
        _MissingFileFixer("SEC_GH_SECURITY_MD_MISSING", "SECURITY.md", TEMPLATE_SECURITY),
        _MissingFileFixer("SEC_GH_CODEOWNERS_MISSING", ".github/CODEOWNERS", TEMPLATE_CODEOWNERS),
        _MissingFileFixer(
            "SEC_PY_PRECOMMIT_MISSING", ".pre-commit-config.yaml", TEMPLATE_PRE_COMMIT
        ),
        _MissingFileFixer(
            "ENT_REPO_AUDIT_WORKFLOW_MISSING",
            ".github/workflows/repo-audit.yml",
            TEMPLATE_REPO_AUDIT_WORKFLOW,
        ),
    ]


def _iter_entry_points(group: str) -> list[Any]:
    try:
        eps = importlib_metadata.entry_points()
    except Exception:
        return []
    if hasattr(eps, "select"):
        return list(eps.select(group=group))
    return []


def load_rule_catalog() -> RuleCatalog:
    rules: list[LoadedRule] = [
        LoadedRule(meta=rule.meta, plugin=rule, source="builtin") for rule in builtin_rules()
    ]
    fixers: list[LoadedFixer] = [
        LoadedFixer(rule_id=fx.rule_id, plugin=fx, source="builtin") for fx in builtin_fixers()
    ]

    for ep in _iter_entry_points("sdetkit.repo_audit_rules"):
        try:
            plugin = ep.load()()
            meta = plugin.meta
            rules.append(LoadedRule(meta=meta, plugin=plugin, source=f"entrypoint:{ep.name}"))
        except Exception:
            continue

    for ep in _iter_entry_points("sdetkit.repo_audit_fixers"):
        try:
            plugin = ep.load()()
            fixers.append(
                LoadedFixer(
                    rule_id=getattr(plugin, "rule_id", ep.name),
                    plugin=plugin,
                    source=f"entrypoint:{ep.name}",
                )
            )
        except Exception:
            continue

    rules.sort(key=lambda item: item.meta.id)
    fixers.sort(key=lambda item: item.rule_id)
    return RuleCatalog(rules=tuple(rules), fixers=tuple(fixers))


def normalize_packs(profile: str, packs_csv: str | None) -> tuple[str, ...]:
    if not packs_csv:
        packs = list(DEFAULT_PACKS_BY_PROFILE.get(profile, (CORE_PACK,)))
    else:
        packs = [p.strip() for p in packs_csv.split(",") if p.strip()]
    dedup: list[str] = []
    for pack in packs:
        if pack not in dedup:
            dedup.append(pack)
    return tuple(dedup)


def normalize_org_packs(values: list[str] | None) -> tuple[str, ...]:
    if not values:
        return ()
    out: list[str] = []
    for raw in values:
        for item in str(raw).split(","):
            name = item.strip()
            if name and name not in out:
                out.append(name)
    return tuple(out)


def load_repo_audit_packs() -> tuple[LoadedPack, ...]:
    packs: list[LoadedPack] = []
    for ep in _iter_entry_points("sdetkit.repo_audit_packs"):
        try:
            plugin = ep.load()()
            name = str(getattr(plugin, "pack_name", ep.name)).strip()
            raw_ids = getattr(plugin, "rule_ids", ())
            if not name or not isinstance(raw_ids, list | tuple):
                continue
            defaults = getattr(plugin, "defaults", {})
            if not isinstance(defaults, dict):
                defaults = {}
            packs.append(
                LoadedPack(
                    pack_name=name,
                    rule_ids=tuple(sorted(str(x) for x in raw_ids if str(x))),
                    defaults={str(k): v for k, v in defaults.items()},
                    source=f"entrypoint:{ep.name}",
                )
            )
        except Exception:
            continue
    packs.sort(key=lambda item: item.pack_name)
    return tuple(packs)


def merge_packs(base: tuple[str, ...], org: tuple[str, ...]) -> tuple[str, ...]:
    merged = list(base)
    for item in org:
        if item not in merged:
            merged.append(item)
    return tuple(merged)


def apply_pack_defaults(
    *,
    selected_org_packs: tuple[str, ...],
    available: tuple[LoadedPack, ...],
    base_fail_on: str,
    base_severity_overrides: dict[str, str],
    known_rule_ids: set[str],
) -> tuple[str, dict[str, str], tuple[str, ...]]:
    fail_on = base_fail_on
    overrides = dict(base_severity_overrides)
    by_name = {item.pack_name: item for item in available}
    unknown = tuple(sorted(name for name in selected_org_packs if name not in by_name))
    for name in selected_org_packs:
        loaded = by_name.get(name)
        if loaded is None:
            continue
        packed_fail = loaded.defaults.get("fail_on")
        if packed_fail in {"none", "warn", "error"}:
            fail_on = packed_fail
        raw_overrides = loaded.defaults.get("severity_overrides")
        if isinstance(raw_overrides, dict):
            for rule_id, level in sorted(raw_overrides.items(), key=lambda x: str(x[0])):
                rid = str(rule_id)
                sev = str(level)
                if rid in known_rule_ids and sev in {"info", "warn", "error"}:
                    overrides[rid] = sev
    return fail_on, overrides, unknown


def select_rules(catalog: RuleCatalog, packs: tuple[str, ...]) -> tuple[LoadedRule, ...]:
    org_rule_map = {item.pack_name: set(item.rule_ids) for item in load_repo_audit_packs()}
    selected = set(packs)
    chosen: list[LoadedRule] = []
    for rule in catalog.rules:
        tags = set(rule.meta.tags)
        rule_packs = {tag.split(":", 1)[1] for tag in tags if tag.startswith("pack:")}
        if not rule_packs:
            rule_packs = {CORE_PACK}
        if rule_packs & selected or any(
            rule.meta.id in org_rule_map.get(pack_name, set()) for pack_name in selected
        ):
            chosen.append(rule)
    chosen.sort(key=lambda item: item.meta.id)
    return tuple(chosen)
