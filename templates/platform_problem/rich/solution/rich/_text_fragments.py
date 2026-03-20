from __future__ import annotations

"""Helpers for preserving ``Text`` metadata when fragmenting content.

Rich splits ``Text`` objects in a number of places: ``divide()``, ``split()``,
``wrap()``, and callers that build structural fragments manually. The core
invariant for this problem is that those fragments should preserve the metadata
that determines how they render later: style, justify mode, overflow mode,
``no_wrap``, line ending, and tab size.

These helpers intentionally keep the metadata copy path explicit so future
changes can extend fragment construction without having to reverse-engineer
which ``Text`` attributes are safe to preserve, which ones should be forwarded
unchanged, and where the fragment ordering contract begins and ends.
"""

from dataclasses import dataclass
from typing import Iterable, Iterator, List, TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover
    from .text import Text


@dataclass(frozen=True)
class FragmentRange:
    """A plain-text slice to materialize as a fragment."""

    start: int
    end: int
    is_last: bool

    @property
    def plain_slice(self) -> slice:
        return slice(self.start, self.end)


@dataclass(frozen=True)
class FragmentMetadata:
    """Render-affecting metadata copied from a source ``Text`` object."""

    style: object
    justify: object
    overflow: object
    no_wrap: object
    end: str
    tab_size: object


class FragmentMetadataBuilder:
    """Collect metadata from a source ``Text`` object."""

    def __init__(self, source: "Text") -> None:
        self.source = source

    def build(self) -> FragmentMetadata:
        return FragmentMetadata(
            style=self.source.style,
            justify=self.source.justify,
            overflow=self.source.overflow,
            no_wrap=self.source.no_wrap,
            end=self.source.end,
            tab_size=self.source.tab_size,
        )


class FragmentSequence:
    """A structured view of fragment ranges derived from divide offsets."""

    def __init__(self, ranges: Iterable[FragmentRange]) -> None:
        self._ranges: List[FragmentRange] = list(ranges)

    def __iter__(self) -> Iterator[FragmentRange]:
        return iter(self._ranges)

    def __len__(self) -> int:
        return len(self._ranges)

    def __getitem__(self, index: int) -> FragmentRange:
        return self._ranges[index]

    @property
    def line_ranges(self) -> List[tuple[int, int]]:
        return [(fragment.start, fragment.end) for fragment in self._ranges]

    @classmethod
    def from_offsets(cls, offsets: Iterable[int], *, text_length: int) -> "FragmentSequence":
        divide_offsets = [0, *offsets, text_length]
        line_ranges = list(zip(divide_offsets, divide_offsets[1:]))
        last_index = len(line_ranges) - 1
        return cls(
            FragmentRange(start=start, end=end, is_last=index == last_index)
            for index, (start, end) in enumerate(line_ranges)
        )


class FragmentFactory:
    """Create ``Text`` fragments with copied render metadata."""

    def __init__(self, source: "Text") -> None:
        self.source = source
        self.metadata = FragmentMetadataBuilder(source).build()

    def make(self, plain: str, *, is_last: bool) -> "Text":
        from .text import Text

        return Text(
            plain,
            style=self.metadata.style,
            justify=self.metadata.justify,
            overflow=self.metadata.overflow,
            no_wrap=self.metadata.no_wrap,
            end=self.metadata.end if is_last else self.metadata.end,
            tab_size=self.metadata.tab_size,
        )


def fragment_ranges(offsets: Iterable[int], *, text_length: int) -> Iterator[FragmentRange]:
    """Generate fragment ranges from divide offsets."""
    yield from FragmentSequence.from_offsets(offsets, text_length=text_length)


def make_fragment(source: "Text", plain: str, *, is_last: bool) -> "Text":
    """Create a text fragment with copied structural metadata."""
    return FragmentFactory(source).make(plain, is_last=is_last)
