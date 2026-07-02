from __future__ import annotations

import json
from base64 import b64encode
from collections.abc import Mapping
from datetime import datetime, timezone
from hashlib import sha256
from html import escape
from os import environ
from typing import Any

JsonObject = dict[str, Any]


def _as_dict(value: object) -> JsonObject:
    return value if isinstance(value, dict) else {}


def _as_list(value: object) -> list[object]:
    return value if isinstance(value, list) else []


def _text(value: object, default: str = "") -> str:
    if value is None:
        return default
    rendered = str(value).strip()
    return rendered or default


def _integer(value: object) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _boolean_text(value: object) -> str:
    return "true" if bool(value) else "false"


def _link(server_url: str, repository: str, suffix: str) -> str:
    if not server_url or not repository or not suffix:
        return ""
    return f"{server_url.rstrip('/')}/{repository}/{suffix.lstrip('/')}"


def _fact(
    fact_id: str,
    label: str,
    value: str,
    status: str,
    source_path: str,
) -> JsonObject:
    return {
        "id": fact_id,
        "label": label,
        "value": value,
        "status": status,
        "source_path": source_path,
    }


def build_live_evidence_snapshot(
    *,
    pr_number: int,
    head_sha: str,
    base_sha: str,
    review_model: JsonObject,
    check_intelligence: JsonObject,
    runtime_proof_artifacts: JsonObject,
    artifact_manifest: JsonObject,
    environment: Mapping[str, str] | None = None,
    generated_at: str | None = None,
) -> JsonObject:
    env = dict(environ if environment is None else environment)
    decision = _as_dict(review_model.get("decision"))
    ghas = _as_dict(review_model.get("ghas_blocker_details"))
    authority = _as_dict(review_model.get("authority_boundary"))
    isolated = _as_dict(runtime_proof_artifacts.get("isolated_proof"))
    benchmark = _as_dict(runtime_proof_artifacts.get("live_benchmark"))
    history = _as_dict(runtime_proof_artifacts.get("trusted_history"))
    inventory = _as_dict(artifact_manifest.get("expected_artifact_inventory_verification"))

    server_url = _text(env.get("GITHUB_SERVER_URL"), "https://github.com")
    repository = _text(env.get("GITHUB_REPOSITORY"))
    run_id = _text(env.get("GITHUB_RUN_ID"))
    run_attempt = _text(env.get("GITHUB_RUN_ATTEMPT"), "1")
    workflow_name = _text(env.get("GITHUB_WORKFLOW"), "PR Quality Comment")
    job_name = _text(env.get("GITHUB_JOB"))
    ref_name = _text(env.get("GITHUB_REF_NAME"))

    resolved_head = _text(
        head_sha
        or ghas.get("current_head_sha")
        or check_intelligence.get("current_head_sha")
        or env.get("GITHUB_SHA")
    )
    observed_head = _text(
        ghas.get("current_head_sha") or check_intelligence.get("current_head_sha")
    )
    if resolved_head and observed_head:
        head_binding = "verified" if resolved_head == observed_head else "mismatch"
    elif resolved_head:
        head_binding = "declared"
    else:
        head_binding = "not_collected"

    workflow_url = _link(server_url, repository, f"actions/runs/{run_id}") if run_id else ""
    provenance = {
        "repository": repository,
        "pr_number": pr_number,
        "head_sha": resolved_head,
        "base_sha": _text(base_sha),
        "observed_head_sha": observed_head,
        "head_binding_status": head_binding,
        "workflow_name": workflow_name,
        "workflow_run_id": run_id,
        "workflow_run_attempt": run_attempt,
        "job_name": job_name,
        "ref_name": ref_name,
        "artifact_name": "pr-quality-comment",
        "artifact_entrypoint": "pr-quality/index.html",
        "pr_url": (_link(server_url, repository, f"pull/{pr_number}") if pr_number > 0 else ""),
        "head_commit_url": (
            _link(server_url, repository, f"commit/{resolved_head}") if resolved_head else ""
        ),
        "workflow_run_url": workflow_url,
        "artifacts_url": f"{workflow_url}#artifacts" if workflow_url else "",
    }

    failed = _integer(decision.get("failed_checks"))
    queued = _integer(decision.get("required_queued_checks"))
    startup = _integer(decision.get("required_startup_failures"))
    missing = _integer(decision.get("missing_required_contexts"))

    security_collected = bool(ghas.get("collected", False))
    current_alerts = _integer(ghas.get("current_alerts"))
    stale_alerts = _integer(ghas.get("stale_alerts"))
    if not security_collected:
        security_status = "unavailable"
        security_value = "collection unavailable"
    elif current_alerts:
        security_status = "attention"
        security_value = f"{current_alerts} current · {stale_alerts} stale alert(s)"
    else:
        security_status = "clear"
        security_value = f"0 current · {stale_alerts} stale alert(s)"

    requested = _integer(isolated.get("profiles_requested"))
    executed = _integer(isolated.get("profiles_executed"))
    passed = _integer(isolated.get("profiles_passed"))
    proof_failed = _integer(isolated.get("profiles_failed"))
    guard_violations = _integer(isolated.get("runtime_guard_violation_count"))
    proof_state = _text(isolated.get("status"), "not_collected")
    proof_status = (
        "clear"
        if proof_state == "passed" and proof_failed == 0 and guard_violations == 0
        else "attention"
        if proof_state != "not_collected"
        else "unavailable"
    )

    scenario_count = _integer(benchmark.get("scenario_count"))
    scenario_passed = _integer(benchmark.get("passed_count"))
    scenario_failed = _integer(benchmark.get("failed_count"))
    anti_cheat = _integer(benchmark.get("anti_cheat_rejection_count"))
    benchmark_state = _text(benchmark.get("status"), "not_collected")
    benchmark_status = (
        "clear"
        if benchmark_state == "passed" and scenario_failed == 0
        else "attention"
        if benchmark_state != "not_collected"
        else "unavailable"
    )

    history_records = _integer(history.get("record_count"))
    ancestry = bool(history.get("base_ancestry_verified", False))
    read_only = bool(history.get("prior_history_is_read_only_input", False))
    history_state = _text(history.get("status"), "not_collected")
    history_status = (
        "clear"
        if history_state == "trusted_history_verified" and ancestry and read_only
        else "attention"
        if history_state != "not_collected"
        else "unavailable"
    )

    expected_artifacts = _integer(inventory.get("expected_artifact_count"))
    missing_authority_paths = len(_as_list(inventory.get("missing_authority_evidence_paths")))
    inventory_state = _text(inventory.get("status"), "not_collected")
    inventory_status = (
        "clear"
        if inventory_state == "passed" and missing_authority_paths == 0
        else "attention"
        if inventory_state != "not_collected"
        else "unavailable"
    )

    facts = [
        _fact(
            "head_binding",
            "Head binding",
            (f"{head_binding}: {resolved_head}" if resolved_head else head_binding),
            "clear" if head_binding == "verified" else "attention",
            "code-scanning/alerts.json",
        ),
        _fact(
            "required_checks",
            "Required checks",
            (f"{failed} failed · {queued} queued · {startup} startup · {missing} missing"),
            "clear" if failed + queued + startup + missing == 0 else "attention",
            "check-intelligence/check-intelligence.json",
        ),
        _fact(
            "security",
            "Security evidence",
            security_value,
            security_status,
            "code-scanning/alerts.json",
        ),
        _fact(
            "runtime_proof",
            "Runtime proof",
            (
                f"{passed}/{executed} profiles passed "
                f"({requested} requested) · "
                f"{guard_violations} guard violation(s)"
            ),
            proof_status,
            "runtime-proof/summary/runtime-proof-artifacts.json",
        ),
        _fact(
            "live_benchmark",
            "Live benchmark",
            (
                f"{scenario_passed}/{scenario_count} scenarios passed · "
                f"{scenario_failed} failed · "
                f"{anti_cheat} anti-cheat rejection(s)"
            ),
            benchmark_status,
            "runtime-proof/summary/runtime-proof-artifacts.json",
        ),
        _fact(
            "trusted_history",
            "Trusted history",
            (
                f"{history_records} record(s) · ancestry "
                f"{_boolean_text(ancestry)} · read-only input "
                f"{_boolean_text(read_only)}"
            ),
            history_status,
            "runtime-proof/summary/runtime-proof-artifacts.json",
        ),
        _fact(
            "artifact_inventory",
            "Artifact inventory",
            (
                f"{expected_artifacts} expected artifact(s) · "
                f"{missing_authority_paths} missing authority path(s)"
            ),
            inventory_status,
            "pr-review-artifacts-manifest.json",
        ),
    ]

    complete = bool(
        repository and run_id and resolved_head and pr_number > 0 and head_binding == "verified"
    )
    generated = generated_at or datetime.now(timezone.utc).replace(microsecond=0).isoformat()

    return {
        "schema_version": "sdetkit.pr_quality.live_evidence.v1",
        "snapshot_kind": "workflow_run_evidence",
        "snapshot_status": "complete" if complete else "partial",
        "generated_at_utc": generated,
        "provenance": provenance,
        "decision_observation": {
            "review_state": _text(decision.get("review_state"), "unknown"),
            "merge_assessment": _text(
                decision.get("merge_assessment"),
                "unknown",
            ),
            "next_action": _text(decision.get("next_action"), "unknown"),
            "risk_surface": _text(decision.get("risk_surface"), "unknown"),
        },
        "facts": facts,
        "lineage": [
            {
                "stage": "collect",
                "source_path": ("check-intelligence/check-intelligence.json"),
                "description": ("Observed checks, required contexts, and security state."),
            },
            {
                "stage": "prove",
                "source_path": ("runtime-proof/summary/runtime-proof-artifacts.json"),
                "description": ("Observed isolated proof, guards, benchmark, and history."),
            },
            {
                "stage": "decide",
                "source_path": "pr-review-model.json",
                "description": ("Canonical reporting-only model for rendered surfaces."),
            },
            {
                "stage": "publish",
                "source_path": "pr-review-artifacts-manifest.json",
                "description": ("Expected artifact inventory and authority source map."),
            },
        ],
        "authority_boundary": {
            "boundary_mode": _text(
                authority.get("boundary_mode"),
                "reporting_only",
            ),
            "patch_automation": bool(authority.get("patch_automation", False)),
            "security_dismissal": bool(authority.get("security_dismissal", False)),
            "merge_authorization": bool(authority.get("merge_authorization", False)),
            "semantic_equivalence_claim": bool(authority.get("semantic_equivalence_claim", False)),
        },
    }


