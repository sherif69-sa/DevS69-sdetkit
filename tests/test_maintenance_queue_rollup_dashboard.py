from __future__ import annotations

import json
from pathlib import Path

from sdetkit import maintenance_queue_rollup_dashboard


def _queue_item(
    *,
    issue_number: int,
    title: str,
    lane: str,
    rank_score: int,
    review_required: bool,
    close_candidate: bool,
) -> dict[str, object]:
    return {
        "issue_number": issue_number,
        "title": title,
        "lane": lane,
        "classification": ("security_followup" if lane == "security" else "generated_tracker"),
        "rank_score": rank_score,
        "review_required": review_required,
        "close_candidate": close_candidate,
        "security_disposition": ("needs review" if lane == "security" else ""),
        "automation_health_state": "",
        "recommended_action": (
            "Review the item manually." if review_required else "Keep as context."
        ),
        "automation_allowed": False,
        "merge_authorized": False,
        "semantic_equivalence_proven": False,
    }


def _rollup_payload(
    *,
    queue_items: list[dict[str, object]] | None = None,
) -> dict[str, object]:
    rows = (
        queue_items
        if queue_items is not None
        else [
            _queue_item(
                issue_number=1502,
                title="Review current security warnings",
                lane="security",
                rank_score=700,
                review_required=True,
                close_candidate=False,
            ),
            _queue_item(
                issue_number=1500,
                title="Generated command center",
                lane="command center",
                rank_score=0,
                review_required=False,
                close_candidate=True,
            ),
        ]
    )
    review_count = sum(item["review_required"] is True for item in rows)
    close_count = sum(item["close_candidate"] is True for item in rows)
    return {
        "schema_version": ("sdetkit.maintenance.queue.rollup.v1"),
        "status": (
            "review required" if review_count else ("ready with proof" if rows else "empty")
        ),
        "source_issue_count": len(rows),
        "queue_item_count": len(rows),
        "review_required_count": review_count,
        "close_candidate_count": close_count,
        "primary_issue": (rows[0]["issue_number"] if rows else None),
        "recommended_next_action": (rows[0]["recommended_action"] if rows else None),
        "queue_items": rows,
        "input_artifacts": {
            "issue_queue_schema_version": ("sdetkit.issue.queue.classifier.v1"),
            "automation_health_schema_version": ("sdetkit.automation.health.v1"),
            "security_schema": ("sdetkit.security.followup.disposition.v1"),
        },
        "automation_allowed": False,
        "merge_authorized": False,
        "semantic_equivalence_proven": False,
    }


def _write_rollup(
    path: Path,
    *,
    payload: dict[str, object] | None = None,
) -> Path:
    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )
    path.write_text(
        json.dumps(
            payload or _rollup_payload(),
            indent=2,
        ),
        encoding="utf-8",
    )
    return path


def test_dashboard_builds_read_only_queue_summary(
    tmp_path: Path,
) -> None:
    rollup = _write_rollup(tmp_path / "maintenance-queue-rollup.json")
    before = rollup.read_bytes()
    out = tmp_path / "dashboard.html"

    payload = maintenance_queue_rollup_dashboard.build_dashboard(
        rollup,
        out_path=out,
    )

    assert payload["schema_version"] == ("sdetkit.maintenance_queue_rollup_dashboard.v1")
    assert payload["status"] == "ready"
    assert payload["rollup_exists"] is True
    assert payload["source_rollup_schema_version"] == ("sdetkit.maintenance.queue.rollup.v1")
    assert payload["source_rollup_status"] == ("review required")
    assert payload["queue_item_count"] == 2
    assert payload["review_required_count"] == 1
    assert payload["close_candidate_count"] == 1
    assert payload["primary_issue"] == 1502
    assert payload["lane_counts"] == {
        "command center": 1,
        "security": 1,
    }
    assert payload["local_only"] is True
    assert payload["read_only"] is True
    assert rollup.read_bytes() == before
    assert all(value is False for value in payload["decision_boundary"].values())


