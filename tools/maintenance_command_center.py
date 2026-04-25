from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any


def _iso_now() -> str:
    return dt.datetime.now(dt.UTC).replace(microsecond=0).isoformat().replace('+00:00', 'Z')


def _parse_iso(value: str) -> dt.datetime:
    return dt.datetime.fromisoformat(value.replace('Z', '+00:00'))


class GitHubClient:
    def __init__(
        self, owner: str, repo: str, token: str | None = None, api_base: str = 'https://api.github.com'
    ) -> None:
        self.owner = owner
        self.repo = repo
        self.token = token or ''
        self.api_base = api_base.rstrip('/')

    def _request(self, method: str, path: str, payload: dict[str, Any] | None = None) -> Any:
        url = f"{self.api_base}{path}"
        data = None
        if payload is not None:
            data = json.dumps(payload).encode('utf-8')
        req = urllib.request.Request(url, method=method, data=data)
        req.add_header('Accept', 'application/vnd.github+json')
        if self.token:
            req.add_header('Authorization', f'Bearer {self.token}')
        req.add_header('X-GitHub-Api-Version', '2022-11-28')
        if payload is not None:
            req.add_header('Content-Type', 'application/json')
        try:
            with urllib.request.urlopen(req) as resp:
                text = resp.read().decode('utf-8')
        except urllib.error.HTTPError as exc:
            body = exc.read().decode('utf-8', errors='replace')
            raise RuntimeError(f'GitHub API error {exc.code} {method} {path}: {body}') from exc

        if not text:
            return None
        return json.loads(text)

    def paginate(self, path: str, params: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        page = 1
        while True:
            query = {'per_page': 100, 'page': page}
            if params:
                query.update(params)
            qs = urllib.parse.urlencode(query)
            chunk = self._request('GET', f"{path}?{qs}")
            if not isinstance(chunk, list):
                break
            out.extend(chunk)
            if len(chunk) < 100:
                break
            page += 1
        return out

    def list_open_issues(self) -> list[dict[str, Any]]:
        issues = self.paginate(f'/repos/{self.owner}/{self.repo}/issues', {'state': 'open'})
        return [item for item in issues if 'pull_request' not in item]

    def ensure_label(self, *, name: str, color: str, description: str) -> None:
        try:
            self._request('GET', f'/repos/{self.owner}/{self.repo}/labels/{urllib.parse.quote(name, safe="")}')
            return
        except RuntimeError as exc:
            if ' 404 ' not in str(exc):
                raise
        self._request(
            'POST',
            f'/repos/{self.owner}/{self.repo}/labels',
            {'name': name, 'color': color, 'description': description},
        )

    def update_issue(self, issue_number: int, payload: dict[str, Any]) -> dict[str, Any]:
        return self._request('PATCH', f'/repos/{self.owner}/{self.repo}/issues/{issue_number}', payload)

    def create_issue(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self._request('POST', f'/repos/{self.owner}/{self.repo}/issues', payload)

    def create_comment(self, issue_number: int, body: str) -> None:
        self._request('POST', f'/repos/{self.owner}/{self.repo}/issues/{issue_number}/comments', {'body': body})


def _load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding='utf-8'))
    except ValueError:
        return {}


def _priority_score(issue: dict[str, Any], now: dt.datetime) -> int:
    labels = {x.get('name', '') for x in issue.get('labels', [])}
    score = 0
    if 'priority:high' in labels:
        score += 300
    elif 'priority:medium' in labels:
        score += 200
    elif 'priority:low' in labels:
        score += 100
    if 'security' in labels:
        score += 80
    if 'ghas' in labels:
        score += 70
    if 'dependencies' in labels:
        score += 50
    created = issue.get('created_at') or _iso_now()
    age_days = (now - _parse_iso(created)).days
    score += max(min(age_days, 30), 0)
    return score


def _is_bot_tracker(issue: dict[str, Any], command_center_title: str) -> bool:
    title = str(issue.get('title', ''))
    if title == command_center_title:
        return False
    if issue.get('user', {}).get('login') != 'github-actions[bot]':
        return False
    return bool(re.search(r'\(\d{4}-\d{2}-\d{2}\)', title))


def _bucket(issue: dict[str, Any]) -> str:
    labels = {x.get('name', '') for x in issue.get('labels', [])}
    title = str(issue.get('title', '')).lower()
    if 'security' in labels or 'ghas' in labels:
        return 'Security & GHAS'
    if 'dependencies' in labels:
        return 'Dependency health'
    if 'docs' in title:
        return 'Documentation experience'
    if 'release' in title:
        return 'Release readiness'
    return 'Platform operations'


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding='utf-8').splitlines():
        raw = line.strip()
        if not raw:
            continue
        try:
            rows.append(json.loads(raw))
        except ValueError:
            continue
    return rows


