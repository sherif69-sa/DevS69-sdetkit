from __future__ import annotations

"""Helpers for serializing Rich styles and metadata back to markup.

These helpers are intentionally separate from :mod:`rich.style` and
:mod:`rich.text` so that style serialization, metadata handling, and tag
formatting stay in one place. This keeps the richer round-trip behavior for
``Text.markup`` honest and easier to audit.

The key design choice here is that links, handlers, and generic metadata are
serialized as first-class markup tokens rather than being flattened into a
string-only style definition. That lets ``Text.markup`` reconstruct richer
state without inventing ad-hoc escaping rules in multiple modules.
"""

from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Tuple


MarkupTags = Tuple[List[str], List[str]]


@dataclass(frozen=True)
class MarkupTagPlan:
    """A structured opening / closing tag plan."""

    opening: List[str]
    closing: List[str]

    def to_pair(self) -> MarkupTags:
        return self.opening, self.closing



def render_open_tag(name: str, parameters: str | None = None) -> str:
    """Render an opening markup tag."""
    return f"[{name}]" if parameters is None else f"[{name}={parameters}]"



def render_close_tag(name: str) -> str:
    """Render a closing markup tag."""
    return f"[/{name}]"



def render_handler_value(value: Any) -> str:
    """Render a handler value in a form understood by ``literal_eval``.

    Rich's markup parser accepts two handler encodings today:

    * literal values such as ``'open()'`` or ``(1, 2, 3)``;
    * command-like tuples such as ``("open_dialog", ("settings", 2))``.

    This helper preserves that contract and emits the most readable syntax
    possible for command-like tuples.
    """

    if (
        isinstance(value, tuple)
        and len(value) == 2
        and isinstance(value[0], str)
        and isinstance(value[1], tuple)
    ):
        handler_name, arguments = value
        rendered_arguments = ", ".join(repr(argument) for argument in arguments)
        return f"{handler_name}({rendered_arguments})"
    return repr(value)



def split_meta(meta: Dict[str, Any]) -> tuple[list[tuple[str, Any]], dict[str, Any]]:
    """Split meta in to handler items and generic metadata.

    Handler keys start with ``@`` and have a dedicated markup shorthand. Other
    metadata is packed in to a synthetic ``@meta`` tag so it can round-trip.
    """

    handlers: list[tuple[str, Any]] = []
    generic_meta: dict[str, Any] = {}
    for key, value in sorted(meta.items()):
        if key.startswith("@") and key != "@meta":
            handlers.append((key, value))
        else:
            generic_meta[key] = value
    return handlers, generic_meta



def has_generic_meta(meta: Dict[str, Any]) -> bool:
    """Check if a meta mapping contains non-handler values."""
    return any(not key.startswith("@") or key == "@meta" for key in meta)



def visual_style_definition(style: Any) -> str:
    """Get the style definition without links or metadata."""
    visual_style = style.clear_meta_and_links()
    visual_definition = str(visual_style)
    return "" if visual_definition == "none" else visual_definition



def style_markup_open_tags(style: Any) -> List[str]:
    """Build markup opening tags for a Rich ``Style`` instance."""
    tags: List[str] = []
    visual_definition = visual_style_definition(style)
    if visual_definition:
        tags.append(render_open_tag(visual_definition))
    if style.link:
        tags.append(render_open_tag("link", style.link))
    handlers, generic_meta = split_meta(style.meta)
    for key, value in handlers:
        tags.append(render_open_tag(key, render_handler_value(value)))
    if generic_meta:
        tags.append(render_open_tag("@meta", repr(generic_meta)))
    return tags



def style_markup_close_tags(style: Any) -> List[str]:
    """Build markup closing tags for a Rich ``Style`` instance."""
    closes: List[str] = []
    meta = style.meta
    if has_generic_meta(meta):
        closes.append(render_close_tag("@meta"))
    for key, _ in reversed(split_meta(meta)[0]):
        closes.append(render_close_tag(key))
    if style.link:
        closes.append(render_close_tag("link"))
    visual_definition = visual_style_definition(style)
    if visual_definition:
        closes.append(render_close_tag(visual_definition))
    return closes



def style_markup_plan(style: Any) -> MarkupTagPlan:
    """Build a structured opening / closing plan for a Rich style."""
    return MarkupTagPlan(
        opening=style_markup_open_tags(style),
        closing=style_markup_close_tags(style),
    )



def style_markup_pairs(style: Any) -> MarkupTags:
    """Build opening and closing tags for a Rich ``Style`` instance."""
    return style_markup_plan(style).to_pair()



def plain_style_markup_pairs(style_definition: str) -> MarkupTags:
    """Render a raw style definition as explicit open/close markup tags."""
    return [render_open_tag(style_definition)], [render_close_tag(style_definition)]



def extend_tokens(destination: List[str], tokens: Iterable[str]) -> None:
    """Extend a destination list with pre-rendered token strings."""
    destination.extend(tokens)
