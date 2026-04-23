from __future__ import annotations

from pathlib import Path

from rich.console import Console
from rich.style import Style
from rich.text import Text

HEADER = '''from __future__ import annotations

from rich.console import Console
from rich.style import Style
from rich.text import Text

'''


def _text_from_markup_with_metadata(
    markup: str,
    *,
    justify: str,
    overflow: str,
    no_wrap: bool,
    end: str,
    tab_size: int,
) -> Text:
    try:
        text = Text.from_markup(markup)
    except TypeError:
        text = _construct_with_init_alias(Text, markup)
    text.justify = justify
    text.overflow = overflow
    text.no_wrap = no_wrap
    text.end = end
    text.tab_size = tab_size
    return text


def _construct_with_init_alias(factory, *args, **kwargs):
    try:
        return factory(*args, **kwargs)
    except TypeError:
        instance = factory()
        init_alias = getattr(instance, "init_", None)
        if callable(init_alias):
            init_alias(*args, **kwargs)
            return instance
        raise


def _build_case_data() -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    styles = [
        "bold",
        "italic",
        "underline",
        "red",
        "green",
        "blue",
        "bold red",
        "italic magenta",
        "underline cyan",
        "reverse yellow",
        "strike white on blue",
    ]
    inner_styles = [
        "",
        "bold",
        "italic",
        "underline",
        "red",
        "green",
        "blue",
        "bold magenta",
        "underline yellow",
        "reverse cyan",
        "strike white on red",
    ]
    handler_templates = [
        lambda i: {"@click": f"open_{i:04d}()"},
        lambda i: {"@click": ("dispatch", (f"modal-{i:04d}", i % 7))},
        lambda i: {"@hover": f"hover_{i:04d}"},
        lambda i: {"@focus": ("focus_panel", (f"pane-{i % 5}",))},
    ]
    meta_templates = [
        lambda i: {"owner": f"user-{i % 17}", "case": f"c{i:04d}"},
        lambda i: {"lane": f"lane-{i % 9}", "topic": f"topic-{i % 13}"},
        lambda i: {"bucket": f"bucket-{i % 11}", "priority": f"p{i % 5}"},
    ]
    markup_cases: list[dict[str, object]] = []
    for i in range(960):
        plain = f"case-{i:04d}-alpha-beta-gamma"
        base_style = styles[i % len(styles)]
        inner_style = inner_styles[i % len(inner_styles)]
        link = f"https://example.org/problem/{i:04d}" if i % 3 != 1 else ""
        meta = meta_templates[i % len(meta_templates)](i)
        meta.update(handler_templates[i % len(handler_templates)](i))
        text = _construct_with_init_alias(Text, plain, style=base_style)
        if link:
            text.stylize(_construct_with_init_alias(Style, link=link), 0, len(text))
        text.stylize(_construct_with_init_alias(Style, meta=meta), 0, len(text))
        if inner_style:
            start = 5 + (i % 4)
            end = len(plain) - (3 + (i % 5))
            if end <= start:
                start, end = 1, len(plain) - 1
            text.stylize(inner_style, start, end)
            probe = start
        else:
            start = end = 0
            probe = len(plain) // 2
        markup_cases.append(
            {
                "plain": plain,
                "base_style": base_style,
                "link": link,
                "meta": meta,
                "inner_style": inner_style,
                "inner_start": start,
                "inner_end": end,
                "probe_offset": probe,
                "expected_markup": text.markup,
            }
        )

    fragment_cases: list[dict[str, object]] = []
    markups = [
        "[bold]alpha beta gamma[/bold]",
        "[link=https://example.org][italic]delta epsilon zeta[/italic][/link]",
        "[@meta={'owner': 'ops'}][underline]eta theta iota[/underline][/@meta]",
        "[bold][@click=dispatch('pane', 3)]kappa lambda mu[/@click][/bold]",
    ]
    justifies = ["left", "center", "right"]
    overflows = ["fold", "ellipsis"]
    for i in range(240):
        markup = markups[i % len(markups)]
        justify = justifies[i % len(justifies)]
        overflow = overflows[i % len(overflows)]
        no_wrap = bool(i % 2)
        end = "!" if i % 2 else "\n"
        tab_size = 2 + (i % 4)
        text = _text_from_markup_with_metadata(
            markup,
            justify=justify,
            overflow=overflow,
            no_wrap=no_wrap,
            end=end,
            tab_size=tab_size,
        )
        offsets = [4 + (i % 3), 9 + (i % 5)]
        fragments = text.divide(offsets)
        fragment_cases.append(
            {
                "markup": markup,
                "justify": justify,
                "overflow": overflow,
                "no_wrap": no_wrap,
                "end": end,
                "tab_size": tab_size,
                "offsets": offsets,
                "expected_markup": text.markup,
                "expected_fragments": [
                    {
                        "plain": fragment.plain,
                        "justify": fragment.justify,
                        "overflow": fragment.overflow,
                        "no_wrap": fragment.no_wrap,
                        "end": fragment.end,
                        "tab_size": fragment.tab_size,
                    }
                    for fragment in fragments
                ],
            }
        )
    return markup_cases, fragment_cases


def render_test_module() -> str:
    markup_cases, fragment_cases = _build_case_data()
    return (
        HEADER
        + f"MARKUP_CASES = {markup_cases!r}\n\n"
        + f"FRAGMENT_CASES = {fragment_cases!r}\n\n"
        + '''

def _build_case_text(case: dict[str, object]) -> Text:
    plain = str(case["plain"])
    text = Text(plain, style=str(case["base_style"]))
    link = str(case["link"])
    if link:
        text.stylize(Style(link=link), 0, len(text))
    text.stylize(Style(meta=dict(case["meta"])), 0, len(text))
    inner_style = str(case["inner_style"])
    if inner_style:
        text.stylize(inner_style, int(case["inner_start"]), int(case["inner_end"]))
    return text


def _build_fragment_text(case: dict[str, object]) -> Text:
    text = Text.from_markup(str(case["markup"]))
    text.justify = str(case["justify"])
    text.overflow = str(case["overflow"])
    text.no_wrap = bool(case["no_wrap"])
    text.end = str(case["end"])
    text.tab_size = int(case["tab_size"])
    return text


def test_markup_roundtrip_problem_cases() -> None:
    console = Console()
    for case in MARKUP_CASES:
        text = _build_case_text(case)
        assert text.markup == case["expected_markup"]
        roundtrip = Text.from_markup(text.markup)
        assert roundtrip.markup == case["expected_markup"]
        expected_meta = dict(case["meta"])
        assert roundtrip.get_style_at_offset(console, int(case["probe_offset"])).meta == expected_meta


def test_fragment_metadata_problem_cases() -> None:
    for case in FRAGMENT_CASES:
        text = _build_fragment_text(case)
        assert text.markup == case["expected_markup"]
        fragments = text.divide(list(case["offsets"]))
        observed = [
            {
                "plain": fragment.plain,
                "justify": fragment.justify,
                "overflow": fragment.overflow,
                "no_wrap": fragment.no_wrap,
                "end": fragment.end,
                "tab_size": fragment.tab_size,
            }
            for fragment in fragments
        ]
        assert observed == case["expected_fragments"]
'''
    )


def main(output: str) -> None:
    Path(output).write_text(render_test_module(), encoding="utf-8")


if __name__ in {"__main__", "main_"}:
    import sys

    if len(sys.argv) != 2:
        raise SystemExit("usage: generate_test_problem.py <output-path>")
    main(sys.argv[1])