def _append_jsonl(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('a', encoding='utf-8') as handle:
        handle.write(json.dumps(payload, sort_keys=True) + '\n')


def _make_rollup(records: list[dict[str, Any]]) -> dict[str, Any]:
    lookback = records[-30:]
    if not lookback:
        return {
            'schema_version': 'sdetkit.maintenance.command-center.rollup.v1',
            'samples': 0,
            'open_trackers_avg': 0,
            'five_heads_avg_score': 0.0,
            'doctor_avg_score': 0.0,
            'high_priority_pressure_avg': 0.0,
            'adaptive_reviewer_confidence_avg': 0.0,
            'top_recurring_titles': [],
        }

    def _avg(values: list[float]) -> float:
        if not values:
            return 0.0
        return round(sum(values) / len(values), 2)

    title_counts: dict[str, int] = {}
    open_counts: list[float] = []
    five_head_scores: list[float] = []
    doctor_scores: list[float] = []
    pressure_scores: list[float] = []
    confidence_scores: list[float] = []

    for row in lookback:
        open_counts.append(float(row.get('open_tracker_count', 0)))
        five_head_scores.append(float(row.get('review', {}).get('five_heads_overall_score', 0.0)))
        doctor_scores.append(float(row.get('doctor', {}).get('score', 0.0)))
        pressure_scores.append(float(row.get('high_priority_pressure', 0.0)))
        confidence_scores.append(float(row.get('review', {}).get('confidence_score', 0.0)))
        for title in row.get('active_titles', []):
            title_counts[title] = title_counts.get(title, 0) + 1

    recurring = sorted(title_counts.items(), key=lambda item: (-item[1], item[0]))[:8]

    return {
        'schema_version': 'sdetkit.maintenance.command-center.rollup.v1',
        'samples': len(lookback),
        'open_trackers_avg': _avg(open_counts),
        'five_heads_avg_score': _avg(five_head_scores),
        'doctor_avg_score': _avg(doctor_scores),
        'high_priority_pressure_avg': _avg(pressure_scores),
        'adaptive_reviewer_confidence_avg': _avg(confidence_scores),
        'top_recurring_titles': [{'title': title, 'count': count} for title, count in recurring],
    }


def _build_body(
    *,
    now_iso: str,
    keep_open: list[dict[str, Any]],
    deferred: list[dict[str, Any]],
    command_center_title: str,
    review_payload: dict[str, Any],
    doctor_payload: dict[str, Any],
    rollup_payload: dict[str, Any],
    max_open_trackers: int,
) -> str:
    top_rows = [
        '| Issue | Title | Labels | Priority score | Created |',
        '| --- | --- | --- | ---: | --- |',
    ]
    if keep_open:
        for item in keep_open:
            issue = item['issue']
            labels = ', '.join(f"`{lbl.get('name', '')}`" for lbl in issue.get('labels', [])) or '-'
            title = str(issue.get('title', '')).replace('|', '\\|')
            top_rows.append(
                f"| #{issue.get('number')} | {title} | {labels} | {item['score']} | {str(issue.get('created_at', ''))[:10]} |"
            )
    else:
        top_rows.append('| - | No active bot trackers | - | - | - |')

    deferred_lines = [
        f"- #{item['issue'].get('number')} · score {item['score']} · {item['issue'].get('title', '')}"
        for item in deferred
    ] or ['- None']

    buckets: dict[str, list[str]] = {}
    for item in keep_open:
        bucket = _bucket(item['issue'])
        buckets.setdefault(bucket, []).append(
            f"- #{item['issue'].get('number')} (score {item['score']}) — {item['issue'].get('title', '')}"
        )

    bucket_sections = []
    for name, lines in buckets.items():
        bucket_sections.append(f"### {name}\n" + '\n'.join(lines))

    five_heads = review_payload.get('five_heads', {})
    heads = five_heads.get('heads', {}) if isinstance(five_heads, dict) else {}
    head_lines = []
    if isinstance(heads, dict):
        for head_name in sorted(heads):
            row = heads.get(head_name, {}) if isinstance(heads.get(head_name), dict) else {}
            head_lines.append(
                f"- {head_name}: score **{row.get('score', 0)}**, status **{row.get('status', 'unknown')}**"
            )

    review_conf = review_payload.get('adaptive_review', {}).get('probe_feedback', {}).get('confidence_delta', 0.0)
    review_score = review_payload.get('adaptive_database', {}).get('quality_matrix', {}).get('confidence_score', 0.0)
    doctor_score = doctor_payload.get('score', 0)

    recurring = rollup_payload.get('top_recurring_titles', [])
    recurring_lines = [f"- {row.get('title')} (seen {row.get('count')} runs)" for row in recurring] or ['- None yet']

    return '\n'.join(
        [
            'This rolling issue keeps maintenance work focused so newly generated automation trackers stay solvable instead of piling up.',
            '',
            f'Generated: {now_iso}',
            '',
            '## Active queue (kept open)',
            *top_rows,
            '',
            '## Deferred queue (closed and tracked here)',
            *deferred_lines,
            '',
            '## Work lanes',
            *(bucket_sections or ['- No active lanes.']),
            '',
            '## Adaptive learning database signal',
            f"- Learning samples: **{rollup_payload.get('samples', 0)}**",
            f"- Avg open trackers (30-run): **{rollup_payload.get('open_trackers_avg', 0)}**",
            f"- Avg doctor score (30-run): **{rollup_payload.get('doctor_avg_score', 0)}**",
            f"- Avg five-head score (30-run): **{rollup_payload.get('five_heads_avg_score', 0)}**",
            f"- Avg adaptive reviewer confidence (30-run): **{rollup_payload.get('adaptive_reviewer_confidence_avg', 0)}**",
            f"- Avg high-priority pressure (30-run): **{rollup_payload.get('high_priority_pressure_avg', 0)}**",
            '',
            '### Recurring tracker patterns',
            *recurring_lines,
            '',
            '## Doctor + adaptive reviewer + intelligence sync',
            f'- Doctor score: **{doctor_score}**',
            f'- Adaptive reviewer confidence score: **{review_score}** (delta {review_conf})',
            f"- Five-head overall: **{five_heads.get('overall', {}).get('status', 'unknown')}** (score {five_heads.get('overall', {}).get('score', 0)})",
            *head_lines,
            '',
            '## Execution playbook',
            '- [ ] Insert every newly detected problem into the maintenance learning DB snapshot.',
            '- [ ] Pick one issue from each active lane and convert it into a concrete remediation PR.',
            '- [ ] Re-run doctor + review after each merged fix so adaptive reviewer and five-head signals refresh.',
            f'- [ ] Keep open tracker count at or below **{max_open_trackers}** and defer non-critical trackers into this command center.',
            '',
            f'> If a deferred tracker becomes blocking, re-open it and link it back to **{command_center_title}**.',
        ]
    )


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description='Update rolling maintenance command center + learning DB')
    parser.add_argument('--owner', required=True)
    parser.add_argument('--repo', required=True)
    parser.add_argument('--token', default=os.getenv('GH_TOKEN', ''))
    parser.add_argument('--command-center-title', default='🧠 Maintenance command center (rolling)')
    parser.add_argument('--max-open-trackers', type=int, default=4)
    parser.add_argument('--doctor-json', type=Path, required=True)
    parser.add_argument('--review-json', type=Path, required=True)
    parser.add_argument('--db-path', type=Path, default=Path('.sdetkit/maintenance/issue-learning-db.jsonl'))
    parser.add_argument('--rollup-path', type=Path, default=Path('.sdetkit/maintenance/issue-learning-rollup.json'))
    parser.add_argument('--plan-out', type=Path, default=None)
    parser.add_argument('--dry-run', action='store_true')
    parser.add_argument('--api-base', default=os.getenv('GITHUB_API_URL', 'https://api.github.com'))
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    ns = parse_args(list(argv or sys.argv[1:]))

    client = GitHubClient(ns.owner, ns.repo, ns.token, api_base=ns.api_base)
    for label in [
        {'name': 'maintenance', 'color': '0E8A16', 'description': 'Automated maintenance tracking'},
        {'name': 'command-center', 'color': '0052cc', 'description': 'Consolidated maintenance command center issue'},
        {
            'name': 'deferred:command-center',
            'color': '6f42c1',
            'description': 'Tracker deferred to maintenance command center',
        },
    ]:
        if ns.dry_run:
            print(f"[dry-run] ensure label: {label['name']}")
        else:
            client.ensure_label(**label)

    now = dt.datetime.now(dt.UTC)
    now_iso = _iso_now()

    issues = client.list_open_issues()
    maintenance_issues = [
        issue for issue in issues if any(lbl.get('name') == 'maintenance' for lbl in issue.get('labels', []))
    ]

    command_center_issue = next(
        (issue for issue in maintenance_issues if issue.get('title') == ns.command_center_title),
        None,
    )

    tracker_issues = [issue for issue in maintenance_issues if _is_bot_tracker(issue, ns.command_center_title)]
    scored = sorted(
        ({'issue': issue, 'score': _priority_score(issue, now)} for issue in tracker_issues),
        key=lambda row: (-row['score'], row['issue'].get('created_at', '')),
    )

    max_open = max(ns.max_open_trackers, 1)
    keep_open = scored[:max_open]
    deferred = scored[max_open:]

    doctor_payload = _load_json(ns.doctor_json)
    review_payload = _load_json(ns.review_json)

    snapshot = {
        'schema_version': 'sdetkit.maintenance.command-center.snapshot.v1',
        'generated_at': now_iso,
        'repo': f'{ns.owner}/{ns.repo}',
        'open_tracker_count': len(keep_open),
        'deferred_tracker_count': len(deferred),
        'high_priority_pressure': sum(row['score'] for row in keep_open),
        'active_titles': [row['issue'].get('title', '') for row in keep_open],
        'doctor': {
            'score': doctor_payload.get('score', 0),
            'status': doctor_payload.get('status') or doctor_payload.get('summary', 'unknown'),
        },
        'review': {
            'status': review_payload.get('status', 'unknown'),
            'severity': review_payload.get('severity', 'unknown'),
            'confidence_score': review_payload.get('adaptive_database', {})
            .get('quality_matrix', {})
            .get('confidence_score', 0.0),
            'five_heads_overall_score': review_payload.get('five_heads', {}).get('overall', {}).get('score', 0.0),
            'five_heads_overall_status': review_payload.get('five_heads', {}).get('overall', {}).get('status', 'unknown'),
            'top5_actions': review_payload.get('adaptive_database', {}).get('top5_actions', [])[:5],
        },
    }

    _append_jsonl(ns.db_path, snapshot)
    records = _read_jsonl(ns.db_path)
    rollup = _make_rollup(records)
    ns.rollup_path.parent.mkdir(parents=True, exist_ok=True)
    ns.rollup_path.write_text(json.dumps(rollup, indent=2, sort_keys=True) + '\n', encoding='utf-8')

    body = _build_body(
        now_iso=now_iso,
        keep_open=keep_open,
        deferred=deferred,
        command_center_title=ns.command_center_title,
        review_payload=review_payload,
        doctor_payload=doctor_payload,
        rollup_payload=rollup,
        max_open_trackers=max_open,
    )

    payload = {
        'title': ns.command_center_title,
        'body': body,
        'labels': ['maintenance', 'command-center'],
    }
    if command_center_issue:
        issue_number = int(command_center_issue['number'])
        if ns.dry_run:
            print(f'[dry-run] would update command center issue #{issue_number}')
        else:
            client.update_issue(issue_number, payload)
            print(f'updated command center issue #{issue_number}')
    else:
        if ns.dry_run:
            issue_number = -1
            print('[dry-run] would create command center issue')
        else:
            created = client.create_issue(payload)
            issue_number = int(created['number'])
            print(f'created command center issue #{issue_number}')

    if ns.plan_out is not None:
        ns.plan_out.parent.mkdir(parents=True, exist_ok=True)
        ns.plan_out.write_text(
            json.dumps(
                {
                    'schema_version': 'sdetkit.maintenance.command-center.plan.v1',
                    'generated_at': now_iso,
                    'repo': f'{ns.owner}/{ns.repo}',
                    'dry_run': ns.dry_run,
                    'command_center_issue': issue_number if issue_number > 0 else None,
                    'total_open_maintenance_issues': len(maintenance_issues),
                    'total_bot_trackers': len(tracker_issues),
                    'max_open_trackers': max_open,
                    'keep_open': [
                        {'number': row['issue'].get('number'), 'score': row['score'], 'title': row['issue'].get('title')}
                        for row in keep_open
                    ],
                    'defer': [
                        {'number': row['issue'].get('number'), 'score': row['score'], 'title': row['issue'].get('title')}
                        for row in deferred
                    ],
                },
                indent=2,
                sort_keys=True,
            )
            + '\n',
            encoding='utf-8',
        )
        print(f'plan-out: {ns.plan_out}')

    for row in deferred:
        issue = row['issue']
        issue_number = int(issue['number'])
        if ns.dry_run:
            print(f'[dry-run] would comment on #{issue_number}')
        else:
            client.create_comment(
                issue_number,
                '\n\n'.join(
                    [
                        f"This tracker was consolidated into **{ns.command_center_title}** to keep the active queue focused.",
                        'If this issue becomes blocking, re-open it with owner + execution plan.',
                    ]
                ),
            )
        labels = [lbl.get('name', '') for lbl in issue.get('labels', [])]
        if 'deferred:command-center' not in labels:
            labels.append('deferred:command-center')
        if ns.dry_run:
            print(f'[dry-run] would close #{issue_number} with deferred:command-center label')
        else:
            client.update_issue(
                issue_number,
                {
                    'labels': labels,
                    'state': 'closed',
                    'state_reason': 'not_planned',
                },
            )
            print(f'deferred and closed #{issue_number}')

    print(f'learning-db: {ns.db_path}')
    print(f'learning-rollup: {ns.rollup_path}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
