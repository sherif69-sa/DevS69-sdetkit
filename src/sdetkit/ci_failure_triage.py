from __future__ import annotations

import argparse
import json
import os
import re
import sys
from collections.abc import Sequence
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "sdetkit.ci_failure_triage.v1"

PYTEST_NODE_RE = re.compile(r"FAILED\s+([A-Za-z0-9_./:-]+::[^\s]+)(?:\s+-\s+(.+))?")
MYPY_ERROR_RE = re.compile(r"^(.+?\.py):\d+:\s+error:\s+(.+)$", re.MULTILINE)
PYTHON_EXCEPTION_RE = re.compile(r"\b([A-Z][A-Za-z]+Error|Exception):\s*(.+)")
EXIT_CODE_RE = re.compile(r"Process completed with exit code (?!0\b)(\d+)")
FILE_PATH_RE = re.compile(r"\b(?:src|tests|docs)/[A-Za-z0-9_./-]+\.(?:py|md)\b")
HOOK_FAILURE_RE = re.compile(r"^(.+?)\.+Failed$", re.MULTILINE)
HOOK_ID_RE = re.compile(r"- hook id:\s*([A-Za-z0-9_.-]+)")
MKDOCS_ERROR_RE = re.compile(r"ERROR\s+-\s+(.+)")
PYTEST_COLLECTION_RE = re.compile(r"ERROR collecting ([^\s]+)")


@dataclass(frozen=True)
class CiFailureTriageReport:
    schema_version: str
    classification: str
    blocker: bool
    headline_failure: str
    actual_failure: str
    root_cause_candidates: tuple[str, ...]
    likely_owner_files: tuple[str, ...]
    contract_that_failed: str
    noise_to_ignore: tuple[str, ...]
    recommended_fix_shape: str
    verification_commands: tuple[str, ...]
    confidence: str
    next_best_action: str


def _clean(value: object, *, limit: int = 260) -> str:
    text = str(value or "").replace("\r", " ").replace("\n", " ").strip()
    text = re.sub(r"\s+", " ", text)
    if len(text) > limit:
        return text[: limit - 1].rstrip() + "\u2026"
    return text


def _unique(values: Sequence[str], *, limit: int = 8) -> tuple[str, ...]:
    out: list[str] = []
    for value in values:
        item = _clean(value)
        if item and item not in out:
            out.append(item)
        if len(out) >= limit:
            break
    return tuple(out)


def _coverage_lines(lines: Sequence[str]) -> tuple[str, ...]:
    hits: list[str] = []
    for line in lines:
        lowered = line.lower()
        if "coverage" in lowered and any(
            token in lowered for token in ("fail", "under", "threshold", "required")
        ):
            hits.append(line)
    return _unique(hits, limit=3)


def _exit_lines(lines: Sequence[str]) -> tuple[str, ...]:
    return _unique([line for line in lines if EXIT_CODE_RE.search(line)], limit=3)


def _pytest_failure(text: str) -> tuple[str, str, str] | None:
    match = PYTEST_NODE_RE.search(text)
    if not match:
        return None
    node = _clean(match.group(1))
    detail = _clean(match.group(2) or "pytest node failed")
    owner = node.split("::", 1)[0]
    return node, detail, owner


def _mypy_failure(text: str) -> tuple[str, str] | None:
    match = MYPY_ERROR_RE.search(text)
    if not match:
        return None
    return _clean(match.group(1)), _clean(match.group(2))


def _python_exception(text: str) -> str:
    match = PYTHON_EXCEPTION_RE.search(text)
    if not match:
        return ""
    return _clean(f"{match.group(1)}: {match.group(2)}")


def _file_mentions(text: str) -> tuple[str, ...]:
    return _unique(FILE_PATH_RE.findall(text), limit=8)


