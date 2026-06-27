from __future__ import annotations

import json
from base64 import b64encode
from hashlib import sha256
from html import escape
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


def _safe(value: object) -> str:
    return escape(_text(value), quote=True)


def _external_link(
    url: str,
    label: str,
    css_class: str = "button",
) -> str:
    if not url:
        return ""
    return (
        f'<a class="{_safe(css_class)}" href="{_safe(url)}" '
        f'target="_blank" rel="noreferrer">{_safe(label)}</a>'
    )


def _status_label(status: str) -> str:
    return {
        "clear": "Clear",
        "attention": "Needs attention",
        "unavailable": "Unavailable",
    }.get(status, status.replace("_", " ").title() or "Unknown")


def _state_label(state: str) -> str:
    return {
        "ready": "Ready for human review",
        "waiting": "Waiting for CI",
        "blocked": "Blocked",
        "review": "Human review required",
        "stale": "Stale evidence",
        "invalid": "Invalid evidence",
    }.get(state, state.replace("_", " ").title() or "Unknown")


def render_pr_quality_review_experience(
    model: JsonObject,
    *,
    embedded_artifacts: JsonObject | None = None,
) -> str:
    snapshot = _as_dict(model.get("live_evidence"))
    if not snapshot:
        return ""

    provenance = _as_dict(snapshot.get("provenance"))
    decision = _as_dict(model.get("decision"))
    primary_failure = _as_dict(model.get("primary_failure"))
    authority = _as_dict(snapshot.get("authority_boundary") or model.get("authority_boundary"))
    facts = [_as_dict(item) for item in _as_list(snapshot.get("facts")) if _as_dict(item)]
    lineage = [_as_dict(item) for item in _as_list(snapshot.get("lineage")) if _as_dict(item)]
    artifact_index = [
        _as_dict(item)
        for item in _as_list(model.get("artifact_index"))
        if _as_dict(item) and _text(_as_dict(item).get("path"))
    ]
    facts_by_id = {_text(item.get("id")): item for item in facts if _text(item.get("id"))}

    embedded_payload: JsonObject = {}
    for path, raw_item in (embedded_artifacts or {}).items():
        artifact_path = _text(path)
        item = _as_dict(raw_item)
        content = item.get("content")
        if not artifact_path or not isinstance(content, str):
            continue
        encoded = content.encode("utf-8")
        embedded_payload[artifact_path] = {
            "mime_type": _text(
                item.get("mime_type"),
                "text/plain;charset=utf-8",
            ),
            "content_base64": b64encode(encoded).decode("ascii"),
            "size_bytes": len(encoded),
            "sha256": sha256(encoded).hexdigest(),
        }

    review_state = _text(decision.get("review_state"), "unknown")
    state_label = _state_label(review_state)
    state_tone = {
        "ready": "clear",
        "waiting": "waiting",
        "blocked": "attention",
        "review": "review",
        "stale": "warning",
        "invalid": "attention",
    }.get(review_state, "neutral")

    metric_specs = (
        ("Required checks", "required_checks"),
        ("Security", "security"),
        ("Runtime proof", "runtime_proof"),
        ("Artifact integrity", "artifact_inventory"),
    )
    metric_cards: list[str] = []
    for title, fact_id in metric_specs:
        fact = facts_by_id.get(fact_id, {})
        status = _text(fact.get("status"), "unavailable")
        value = _text(fact.get("value"), "not collected")
        if (
            fact_id == "required_checks"
            and review_state == "blocked"
            and bool(primary_failure.get("available"))
        ):
            unique_count = max(
                _integer(primary_failure.get("unique_failure_count")),
                1,
            )
            failed_count = max(
                _integer(primary_failure.get("failed_check_count")),
                unique_count,
            )
            value = (
                f"{unique_count} unique failure"
                + ("" if unique_count == 1 else "s")
                + f" repeated across {failed_count} checks"
            )
        metric_cards.append(
            "".join(
                (
                    f'<article class="health-card health-{_safe(status)}">',
                    '<div class="health-top">',
                    f"<span>{_safe(title)}</span>",
                    f'<strong class="health-status">{_safe(_status_label(status))}</strong>',
                    "</div>",
                    f"<p>{_safe(value)}</p>",
                    "</article>",
                )
            )
        )

    risk_surface = _text(decision.get("risk_surface"), "not collected")
    next_action = _text(decision.get("next_action"), "review_and_decide")
    merge_assessment = _text(
        decision.get("merge_assessment"),
        "human_decision_required",
    )

    timeline_items = "\n".join(
        "".join(
            (
                '<li class="timeline-item">',
                '<span class="timeline-dot"></span>',
                "<div>",
                f"<strong>{_safe(item.get('stage'))}</strong>",
                f"<p>{_safe(item.get('description'))}</p>",
                f"<code>{_safe(item.get('source_path'))}</code>",
                "</div>",
                "</li>",
            )
        )
        for item in lineage
    )
    if not timeline_items:
        timeline_items = (
            '<li class="timeline-item"><span class="timeline-dot"></span>'
            "<div><strong>No lineage emitted</strong>"
            "<p>This run did not publish evidence-lineage records.</p></div></li>"
        )

    facts_rows = "\n".join(
        "".join(
            (
                f'<tr data-evidence-search="{_safe(" ".join((_text(item.get("label")), _text(item.get("value")), _text(item.get("source_path")))).lower())}">',
                f"<td><strong>{_safe(item.get('label'))}</strong></td>",
                f'<td><span class="status-chip {_safe(item.get("status"))}">{_safe(_status_label(_text(item.get("status"))))}</span></td>',
                f"<td>{_safe(item.get('value'))}</td>",
                f"<td><code>{_safe(item.get('source_path'))}</code></td>",
                "</tr>",
            )
        )
        for item in facts
    )

    artifacts_url = _text(provenance.get("artifacts_url"))
    artifact_rows: list[str] = []
    for item in artifact_index:
        artifact_path = _text(item.get("path"))
        artifact_kind = _text(
            item.get("kind") or item.get("format"),
            "artifact",
        )
        title = _text(item.get("title"), artifact_path)
        description = _text(
            item.get("description") or item.get("surface"),
            "Workflow artifact",
        )
        embedded = _as_dict(embedded_payload.get(artifact_path))
        size = _integer(embedded.get("size_bytes"))
        digest = _text(embedded.get("sha256"))
        digest_short = digest[:12] if digest else "external"
        size_text = f"{size / 1024:.1f} KiB" if size >= 1024 else f"{size} B" if size else "bundle"

        if artifact_kind == "github_artifact":
            action = (
                _external_link(
                    artifacts_url,
                    "Download full bundle",
                    "button",
                )
                if artifacts_url
                else '<span class="button disabled">Artifact unavailable</span>'
            )
        elif artifact_path == "index.html":
            action = '<a class="button" href="#overview">Current dashboard</a>'
        elif embedded:
            action = "".join(
                (
                    '<div class="artifact-actions">',
                    f'<button class="button primary" type="button" data-open-artifact="{_safe(artifact_path)}">Open</button>',
                    f'<button class="button" type="button" data-download-artifact="{_safe(artifact_path)}">Download</button>',
                    "</div>",
                )
            )
        elif artifacts_url:
            action = _external_link(
                artifacts_url,
                "Download full bundle",
                "button",
            )
        else:
            action = '<span class="button disabled">Not embedded</span>'

        artifact_rows.append(
            "".join(
                (
                    f'<article class="artifact-row" data-artifact-search="{_safe(" ".join((title, artifact_path, artifact_kind, description)).lower())}">',
                    '<div class="artifact-icon">',
                    _safe(artifact_kind[:1].upper()),
                    "</div>",
                    '<div class="artifact-main">',
                    '<div class="artifact-title-line">',
                    f"<h3>{_safe(title)}</h3>",
                    f'<span class="format-chip">{_safe(artifact_kind)}</span>',
                    "</div>",
                    f"<p>{_safe(description)}</p>",
                    f"<code>{_safe(artifact_path)}</code>",
                    "</div>",
                    '<div class="artifact-trust">',
                    '<span class="trust-label">Integrity</span>',
                    f"<strong>{'Verified' if embedded else 'External'}</strong>",
                    f"<small>{_safe(size_text)} · {_safe(digest_short)}</small>",
                    "</div>",
                    action,
                    "</article>",
                )
            )
        )

    pr_number = _integer(provenance.get("pr_number"))
    head_sha = _text(provenance.get("head_sha"))
    head_short = head_sha[:12] if head_sha else "not collected"
    run_id = _text(provenance.get("workflow_run_id"), "not collected")
    generated_at = _text(
        snapshot.get("generated_at_utc"),
        "not collected",
    )
    artifact_entrypoint = _text(
        provenance.get("artifact_entrypoint"),
        "pr-quality/index.html",
    )

    top_actions = " ".join(
        item
        for item in (
            _external_link(
                _text(provenance.get("pr_url")),
                "Open pull request",
            ),
            _external_link(
                _text(provenance.get("workflow_run_url")),
                f"Workflow run {run_id}",
            ),
            _external_link(
                artifacts_url,
                "Open Artifact Center",
                "button primary",
            ),
        )
        if item
    )

    failure_first = ""
    if review_state == "blocked" and bool(primary_failure.get("available")):
        unique_count = max(
            _integer(primary_failure.get("unique_failure_count")),
            1,
        )
        failed_count = max(
            _integer(primary_failure.get("failed_check_count")),
            unique_count,
        )
        repeated = (
            f"{unique_count} unique failure"
            + ("" if unique_count == 1 else "s")
            + f" repeated across {failed_count} checks"
        )
        source_path = _text(primary_failure.get("source_path"))
        source_line = _integer(primary_failure.get("source_line"))
        source_location = (
            f"{source_path}:{source_line}"
            if source_path and source_line
            else source_path or "Not captured"
        )
        step_name = _text(primary_failure.get("step_name"))
        step_display = step_name or "Not captured — collector evidence gap"
        command = _text(primary_failure.get("reproduction_command"))
        check_name = _text(
            primary_failure.get("check_name"),
            "Not captured",
        )
        check_url = _text(primary_failure.get("check_url"))
        check_display = (
            _external_link(check_url, check_name, "text-link")
            if check_url
            else f"<code>{_safe(check_name)}</code>"
        )
        gaps = ", ".join(
            _text(item) for item in _as_list(primary_failure.get("evidence_gaps")) if _text(item)
        )
        gap_html = (
            f'<p class="evidence-gap"><strong>Evidence gap:</strong> {_safe(gaps)}</p>'
            if gaps
            else ""
        )
        command_html = (
            "".join(
                (
                    '<div class="repro-box">',
                    f"<code>{_safe(command)}</code>",
                    f'<button class="button" type="button" data-copy-text="{_safe(command)}">Copy command</button>',
                    "</div>",
                )
            )
            if command
            else '<p class="evidence-gap">Reproduction command was not captured.</p>'
        )
        failure_first = "".join(
            (
                '<section class="section failure-first" id="failure-first">',
                '<div class="section-heading"><div><div class="eyebrow">First actionable failure</div>',
                f"<h2>{_safe(repeated)}</h2></div>",
                "<p>One root cause is collapsed across repeated matrix executions.</p></div>",
                '<div class="failure-layout"><article class="failure-card">',
                '<dl class="failure-fields">',
                f"<div><dt>Check</dt><dd>{check_display}</dd></div>",
                f"<div><dt>Test</dt><dd><code>{_safe(primary_failure.get('test_node'))}</code></dd></div>",
                f"<div><dt>Source</dt><dd><code>{_safe(source_location)}</code></dd></div>",
                f"<div><dt>Step</dt><dd>{_safe(step_display)}</dd></div>",
                f"<div><dt>Expected</dt><dd><code>{_safe(primary_failure.get('expected'))}</code></dd></div>",
                f"<div><dt>Observed</dt><dd><code>{_safe(primary_failure.get('observed'))}</code></dd></div>",
                "</dl>",
                "<h3>Failure</h3>",
                f'<pre class="failure-message">{_safe(primary_failure.get("message"))}</pre>',
                "<h3>Reproduce</h3>",
                command_html,
                gap_html,
                "</article></div></section>",
            )
        )

    contract_payload = {
        "review": {
            "state": review_state,
            "primary_failure": primary_failure,
            "head": head_sha,
            "head_binding": _text(
                provenance.get("head_binding_status"),
                "not collected",
            ),
            "risk_surface": risk_surface,
            "next_action": next_action,
        },
        "quality": {
            fact_id: {
                "status": _text(
                    facts_by_id.get(fact_id, {}).get("status"),
                    "unavailable",
                ),
                "value": _text(
                    facts_by_id.get(fact_id, {}).get("value"),
                    "not collected",
                ),
            }
            for fact_id in (
                "required_checks",
                "security",
                "runtime_proof",
                "artifact_inventory",
            )
        },
        "authority": {
            "mode": _text(
                authority.get("boundary_mode"),
                "reporting_only",
            ),
            "merge_authorized": bool(authority.get("merge_authorization", False)),
            "patch_automation": bool(authority.get("patch_automation", False)),
            "security_dismissal": bool(authority.get("security_dismissal", False)),
        },
    }

    payload = json.dumps(
        {
            "snapshot": snapshot,
            "decision": decision,
            "primary_failure": primary_failure,
            "facts": facts,
            "contract": contract_payload,
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
<title>PR Quality Artifact Center</title>
<style>
:root{color-scheme:light;--bg:#f5f7fb;--surface:#fff;--surface-soft:#f8fafc;--surface-strong:#eef2f7;--text:#152033;--muted:#66758a;--border:#d9e1ec;--accent:#315efb;--accent-2:#6d45e8;--clear:#14804a;--clear-bg:#e9f8ef;--attention:#b54708;--attention-bg:#fff2e0;--waiting:#0969da;--waiting-bg:#e5f1ff;--review:#7047eb;--review-bg:#f1ebff;--shadow:0 18px 55px rgba(27,42,78,.09);--radius:22px;--mono:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace}
html[data-theme="dark"]{color-scheme:dark;--bg:#090f1c;--surface:#111a2a;--surface-soft:#152033;--surface-strong:#1d2a40;--text:#edf3fb;--muted:#9aabc0;--border:#2b3950;--accent:#7fa1ff;--accent-2:#b49aff;--clear:#6bdd9b;--clear-bg:#123724;--attention:#ffbd70;--attention-bg:#40280f;--waiting:#82bdff;--waiting-bg:#133456;--review:#c4afff;--review-bg:#30234d;--shadow:0 22px 70px rgba(0,0,0,.34)}
*{box-sizing:border-box}html{scroll-behavior:smooth}body{margin:0;background:radial-gradient(circle at 78% -8%,rgba(49,94,251,.13),transparent 34rem),var(--bg);color:var(--text);font:15px/1.6 Inter,ui-sans-serif,system-ui,-apple-system,Segoe UI,sans-serif}button,input{font:inherit}button{cursor:pointer}a{color:var(--accent)}code,pre{font-family:var(--mono)}code{overflow-wrap:anywhere}.shell{width:min(1380px,calc(100% - 40px));margin:0 auto;padding:22px 0 88px}.topbar{display:flex;align-items:center;justify-content:space-between;gap:18px;padding:12px 4px 24px}.brand{display:flex;align-items:center;gap:12px}.brand-mark{width:44px;height:44px;display:grid;place-items:center;border-radius:14px;color:#fff;font-weight:900;background:linear-gradient(135deg,var(--accent),var(--accent-2));box-shadow:0 12px 30px rgba(49,94,251,.25)}.brand strong,.brand small{display:block}.brand small{color:var(--muted)}.top-actions,.artifact-actions,.dialog-actions,.view-tabs{display:flex;gap:8px;flex-wrap:wrap}.button{display:inline-flex;align-items:center;justify-content:center;min-height:40px;padding:9px 13px;border:1px solid var(--border);border-radius:12px;background:var(--surface);color:var(--text);font-weight:700;text-decoration:none}.button:hover{border-color:var(--accent)}.button.primary{color:#fff;border-color:transparent;background:linear-gradient(135deg,var(--accent),var(--accent-2))}.button.disabled{cursor:not-allowed;color:var(--muted);background:var(--surface-soft)}.hero{padding:46px;border:1px solid var(--border);border-radius:30px;background:linear-gradient(145deg,var(--surface),var(--surface-soft));box-shadow:var(--shadow)}.hero-grid{display:grid;grid-template-columns:minmax(0,1.4fr) minmax(310px,.6fr);gap:38px;align-items:start}.eyebrow{color:var(--accent);font-family:var(--mono);font-size:12px;font-weight:800;letter-spacing:.1em;text-transform:uppercase}.hero h1{margin:12px 0 14px;font-size:clamp(38px,5.8vw,72px);line-height:1.02;letter-spacing:-.055em}.hero p{max-width:780px;margin:0;color:var(--muted);font-size:18px}.verdict{padding:24px;border:1px solid var(--border);border-radius:22px;background:var(--surface)}.verdict-label{display:inline-flex;padding:7px 11px;border-radius:999px;font-weight:850}.verdict-label.clear{color:var(--clear);background:var(--clear-bg)}.verdict-label.attention{color:var(--attention);background:var(--attention-bg)}.verdict-label.waiting{color:var(--waiting);background:var(--waiting-bg)}.verdict-label.review{color:var(--review);background:var(--review-bg)}.verdict h2{margin:18px 0 8px;font-size:24px}.verdict p{font-size:14px}.meta-strip{display:flex;gap:8px;flex-wrap:wrap;margin-top:25px}.meta-pill{padding:8px 11px;border:1px solid var(--border);border-radius:999px;background:var(--surface);font-size:12px}.health-grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:16px;margin:30px 0 52px}.health-card{min-height:170px;padding:23px;border:1px solid var(--border);border-radius:var(--radius);background:var(--surface)}.health-card p{margin:24px 0 0;color:var(--muted)}.health-top{display:flex;align-items:flex-start;justify-content:space-between;gap:14px}.health-top>span{font-weight:800}.health-status{font-size:12px}.health-clear{border-top:4px solid var(--clear)}.health-attention{border-top:4px solid var(--attention)}.health-unavailable{border-top:4px solid var(--muted)}.section{margin-top:58px}.section-heading{display:flex;align-items:end;justify-content:space-between;gap:20px;margin-bottom:20px}.section-heading h2{margin:5px 0 0;font-size:32px;letter-spacing:-.025em}.section-heading p{margin:0;color:var(--muted)}.review-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:18px}.review-panel{padding:28px;border:1px solid var(--border);border-radius:var(--radius);background:var(--surface)}.review-panel span{color:var(--muted);font-size:12px;font-weight:800;letter-spacing:.08em;text-transform:uppercase}.review-panel h3{margin:10px 0 8px;font-size:24px}.review-panel p{margin:0;color:var(--muted)}.failure-first{margin-top:30px}.failure-layout{display:grid;gap:18px}.failure-card{padding:28px;border:2px solid var(--attention);border-radius:var(--radius);background:var(--surface);box-shadow:var(--shadow)}.failure-fields{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px;margin:0 0 24px}.failure-fields div{padding:14px;border:1px solid var(--border);border-radius:14px;background:var(--surface-soft)}.failure-fields dt{color:var(--muted);font-size:12px;font-weight:800;text-transform:uppercase}.failure-fields dd{margin:5px 0 0}.failure-message{padding:18px;border-radius:14px;background:#2a120d;color:#ffd9c7;white-space:pre-wrap;overflow-wrap:anywhere}.repro-box{display:flex;align-items:center;justify-content:space-between;gap:14px;padding:16px;border:1px solid var(--border);border-radius:14px;background:var(--surface-soft)}.repro-box code{min-width:0;overflow-wrap:anywhere}.evidence-gap{margin:14px 0 0;color:var(--attention)}.text-link{font-weight:800}.timeline{position:relative;display:grid;grid-template-columns:repeat(auto-fit,minmax(190px,1fr));gap:18px;padding:0;list-style:none}.timeline:before{content:"";position:absolute;left:20px;right:20px;top:14px;height:2px;background:var(--border)}.timeline-item{position:relative;padding:42px 18px 20px;border:1px solid var(--border);border-radius:18px;background:var(--surface)}.timeline-dot{position:absolute;top:6px;left:18px;width:18px;height:18px;border:5px solid var(--surface);border-radius:50%;background:var(--accent);box-shadow:0 0 0 2px var(--accent)}.timeline-item p{color:var(--muted)}.timeline-item code{font-size:11px}.artifact-toolbar{display:flex;align-items:center;justify-content:space-between;gap:14px;margin-bottom:16px}.search{width:min(520px,100%);padding:12px 14px;border:1px solid var(--border);border-radius:13px;background:var(--surface);color:var(--text);outline:none}.search:focus{border-color:var(--accent);box-shadow:0 0 0 3px color-mix(in srgb,var(--accent) 18%,transparent)}.artifact-list{display:grid;gap:12px}.artifact-row{display:grid;grid-template-columns:52px minmax(0,1fr) 170px auto;align-items:center;gap:18px;padding:19px;border:1px solid var(--border);border-radius:18px;background:var(--surface)}.artifact-row.hidden{display:none}.artifact-icon{width:48px;height:48px;display:grid;place-items:center;border-radius:14px;background:var(--surface-strong);color:var(--accent);font-size:18px;font-weight:900}.artifact-main h3{margin:0}.artifact-main p{margin:4px 0;color:var(--muted)}.artifact-title-line{display:flex;align-items:center;gap:8px;flex-wrap:wrap}.format-chip,.status-chip{display:inline-flex;padding:4px 8px;border-radius:999px;background:var(--surface-strong);font-size:11px;font-weight:800;text-transform:uppercase}.artifact-trust span,.artifact-trust small{display:block;color:var(--muted)}.artifact-trust strong{display:block}.artifact-trust small{font-family:var(--mono);font-size:10px}.details-stack{display:grid;gap:12px}.details-card{border:1px solid var(--border);border-radius:18px;background:var(--surface);overflow:hidden}.details-card summary{cursor:pointer;padding:19px 22px;font-size:17px;font-weight:800}.details-body{padding:0 22px 22px}.evidence-table{width:100%;border-collapse:collapse}.evidence-table th,.evidence-table td{padding:12px;border-bottom:1px solid var(--border);text-align:left;vertical-align:top}.evidence-table th{color:var(--muted)}.status-chip.clear{color:var(--clear);background:var(--clear-bg)}.status-chip.attention{color:var(--attention);background:var(--attention-bg)}.status-chip.unavailable{color:var(--muted)}.contract-grid{display:grid;grid-template-columns:minmax(0,1fr) 260px;gap:18px}.yaml-panel{max-height:520px;overflow:auto;padding:20px;border-radius:16px;background:#0d1727;color:#d9e7ff;white-space:pre-wrap}.authority-list{display:grid;gap:10px}.authority-item{padding:13px;border:1px solid var(--border);border-radius:13px;background:var(--surface-soft)}.authority-item span{display:block;color:var(--muted);font-size:12px}.footer-boundary{margin-top:58px;padding:24px;border:1px solid var(--border);border-radius:20px;background:var(--surface);color:var(--muted)}dialog{width:min(1080px,calc(100vw - 34px));max-height:calc(100vh - 34px);padding:0;border:1px solid var(--border);border-radius:22px;background:var(--surface);color:var(--text);box-shadow:0 34px 110px rgba(0,0,0,.38)}dialog.fullscreen{width:calc(100vw - 20px);height:calc(100vh - 20px);max-height:none}dialog::backdrop{background:rgba(5,10,20,.68);backdrop-filter:blur(6px)}.dialog-header{position:sticky;top:0;z-index:5;display:flex;align-items:flex-start;justify-content:space-between;gap:16px;padding:18px 20px;border-bottom:1px solid var(--border);background:var(--surface)}.dialog-header h2{margin:3px 0 0}.dialog-body{padding:20px}.dialog-meta{display:flex;gap:9px;flex-wrap:wrap;margin-bottom:14px}.artifact-frame{width:100%;height:min(64vh,760px);border:1px solid var(--border);border-radius:14px;background:#fff}.artifact-text{max-height:64vh;overflow:auto;padding:18px;border:1px solid var(--border);border-radius:14px;background:var(--surface-soft);white-space:pre-wrap;overflow-wrap:anywhere}.view-tab.active{border-color:var(--accent);color:var(--accent)}@media(max-width:980px){.hero-grid,.contract-grid{grid-template-columns:1fr}.health-grid{grid-template-columns:repeat(2,minmax(0,1fr))}.artifact-row{grid-template-columns:48px minmax(0,1fr);}.artifact-trust,.artifact-row>.artifact-actions,.artifact-row>.button{grid-column:2}.timeline:before{display:none}}@media(max-width:620px){.shell{width:min(100% - 24px,1380px)}.hero{padding:28px}.health-grid,.review-grid{grid-template-columns:1fr}.section-heading,.artifact-toolbar,.topbar{align-items:stretch;flex-direction:column}.artifact-row{grid-template-columns:1fr}.artifact-icon,.artifact-trust,.artifact-row>.artifact-actions,.artifact-row>.button{grid-column:1}.hero h1{font-size:40px}}@media print{.topbar,.button,.artifact-toolbar,dialog{display:none!important}.shell{width:100%;padding:0}.hero,.health-card,.review-panel,.artifact-row,.details-card{box-shadow:none;break-inside:avoid}}
</style>
</head>
<body>
<div class="shell">
<header class="topbar">
  <div class="brand"><div class="brand-mark">S</div><div><strong>SDET Quality Gate</strong><small>Review Experience V2</small></div></div>
  <div class="top-actions"><button id="themeButton" class="button" type="button">Theme</button><button id="printButton" class="button" type="button">Print</button></div>
</header>
<main>
<span id="live-evidence" hidden></span>
<section id="overview" class="hero">
  <div class="hero-grid">
    <div>
      <div class="eyebrow">__PR_LABEL__ · exact-head workflow evidence</div>
      <h1>PR Quality Artifact Center</h1>
      <p>A focused review workspace for the current pull-request head. Start with the verdict, inspect the risk surface, then open evidence only when you need it.</p>
      <div class="meta-strip">
        <span class="meta-pill">Head <code>__HEAD_SHORT__</code></span>
        <span class="meta-pill">Run <code>__RUN_ID__</code></span>
        <span class="meta-pill">Binding <code>__HEAD_BINDING__</code></span>
        <span class="meta-pill">Generated <code>__GENERATED_AT__</code></span>
        <span class="meta-pill">Entrypoint <code>__ENTRYPOINT__</code></span>
      </div>
      <div class="top-actions" style="margin-top:24px">__TOP_ACTIONS__</div>
    </div>
    <aside class="verdict">
      <span class="verdict-label __STATE_TONE__">__STATE_LABEL__</span>
      <h2>Human decision remains required</h2>
      <p>Automated evidence is advisory. Review scope, risk and authority before merging.</p>
    </aside>
  </div>
</section>
__FAILURE_FIRST__
<section class="health-grid">__METRIC_CARDS__</section>
<section class="section" id="review-focus">
  <div class="section-heading"><div><div class="eyebrow">Reviewer focus</div><h2>What needs your attention</h2></div><p>Decision guidance without duplicating the raw evidence.</p></div>
  <div class="review-grid">
    <article class="review-panel"><span>Risk surface</span><h3>__RISK_SURFACE__</h3><p>Review the changed surface and its evidence before deciding.</p></article>
    <article class="review-panel"><span>Recommended action</span><h3>__NEXT_ACTION__</h3><p>Merge assessment: <code>__MERGE_ASSESSMENT__</code></p></article>
  </div>
</section>
<section class="section" id="lineage">
  <div class="section-heading"><div><div class="eyebrow">Evidence flow</div><h2>From collection to review</h2></div><p>Each stage remains bound to this exact PR head.</p></div>
  <ol class="timeline">__TIMELINE_ITEMS__</ol>
</section>
<section class="section" id="artifacts">
  <div class="section-heading"><div><div class="eyebrow">Artifact explorer</div><h2>Open only what you need</h2></div><p>JSON opens as YAML first, with raw JSON always available.</p></div>
  <div class="artifact-toolbar"><input id="artifactSearch" class="search" type="search" placeholder="Search artifacts by name, path or format"><span id="artifactCount"></span></div>
  <div id="artifactList" class="artifact-list">__ARTIFACT_ROWS__</div>
</section>
<section class="section" id="technical">
  <div class="section-heading"><div><div class="eyebrow">Technical depth</div><h2>Details stay collapsed</h2></div><p>Open these only when the high-level decision needs supporting evidence.</p></div>
  <div class="details-stack">
    <details class="details-card"><summary>Observed evidence facts</summary><div class="details-body"><table class="evidence-table"><thead><tr><th>Indicator</th><th>Status</th><th>Observed value</th><th>Source</th></tr></thead><tbody>__FACT_ROWS__</tbody></table></div></details>
    <details class="details-card"><summary>Machine decision contract — YAML view</summary><div class="details-body contract-grid"><pre id="contractYaml" class="yaml-panel"></pre><div class="authority-list">__AUTHORITY_ITEMS__<button id="copyContract" class="button" type="button">Copy YAML</button></div></div></details>
  </div>
</section>
<footer class="footer-boundary"><strong>Reporting-only authority.</strong> This review product does not authorize merge, patch automation, security dismissal or semantic-equivalence claims.</footer>
</main>
</div>
<dialog id="artifactDialog">
  <div class="dialog-header">
    <div><div id="artifactDialogPath" class="eyebrow"></div><h2 id="artifactDialogTitle">Artifact viewer</h2></div>
    <div class="dialog-actions"><button id="previousArtifact" class="button" type="button">Previous</button><button id="nextArtifact" class="button" type="button">Next</button><button id="fullscreenArtifact" class="button" type="button">Fullscreen</button><button class="button" data-close-artifact-dialog type="button">Close</button></div>
  </div>
  <div class="dialog-body">
    <div class="dialog-meta"><span id="artifactMime" class="meta-pill"></span><span id="artifactSize" class="meta-pill"></span><span id="artifactDigest" class="meta-pill"></span></div>
    <div class="view-tabs"><button class="button view-tab active" data-artifact-view="formatted" type="button">YAML / Preview</button><button class="button view-tab" data-artifact-view="raw" type="button">Raw source</button></div>
    <div class="dialog-actions" style="margin:14px 0"><button id="copyArtifact" class="button" type="button">Copy current view</button><button id="openArtifactTab" class="button" type="button">Open in new tab</button><button id="downloadArtifact" class="button primary" type="button">Download</button></div>
    <iframe id="artifactFrame" class="artifact-frame" title="Artifact preview" sandbox="allow-scripts"></iframe>
    <pre id="artifactText" class="artifact-text" hidden></pre>
  </div>
</dialog>
<script type="application/json" id="evidenceData">__PAYLOAD__</script>
<script>
const payload=JSON.parse(document.getElementById("evidenceData").textContent);
const embeddedArtifacts=payload.embedded_artifacts||{};
const artifactOrder=Object.keys(embeddedArtifacts);
let currentArtifactPath="";
let currentArtifactView="formatted";
let currentRenderedText="";
const artifactDialog=document.getElementById("artifactDialog");
function decodeArtifact(item){const binary=atob(item.content_base64||"");const bytes=Uint8Array.from(binary,char=>char.charCodeAt(0));return new TextDecoder("utf-8").decode(bytes)}
function yamlScalar(value){if(value===null)return"null";if(value===true)return"true";if(value===false)return"false";if(typeof value==="number")return String(value);const text=String(value);if(text===""||/[:#\-\n\r\t{}\[\],&*!|>'"%@`]/.test(text)||/^(true|false|null|~|[-+]?\d+(\.\d+)?)$/i.test(text))return JSON.stringify(text);return text}
function toYaml(value,depth=0){const pad="  ".repeat(depth);if(Array.isArray(value)){if(value.length===0)return"[]";return value.map(item=>{if(item&&typeof item==="object")return `${pad}-\n${toYaml(item,depth+1)}`;return `${pad}- ${yamlScalar(item)}`}).join("\n")}if(value&&typeof value==="object"){const entries=Object.entries(value);if(entries.length===0)return"{}";return entries.map(([key,item])=>{const safeKey=/^[A-Za-z_][A-Za-z0-9_-]*$/.test(key)?key:JSON.stringify(key);if(item&&typeof item==="object")return `${pad}${safeKey}:\n${toYaml(item,depth+1)}`;return `${pad}${safeKey}: ${yamlScalar(item)}`}).join("\n")}return `${pad}${yamlScalar(value)}`}
function escapeHtml(value){return String(value).replace(/[&<>"']/g,char=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[char]))}
function markdownDocument(source){const lines=source.split(/\r?\n/);let inCode=false;let html='<style>body{font:15px/1.65 system-ui;padding:28px;max-width:900px;margin:auto;color:#172033}pre,code{font-family:ui-monospace,monospace;background:#f1f5f9;border-radius:7px}pre{padding:14px;overflow:auto}code{padding:2px 5px}h1,h2,h3{line-height:1.2}blockquote{border-left:4px solid #315efb;padding-left:14px;color:#64748b}li{margin:5px 0}</style>';for(const raw of lines){const line=escapeHtml(raw);if(line.startsWith("```")){html+=inCode?"</code></pre>":"<pre><code>";inCode=!inCode;continue}if(inCode){html+=line+"\n";continue}if(/^### /.test(line))html+=`<h3>${line.slice(4)}</h3>`;else if(/^## /.test(line))html+=`<h2>${line.slice(3)}</h2>`;else if(/^# /.test(line))html+=`<h1>${line.slice(2)}</h1>`;else if(/^> /.test(line))html+=`<blockquote>${line.slice(2)}</blockquote>`;else if(/^[-*] /.test(line))html+=`<ul><li>${line.slice(2)}</li></ul>`;else if(line.trim()==="")html+="<br>";else html+=`<p>${line}</p>`}return html}
function artifactBlob(path){const item=embeddedArtifacts[path];if(!item)return null;return new Blob([decodeArtifact(item)],{type:item.mime_type||"text/plain;charset=utf-8"})}
function renderArtifactView(){const item=embeddedArtifacts[currentArtifactPath];if(!item)return;const content=decodeArtifact(item);const mime=item.mime_type||"text/plain;charset=utf-8";const frame=document.getElementById("artifactFrame");const text=document.getElementById("artifactText");if(currentArtifactView==="raw"){frame.hidden=true;frame.removeAttribute("srcdoc");text.hidden=false;text.textContent=content;currentRenderedText=content;return}if(mime.startsWith("application/json")){frame.hidden=true;frame.removeAttribute("srcdoc");text.hidden=false;try{currentRenderedText=toYaml(JSON.parse(content));text.textContent=currentRenderedText}catch{currentRenderedText=content;text.textContent=content}return}if(mime.startsWith("text/markdown")){text.hidden=true;frame.hidden=false;frame.srcdoc=markdownDocument(content);currentRenderedText=content;return}if(mime.startsWith("text/html")){text.hidden=true;frame.hidden=false;frame.srcdoc=content;currentRenderedText=content;return}frame.hidden=true;text.hidden=false;text.textContent=content;currentRenderedText=content}
function openArtifact(path){const item=embeddedArtifacts[path];if(!item)return;currentArtifactPath=path;currentArtifactView="formatted";document.getElementById("artifactDialogPath").textContent=path;document.getElementById("artifactDialogTitle").textContent=path.split("/").pop()||"Artifact viewer";document.getElementById("artifactMime").textContent=item.mime_type||"unknown";document.getElementById("artifactSize").textContent=`${item.size_bytes||0} bytes`;document.getElementById("artifactDigest").textContent=`sha256:${(item.sha256||"").slice(0,16)}`;document.querySelectorAll("[data-artifact-view]").forEach(button=>button.classList.toggle("active",button.dataset.artifactView==="formatted"));renderArtifactView();artifactDialog.showModal()}
function downloadArtifact(path){const blob=artifactBlob(path);if(!blob)return;const url=URL.createObjectURL(blob);const anchor=document.createElement("a");anchor.href=url;anchor.download=path.split("/").pop()||"artifact.txt";document.body.appendChild(anchor);anchor.click();anchor.remove();setTimeout(()=>URL.revokeObjectURL(url),1000)}
function openArtifactInNewTab(path){const blob=artifactBlob(path);if(!blob)return;const url=URL.createObjectURL(blob);const anchor=document.createElement("a");anchor.href=url;anchor.target="_blank";anchor.rel="noopener";document.body.appendChild(anchor);anchor.click();anchor.remove();setTimeout(()=>URL.revokeObjectURL(url),60000)}
function moveArtifact(offset){if(!artifactOrder.length)return;const index=Math.max(0,artifactOrder.indexOf(currentArtifactPath));const next=(index+offset+artifactOrder.length)%artifactOrder.length;openArtifact(artifactOrder[next])}
function filterArtifacts(){const query=document.getElementById("artifactSearch").value.trim().toLowerCase();let visible=0;document.querySelectorAll("[data-artifact-search]").forEach(row=>{const show=!query||row.dataset.artifactSearch.includes(query);row.classList.toggle("hidden",!show);if(show)visible++});document.getElementById("artifactCount").textContent=`${visible} artifact${visible===1?"":"s"}`}
document.querySelectorAll("[data-open-artifact]").forEach(button=>button.onclick=()=>openArtifact(button.dataset.openArtifact));
document.querySelectorAll("[data-download-artifact]").forEach(button=>button.onclick=()=>downloadArtifact(button.dataset.downloadArtifact));
document.querySelectorAll("[data-copy-text]").forEach(button=>button.onclick=async()=>navigator.clipboard.writeText(button.dataset.copyText||""));
document.querySelectorAll("[data-artifact-view]").forEach(button=>button.onclick=()=>{currentArtifactView=button.dataset.artifactView;document.querySelectorAll("[data-artifact-view]").forEach(item=>item.classList.toggle("active",item===button));renderArtifactView()});
document.querySelector("[data-close-artifact-dialog]").onclick=()=>artifactDialog.close();
document.getElementById("previousArtifact").onclick=()=>moveArtifact(-1);
document.getElementById("nextArtifact").onclick=()=>moveArtifact(1);
document.getElementById("fullscreenArtifact").onclick=()=>artifactDialog.classList.toggle("fullscreen");
document.getElementById("copyArtifact").onclick=async()=>navigator.clipboard.writeText(currentRenderedText);
document.getElementById("openArtifactTab").onclick=()=>openArtifactInNewTab(currentArtifactPath);
document.getElementById("downloadArtifact").onclick=()=>downloadArtifact(currentArtifactPath);
document.getElementById("artifactSearch").oninput=filterArtifacts;
document.getElementById("themeButton").onclick=()=>{const root=document.documentElement;root.dataset.theme=root.dataset.theme==="dark"?"light":"dark";localStorage.setItem("sdet-review-theme",root.dataset.theme)};
document.getElementById("printButton").onclick=()=>print();
const contractYaml=toYaml(payload.contract||{});
document.getElementById("contractYaml").textContent=contractYaml;
document.getElementById("copyContract").onclick=async()=>navigator.clipboard.writeText(contractYaml);
const savedTheme=localStorage.getItem("sdet-review-theme");if(savedTheme)document.documentElement.dataset.theme=savedTheme;
filterArtifacts();
</script>
</body>
</html>"""

    authority_items = "\n".join(
        "".join(
            (
                '<div class="authority-item">',
                f"<span>{_safe(label)}</span>",
                f"<strong>{_safe(value)}</strong>",
                "</div>",
            )
        )
        for label, value in (
            (
                "Boundary mode",
                _text(authority.get("boundary_mode"), "reporting_only"),
            ),
            (
                "Merge authorization",
                str(bool(authority.get("merge_authorization", False))).lower(),
            ),
            (
                "Patch automation",
                str(bool(authority.get("patch_automation", False))).lower(),
            ),
            (
                "Security dismissal",
                str(bool(authority.get("security_dismissal", False))).lower(),
            ),
        )
    )

    replacements = {
        "__PR_LABEL__": _safe(f"PR #{pr_number}" if pr_number else "Pull request"),
        "__HEAD_SHORT__": _safe(head_short),
        "__RUN_ID__": _safe(run_id),
        "__HEAD_BINDING__": _safe(provenance.get("head_binding_status")),
        "__GENERATED_AT__": _safe(generated_at),
        "__ENTRYPOINT__": _safe(artifact_entrypoint),
        "__TOP_ACTIONS__": top_actions,
        "__STATE_TONE__": _safe(state_tone),
        "__STATE_LABEL__": _safe(state_label),
        "__FAILURE_FIRST__": failure_first,
        "__METRIC_CARDS__": "\n".join(metric_cards),
        "__RISK_SURFACE__": _safe(risk_surface.replace("_", " ").title()),
        "__NEXT_ACTION__": _safe(next_action.replace("_", " ").title()),
        "__MERGE_ASSESSMENT__": _safe(merge_assessment),
        "__TIMELINE_ITEMS__": timeline_items,
        "__ARTIFACT_ROWS__": "\n".join(artifact_rows),
        "__FACT_ROWS__": facts_rows,
        "__AUTHORITY_ITEMS__": authority_items,
        "__PAYLOAD__": payload,
    }
    for marker, value in replacements.items():
        template = template.replace(marker, value)
    return template