def render_live_evidence_markdown(snapshot: JsonObject) -> str:
    if not snapshot:
        return ""

    provenance = _as_dict(snapshot.get("provenance"))
    facts = [_as_dict(item) for item in _as_list(snapshot.get("facts")) if _as_dict(item)]
    lines = [
        "## Live evidence snapshot",
        "",
        (
            "> Generated from structured workflow artifacts for this exact "
            "PR head; these values are not manually maintained status prose."
        ),
        "",
        "| Provenance | Value |",
        "|---|---|",
    ]

    pr_number = _integer(provenance.get("pr_number"))
    pr_url = _text(provenance.get("pr_url"))
    if pr_number:
        lines.append(
            f"| Pull request | {f'[#{pr_number}]({pr_url})' if pr_url else f'#{pr_number}'} |"
        )

    head_sha = _text(provenance.get("head_sha"))
    head_url = _text(provenance.get("head_commit_url"))
    if head_sha:
        head_label = f"`{head_sha[:12]}`"
        if head_url:
            head_label = f"[{head_label}]({head_url})"
        lines.append(f"| Exact head | {head_label} |")

    run_id = _text(provenance.get("workflow_run_id"))
    run_url = _text(provenance.get("workflow_run_url"))
    if run_id:
        lines.append(f"| Producer run | {f'[{run_id}]({run_url})' if run_url else run_id} |")

    artifact_name = _text(
        provenance.get("artifact_name"),
        "pr-quality-comment",
    )
    entrypoint = _text(
        provenance.get("artifact_entrypoint"),
        "pr-quality/index.html",
    )
    artifact_label = f"`{artifact_name}` → `{entrypoint}`"
    artifacts_url = _text(provenance.get("artifacts_url"))
    if artifacts_url:
        artifact_label = f"[{artifact_label}]({artifacts_url})"
    lines.extend(
        [
            f"| Dashboard artifact | {artifact_label} |",
            (f"| Head binding | `{_text(provenance.get('head_binding_status'), 'unknown')}` |"),
            (f"| Snapshot generated | `{_text(snapshot.get('generated_at_utc'), 'unknown')}` |"),
            "",
            "### Observed indicators",
            "",
            "| Indicator | Observed value | Evidence source |",
            "|---|---|---|",
        ]
    )

    for fact in facts:
        lines.append(
            "| "
            + _text(fact.get("label"), "Unnamed indicator")
            + " | "
            + f"**{_text(fact.get('status'), 'unknown')}** — "
            + _text(fact.get("value"), "not collected")
            + " | "
            + f"`{_text(fact.get('source_path'), 'unknown')}` |"
        )

    lines.extend(
        [
            "",
            (
                "> Download the `pr-quality-comment` artifact and open "
                "`pr-quality/index.html` for the visual evidence center."
            ),
        ]
    )
    return "\n".join(lines) + "\n"