def _hook_failure(text: str) -> tuple[str, str] | None:
    hook_id = HOOK_ID_RE.search(text)
    failed = HOOK_FAILURE_RE.search(text)
    if hook_id:
        return _clean(hook_id.group(1)), _clean(failed.group(1)) if failed else _clean(
            hook_id.group(1)
        )
    if failed and "hook id:" in text.lower():
        return _clean(failed.group(1)), _clean(failed.group(1))
    if failed and "ruff format" in failed.group(1).lower():
        return "ruff-format", _clean(failed.group(1))
    return None


def _mkdocs_failure(text: str) -> str:
    lowered = text.lower()
    if "mkdocs" not in lowered and "documentation file" not in lowered:
        return ""
    match = MKDOCS_ERROR_RE.search(text)
    if match:
        return _clean(match.group(1))
    if "strict mode" in lowered:
        return "MkDocs strict mode failed"
    return ""


def _pytest_collection_failure(text: str) -> tuple[str, str] | None:
    match = PYTEST_COLLECTION_RE.search(text)
    if not match:
        return None
    owner = _clean(match.group(1))
    exception = _python_exception(text)
    actual = exception or f"ERROR collecting {owner}"
    return owner, actual


def _as_payload(report: CiFailureTriageReport) -> dict[str, Any]:
    return asdict(report)