def test_dashboard_renders_static_escaped_html(
    tmp_path: Path,
) -> None:
    item = _queue_item(
        issue_number=1502,
        title="<script>alert('x')</script>",
        lane="security",
        rank_score=700,
        review_required=True,
        close_candidate=False,
    )
    item["recommended_action"] = "<img src=x onerror=alert(1)>"
    rollup = _write_rollup(
        tmp_path / "maintenance-queue-rollup.json",
        payload=_rollup_payload(queue_items=[item]),
    )
    out = tmp_path / "dashboard.html"

    rc = maintenance_queue_rollup_dashboard.main(
        [
            "--rollup-path",
            str(rollup),
            "--format",
            "html",
            "--out",
            str(out),
        ]
    )

    assert rc == 0
    text = out.read_text(encoding="utf-8")
    assert "Maintenance queue rollup dashboard" in text
    assert "Static, local-only, read-only" in text
    assert "&lt;script&gt;" in text
    assert "&lt;img src=x onerror=alert(1)&gt;" in text
    assert "<script>" not in text
    assert "issue_mutation_allowed</strong>: false" in text
    assert "security_dismissal_allowed</strong>: false" in text
    assert "merge_authorized</strong>: false" in text


def test_dashboard_writes_deterministic_json(
    tmp_path: Path,
) -> None:
    rollup = _write_rollup(tmp_path / "maintenance-queue-rollup.json")
    before = rollup.read_bytes()
    first = tmp_path / "dashboard-1.json"
    second = tmp_path / "dashboard-2.json"

    for out in (first, second):
        rc = maintenance_queue_rollup_dashboard.main(
            [
                "--rollup-path",
                str(rollup),
                "--format",
                "json",
                "--out",
                str(out),
            ]
        )
        assert rc == 0

    assert first.read_bytes() == second.read_bytes()
    assert rollup.read_bytes() == before

    payload = json.loads(first.read_text(encoding="utf-8"))
    assert payload["queue_item_count"] == 2
    assert payload["decision_boundary"]["automation_allowed"] is False
    assert payload["decision_boundary"]["issue_mutation_allowed"] is False
    assert payload["decision_boundary"]["merge_authorized"] is False


def test_dashboard_renders_valid_empty_rollup(
    tmp_path: Path,
) -> None:
    rollup = _write_rollup(
        tmp_path / "maintenance-queue-rollup.json",
        payload=_rollup_payload(queue_items=[]),
    )
    out = tmp_path / "dashboard.html"

    rc = maintenance_queue_rollup_dashboard.main(
        [
            "--rollup-path",
            str(rollup),
            "--out",
            str(out),
        ]
    )

    assert rc == 0
    text = out.read_text(encoding="utf-8")
    assert "No maintenance queue items" in text

    payload = maintenance_queue_rollup_dashboard.build_dashboard(
        rollup,
        out_path=out,
    )
    assert payload["status"] == "empty"
    assert payload["queue_item_count"] == 0
    assert payload["primary_issue"] is None
    assert payload["lane_counts"] == {}


def test_dashboard_rejects_missing_or_malformed_rollup(
    tmp_path: Path,
    capsys,
) -> None:
    out = tmp_path / "dashboard.html"

    rc = maintenance_queue_rollup_dashboard.main(
        [
            "--rollup-path",
            str(tmp_path / "missing.json"),
            "--out",
            str(out),
        ]
    )

    assert rc == 2
    assert not out.exists()
    assert "error=" in capsys.readouterr().err

    malformed = tmp_path / "malformed.json"
    malformed.write_text(
        "{not-json",
        encoding="utf-8",
    )

    rc = maintenance_queue_rollup_dashboard.main(
        [
            "--rollup-path",
            str(malformed),
            "--out",
            str(out),
        ]
    )

    assert rc == 2
    assert not out.exists()
    assert "error=" in capsys.readouterr().err


