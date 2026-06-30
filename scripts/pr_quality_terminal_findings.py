from __future__ import annotations

from collections.abc import Mapping

from pr_quality_terminal_core import number, text


def finding_rows(alerts, head_sha: str, merge_sha: str, pr_number: int):
    complete, incomplete = [], []
    accepted = {value for value in (head_sha, merge_sha) if value}
    merge_ref = f"refs/pull/{pr_number}/merge"
    for alert in alerts:
        rule = alert.get("rule") if isinstance(alert.get("rule"), Mapping) else {}
        instance = (
            alert.get("most_recent_instance")
            if isinstance(alert.get("most_recent_instance"), Mapping)
            else {}
        )
        location = instance.get("location") if isinstance(instance.get("location"), Mapping) else {}
        message = instance.get("message") if isinstance(instance.get("message"), Mapping) else {}
        commit_sha, ref = text(instance.get("commit_sha")), text(instance.get("ref"))
        row = {
            "number": number(alert.get("number")),
            "rule_id": text(rule.get("id")),
            "severity": text(rule.get("security_severity_level") or rule.get("severity")),
            "state": text(alert.get("state")),
            "path": text(location.get("path")),
            "start_line": number(location.get("start_line")),
            "commit_sha": commit_sha,
            "ref": ref,
            "message": text(message.get("text")),
            "url": text(alert.get("html_url")),
            "current_head_relation": commit_sha in accepted or ref == merge_ref,
        }
        required = (
            "number",
            "rule_id",
            "severity",
            "path",
            "start_line",
            "message",
            "url",
            "current_head_relation",
        )
        gaps = [key for key in required if not row[key]]
        if gaps:
            row["evidence_gaps"] = gaps
            incomplete.append(row)
        else:
            complete.append(row)
    return complete, incomplete