def build_triage_report(text: str) -> CiFailureTriageReport:
    lines = text.splitlines()
    coverage = _coverage_lines(lines)
    exits = _exit_lines(lines)
    pytest = _pytest_failure(text)
    mypy = _mypy_failure(text)
    hook = _hook_failure(text)
    mkdocs = _mkdocs_failure(text)
    collection = _pytest_collection_failure(text)
    exception = _python_exception(text)
    owners = list(_file_mentions(text))

    if collection is not None:
        owner, actual = collection
        if owner not in owners:
            owners.insert(0, owner)
        return CiFailureTriageReport(
            schema_version=SCHEMA_VERSION,
            classification="pytest_collection_failure",
            blocker=True,
            headline_failure=f"ERROR collecting {owner}",
            actual_failure=actual,
            root_cause_candidates=(
                "pytest could not import or collect the test module",
                "fix import/module availability before debugging assertions",
            ),
            likely_owner_files=_unique(owners),
            contract_that_failed="pytest collection/import contract",
            noise_to_ignore=_unique(["nonzero process exit is a wrapper"] if exits else []),
            recommended_fix_shape=(
                "Fix the missing import, package exposure, or test module collection path; "
                "do not change assertion behavior first."
            ),
            verification_commands=(f"python -m pytest -q {owner} --collect-only -o addopts=",),
            confidence="high",
            next_best_action=f"run collection-only for {owner} and inspect the first import error",
        )

    if hook is not None:
        hook_id, hook_title = hook
        is_ruff_format = hook_id == "ruff-format" or "ruff format" in hook_title.lower()
        classification = "formatting_drift" if is_ruff_format else "pre_commit_hook_failure"
        contract = "ruff formatting contract" if is_ruff_format else "pre-commit hook contract"
        command = (
            "python -m ruff format --check ."
            if is_ruff_format
            else f"python -m pre_commit run {hook_id} --all-files"
        )
        return CiFailureTriageReport(
            schema_version=SCHEMA_VERSION,
            classification=classification,
            blocker=True,
            headline_failure=hook_title,
            actual_failure=f"{hook_id} modified files or reported failure",
            root_cause_candidates=(
                "a pre-commit hook changed the worktree",
                "accept hook edits and rerun the same proof before committing",
            ),
            likely_owner_files=_unique(owners),
            contract_that_failed=contract,
            noise_to_ignore=_unique(["nonzero process exit is a wrapper"] if exits else []),
            recommended_fix_shape=(
                "Accept the hook-produced file changes, rerun focused tests, then rerun pre-commit."
            ),
            verification_commands=(command, "python -m pre_commit run -a"),
            confidence="high",
            next_best_action=f"rerun {hook_id} after accepting generated formatting changes",
        )

    if mkdocs:
        return CiFailureTriageReport(
            schema_version=SCHEMA_VERSION,
            classification="docs_contract_gap",
            blocker=True,
            headline_failure=mkdocs,
            actual_failure=mkdocs,
            root_cause_candidates=(
                "MkDocs strict mode found a documentation contract problem",
                "fix the first missing page/link before changing unrelated docs",
            ),
            likely_owner_files=_unique(owners),
            contract_that_failed="MkDocs strict documentation contract",
            noise_to_ignore=_unique(["nonzero process exit is a wrapper"] if exits else []),
            recommended_fix_shape="Repair the first strict docs error and rebuild the docs locally.",
            verification_commands=("NO_MKDOCS_2_WARNING=1 python -m mkdocs build --strict",),
            confidence="high",
            next_best_action="open the referenced docs page or missing link target",
        )

    if pytest is not None:
        node, detail, owner = pytest
        if owner not in owners:
            owners.insert(0, owner)
        noise = []
        if coverage:
            noise.append("coverage wrapper reported after an earlier pytest failure")
        if exits:
            noise.append("nonzero process exit is a wrapper after the failing test")
        return CiFailureTriageReport(
            schema_version=SCHEMA_VERSION,
            classification="test_failure",
            blocker=True,
            headline_failure=coverage[-1] if coverage else (exits[-1] if exits else node),
            actual_failure=f"{node} - {detail}",
            root_cause_candidates=(
                "the first failing pytest assertion is the real blocker",
                "later CI wrapper failures should not be patched first",
            ),
            likely_owner_files=_unique(owners),
            contract_that_failed="pytest behavior contract",
            noise_to_ignore=_unique(noise),
            recommended_fix_shape=(
                "Fix the failing pytest assertion or owner implementation before changing "
                "coverage, workflow, or quality gates."
            ),
            verification_commands=(f"python -m pytest -q {node} -o addopts=",),
            confidence="high",
            next_best_action=f"open {owner} and reproduce {node}",
        )

    if mypy is not None:
        owner, detail = mypy
        if owner not in owners:
            owners.insert(0, owner)
        return CiFailureTriageReport(
            schema_version=SCHEMA_VERSION,
            classification="test_contract_failure",
            blocker=True,
            headline_failure=f"{owner}: {detail}",
            actual_failure=f"{owner}: {detail}",
            root_cause_candidates=("type/API contract mismatch",),
            likely_owner_files=_unique(owners),
            contract_that_failed="mypy type contract",
            noise_to_ignore=_unique(["nonzero process exit is a wrapper"] if exits else []),
            recommended_fix_shape="Fix the first type/API mismatch; do not broaden into style cleanup.",
            verification_commands=("python -m mypy src",),
            confidence="medium",
            next_best_action=f"inspect the first mypy error in {owner}",
        )

    if coverage:
        return CiFailureTriageReport(
            schema_version=SCHEMA_VERSION,
            classification="quality_wrapper",
            blocker=True,
            headline_failure=coverage[-1],
            actual_failure=coverage[0],
            root_cause_candidates=("coverage gate reported below-threshold evidence",),
            likely_owner_files=_unique(owners),
            contract_that_failed="coverage policy",
            noise_to_ignore=_unique(
                [
                    "no earlier pytest node failure was found in the log",
                    *(["nonzero process exit is a wrapper"] if exits else []),
                ]
            ),
            recommended_fix_shape=(
                "Inspect missed coverage or missing regression tests; do not lower the gate "
                "unless policy intentionally changed."
            ),
            verification_commands=("python -m pytest --cov",),
            confidence="medium",
            next_best_action="rerun coverage locally and inspect the first missed owner file",
        )

    if exception:
        return CiFailureTriageReport(
            schema_version=SCHEMA_VERSION,
            classification="product_bug",
            blocker=True,
            headline_failure=exception,
            actual_failure=exception,
            root_cause_candidates=("Python exception raised during CI command",),
            likely_owner_files=_unique(owners),
            contract_that_failed="runtime command contract",
            noise_to_ignore=_unique(["nonzero process exit is a wrapper"] if exits else []),
            recommended_fix_shape="Reproduce the command path and patch the smallest owner module.",
            verification_commands=("python -m pytest -q <focused-test> -o addopts=",),
            confidence="medium",
            next_best_action="inspect the traceback owner file and add a focused regression test",
        )

    if exits:
        return CiFailureTriageReport(
            schema_version=SCHEMA_VERSION,
            classification="ci_failure_real_flake",
            blocker=True,
            headline_failure=exits[-1],
            actual_failure=exits[0],
            root_cause_candidates=("nonzero CI exit found without a more specific parsed blocker",),
            likely_owner_files=_unique(owners),
            contract_that_failed="CI command contract",
            noise_to_ignore=(),
            recommended_fix_shape="Open the failed step log around the first nonzero command.",
            verification_commands=("python -m pytest -q <focused-test> -o addopts=",),
            confidence="low",
            next_best_action="capture more log context around the first failed command",
        )

    return CiFailureTriageReport(
        schema_version=SCHEMA_VERSION,
        classification="unknown",
        blocker=False,
        headline_failure="none",
        actual_failure="none",
        root_cause_candidates=(),
        likely_owner_files=_unique(owners),
        contract_that_failed="none",
        noise_to_ignore=(),
        recommended_fix_shape="No actionable CI failure signature was found.",
        verification_commands=(),
        confidence="low",
        next_best_action="provide a failed job log with the failing step output",
    )


