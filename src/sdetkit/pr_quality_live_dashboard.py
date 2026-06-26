from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime, timezone
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