def render_live_evidence_html(snapshot: JsonObject) -> str:
    if not snapshot:
        return ""

    provenance = _as_dict(snapshot.get("provenance"))
    facts = [_as_dict(item) for item in _as_list(snapshot.get("facts")) if _as_dict(item)]
    lineage = [_as_dict(item) for item in _as_list(snapshot.get("lineage")) if _as_dict(item)]

    def safe(value: object) -> str:
        return escape(_text(value), quote=True)

    fact_cards = "\n".join(
        (
            f'<article class="live-fact live-{safe(fact.get("status"))}">'
            f'<span class="live-fact-label">'
            f"{safe(fact.get('label'))}</span>"
            f"<strong>{safe(fact.get('value'))}</strong>"
            f"<code>{safe(fact.get('source_path'))}</code>"
            "</article>"
        )
        for fact in facts
    )
    lineage_rows = "\n".join(
        (
            "<tr>"
            f"<td><strong>{safe(item.get('stage'))}</strong></td>"
            f"<td><code>{safe(item.get('source_path'))}</code></td>"
            f"<td>{safe(item.get('description'))}</td>"
            "</tr>"
        )
        for item in lineage
    )

    links = [
        (
            _text(provenance.get("pr_url")),
            f"PR #{_integer(provenance.get('pr_number'))}",
        ),
        (
            _text(provenance.get("head_commit_url")),
            f"Head {_text(provenance.get('head_sha'))[:12]}",
        ),
        (
            _text(provenance.get("workflow_run_url")),
            f"Workflow run {_text(provenance.get('workflow_run_id'))}",
        ),
        (
            _text(provenance.get("artifacts_url")),
            "Download dashboard artifact",
        ),
    ]
    rendered_links = " ".join(
        (
            f'<span class="live-link">'
            f'<a href="{safe(url)}" target="_blank" rel="noreferrer">'
            f"{safe(label)}</a></span>"
        )
        for url, label in links
        if url
    )

    return f"""
<style>
.live-evidence {{ margin-top: 1rem; }}
.live-evidence-header {{
  display: flex; gap: 1rem; align-items: flex-start;
  justify-content: space-between; flex-wrap: wrap;
}}
.live-evidence-header p {{
  color: var(--muted, #8b949e); max-width: 760px;
}}
.live-badge {{
  border: 1px solid var(--border, #30363d);
  border-radius: 999px; padding: .35rem .7rem; font-weight: 800;
}}
.live-links {{
  display: flex; flex-wrap: wrap; gap: .5rem; margin: 1rem 0;
}}
.live-link a {{
  display: inline-flex; padding: .45rem .7rem;
  border: 1px solid var(--border, #30363d);
  border-radius: 10px; text-decoration: none;
}}
.live-facts {{
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
  gap: .75rem;
}}
.live-fact {{
  display: grid; gap: .35rem;
  border: 1px solid var(--border, #30363d);
  border-radius: 14px; padding: .9rem;
  background: rgba(13,17,23,.46);
}}
.live-fact-label {{
  color: var(--muted, #8b949e); font-size: .82rem;
  font-weight: 800; text-transform: uppercase; letter-spacing: .06em;
}}
.live-fact code {{ overflow-wrap: anywhere; }}
.live-clear {{ border-color: rgba(63,185,80,.45); }}
.live-attention {{ border-color: rgba(240,183,47,.55); }}
.live-unavailable {{ border-color: rgba(139,148,158,.55); }}
.live-lineage {{
  width: 100%; margin-top: 1rem; border-collapse: collapse;
}}
.live-lineage th, .live-lineage td {{
  padding: .65rem;
  border-bottom: 1px solid var(--border, #30363d);
  text-align: left; vertical-align: top;
}}
</style>
<section id="live-evidence" class="card live-evidence">
  <div class="live-evidence-header">
    <div>
      <div class="eyebrow">Observed workflow evidence</div>
      <h2>Live evidence snapshot</h2>
      <p>Generated from the exact PR head, check intelligence, security collection, runtime proof, trusted history, and artifact manifest. It is a per-run evidence snapshot, not a manually maintained status page.</p>
    </div>
    <span class="live-badge">{safe(snapshot.get("snapshot_status"))}</span>
  </div>
  <div class="live-links">{rendered_links}</div>
  <div class="live-facts">{fact_cards}</div>
  <table class="live-lineage">
    <thead>
      <tr><th>Stage</th><th>Source</th><th>Observed role</th></tr>
    </thead>
    <tbody>{lineage_rows}</tbody>
  </table>
  <p class="boundary">Head binding: <code>{safe(provenance.get("head_binding_status"))}</code> · Generated: <code>{safe(snapshot.get("generated_at_utc"))}</code> · Artifact entrypoint: <code>{safe(provenance.get("artifact_entrypoint"))}</code></p>
</section>
""".strip()