def _render_text(report: CiFailureTriageReport) -> str:
    payload = _as_payload(report)
    lines: list[str] = []
    for key, value in payload.items():
        if isinstance(value, bool):
            rendered = "yes" if value else "no"
        elif isinstance(value, (list, tuple)):
            rendered = "; ".join(str(item) for item in value) if value else "none"
        else:
            rendered = str(value)
        lines.append(f"{key}={rendered}")
    return "\n".join(lines) + "\n"


def _render_markdown(report: CiFailureTriageReport) -> str:
    owner_files = ", ".join(report.likely_owner_files) or "none"
    noise = ", ".join(report.noise_to_ignore) or "none"
    verification = ", ".join(report.verification_commands) or "none"
    return (
        "# CI failure triage\n\n"
        "## Summary\n\n"
        f"- classification: `{report.classification}`\n"
        f"- blocker: `{'yes' if report.blocker else 'no'}`\n"
        f"- confidence: `{report.confidence}`\n\n"
        "## Failure\n\n"
        f"- headline failure: {report.headline_failure}\n"
        f"- actual failure: {report.actual_failure}\n"
        f"- contract that failed: {report.contract_that_failed}\n\n"
        "## Ownership and noise\n\n"
        f"- likely owner files: {owner_files}\n"
        f"- noise to ignore: {noise}\n\n"
        "## Recommended action\n\n"
        f"- recommended fix shape: {report.recommended_fix_shape}\n"
        f"- verification: {verification}\n"
        f"- next best action: {report.next_best_action}\n"
    )


CLUSTER_SCHEMA_VERSION = "sdetkit.cluster.v1"

HEX_ADDR_RE = re.compile(r"0x[0-9a-fA-F]+")
UUID_RE = re.compile(r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}")
TIMESTAMP_RE = re.compile(
    r"\d{4}-\d{2}-\d{2}[T\s]\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})?"
)
LINE_NUM_RE = re.compile(r"\bline\s+\d+\b", re.IGNORECASE)
PORT_RE = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}:\d+\b")
TOKEN_SPLIT_RE = re.compile(r"[^A-Za-z0-9_]+")


@dataclass(frozen=True)
class NormalizedFailureSignature:
    raw_id: str
    test_node: str
    exception_type: str
    normalized_message: str
    failing_file: str
    root_module: str
    tokens: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "test_node": self.test_node,
            "exception_type": self.exception_type,
            "normalized_message": self.normalized_message,
            "failing_file": self.failing_file,
            "root_module": self.root_module,
        }


