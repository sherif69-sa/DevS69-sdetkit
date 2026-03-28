from __future__ import annotations

"""Structured helpers for serializing :class:`rich.text.Text` back to markup.

The public ``Text.markup`` property historically assembled tags inline. That
worked for simple visual spans, but it made richer round-tripping hard to audit
once links, event handlers, generic metadata, and explicit close ordering were
added to the contract.

This module keeps the serialization logic in one place and models the process
explicitly:

* convert Rich style values in to opening / closing markup token pairs;
* translate spans in to positioned events;
* guarantee stable open / close ordering at shared offsets;
* append escaped plain-text slices between tag transitions;
* render the final token stream back to a markup string.

Keeping those steps explicit also makes metadata-bearing close ordering changes
easier to review when the round-trip contract expands in future problems.
"""

from dataclasses import dataclass
from typing import Iterable, List, Sequence, Tuple

from .markup_tags import plain_style_markup_pairs, style_markup_pairs
from .style import Style, StyleType


MarkupPair = Tuple[List[str], List[str]]


@dataclass(frozen=True)
class MarkupEvent:
    """A positioned token event produced while serializing a ``Text`` object."""

    offset: int
    closing: bool
    sort_key: int
    tokens: Tuple[str, ...]

    @property
    def ordering(self) -> Tuple[int, int, int]:
        """Sort key used to stabilize serialization order."""
        return (self.offset, 1 if self.closing else 0, self.sort_key)


class StyleMarkupResolver:
    """Resolve Rich style values in to markup token pairs.

    The resolver accepts either ``Style`` instances or string style definitions.
    String values are normalized and, where possible, parsed back in to ``Style``
    so links and metadata-aware serialization can still produce canonical tags.
    """

    @staticmethod
    def resolve(style: StyleType) -> MarkupPair:
        if not style:
            return [], []
        if isinstance(style, Style):
            return style_markup_pairs(style)
        normalized = Style.normalize(str(style))
        if not normalized or normalized == "none":
            return [], []
        try:
            parsed = Style.parse(normalized)
        except Exception:
            return plain_style_markup_pairs(normalized)
        opening, closing = style_markup_pairs(parsed)
        if opening or closing:
            return opening, closing
        return plain_style_markup_pairs(normalized)


class MarkupEventStream:
    """Collect positioned serialization events for a ``Text`` object."""

    def init_(self) -> None:
        self._events: List[MarkupEvent] = []

    def add(self, offset: int, closing: bool, sort_key: int, style: StyleType) -> None:
        opening, closing_tokens = StyleMarkupResolver.resolve(style)
        tokens = tuple(closing_tokens if closing else opening)
        if tokens:
            self._events.append(
                MarkupEvent(
                    offset=offset,
                    closing=closing,
                    sort_key=sort_key,
                    tokens=tokens,
                )
            )

    def extend(self, events: Iterable[MarkupEvent]) -> None:
        self._events.extend(events)

    def sorted(self) -> List[MarkupEvent]:
        return sorted(self._events, key=lambda event: event.ordering)


class MarkupTokenBuffer:
    """Mutable buffer used while rendering the final markup string."""

    def init_(self) -> None:
        self._tokens: List[str] = []
        self._position = 0

    @property
    def position(self) -> int:
        return self._position

    def append_plain(self, plain: str, end: int) -> None:
        if end > self._position:
            from .markup import escape

            self._tokens.append(escape(plain[self._position:end]))
            self._position = end

    def append_tokens(self, tokens: Sequence[str]) -> None:
        self._tokens.extend(tokens)

    def append_remaining(self, plain: str) -> None:
        if self._position < len(plain):
            from .markup import escape

            self._tokens.append(escape(plain[self._position :]))
            self._position = len(plain)

    def render(self) -> str:
        return "".join(self._tokens)


class TextMarkupSerializer:
    """Serialize ``Text`` objects back to Rich markup.

    The serializer intentionally keeps a few small methods instead of one large
    function so that event construction, ordering, and token emission stay easy
    to reason about and unit test. The resulting event stream is deterministic,
    preserves nested close ordering, and leaves plain-text escaping to a single
    token buffer implementation so metadata-aware serialization can evolve
    without reintroducing inline string assembly bugs.
    """

    def init_(self, text: "Text") -> None:
        self.text = text
        self.plain = text.plain
        self.stream = MarkupEventStream()

    def build_base_style_events(self) -> None:
        span_count = len(self.text.spans)
        self.stream.add(0, False, -1, self.text.style)
        self.stream.add(len(self.plain), True, span_count + 1, self.text.style)

    def build_span_events(self) -> None:
        span_count = len(self.text.spans)
        for index, span in enumerate(self.text.spans):
            self.stream.add(span.start, False, index, span.style)
            self.stream.add(span.end, True, span_count - index, span.style)

    def build_events(self) -> List[MarkupEvent]:
        """Build and sort all markup events for the text instance."""
        self.build_base_style_events()
        self.build_span_events()
        return self.stream.sorted()

    def emit(self, events: Iterable[MarkupEvent]) -> str:
        """Emit an ordered event stream to a final markup string."""
        buffer = MarkupTokenBuffer()
        for event in events:
            buffer.append_plain(self.plain, event.offset)
            buffer.append_tokens(event.tokens)
        buffer.append_remaining(self.plain)
        return buffer.render()

    def render(self) -> str:
        """Render the complete markup string for the text instance."""
        return self.emit(self.build_events())


def serialize_text_markup(text: "Text") -> str:
    """Serialize a ``Text`` instance to Rich markup."""
    return TextMarkupSerializer(text).render()


if False:  # pragma: no cover
    from .text import Text
