from __future__ import annotations

import argparse
import json
from collections.abc import Sequence
from pathlib import Path

_QUICK_JUMP_START = '<div class="quick-jump" markdown>'
_QUICK_JUMP_END = '</div>'

_REQUIRED_LINKS = [
    '[⚡ Fast start](#fast-start)',
    '[🛠 CLI commands](cli.md)',
    '[🩺 Doctor checks](doctor.md)',
    '[🤝 Contribute](contributing.md)',
    '[✅ Day 10 ultra report](day-10-ultra-upgrade-report.md)',
    '[🧭 Day 11 ultra report](day-11-ultra-upgrade-report.md)',
]

_DAY11_SECTION_HEADER = '## Day 11 ultra upgrades (docs navigation tune-up)'
_DAY11_JOURNEYS_HEADER = '### Day 11 top journeys'

_TOP_JOURNEYS = [
    'Run first command in under 60 seconds',
    'Validate docs links and anchors before publishing',
    'Ship a first contribution with deterministic quality gates',
]

_DAY11_QUICK_JUMP_BLOCK = """<div class=\"quick-jump\" markdown>

[⚡ Fast start](#fast-start) · [🚀 Phase-1 daily plan](top-10-github-strategy.md#phase-1-days-1-30-positioning-conversion-daily-execution) · [✅ Day 10 ultra report](day-10-ultra-upgrade-report.md) · [🧭 Day 11 ultra report](day-11-ultra-upgrade-report.md) · [🧭 Repo tour](repo-tour.md) · [📈 Top-10 strategy](top-10-github-strategy.md) · [🤖 AgentOS](agentos-foundation.md) · [🍳 Cookbook](agentos-cookbook.md) · [🛠 CLI commands](cli.md) · [🩺 Doctor checks](doctor.md) · [🤝 Contribute](contributing.md)

</div>
"""

_DAY11_JOURNEYS_BLOCK = """### Day 11 top journeys

- Run first command in under 60 seconds
- Validate docs links and anchors before publishing
- Ship a first contribution with deterministic quality gates
"""


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog='sdetkit docs-nav',
        description='Render and validate Day 11 docs navigation one-click journeys from docs home.',
    )
    p.add_argument('--format', choices=['text', 'markdown', 'json'], default='text')
    p.add_argument('--root', default='.', help='Repository root where docs/index.md lives.')
    p.add_argument('--output', default='', help='Optional output file path.')
    p.add_argument('--strict', action='store_true', help='Return non-zero when required docs navigation entries are missing.')
    p.add_argument(
        '--write-defaults',
        action='store_true',
        help='Repair Day 11 quick-jump + top-journey baseline content in docs/index.md, then validate again.',
    )
    return p


def _read(path: Path) -> str:
    if not path.exists():
        return ''
    return path.read_text(encoding='utf-8')


def _extract_quick_jump(text: str) -> str:
    start = text.find(_QUICK_JUMP_START)
    if start < 0:
        return ''
    end = text.find(_QUICK_JUMP_END, start)
    if end < 0:
        return ''
    return text[start : end + len(_QUICK_JUMP_END)]


def _replace_or_append_block(text: str, start_marker: str, end_marker: str, block: str) -> tuple[str, bool]:
    start = text.find(start_marker)
    end = text.find(end_marker, start) if start >= 0 else -1
    if start >= 0 and end >= 0:
        updated = text[:start] + block + text[end + len(end_marker) :]
        return updated, updated != text
    updated = text.rstrip() + ('\n\n' if text.strip() else '') + block
    return updated, updated != text


def _ensure_day11_section_header(text: str) -> tuple[str, bool]:
    if _DAY11_SECTION_HEADER in text:
        return text, False
    updated = text.rstrip() + '\n\n' + _DAY11_SECTION_HEADER + '\n'
    return updated, updated != text


def _ensure_journey_block(text: str) -> tuple[str, bool]:
    if _DAY11_JOURNEYS_HEADER in text and all(f'- {journey}' in text for journey in _TOP_JOURNEYS):
        return text, False

    updated = text.rstrip() + '\n\n' + _DAY11_JOURNEYS_BLOCK + '\n'
    return updated, updated != text


def _check_results(index_text: str) -> list[dict[str, object]]:
    quick_jump = _extract_quick_jump(index_text)
    checks: list[tuple[str, str, str]] = [
        ('quick-jump-wrapper', _QUICK_JUMP_START, 'quick_jump'),
        ('day11-upgrade-section', _DAY11_SECTION_HEADER, 'index'),
        ('day11-top-journeys-header', _DAY11_JOURNEYS_HEADER, 'index'),
    ]
    checks.extend((f'quick-jump-link:{link}', link, 'quick_jump') for link in _REQUIRED_LINKS)
    checks.extend((f'top-journey:{journey}', f'- {journey}', 'index') for journey in _TOP_JOURNEYS)

    results: list[dict[str, object]] = []
    for check_id, needle, scope in checks:
        target = quick_jump if scope == 'quick_jump' else index_text
        results.append(
            {
                'id': check_id,
                'scope': scope,
                'needle': needle,
                'present': needle in target,
            }
        )
    return results