def render_live_product_dashboard(
    model: JsonObject,
    *,
    embedded_artifacts: JsonObject | None = None,
) -> str:
    snapshot = _as_dict(model.get("live_evidence"))
    if not snapshot:
        return ""

    provenance = _as_dict(snapshot.get("provenance"))
    decision = _as_dict(model.get("decision"))
    authority = _as_dict(snapshot.get("authority_boundary"))
    facts = [_as_dict(item) for item in _as_list(snapshot.get("facts")) if _as_dict(item)]
    lineage = [_as_dict(item) for item in _as_list(snapshot.get("lineage")) if _as_dict(item)]
    artifacts = [
        _as_dict(item)
        for item in _as_list(model.get("artifact_index"))
        if _as_dict(item) and _text(_as_dict(item).get("path"))
    ]
    embedded_sources = {
        _text(path): _as_dict(item)
        for path, item in (embedded_artifacts or {}).items()
        if _text(path) and _as_dict(item)
    }
    embedded_payload: JsonObject = {}
    for artifact_path, item in embedded_sources.items():
        content = item.get("content")
        if not isinstance(content, str):
            continue
        content_bytes = content.encode("utf-8")
        embedded_payload[artifact_path] = {
            "mime_type": _text(
                item.get("mime_type"),
                "text/plain;charset=utf-8",
            ),
            "content_base64": b64encode(content_bytes).decode("ascii"),
            "size_bytes": len(content_bytes),
            "sha256": sha256(content_bytes).hexdigest(),
        }

    def safe(value: object) -> str:
        return escape(_text(value), quote=True)

    def external_link(url: str, label: str, css_class: str) -> str:
        if not url:
            return ""
        return (
            f'<a class="{css_class}" href="{safe(url)}" '
            f'target="_blank" rel="noreferrer">{safe(label)}</a>'
        )

    review_state = _text(decision.get("review_state"), "unknown")
    state_label = {
        "ready": "Ready for human decision",
        "waiting": "Waiting for CI",
        "blocked": "Blocked",
        "review": "Human review required",
        "stale": "Stale evidence",
        "invalid": "Invalid evidence",
    }.get(review_state, review_state.replace("_", " ").title())
    state_tone = {
        "ready": "success",
        "waiting": "waiting",
        "blocked": "danger",
        "review": "review",
        "stale": "warning",
        "invalid": "danger",
    }.get(review_state, "neutral")

    facts_by_id = {_text(item.get("id")): item for item in facts if _text(item.get("id"))}
    metric_specs = [
        ("Required checks", "required_checks"),
        ("Security", "security"),
        ("Runtime proof", "runtime_proof"),
        ("Artifact inventory", "artifact_inventory"),
    ]
    metric_cards = "\n".join(
        (
            f'<article class="metric metric-{safe(fact.get("status"))}">'
            f"<span>{safe(label)}</span>"
            f"<strong>{safe(fact.get('value') or 'not collected')}</strong>"
            "</article>"
        )
        for label, fact_id in metric_specs
        for fact in [facts_by_id.get(fact_id, {})]
    )

    status_counts = {
        status: sum(_text(item.get("status")) == status for item in facts)
        for status in ("clear", "attention", "unavailable")
    }

    fact_cards = "\n".join(
        (
            f'<article class="evidence-card" '
            f'data-id="{safe(item.get("id"))}" '
            f'data-status="{safe(item.get("status"))}" '
            f'data-search="{safe(" ".join((_text(item.get("label")), _text(item.get("value")), _text(item.get("source_path")))).lower())}">'
            '<div class="evidence-card-top">'
            "<div>"
            f'<div class="eyebrow">{safe(item.get("source_path"))}</div>'
            f"<h3>{safe(item.get('label'))}</h3>"
            "</div>"
            f'<span class="status-badge {safe(item.get("status"))}">'
            f"{safe(item.get('status'))}</span>"
            "</div>"
            f"<p>{safe(item.get('value'))}</p>"
            '<div class="evidence-card-actions">'
            f"<code>{safe(item.get('id'))}</code>"
            f'<button class="button primary" type="button" '
            f'data-open-evidence="{safe(item.get("id"))}">'
            "Open evidence</button>"
            "</div>"
            "</article>"
        )
        for item in facts
    )
    if not fact_cards:
        fact_cards = (
            '<div class="empty-state visible">'
            "No live evidence facts were emitted for this run."
            "</div>"
        )

    def artifact_link(item: JsonObject) -> str:
        artifact_path = _text(item.get("path"))
        artifact_kind = _text(item.get("kind") or item.get("format"))
        artifacts_url = _text(provenance.get("artifacts_url"))
        if artifact_kind == "github_artifact":
            if artifacts_url:
                return external_link(
                    artifacts_url,
                    "Download full bundle",
                    "button",
                )
            return '<span class="button">Artifact unavailable</span>'
        if artifact_path == "index.html":
            return '<a class="button" href="#overview">View dashboard</a>'
        if artifact_path in embedded_payload:
            return (
                '<div class="artifact-actions">'
                f'<button class="button primary" type="button" '
                f'data-open-artifact="{safe(artifact_path)}">'
                "Open artifact</button>"
                f'<button class="button" type="button" '
                f'data-download-artifact="{safe(artifact_path)}">'
                "Download file</button>"
                "</div>"
            )
        if artifacts_url:
            return external_link(
                artifacts_url,
                "Download full bundle",
                "button",
            )
        return '<span class="button">Artifact not embedded</span>'

    artifact_cards = "\n".join(
        "".join(
            (
                '<article class="artifact-card">',
                "<div>",
                f'<div class="eyebrow">{safe(item.get("kind") or item.get("format") or "artifact")}</div>',
                f"<h3>{safe(item.get('title') or item.get('path'))}</h3>",
                f"<p>{safe(item.get('description') or item.get('surface') or 'Workflow artifact')}</p>",
                "</div>",
                artifact_link(item),
                f"<code>{safe(item.get('path'))}</code>",
                "</article>",
            )
        )
        for item in artifacts
    )
    if not artifact_cards:
        artifact_cards = (
            '<div class="empty-state visible">'
            "The review model did not publish an artifact index."
            "</div>"
        )

    lineage_rows = "\n".join(
        (
            "<tr>"
            f"<td><strong>{safe(item.get('stage'))}</strong></td>"
            f"<td><code>{safe(item.get('source_path'))}</code></td>"
            f"<td>{safe(item.get('description'))}</td>"
            "</tr>"
        )
        for item in lineage
    )

    decision_rows = [
        ("Review state", review_state),
        ("Merge assessment", decision.get("merge_assessment")),
        ("Next action", decision.get("next_action")),
        ("Risk surface", decision.get("risk_surface")),
        ("Signal title", decision.get("signal_title")),
        ("Head binding", provenance.get("head_binding_status")),
    ]
    decision_table = "\n".join(
        f"<tr><th>{safe(label)}</th><td><code>{safe(value)}</code></td></tr>"
        for label, value in decision_rows
    )

    authority_rows = [
        ("Boundary mode", authority.get("boundary_mode")),
        ("Patch automation", authority.get("patch_automation")),
        ("Security dismissal", authority.get("security_dismissal")),
        ("Merge authorization", authority.get("merge_authorization")),
        (
            "Semantic equivalence claim",
            authority.get("semantic_equivalence_claim"),
        ),
    ]
    authority_table = "\n".join(
        f"<tr><th>{safe(label)}</th><td><code>{safe(value)}</code></td></tr>"
        for label, value in authority_rows
    )

    pr_number = _integer(provenance.get("pr_number"))
    pr_label = f"PR #{pr_number}" if pr_number else "Pull request"
    head_sha = _text(provenance.get("head_sha"))
    head_short = head_sha[:12] if head_sha else "not collected"
    run_id = _text(provenance.get("workflow_run_id"), "not collected")
    generated_at = _text(snapshot.get("generated_at_utc"), "not collected")
    artifact_entrypoint = _text(
        provenance.get("artifact_entrypoint"),
        "pr-quality/index.html",
    )

    top_actions = " ".join(
        item
        for item in (
            external_link(
                _text(provenance.get("pr_url")),
                "Open PR",
                "button",
            ),
            external_link(
                _text(provenance.get("head_commit_url")),
                f"Head {head_short}",
                "button",
            ),
            external_link(
                _text(provenance.get("workflow_run_url")),
                f"Workflow run {run_id}",
                "button",
            ),
            external_link(
                _text(provenance.get("artifacts_url")),
                "Download dashboard artifact",
                "button primary",
            ),
        )
        if item
    )

    payload = json.dumps(
        {
            "snapshot": snapshot,
            "decision": decision,
            "facts": facts,
            "embedded_artifacts": embedded_payload,
        },
        ensure_ascii=False,
        sort_keys=True,
    ).replace("</", "<\\/")

    template = r"""<!doctype html>
<html lang="en" data-theme="light">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>__PAGE_TITLE__</title>
<style>
:root{color-scheme:light;--bg:#f4f7fb;--surface:#fff;--surface2:#f8fafc;--surface3:#eef3f8;--text:#172033;--muted:#64748b;--border:#d8e0ea;--accent:#315efb;--accent2:#7c3aed;--success:#14804a;--success-bg:#e9f8ef;--warning:#9a6700;--warning-bg:#fff6d8;--danger:#c9372c;--danger-bg:#ffebe9;--waiting:#0969da;--waiting-bg:#ddf4ff;--review:#7c3aed;--review-bg:#f2eaff;--shadow:0 18px 50px rgba(24,39,75,.09);--radius:18px;--mono:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace}
html[data-theme="dark"]{color-scheme:dark;--bg:#0b1020;--surface:#111827;--surface2:#172033;--surface3:#1f2a3d;--text:#edf2f7;--muted:#9aa8ba;--border:#2d3a50;--accent:#7aa2ff;--accent2:#b28cff;--success:#67d391;--success-bg:#123624;--warning:#f5c451;--warning-bg:#3d3010;--danger:#ff8d85;--danger-bg:#421d20;--waiting:#75baff;--waiting-bg:#112f4d;--review:#c4a7ff;--review-bg:#2e2148;--shadow:0 18px 50px rgba(0,0,0,.32)}
*{box-sizing:border-box}html{scroll-behavior:smooth}body{margin:0;background:radial-gradient(circle at 80% -10%,rgba(49,94,251,.12),transparent 32rem),var(--bg);color:var(--text);font:15px/1.55 Inter,ui-sans-serif,system-ui,-apple-system,Segoe UI,sans-serif}button,input{font:inherit}button{cursor:pointer}a{color:var(--accent)}code{font-family:var(--mono);overflow-wrap:anywhere}
.app{display:grid;grid-template-columns:280px minmax(0,1fr);min-height:100vh}.sidebar{position:sticky;top:0;height:100vh;overflow:auto;padding:24px 20px;border-right:1px solid var(--border);background:var(--surface)}.brand{display:flex;gap:12px;align-items:center;margin-bottom:28px}.brand-mark{width:42px;height:42px;border-radius:12px;display:grid;place-items:center;color:#fff;font-weight:800;background:linear-gradient(135deg,var(--accent),var(--accent2));box-shadow:0 8px 24px rgba(49,94,251,.28)}.brand strong{display:block}.brand small{color:var(--muted)}.sidebar h4{margin:24px 0 10px;color:var(--muted);font-size:11px;letter-spacing:.12em;text-transform:uppercase}.nav-link{display:flex;justify-content:space-between;padding:9px 10px;border-radius:10px;color:var(--text);text-decoration:none}.nav-link:hover{background:var(--surface3)}.filter-stack{display:flex;flex-wrap:wrap;gap:7px}.filter-chip{border:1px solid var(--border);background:var(--surface);color:var(--text);padding:6px 9px;border-radius:999px;font-size:12px}.filter-chip span{color:var(--muted);margin-left:4px}.filter-chip.active{border-color:var(--accent);box-shadow:0 0 0 2px color-mix(in srgb,var(--accent) 18%,transparent)}.sidebar-footer{margin-top:30px;color:var(--muted);font-size:12px}
.main{min-width:0;padding:28px 34px 80px}.topbar{display:flex;gap:12px;align-items:center;justify-content:space-between;margin-bottom:24px}.search{flex:1;max-width:620px;border:1px solid var(--border);background:var(--surface);color:var(--text);border-radius:12px;padding:11px 14px;outline:none}.search:focus{border-color:var(--accent);box-shadow:0 0 0 3px color-mix(in srgb,var(--accent) 18%,transparent)}.top-actions{display:flex;gap:8px;flex-wrap:wrap}.button{display:inline-flex;align-items:center;justify-content:center;border:1px solid var(--border);background:var(--surface);color:var(--text);border-radius:11px;padding:9px 12px;font-weight:650;text-decoration:none}.button.primary{color:#fff;border-color:transparent;background:linear-gradient(135deg,var(--accent),var(--accent2))}
.hero{overflow:hidden;position:relative;padding:32px;border:1px solid var(--border);border-radius:24px;background:linear-gradient(135deg,var(--surface),var(--surface2));box-shadow:var(--shadow)}.hero:after{content:"";position:absolute;width:320px;height:320px;right:-130px;top:-180px;border-radius:50%;background:linear-gradient(135deg,rgba(49,94,251,.28),rgba(124,58,237,.18))}.hero>*{position:relative;z-index:1}.hero-top{display:flex;align-items:flex-start;justify-content:space-between;gap:18px;flex-wrap:wrap}.eyebrow{color:var(--accent);font-family:var(--mono);font-size:12px;letter-spacing:.08em;text-transform:uppercase}.hero h1{max-width:880px;margin:8px 0 10px;font-size:clamp(32px,5vw,58px);line-height:1.05;letter-spacing:-.045em}.hero p{max-width:800px;color:var(--muted);font-size:17px}.hero-meta{display:flex;gap:9px;flex-wrap:wrap;margin-top:18px}.pill{border:1px solid var(--border);background:var(--surface);border-radius:999px;padding:7px 10px;font-size:12px}.status-badge{align-self:flex-start;white-space:nowrap;padding:8px 12px;border-radius:999px;font-size:12px;font-weight:800;text-transform:uppercase}.status-badge.success,.status-badge.clear{color:var(--success);background:var(--success-bg)}.status-badge.waiting{color:var(--waiting);background:var(--waiting-bg)}.status-badge.danger,.status-badge.attention{color:var(--danger);background:var(--danger-bg)}.status-badge.review{color:var(--review);background:var(--review-bg)}.status-badge.warning,.status-badge.unavailable{color:var(--warning);background:var(--warning-bg)}
.metric-grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:14px;margin:22px 0 38px}.metric{padding:20px;border:1px solid var(--border);border-radius:var(--radius);background:var(--surface)}.metric strong{display:block;margin-top:6px;font-size:16px;line-height:1.35}.metric span{color:var(--muted)}.metric-clear{border-color:color-mix(in srgb,var(--success) 35%,var(--border))}.metric-attention{border-color:color-mix(in srgb,var(--danger) 35%,var(--border))}.section-heading{display:flex;align-items:end;justify-content:space-between;gap:18px;margin:42px 0 16px}.section-heading h2{margin:0;font-size:28px}.section-heading p{margin:4px 0 0;color:var(--muted)}
.evidence-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:14px}.evidence-card{display:flex;flex-direction:column;gap:16px;min-height:245px;border:1px solid var(--border);border-radius:var(--radius);background:var(--surface);padding:18px;transition:.18s}.evidence-card:hover{transform:translateY(-2px);box-shadow:var(--shadow)}.evidence-card.hidden{display:none}.evidence-card-top{display:flex;justify-content:space-between;gap:12px}.evidence-card h3{margin:5px 0 0;font-size:18px}.evidence-card p{color:var(--muted);font-size:16px}.evidence-card-actions{margin-top:auto;display:flex;justify-content:space-between;align-items:center;gap:12px}.evidence-card-actions code{max-width:52%;color:var(--muted);font-size:11px}
.card-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:14px}.panel,.artifact-card{border:1px solid var(--border);border-radius:var(--radius);background:var(--surface);padding:20px}.panel h3,.artifact-card h3{margin:6px 0}.panel table,.lineage-table{width:100%;border-collapse:collapse}.panel th,.panel td,.lineage-table th,.lineage-table td{padding:10px;border-bottom:1px solid var(--border);text-align:left;vertical-align:top}.panel th{width:42%;color:var(--muted)}.artifact-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:14px}.artifact-card{display:grid;gap:12px}.artifact-card p{color:var(--muted)}.artifact-card .button{justify-self:start}.empty-state{display:none;padding:40px;text-align:center;border:1px dashed var(--border);border-radius:var(--radius);color:var(--muted)}.empty-state.visible{display:block}
dialog{width:min(880px,calc(100vw - 36px));max-height:calc(100vh - 36px);padding:0;border:1px solid var(--border);border-radius:20px;background:var(--surface);color:var(--text);box-shadow:0 30px 100px rgba(0,0,0,.35)}dialog::backdrop{background:rgba(8,15,30,.65);backdrop-filter:blur(6px)}.dialog-header{position:sticky;top:0;z-index:4;display:flex;justify-content:space-between;padding:18px 20px;border-bottom:1px solid var(--border);background:var(--surface)}.dialog-header h2{margin:0}.dialog-body{padding:20px}.snapshot-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:10px}.snapshot{padding:14px;border:1px solid var(--border);border-radius:12px;background:var(--surface2)}.snapshot span{display:block;color:var(--muted);font-size:12px}.raw-panel{max-height:330px;overflow:auto;padding:14px;border-radius:12px;background:var(--surface2);white-space:pre-wrap}
.artifact-actions{display:flex;gap:8px;flex-wrap:wrap}.artifact-meta{color:var(--muted);font-family:var(--mono);font-size:12px}.artifact-frame{width:100%;height:min(68vh,720px);border:1px solid var(--border);border-radius:12px;background:#fff}.artifact-text{max-height:68vh;overflow:auto;padding:16px;border:1px solid var(--border);border-radius:12px;background:var(--surface2);white-space:pre-wrap;overflow-wrap:anywhere}
@media(max-width:1050px){.app{grid-template-columns:1fr}.sidebar{position:relative;height:auto;border-right:0;border-bottom:1px solid var(--border)}.metric-grid,.evidence-grid{grid-template-columns:repeat(2,minmax(0,1fr))}}@media(max-width:680px){.main{padding:20px}.metric-grid,.evidence-grid,.card-grid,.artifact-grid,.snapshot-grid{grid-template-columns:1fr}.hero{padding:24px}.topbar{align-items:stretch;flex-direction:column}}@media print{.sidebar,.topbar,.button,dialog{display:none!important}.app{display:block}.main{padding:0}.hero,.metric,.evidence-card,.panel,.artifact-card{box-shadow:none;break-inside:avoid}}
</style>
</head>
<body>
<div class="app">
<aside class="sidebar">
  <div class="brand"><div class="brand-mark">S</div><div><strong>SDET Quality Gate</strong><small>Live review product</small></div></div>
  <h4>Navigate</h4>
  <a class="nav-link" href="#overview">Overview <span>01</span></a>
  <a class="nav-link" href="#live-evidence">Indicators <span>02</span></a>
  <a class="nav-link" href="#lineage">Evidence lineage <span>03</span></a>
  <a class="nav-link" href="#artifacts">Artifacts <span>04</span></a>
  <a class="nav-link" href="#authority">Authority <span>05</span></a>
  <h4>Indicator status</h4>
  <div class="filter-stack">
    <button class="filter-chip active" data-status-filter="all">All <span>__FACT_COUNT__</span></button>
    <button class="filter-chip" data-status-filter="clear">Clear <span>__CLEAR_COUNT__</span></button>
    <button class="filter-chip" data-status-filter="attention">Attention <span>__ATTENTION_COUNT__</span></button>
    <button class="filter-chip" data-status-filter="unavailable">Unavailable <span>__UNAVAILABLE_COUNT__</span></button>
  </div>
  <div class="sidebar-footer">Per-run static artifact. Regenerated by the Quality Gate workflow for each exact PR head.</div>
</aside>
<main class="main">
  <div class="topbar">
    <input id="dashboardSearch" class="search" type="search" placeholder="Search indicators, values, and evidence paths">
    <div class="top-actions">
      <button id="themeButton" class="button" type="button">Toggle theme</button>
      <button id="printButton" class="button" type="button">Print report</button>
    </div>
  </div>
  <section id="overview" class="hero">
    <div class="hero-top">
      <div>
        <div class="eyebrow">SDET Quality Gate — Live Review Dashboard · __PR_LABEL__ · workflow-run evidence</div>
        <h1>PR Quality Artifact Center</h1>
        <p>This dashboard is generated from structured evidence for one exact pull-request head. Every indicator names its source artifact; no card is manually maintained status prose.</p>
      </div>
      <span class="status-badge __STATE_TONE__">__STATE_LABEL__</span>
    </div>
    <div class="hero-meta">
      <span class="pill">Head <code>__HEAD_SHORT__</code></span>
      <span class="pill">Run <code>__RUN_ID__</code></span>
      <span class="pill">Binding <code>__HEAD_BINDING__</code></span>
      <span class="pill">Generated <code>__GENERATED_AT__</code></span>
      <span class="pill">Entrypoint <code>__ENTRYPOINT__</code></span>
    </div>
    <div class="top-actions" style="margin-top:18px">__TOP_ACTIONS__</div>
  </section>
  <section class="metric-grid">__METRIC_CARDS__</section>
  <section id="live-evidence">
    <div class="section-heading"><div><h2>Observed indicators</h2><p>Searchable cards derived from the current workflow run.</p></div></div>
    <div id="indicatorGrid" class="evidence-grid">__FACT_CARDS__</div>
    <div id="emptyState" class="empty-state">No indicators match the current filter.</div>
  </section>
  <section id="lineage">
    <div class="section-heading"><div><h2>Evidence lineage</h2><p>How collected evidence becomes the published reviewer surface.</p></div></div>
    <div class="panel"><table class="lineage-table"><thead><tr><th>Stage</th><th>Source</th><th>Role</th></tr></thead><tbody>__LINEAGE_ROWS__</tbody></table></div>
  </section>
  <section id="decision">
    <div class="section-heading"><div><h2>Decision and authority</h2><p>Canonical decision fields remain separate from automation authority.</p></div></div>
    <div class="card-grid">
      <article class="panel"><h3>Decision observation</h3><table>__DECISION_TABLE__</table></article>
      <article id="authority" class="panel"><h3>Authority boundary</h3><table>__AUTHORITY_TABLE__</table><p><strong>Reporting-only.</strong> This dashboard does not authorize merge, patch code, or dismiss security findings.</p></article>
    </div>
  </section>
  <section id="artifacts">
    <div class="section-heading"><div><h2>Product artifacts</h2><p>Open the exact files emitted in this run-bound bundle.</p></div></div>
    <div class="artifact-grid">__ARTIFACT_CARDS__</div>
  </section>
</main>
</div>
<dialog id="evidenceDialog">
  <div class="dialog-header"><div><div id="dialogSource" class="eyebrow"></div><h2 id="dialogTitle">Evidence detail</h2></div><button class="button" data-close-dialog type="button">Close</button></div>
  <div class="dialog-body">
    <div class="snapshot-grid">
      <div class="snapshot"><span>Status</span><strong id="dialogStatus"></strong></div>
      <div class="snapshot"><span>Indicator ID</span><strong id="dialogId"></strong></div>
    </div>
    <h3>Observed value</h3><p id="dialogValue"></p>
    <h3>Evidence source</h3><code id="dialogPath"></code>
    <h3>Raw fact</h3><pre id="dialogRaw" class="raw-panel"></pre>
    <button id="copyFact" class="button" type="button">Copy raw fact</button>
  </div>
</dialog>
<dialog id="artifactDialog">
  <div class="dialog-header"><div><div id="artifactDialogPath" class="eyebrow"></div><h2 id="artifactDialogTitle">Artifact viewer</h2></div><button class="button" data-close-artifact-dialog type="button">Close</button></div>
  <div class="dialog-body">
    <p id="artifactDialogMeta" class="artifact-meta"></p>
    <div class="artifact-actions" style="margin-bottom:14px">
      <button id="openArtifactTab" class="button primary" type="button">Open in new tab</button>
      <button id="downloadArtifact" class="button" type="button">Download file</button>
    </div>
    <iframe id="artifactFrame" class="artifact-frame" title="Embedded artifact viewer" sandbox="allow-scripts"></iframe>
    <pre id="artifactText" class="artifact-text" hidden></pre>
  </div>
</dialog>
<script type="application/json" id="evidenceData">__FACT_PAYLOAD__</script>
<script>
const payload=JSON.parse(document.getElementById("evidenceData").textContent);
const facts=payload.facts||[];
const byId=Object.fromEntries(facts.map(item=>[item.id,item]));
const embeddedArtifacts=payload.embedded_artifacts||{};
let statusFilter="all";
let currentArtifactPath="";
const dialog=document.getElementById("evidenceDialog");
const artifactDialog=document.getElementById("artifactDialog");
function applyFilters(){
  const query=document.getElementById("dashboardSearch").value.trim().toLowerCase();
  let visible=0;
  document.querySelectorAll(".evidence-card").forEach(card=>{
    const show=(statusFilter==="all"||card.dataset.status===statusFilter)&&(!query||card.dataset.search.includes(query));
    card.classList.toggle("hidden",!show);
    if(show) visible++;
  });
  document.getElementById("emptyState").classList.toggle("visible",visible===0);
}
function openEvidence(id){
  const item=byId[id];
  if(!item) return;
  document.getElementById("dialogSource").textContent=item.source_path||"unknown source";
  document.getElementById("dialogTitle").textContent=item.label||"Evidence detail";
  document.getElementById("dialogStatus").textContent=item.status||"unknown";
  document.getElementById("dialogId").textContent=item.id||"unknown";
  document.getElementById("dialogValue").textContent=item.value||"not collected";
  document.getElementById("dialogPath").textContent=item.source_path||"unknown";
  document.getElementById("dialogRaw").textContent=JSON.stringify(item,null,2);
  dialog.dataset.current=id;
  dialog.showModal();
}
function decodeArtifact(item){
  const binary=atob(item.content_base64||"");
  const bytes=Uint8Array.from(binary,char=>char.charCodeAt(0));
  return new TextDecoder("utf-8").decode(bytes);
}
function artifactBlob(path){
  const item=embeddedArtifacts[path];
  if(!item) return null;
  return new Blob([decodeArtifact(item)],{type:item.mime_type||"text/plain;charset=utf-8"});
}
function openArtifact(path){
  const item=embeddedArtifacts[path];
  if(!item) return;
  const content=decodeArtifact(item);
  const mime=item.mime_type||"text/plain;charset=utf-8";
  currentArtifactPath=path;
  document.getElementById("artifactDialogPath").textContent=path;
  document.getElementById("artifactDialogTitle").textContent="Artifact viewer";
  document.getElementById("artifactDialogMeta").textContent=`${mime} · ${item.size_bytes||0} bytes · sha256:${item.sha256||"not collected"}`;
  const frame=document.getElementById("artifactFrame");
  const text=document.getElementById("artifactText");
  if(mime.startsWith("text/html")){
    text.hidden=true;
    frame.hidden=false;
    frame.srcdoc=content;
  }else{
    frame.hidden=true;
    frame.removeAttribute("srcdoc");
    text.hidden=false;
    text.textContent=content;
  }
  artifactDialog.showModal();
}
function downloadArtifact(path){
  const blob=artifactBlob(path);
  if(!blob) return;
  const url=URL.createObjectURL(blob);
  const anchor=document.createElement("a");
  anchor.href=url;
  anchor.download=path.split("/").pop()||"artifact.txt";
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  setTimeout(()=>URL.revokeObjectURL(url),1000);
}
function openArtifactInNewTab(path){
  const blob=artifactBlob(path);
  if(!blob) return;
  const url=URL.createObjectURL(blob);
  const anchor=document.createElement("a");
  anchor.href=url;
  anchor.target="_blank";
  anchor.rel="noopener";
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  setTimeout(()=>URL.revokeObjectURL(url),60000);
}
document.querySelectorAll("[data-open-evidence]").forEach(button=>button.onclick=()=>openEvidence(button.dataset.openEvidence));
document.querySelectorAll("[data-open-artifact]").forEach(button=>button.onclick=()=>openArtifact(button.dataset.openArtifact));
document.querySelectorAll("[data-download-artifact]").forEach(button=>button.onclick=()=>downloadArtifact(button.dataset.downloadArtifact));
document.querySelectorAll("[data-status-filter]").forEach(button=>button.onclick=()=>{
  statusFilter=button.dataset.statusFilter;
  document.querySelectorAll("[data-status-filter]").forEach(item=>item.classList.toggle("active",item===button));
  applyFilters();
});
document.getElementById("dashboardSearch").oninput=applyFilters;
document.querySelector("[data-close-dialog]").onclick=()=>dialog.close();
document.querySelector("[data-close-artifact-dialog]").onclick=()=>artifactDialog.close();
document.getElementById("openArtifactTab").onclick=()=>openArtifactInNewTab(currentArtifactPath);
document.getElementById("downloadArtifact").onclick=()=>downloadArtifact(currentArtifactPath);
document.getElementById("themeButton").onclick=()=>{
  const root=document.documentElement;
  root.dataset.theme=root.dataset.theme==="dark"?"light":"dark";
  localStorage.setItem("sdet-live-theme",root.dataset.theme);
};
document.getElementById("printButton").onclick=()=>print();
document.getElementById("copyFact").onclick=async()=>{
  const item=byId[dialog.dataset.current];
  if(!item) return;
  await navigator.clipboard.writeText(JSON.stringify(item,null,2));
};
const savedTheme=localStorage.getItem("sdet-live-theme");
if(savedTheme) document.documentElement.dataset.theme=savedTheme;
</script>
</body>
</html>"""

    replacements = {
        "__PAGE_TITLE__": "PR Quality Artifact Center",
        "__PR_LABEL__": safe(pr_label),
        "__STATE_TONE__": safe(state_tone),
        "__STATE_LABEL__": safe(state_label),
        "__HEAD_SHORT__": safe(head_short),
        "__RUN_ID__": safe(run_id),
        "__HEAD_BINDING__": safe(provenance.get("head_binding_status")),
        "__GENERATED_AT__": safe(generated_at),
        "__ENTRYPOINT__": safe(artifact_entrypoint),
        "__TOP_ACTIONS__": top_actions,
        "__METRIC_CARDS__": metric_cards,
        "__FACT_CARDS__": fact_cards,
        "__FACT_COUNT__": str(len(facts)),
        "__CLEAR_COUNT__": str(status_counts["clear"]),
        "__ATTENTION_COUNT__": str(status_counts["attention"]),
        "__UNAVAILABLE_COUNT__": str(status_counts["unavailable"]),
        "__LINEAGE_ROWS__": lineage_rows,
        "__DECISION_TABLE__": decision_table,
        "__AUTHORITY_TABLE__": authority_table,
        "__ARTIFACT_CARDS__": artifact_cards,
        "__FACT_PAYLOAD__": payload,
    }
    for marker, value in replacements.items():
        template = template.replace(marker, value)
    return template