def test_dashboard_rejects_unknown_schema_or_count_drift(
    tmp_path: Path,
    capsys,
) -> None:
    out = tmp_path / "dashboard.json"

    unknown = _rollup_payload()
    unknown["schema_version"] = "sdetkit.maintenance.queue.rollup.v999"
    unknown_path = _write_rollup(
        tmp_path / "unknown.json",
        payload=unknown,
    )

    rc = maintenance_queue_rollup_dashboard.main(
        [
            "--rollup-path",
            str(unknown_path),
            "--format",
            "json",
            "--out",
            str(out),
        ]
    )

    assert rc == 2
    assert not out.exists()
    assert "unsupported maintenance queue rollup schema" in capsys.readouterr().err

    inconsistent = _rollup_payload()
    inconsistent["queue_item_count"] = 99
    inconsistent_path = _write_rollup(
        tmp_path / "inconsistent.json",
        payload=inconsistent,
    )

    rc = maintenance_queue_rollup_dashboard.main(
        [
            "--rollup-path",
            str(inconsistent_path),
            "--format",
            "json",
            "--out",
            str(out),
        ]
    )

    assert rc == 2
    assert not out.exists()
    assert "queue_item_count does not match" in capsys.readouterr().err


def test_dashboard_rejects_derived_count_or_primary_drift(
    tmp_path: Path,
    capsys,
) -> None:
    out = tmp_path / "dashboard.json"

    review_drift = _rollup_payload()
    review_drift["review_required_count"] = 0
    review_path = _write_rollup(
        tmp_path / "review-drift.json",
        payload=review_drift,
    )

    rc = maintenance_queue_rollup_dashboard.main(
        [
            "--rollup-path",
            str(review_path),
            "--format",
            "json",
            "--out",
            str(out),
        ]
    )

    assert rc == 2
    assert not out.exists()
    assert "review_required_count does not match" in capsys.readouterr().err

    primary_drift = _rollup_payload()
    primary_drift["primary_issue"] = 1500
    primary_path = _write_rollup(
        tmp_path / "primary-drift.json",
        payload=primary_drift,
    )

    rc = maintenance_queue_rollup_dashboard.main(
        [
            "--rollup-path",
            str(primary_path),
            "--format",
            "json",
            "--out",
            str(out),
        ]
    )

    assert rc == 2
    assert not out.exists()
    assert "primary_issue does not match" in capsys.readouterr().err


def test_dashboard_rejects_authority_expansion(
    tmp_path: Path,
    capsys,
) -> None:
    out = tmp_path / "dashboard.json"

    expanded = _rollup_payload()
    expanded["automation_allowed"] = True
    expanded_path = _write_rollup(
        tmp_path / "expanded.json",
        payload=expanded,
    )

    rc = maintenance_queue_rollup_dashboard.main(
        [
            "--rollup-path",
            str(expanded_path),
            "--format",
            "json",
            "--out",
            str(out),
        ]
    )

    assert rc == 2
    assert not out.exists()
    assert "authority boundary must remain denied" in capsys.readouterr().err

    item_expanded = _rollup_payload()
    item = item_expanded["queue_items"][0]
    assert isinstance(item, dict)
    item["merge_authorized"] = True
    item_path = _write_rollup(
        tmp_path / "item-expanded.json",
        payload=item_expanded,
    )

    rc = maintenance_queue_rollup_dashboard.main(
        [
            "--rollup-path",
            str(item_path),
            "--format",
            "json",
            "--out",
            str(out),
        ]
    )

    assert rc == 2
    assert not out.exists()
    assert "maintenance queue item authority boundary" in capsys.readouterr().err


def test_project_registers_maintenance_queue_rollup_dashboard_script() -> None:
    pyproject = Path("pyproject.toml").read_text(encoding="utf-8")

    registration = (
        "sdetkit-maintenance-queue-rollup-dashboard = "
        '"sdetkit.maintenance_queue_rollup_dashboard:main"'
    )

    assert pyproject.count(registration) == 1


def test_dashboard_accepts_current_v2_rollup_schema(
    tmp_path: Path,
) -> None:
    from sdetkit import maintenance_queue_rollup

    payload = _rollup_payload()
    payload["schema_version"] = maintenance_queue_rollup.SCHEMA_VERSION
    rollup = _write_rollup(
        tmp_path / "maintenance-queue-rollup-v2.json",
        payload=payload,
    )
    dashboard = maintenance_queue_rollup_dashboard.build_dashboard(
        rollup,
        out_path=tmp_path / "dashboard.html",
    )
    assert dashboard["source_rollup_schema_version"] == maintenance_queue_rollup.SCHEMA_VERSION
