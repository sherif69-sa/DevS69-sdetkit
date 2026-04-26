from __future__ import annotations

import argparse
import datetime as dt
import json
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

DEFAULT_HTTP_TIMEOUT_SECONDS = 30


def _utc_now() -> str:
    return dt.datetime.now(dt.UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


class GitHubIssueClient:
    def __init__(
        self,
        owner: str,
        repo: str,
        *,
        token: str = "",
        api_base: str = "https://api.github.com",
    ) -> None:
        self.owner = owner
        self.repo = repo
        self.token = token
        self.api_base = api_base.rstrip("/")

    def _request(self, method: str, path: str) -> Any:
        url = f"{self.api_base}{path}"
        req = urllib.request.Request(url, method=method)
        req.add_header("Accept", "application/vnd.github+json")
        req.add_header("X-GitHub-Api-Version", "2022-11-28")
        if self.token:
            req.add_header("Authorization", f"Bearer {self.token}")
        try:
            with urllib.request.urlopen(req, timeout=DEFAULT_HTTP_TIMEOUT_SECONDS) as resp:
                payload = resp.read().decode("utf-8")
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"GitHub API error {exc.code} {method} {path}: {body}") from exc
        return json.loads(payload) if payload else None

    def list_open_issues(self) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        page = 1
        while True:
            query = urllib.parse.urlencode({"state": "open", "per_page": 100, "page": page})
            page_payload = self._request("GET", f"/repos/{self.owner}/{self.repo}/issues?{query}")
            if not isinstance(page_payload, list):
                break
            issues_only = [
                x for x in page_payload if isinstance(x, dict) and "pull_request" not in x
            ]
            items.extend(issues_only)
            if len(page_payload) < 100:
                break
            page += 1
        return items


def _run_json_command(cmd: list[str]) -> dict[str, Any]:
    proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if proc.returncode != 0:
        return {
            "ok": False,
            "returncode": proc.returncode,
            "stdout": proc.stdout,
            "stderr": proc.stderr,
        }
    try:
        payload = json.loads(proc.stdout) if proc.stdout.strip() else {}
    except ValueError:
        payload = {"raw_stdout": proc.stdout}
    return {"ok": True, "returncode": proc.returncode, "payload": payload}


def _summarize_security(payload: dict[str, Any]) -> dict[str, Any]:
    findings = payload.get("findings", [])
    if not isinstance(findings, list):
        findings = []
    counts_by_rule: dict[str, int] = {}
    counts_by_severity: dict[str, int] = {}
    for item in findings:
        if not isinstance(item, dict):
            continue
        rule = str(item.get("rule_id", "")).strip() or "unknown"
        sev = str(item.get("severity", "")).strip() or "unknown"
        counts_by_rule[rule] = counts_by_rule.get(rule, 0) + 1
        counts_by_severity[sev] = counts_by_severity.get(sev, 0) + 1
    top_rules = sorted(counts_by_rule.items(), key=lambda pair: (-pair[1], pair[0]))[:10]
    actionable_findings = [
        item
        for item in findings
        if isinstance(item, dict) and str(item.get("severity", "")).strip() in {"warn", "error"}
    ]
    actionable_by_rule: dict[str, int] = {}
    for item in actionable_findings:
        rule = str(item.get("rule_id", "")).strip() or "unknown"
        actionable_by_rule[rule] = actionable_by_rule.get(rule, 0) + 1
    actionable_top_rules = sorted(actionable_by_rule.items(), key=lambda pair: (-pair[1], pair[0]))[
        :10
    ]
    return {
        "total_findings": len(findings),
        "actionable_findings": len(actionable_findings),
        "counts_by_rule": counts_by_rule,
        "counts_by_severity": counts_by_severity,
        "top_rules": [{"rule_id": rule, "count": count} for rule, count in top_rules],
        "actionable_top_rules": [
            {"rule_id": rule, "count": count} for rule, count in actionable_top_rules
        ],
    }


def _is_maintenance_issue(issue: dict[str, Any]) -> bool:
    labels = {
        str(x.get("name", "")).strip() for x in issue.get("labels", []) if isinstance(x, dict)
    }
    return "maintenance" in labels


def _issue_row(issue: dict[str, Any]) -> dict[str, Any]:
    labels_raw = issue.get("labels", [])
    labels: list[str] = []
    if isinstance(labels_raw, list):
        for item in labels_raw:
            if isinstance(item, dict):
                labels.append(str(item.get("name", "")).strip())
            elif isinstance(item, str):
                labels.append(item.strip())
    return {
        "number": issue.get("number"),
        "title": issue.get("title"),
        "created_at": issue.get("created_at"),
        "labels": labels,
        "url": issue.get("html_url"),
    }


def _recommend_next_issues(issues: list[dict[str, Any]]) -> list[int]:
    def score(issue: dict[str, Any]) -> int:
        labels = set(issue.get("labels", []))
        points = 0
        if "priority:high" in labels:
            points += 300
        elif "priority:medium" in labels:
            points += 200
        if "security" in labels:
            points += 100
        if "ghas" in labels:
            points += 80
        return points

    normalized = [_issue_row(x) for x in issues]
    actionable = [
        item
        for item in normalized
        if "command-center" not in set(item.get("labels", []))
        and "maintenance command center (rolling)" not in str(item.get("title", "")).lower()
    ]
    ordered = sorted(actionable, key=score, reverse=True)
    return [int(x["number"]) for x in ordered if isinstance(x.get("number"), int)]


