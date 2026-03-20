from __future__ import annotations

"""Helpers for redistributing ``Text`` spans across fragment ranges.

The original span redistribution code lived inline in ``Text.divide``. Pulling it
out into a dedicated helper makes the long-horizon problem contract easier to
reason about: text fragments now preserve both structural metadata and the
correct span slices after splitting, dividing, and wrapping.

The helpers below are intentionally boring and explicit. They do not try to
compress range handling into clever one-liners because the correctness surface
for span slicing is subtle: a span may start in one fragment and end several
fragments later, and each output slice must be re-based to fragment-local
coordinates without dropping zero-width guards or upsetting the original style
association.
"""

from dataclasses import dataclass
from typing import Iterable, List, Sequence, Tuple, TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover
    from .text import Span


LineRange = Tuple[int, int]


@dataclass(frozen=True)
class SpanSlice:
    """A span fragment targeted at a specific output line."""

    line_no: int
    start: int
    end: int
    style: object


class LineRangeIndex:
    """Binary-search helpers for locating fragment ranges."""

    def __init__(self, line_ranges: Sequence[LineRange]) -> None:
        self.line_ranges = list(line_ranges)
        self.line_count = len(self.line_ranges)

    def _range_contains(self, line_no: int, offset: int) -> bool:
        line_start, line_end = self.line_ranges[line_no]
        return line_start <= offset <= line_end

    def locate_start(self, offset: int) -> int:
        lower_bound = 0
        upper_bound = self.line_count - 1
        line_no = (lower_bound + upper_bound) // 2
        while True:
            line_start, line_end = self.line_ranges[line_no]
            if offset < line_start:
                upper_bound = line_no - 1
            elif offset > line_end:
                lower_bound = line_no + 1
            else:
                return line_no
            line_no = (lower_bound + upper_bound) // 2

    def locate_end(self, offset: int, *, start_line_no: int) -> int:
        line_start, line_end = self.line_ranges[start_line_no]
        if offset < line_end:
            return start_line_no
        lower_bound = start_line_no
        upper_bound = self.line_count - 1
        line_no = start_line_no
        while True:
            line_start, line_end = self.line_ranges[line_no]
            if offset < line_start:
                upper_bound = line_no - 1
            elif offset > line_end:
                lower_bound = line_no + 1
            else:
                return line_no
            line_no = (lower_bound + upper_bound) // 2


class SpanDistributor:
    """Redistribute spans over a sequence of fragment ranges.

    Each resulting ``SpanSlice`` is re-based to fragment-local coordinates so
    callers can append it directly to the target ``Text`` fragment without any
    additional offset correction.
    """

    def __init__(self, line_ranges: Sequence[LineRange]) -> None:
        self.line_ranges = list(line_ranges)
        self.index = LineRangeIndex(self.line_ranges)

    def slice_span(self, span: "Span") -> List[SpanSlice]:
        span_start, span_end, style = span
        start_line_no = self.index.locate_start(span_start)
        end_line_no = self.index.locate_end(span_end, start_line_no=start_line_no)
        slices: List[SpanSlice] = []
        for line_no in range(start_line_no, end_line_no + 1):
            line_start, line_end = self.line_ranges[line_no]
            new_start = max(0, span_start - line_start)
            new_end = min(span_end - line_start, line_end - line_start)
            if new_end > new_start:
                slices.append(SpanSlice(line_no=line_no, start=new_start, end=new_end, style=style))
        return slices

    def distribute(self, spans: Iterable["Span"]) -> List[List[SpanSlice]]:
        grouped: List[List[SpanSlice]] = [[] for _ in self.line_ranges]
        for span in spans:
            for span_slice in self.slice_span(span):
                grouped[span_slice.line_no].append(span_slice)
        return grouped
