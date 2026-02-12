from __future__ import annotations

import hashlib
import importlib.metadata as importlib_metadata
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
                id="SEC_DEPENDABOT_MISSING",
                title="Dependabot config exists",
                description="Repository should configure dependency update automation.",
                default_severity="warn",
                tags=("pack:enterprise", "pack:security", "dependencies"),
                supports_fix=True,
            ),
            rel_path=".github/dependabot.yml",
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
        _MissingFileFixer("SEC_DEPENDABOT_MISSING", ".github/dependabot.yml", TEMPLATE_DEPENDABOT),
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
            if not name or not isinstance(raw_ids, (list, tuple)):
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