def normalize_failure(raw_failure: dict[str, Any] | str) -> NormalizedFailureSignature:
    if isinstance(raw_failure, str):
        text = raw_failure
        test_node = "unknown"
        failing_file = ""
        node_match = PYTEST_NODE_RE.search(text)
        if node_match:
            test_node = node_match.group(1).strip()
            failing_file = test_node.split("::")[0]
    else:
        test_node = str(
            raw_failure.get("node")
            or raw_failure.get("name")
            or raw_failure.get("test_id")
            or raw_failure.get("test")
            or "unknown"
        )
        failing_file = str(
            raw_failure.get("file") or raw_failure.get("path") or test_node.split("::")[0]
        )
        text = str(
            raw_failure.get("message")
            or raw_failure.get("details")
            or raw_failure.get("traceback")
            or raw_failure.get("error")
            or ""
        )

    cleaned = HEX_ADDR_RE.sub("<HEX>", text)
    cleaned = UUID_RE.sub("<UUID>", cleaned)
    cleaned = TIMESTAMP_RE.sub("<TIMESTAMP>", cleaned)
    cleaned = LINE_NUM_RE.sub("line <N>", cleaned)
    cleaned = PORT_RE.sub("<HOST:PORT>", cleaned)

    exc_type = "Failure"
    exc_match = PYTHON_EXCEPTION_RE.search(cleaned)
    if exc_match:
        exc_type = exc_match.group(1).strip()
    elif "AssertionError" in cleaned:
        exc_type = "AssertionError"
    elif "TimeoutError" in cleaned or "timed out" in cleaned.lower():
        exc_type = "TimeoutError"
    elif "ConnectionRefused" in cleaned:
        exc_type = "ConnectionRefusedError"
    elif "KeyError" in cleaned:
        exc_type = "KeyError"
    elif "TypeError" in cleaned:
        exc_type = "TypeError"
    elif "ValueError" in cleaned:
        exc_type = "ValueError"

    root_module = failing_file
    files = FILE_PATH_RE.findall(cleaned)
    for f in files:
        if "tests/" not in f:
            root_module = f
            break

    words = [
        w.lower()
        for w in TOKEN_SPLIT_RE.split(cleaned)
        if len(w) > 2
        and not w.isdigit()
        and w not in {"hex", "uuid", "timestamp", "none", "true", "false"}
    ]
    tokens = tuple(sorted(set(words)))

    first_line = (
        cleaned.strip().splitlines()[0] if cleaned.strip() else f"{exc_type} in {test_node}"
    )
    normalized_msg = _clean(first_line, limit=180)

    return NormalizedFailureSignature(
        raw_id=f"{test_node}::{exc_type}",
        test_node=test_node,
        exception_type=exc_type,
        normalized_message=normalized_msg,
        failing_file=failing_file,
        root_module=root_module,
        tokens=tokens,
    )


def compute_signature_similarity(
    sig_a: NormalizedFailureSignature, sig_b: NormalizedFailureSignature
) -> float:
    same_exc = sig_a.exception_type == sig_b.exception_type
    exc_score = 0.4 if same_exc else 0.0

    set_a = set(sig_a.tokens)
    set_b = set(sig_b.tokens)
    union = set_a | set_b
    if union:
        jaccard = len(set_a & set_b) / len(union)
    else:
        jaccard = 1.0 if sig_a.normalized_message == sig_b.normalized_message else 0.0
    token_score = jaccard * 0.5

    same_module = bool(sig_a.root_module and sig_a.root_module == sig_b.root_module)
    module_score = 0.1 if same_module else 0.0

    similarity = exc_score + token_score + module_score
    if not same_exc:
        similarity = min(0.45, similarity)
    return round(min(1.0, similarity), 3)