def _write_defaults(base: Path) -> list[str]:
    path = base / 'docs/index.md'
    current = _read(path)
    if not current:
        current = '# Documentation Home\n\n'

    updated, changed_quick_jump = _replace_or_append_block(current, _QUICK_JUMP_START, _QUICK_JUMP_END, _DAY11_QUICK_JUMP_BLOCK)
    updated, changed_section = _ensure_day11_section_header(updated)
    updated, changed_journeys = _ensure_journey_block(updated)

    if not (changed_quick_jump or changed_section or changed_journeys or not path.exists()):
        return []

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(updated, encoding='utf-8')
    return ['docs/index.md']


def build_docs_navigation_status(root: str = '.') -> dict[str, object]:
    base = Path(root)
    docs_index = base / 'docs/index.md'
    index_text = _read(docs_index)
    checks = _check_results(index_text)
    missing = [str(check['needle']) for check in checks if not check['present']]

    total_checks = len(checks)
    passed_checks = sum(1 for check in checks if check['present'])
    score = round((passed_checks / total_checks) * 100, 1) if total_checks else 0.0

    return {
        'name': 'day11-docs-navigation',
        'score': score,
        'total_checks': total_checks,
        'passed_checks': passed_checks,
        'journeys': list(_TOP_JOURNEYS),
        'required_links': list(_REQUIRED_LINKS),
        'docs_index': str(docs_index),
        'missing': missing,
        'checks': checks,
        'actions': {
            'open_docs_home': 'docs/index.md',
            'validate': 'sdetkit docs-nav --format json --strict',
            'write_defaults': 'sdetkit docs-nav --write-defaults --format json --strict',
            'artifact': 'sdetkit docs-nav --format markdown --output docs/artifacts/day11-docs-navigation-sample.md',
        },
    }


def _render_text(payload: dict[str, object]) -> str:
    lines = [
        'Day 11 docs navigation tune-up',
        f"score: {payload['score']} ({payload['passed_checks']}/{payload['total_checks']})",
        '',
        'top journeys:',
    ]
    for idx, item in enumerate(payload['journeys'], start=1):
        lines.append(f'{idx}. {item}')
    lines.extend(['', 'required links:'])
    for link in payload['required_links']:
        lines.append(f'- {link}')
    lines.extend(['', f"docs home: {payload['docs_index']}"])
    if payload['missing']:
        lines.append('missing docs navigation content:')
        for item in payload['missing']:
            lines.append(f'- {item}')
    else:
        lines.append('missing docs navigation content: none')
    lines.extend(['', 'actions:'])
    lines.append(f"- open docs home: {payload['actions']['open_docs_home']}")
    lines.append(f"- validate: {payload['actions']['validate']}")
    lines.append(f"- write defaults: {payload['actions']['write_defaults']}")
    lines.append(f"- export artifact: {payload['actions']['artifact']}")
    return '\n'.join(lines) + '\n'


def _render_markdown(payload: dict[str, object]) -> str:
    lines = [
        '# Day 11 docs navigation tune-up',
        '',
        f"- Score: **{payload['score']}** ({payload['passed_checks']}/{payload['total_checks']})",
        f"- Docs home: `{payload['docs_index']}`",
        '',
        '## Top journeys',
        '',
    ]
    for item in payload['journeys']:
        lines.append(f'- [ ] {item}')
    lines.extend(['', '## Required one-click links', ''])
    for item in payload['required_links']:
        lines.append(f'- `{item}`')
    lines.extend(['', '## Missing docs navigation content', ''])
    if payload['missing']:
        for item in payload['missing']:
            lines.append(f'- `{item}`')
    else:
        lines.append('- none')
    lines.extend(['', '## Actions', ''])
    lines.append(f"- `{payload['actions']['open_docs_home']}`")
    lines.append(f"- `{payload['actions']['validate']}`")
    lines.append(f"- `{payload['actions']['write_defaults']}`")
    lines.append(f"- `{payload['actions']['artifact']}`")
    return '\n'.join(lines) + '\n'


def main(argv: Sequence[str] | None = None) -> int:
    args = _build_parser().parse_args(list(argv) if argv is not None else None)

    touched: list[str] = []
    if args.write_defaults:
        touched = _write_defaults(Path(args.root))

    payload = build_docs_navigation_status(args.root)
    payload['touched_files'] = touched

    if args.format == 'json':
        rendered = json.dumps(payload, indent=2) + '\n'
    elif args.format == 'markdown':
        rendered = _render_markdown(payload)
    else:
        rendered = _render_text(payload)

    if args.output:
        out = Path(args.output)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(rendered, encoding='utf-8')

    print(rendered, end='')

    if args.strict and payload['passed_checks'] != payload['total_checks']:
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