def build_report(
    *,
    owner: str,
    repo: str,
    token: str,
    run_local_checks: bool,
) -> dict[str, Any]:
    gh = GitHubIssueClient(owner, repo, token=token)
    open_issues = gh.list_open_issues()
    maintenance_open = [_issue_row(x) for x in open_issues if _is_maintenance_issue(x)]
    security_open = [
        item
        for item in maintenance_open
        if "security" in item.get("labels", []) or "ghas" in item.get("labels", [])
    ]

    local: dict[str, Any] = {"enabled": run_local_checks}
    if run_local_checks:
        local["doctor"] = _run_json_command(
            [sys.executable, "-m", "sdetkit", "doctor", "--format", "json"]
        )
        local["repo_enterprise"] = _run_json_command(
            [
                sys.executable,
                "-m",
                "sdetkit",
                "repo",
                "check",
                ".",
                "--profile",
                "enterprise",
                "--format",
                "json",
                "--force",
            ]
        )
        local["security_check"] = _run_json_command(
            [
                sys.executable,
                "-m",
                "sdetkit",
                "security",
                "check",
                "--root",
                ".",
                "--format",
                "json",
            ]
        )
        sec_payload = local["security_check"].get("payload", {})
        local["security_summary"] = (
            _summarize_security(sec_payload) if isinstance(sec_payload, dict) else {}
        )

    return {
        "schema_version": "sdetkit.maintenance.issue-workbench.v1",
        "generated_at": _utc_now(),
        "repo": f"{owner}/{repo}",
        "open_issue_counts": {
            "all_open": len(open_issues),
            "maintenance_open": len(maintenance_open),
            "security_maintenance_open": len(security_open),
        },
        "maintenance_open": maintenance_open,
        "next_issue_order": _recommend_next_issues(maintenance_open),
        "local_checks": local,
    }


def _render_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# Maintenance issue workbench",
        "",
        f"- Generated: `{report.get('generated_at', '')}`",
        f"- Repo: `{report.get('repo', '')}`",
        "",
        "## Open issue snapshot",
        "",
    ]
    counts = report.get("open_issue_counts", {})
    lines.append(f"- All open issues: **{counts.get('all_open', 0)}**")
    lines.append(f"- Open maintenance issues: **{counts.get('maintenance_open', 0)}**")
    lines.append(
        f"- Open security/GHAS maintenance issues: **{counts.get('security_maintenance_open', 0)}**"
    )
    lines.extend(["", "## Recommended one-by-one issue order", ""])
    for num in report.get("next_issue_order", []):
        lines.append(f"- #{num}")
    lines.extend(
        [
            "",
            "## Active maintenance issues",
            "",
            "| Issue | Title | Labels |",
            "| --- | --- | --- |",
        ]
    )
    for item in report.get("maintenance_open", []):
        labels = ", ".join(f"`{x}`" for x in item.get("labels", []))
        lines.append(f"| #{item.get('number')} | {item.get('title', '')} | {labels} |")

    local = report.get("local_checks", {})
    if local.get("enabled"):
        lines.extend(["", "## Local quality/security execution", ""])
        doctor = local.get("doctor", {})
        repo = local.get("repo_enterprise", {})
        sec = local.get("security_summary", {})
        lines.append(f"- doctor command ok: **{doctor.get('ok', False)}**")
        lines.append(f"- repo enterprise check ok: **{repo.get('ok', False)}**")
        lines.append(f"- security total findings: **{sec.get('total_findings', 0)}**")
        lines.append(
            f"- security actionable findings (warn/error): **{sec.get('actionable_findings', 0)}**"
        )
        lines.append("- top security rules:")
        for rule in sec.get("top_rules", []):
            lines.append(f"  - `{rule.get('rule_id', 'unknown')}`: {rule.get('count', 0)}")
        lines.append("- top actionable security rules:")
        for rule in sec.get("actionable_top_rules", []):
            lines.append(f"  - `{rule.get('rule_id', 'unknown')}`: {rule.get('count', 0)}")
    return "\n".join(lines).strip() + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Generate a one-stop maintenance workbench: open maintenance issue view + "
            "local security/quality checks for one-by-one remediation."
        )
    )
    parser.add_argument("--owner", required=True)
    parser.add_argument("--repo", required=True)
    parser.add_argument("--token", default="")
    parser.add_argument("--skip-local-checks", action="store_true")
    parser.add_argument("--json-out", default="build/maintenance/issue-workbench.json")
    parser.add_argument("--md-out", default="build/maintenance/issue-workbench.md")
    args = parser.parse_args(argv)

    report = build_report(
        owner=args.owner,
        repo=args.repo,
        token=args.token,
        run_local_checks=not args.skip_local_checks,
    )
    json_out = Path(args.json_out)
    md_out = Path(args.md_out)
    json_out.parent.mkdir(parents=True, exist_ok=True)
    json_out.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    md_out.parent.mkdir(parents=True, exist_ok=True)
    md_out.write_text(_render_markdown(report), encoding="utf-8")
    print(f"json: {json_out}")
    print(f"markdown: {md_out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