def classify_root_cause_category(
    signatures: Sequence[NormalizedFailureSignature],
) -> str:
    combined = " ".join(
        f"{s.exception_type} {s.normalized_message} {' '.join(s.tokens)}" for s in signatures
    ).lower()

    if any(k in combined for k in ("deadlock", "race", "asyncio", "lock", "thread", "concurrency")):
        return "CONCURRENCY_RACE"
    if any(
        k in combined
        for k in (
            "timeout",
            "timed out",
            "deadline",
            "connectionrefused",
            "unreachable",
            "timedout",
        )
    ):
        return "ENVIRONMENT_TIMEOUT"
    if any(
        k in combined
        for k in (
            "oom",
            "memory",
            "pool exhausted",
            "out of memory",
            "too many open",
        )
    ):
        return "RESOURCE_EXHAUSTION"
    if any(
        k in combined
        for k in (
            "keyerror",
            "attributeerror",
            "typeerror",
            "schema",
            "contract",
            "missing required",
        )
    ):
        return "SCHEMA_CONTRACT_MISMATCH"
    if any(k in combined for k in ("assertionerror", "assert", "mismatch", "not equal")):
        return "ASSERTION_REGRESSION"
    return "INFRASTRUCTURE_FLAKE"


def cluster_failures(
    raw_failures: Sequence[dict[str, Any] | str],
    min_similarity: float = 0.65,
) -> dict[str, Any]:
    signatures = [normalize_failure(f) for f in raw_failures]
    if not signatures:
        return {
            "schema_version": CLUSTER_SCHEMA_VERSION,
            "total_failures": 0,
            "cluster_count": 0,
            "clusters": [],
            "root_cause_graph": {"nodes": [], "edges": []},
            "summary": "No failures detected to cluster.",
        }

    clusters: list[list[NormalizedFailureSignature]] = []

    for sig in signatures:
        best_cluster_idx = -1
        best_sim = -1.0
        for idx, cluster in enumerate(clusters):
            sims = [compute_signature_similarity(sig, member) for member in cluster]
            avg_sim = sum(sims) / len(sims)
            if avg_sim >= min_similarity and avg_sim > best_sim:
                best_sim = avg_sim
                best_cluster_idx = idx

        if best_cluster_idx >= 0:
            clusters[best_cluster_idx].append(sig)
        else:
            clusters.append([sig])

    cluster_objects = []
    graph_nodes = []
    graph_edges = []

    for i, cluster in enumerate(clusters, start=1):
        c_id = f"cluster_{i:03d}"
        category = classify_root_cause_category(cluster)

        if len(cluster) == 1:
            anchor = cluster[0]
        else:
            scores = []
            for candidate in cluster:
                score = sum(compute_signature_similarity(candidate, other) for other in cluster)
                scores.append((score, candidate))
            anchor = sorted(scores, key=lambda x: x[0], reverse=True)[0][1]

        primary_exc = anchor.exception_type
        root_mod = anchor.root_module or "shared-component"
        title = f"{primary_exc} across {len(cluster)} tests via {root_mod}"

        fix_strategy = (
            f"Fix primary anchor test `{anchor.test_node}` in `{root_mod}` to resolve "
            f"all {len(cluster)} cascading failures in this cluster ({category})."
        )

        cluster_obj = {
            "cluster_id": c_id,
            "title": title,
            "root_cause_category": category,
            "size": len(cluster),
            "primary_anchor_test": anchor.test_node,
            "primary_exception": primary_exc,
            "root_module": root_mod,
            "recommended_fix_strategy": fix_strategy,
            "failures": [s.to_dict() for s in cluster],
        }
        cluster_objects.append(cluster_obj)

        graph_nodes.append({"id": c_id, "label": f"{title} [{category}]", "type": "cluster"})
        for member in cluster:
            graph_nodes.append({"id": member.test_node, "label": member.test_node, "type": "test"})
            graph_edges.append({"source": c_id, "target": member.test_node})

    return {
        "schema_version": CLUSTER_SCHEMA_VERSION,
        "total_failures": len(signatures),
        "cluster_count": len(cluster_objects),
        "min_similarity_threshold": min_similarity,
        "clusters": cluster_objects,
        "root_cause_graph": {"nodes": graph_nodes, "edges": graph_edges},
        "summary": (
            f"Clustered {len(signatures)} failure signatures into {len(cluster_objects)} distinct "
            f"root-cause clusters (deduplication ratio: {round(len(signatures) / max(1, len(cluster_objects)), 1)}x)."
        ),
    }


def render_cluster_markdown(report: dict[str, Any]) -> str:
    total_failures = report.get("total_failures", 0)
    cluster_count = report.get("cluster_count", 0)
    clusters = report.get("clusters", [])

    lines = [
        "# Failure Signature & Root-Cause Clustering Report",
        "",
        f"- **Total Failures Analyzed:** {total_failures}",
        f"- **Root-Cause Clusters:** {cluster_count}",
        f"- **Deduplication Ratio:** {round(total_failures / max(1, cluster_count), 1)}x",
        "",
        "## Root-Cause Clusters Overview",
        "",
        "| Cluster ID | Category | Size | Primary Anchor Test | Root Module |",
        "| :--- | :--- | :--- | :--- | :--- |",
    ]

    for c in clusters:
        c_id = c["cluster_id"]
        cat = f"`{c['root_cause_category']}`"
        sz = c["size"]
        anchor = f"`{c['primary_anchor_test']}`"
        mod = f"`{c['root_module']}`"
        lines.append(f"| **{c_id}** | {cat} | {sz} | {anchor} | {mod} |")

    lines.extend(["", "## Root-Cause Dependency Graph", "", "```mermaid", "graph TD"])
    for c in clusters:
        c_id = c["cluster_id"]
        c_label = f'"{c["cluster_id"]}: {c["primary_exception"]} ({c["size"]} tests)"'
        lines.append(f"    {c_id}[{c_label}]")
        for f in c.get("failures", []):
            node_id = re.sub(r"[^A-Za-z0-9_]", "_", f["test_node"])[:32]
            lines.append(f'    {c_id} --> {node_id}["{f["test_node"]}"]')
    lines.extend(["```", "", "## Prioritized Remediation Guidance", ""])

    for c in clusters:
        lines.append(f"### {c['cluster_id']}: {c['title']}")
        lines.append(f"- **Category:** `{c['root_cause_category']}`")
        lines.append(f"- **Primary Anchor:** `{c['primary_anchor_test']}`")
        lines.append(f"- **Strategy:** {c['recommended_fix_strategy']}")
        lines.append("")

    return "\n".join(lines)


def _collect_cluster_inputs(
    root: Path, input_path: Path | None = None
) -> list[dict[str, Any] | str]:
    target = input_path or (root / "build")
    items: list[dict[str, Any] | str] = []

    if input_path and input_path.is_file():
        try:
            content = input_path.read_text(encoding="utf-8", errors="replace")
            if input_path.suffix in (".json", ".jsonl"):
                data = json.loads(content)
                if isinstance(data, list):
                    items.extend(data)
                elif isinstance(data, dict):
                    if "failures" in data and isinstance(data["failures"], list):
                        items.extend(data["failures"])
                    elif "errors" in data and isinstance(data["errors"], list):
                        items.extend(data["errors"])
                    else:
                        items.append(data)
            else:
                for line in content.splitlines():
                    if PYTEST_NODE_RE.search(line) or "FAILED" in line or "Error:" in line:
                        items.append(line)
        except (OSError, json.JSONDecodeError, UnicodeDecodeError):
            # Fall back to empty list on unreadable input file
            pass
        return items

    if target.is_dir():
        for file_p in target.glob("*.json"):
            try:
                data = json.loads(file_p.read_text(encoding="utf-8"))
                if isinstance(data, dict) and data.get("verdict") in (
                    "NO_SHIP",
                    "FAIL",
                    "BREACHED",
                ):
                    items.append(data)
            except (OSError, json.JSONDecodeError, UnicodeDecodeError):
                # Silently ignore unreadable artifacts in build directory
                pass

    return items


def cluster_main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="sdetkit cluster",
        description="Cluster failure signatures and graph shared root causes across test runs",
    )
    parser.add_argument(
        "subcommand",
        nargs="?",
        default="analyze",
        choices=["analyze", "graph", "report"],
        help="Clustering action",
    )
    parser.add_argument("--repo-root", default=".", help="Target repository root")
    parser.add_argument(
        "--input",
        default=None,
        help="Path to CI log, JSON failure report, or directory",
    )
    parser.add_argument(
        "--min-similarity",
        type=float,
        default=0.65,
        help="Minimum similarity threshold (0.0 to 1.0) for clustering",
    )
    parser.add_argument(
        "--format",
        choices=["text", "json", "md"],
        default="text",
        help="Output format",
    )
    parser.add_argument("--out", default=None, help="Path to write JSON output report")
    parser.add_argument("--summary-out", default=None, help="Path to write Markdown summary")
    parser.add_argument(
        "--fail-on",
        choices=["any", "clusters", "none"],
        default="clusters",
        help="Trigger non-zero exit code on failure",
    )

    args = parser.parse_args(list(argv) if argv is not None else None)
    root = Path(args.repo_root).resolve()
    inp = Path(args.input).resolve() if args.input else None

    failures = _collect_cluster_inputs(root, inp)
    report = cluster_failures(failures, min_similarity=args.min_similarity)

    rendered_json = json.dumps(report, indent=2, sort_keys=True) + "\n"
    rendered_md = render_cluster_markdown(report)

    if args.out:
        out_p = Path(args.out)
        out_p.parent.mkdir(parents=True, exist_ok=True)
        out_p.write_text(rendered_json, encoding="utf-8")

    if args.summary_out:
        sum_p = Path(args.summary_out)
        sum_p.parent.mkdir(parents=True, exist_ok=True)
        sum_p.write_text(rendered_md, encoding="utf-8")

    if args.format == "json":
        sys.stdout.write(rendered_json)
    elif args.format == "md":
        sys.stdout.write(rendered_md + "\n")
    else:
        sys.stdout.write(
            f"Failure Clusters: {report['cluster_count']} clusters across {report['total_failures']} failures\n"
        )
        for c in report["clusters"]:
            sys.stdout.write(
                f"  - [{c['cluster_id']}] {c['title']} ({c['root_cause_category']}) -> Anchor: {c['primary_anchor_test']}\n"
            )
        if report["clusters"]:
            sys.stdout.write(f"Summary: {report['summary']}\n")

    if args.fail_on == "any" and report["total_failures"] > 0:
        return 1
    if args.fail_on == "clusters" and report["cluster_count"] > 0:
        return 1
    return 0


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="sdetkit triage-ci",
        description="Diagnose failed CI logs and recommend advisory-only verification.",
    )
    parser.add_argument("--log", required=True, help="Path to a saved failed CI job log.")
    parser.add_argument(
        "--format",
        choices=["text", "json", "md", "markdown"],
        default="text",
        help="Output format.",
    )
    parser.add_argument("--output", default="", help="Optional file path to write the report.")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    subcommand_env = os.environ.get("SDETKIT_SUBCOMMAND")
    effective_argv = list(argv) if argv is not None else sys.argv[1:]
    if subcommand_env == "cluster" and (not effective_argv or effective_argv[0] != "cluster"):
        effective_argv = ["cluster", *effective_argv]

    if effective_argv and effective_argv[0] == "cluster":
        return cluster_main(effective_argv[1:])

    args = _build_parser().parse_args(effective_argv)
    text = Path(args.log).read_text(encoding="utf-8", errors="replace")
    report = build_triage_report(text)

    if args.format == "json":
        rendered = json.dumps(_as_payload(report), indent=2, sort_keys=True) + "\n"
    elif args.format in {"md", "markdown"}:
        rendered = _render_markdown(report)
    else:
        rendered = _render_text(report)

    if args.output:
        out = Path(args.output)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(rendered, encoding="utf-8")

    print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
