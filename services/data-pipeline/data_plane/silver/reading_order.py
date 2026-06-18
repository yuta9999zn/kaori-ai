"""
Pattern 4 (MinerU borrow) — multi-column reading-order reconstruction.

Why this exists
---------------
pypdf's `page.extract_text()` walks the PDF content stream in raw
construction order. For 2-column layouts (Vietnamese regulations,
financial reports, academic papers) this interleaves left + right
columns line-by-line — the output looks like:

    Article 1 first sentence    Article 2 first sentence
    Article 1 second sentence   Article 2 second sentence

becomes

    Article 1 first sentence Article 2 first sentence
    Article 1 second sentence Article 2 second sentence

…which kills downstream comprehension. DocSage Schema Discovery, the
classifier + summariser AI nodes, and trace-based reasoning all see
nonsense prose.

Pattern 4 fix
-------------
Use pdfplumber's word-level bbox info to:
  1. Detect whether a page is multi-column (X-position histogram has
     2+ peaks separated by a clear valley).
  2. Cluster words into column bands by X-center.
  3. Within each band, sort top-to-bottom (by Y) and concatenate.
  4. Emit the reordered per-page text — drop-in replacement for the
     raw pypdf string.

Single-column pages (the vast majority of business docs: invoices,
receipts, contracts, CVs) get skipped — em return None and the caller
keeps the pypdf text. Costs ~0 for the common case.

Why not use pypdf's layout=True
-------------------------------
pypdf 3.x layout-aware extraction is unreliable on tables + nested
multi-column; em prefer pdfplumber which already ships in the
dependency tree for Pattern 3. One PDF parse, two outputs.

K-rules
-------
K-3 N/A — no LLM, deterministic Python. K-5 N/A — bytes never leave
process. side_effect_class = pure compute.
"""
from __future__ import annotations

import io
import math
from dataclasses import dataclass
from typing import Optional

import structlog

log = structlog.get_logger()


# ─── Knobs ──────────────────────────────────────────────────────────

# A page needs at least this many words for column detection to be
# meaningful. Sparse pages (cover sheets, title pages) skip detection.
_MIN_WORDS_FOR_DETECTION = 15

# Histogram bin count for X-center clustering. 30 bins ≈ 20-pt-wide
# bins on an A4 page (595pt wide) — enough resolution to find the
# valley between two columns without over-fragmenting.
_X_HIST_BINS = 30

# Two adjacent peaks count as "columns" only if the valley between
# them drops below this fraction of the smaller peak. Tighter = fewer
# false positives on single-column docs with one wide chart.
_VALLEY_RATIO = 0.35

# Y-tolerance for grouping words into lines within a column. PDF
# typography varies; em use page height / 200 as a rough line gap.
# (Tested empirically against VN regulations + reports.)
_LINE_GROUP_FRACTION = 1.0 / 200.0


# ─── Shape ──────────────────────────────────────────────────────────


@dataclass(frozen=True)
class _Word:
    """One pdfplumber-extracted word + bbox. We carry the bbox in
    PDF user-space (origin = bottom-left of page, units = points)."""
    text:    str
    x0:      float
    x1:      float
    top:     float       # distance from page top (pdfplumber convention)
    bottom:  float

    @property
    def x_center(self) -> float:
        return (self.x0 + self.x1) / 2.0


@dataclass(frozen=True)
class ColumnBand:
    """One detected column on a page. `x_min` and `x_max` define the
    horizontal span; words with x_center inside get assigned to this
    band."""
    x_min: float
    x_max: float

    @property
    def width(self) -> float:
        return self.x_max - self.x_min

    def contains(self, x_center: float) -> bool:
        return self.x_min <= x_center <= self.x_max


@dataclass(frozen=True)
class PageReadingOrder:
    """Reordered text for one page + which column detection branch we
    took. Callers use `text` directly; `column_count` is telemetry."""
    page_idx:     int
    text:         str        # reordered, '\n'-separated per logical line
    column_count: int        # 1 = single column (no reorder happened),
                             # 2+ = multi-column reorder applied
    word_count:   int


# ─── Detection ──────────────────────────────────────────────────────


def _x_histogram(words: list[_Word], page_width: float) -> list[int]:
    """Bin word X-centers across the page. Returns `_X_HIST_BINS` counts."""
    if page_width <= 0:
        return [0] * _X_HIST_BINS
    bin_width = page_width / _X_HIST_BINS
    hist = [0] * _X_HIST_BINS
    for w in words:
        idx = int(w.x_center / bin_width)
        if idx >= _X_HIST_BINS:
            idx = _X_HIST_BINS - 1
        elif idx < 0:
            idx = 0
        hist[idx] += 1
    return hist


def _find_peaks_and_valley(hist: list[int]) -> Optional[tuple[int, int, int]]:
    """Return (left_peak_bin, valley_bin, right_peak_bin) if the
    histogram shows a clear bimodal pattern, else None.

    Algorithm: pick the two largest non-adjacent bins as peaks; find
    the min bin strictly between them; require valley/min(peak) below
    threshold."""
    if not hist or max(hist) == 0:
        return None
    # Sort bins by count desc; pick top candidates.
    ranked = sorted(range(len(hist)), key=lambda i: hist[i], reverse=True)
    top1 = ranked[0]
    top2 = None
    for cand in ranked[1:]:
        if abs(cand - top1) >= 3:    # at least 3 bins apart (~10% of page)
            top2 = cand
            break
    if top2 is None:
        return None

    left, right = sorted((top1, top2))
    valley_slice = hist[left + 1 : right]
    if not valley_slice:
        return None
    valley_count = min(valley_slice)
    smaller_peak = min(hist[left], hist[right])
    if smaller_peak == 0:
        return None
    if valley_count / smaller_peak > _VALLEY_RATIO:
        return None
    # When multiple bins tie at the minimum (common for empty-band
    # valleys), pick the MIDPOINT of the tie range so the column
    # boundary lands between the clusters rather than against one
    # of the peaks.
    min_positions = [
        i for i, v in enumerate(valley_slice) if v == valley_count
    ]
    mid_in_slice = min_positions[len(min_positions) // 2]
    valley_idx = left + 1 + mid_in_slice
    return left, valley_idx, right


def detect_columns(
    words:      list[_Word],
    page_width: float,
) -> list[ColumnBand]:
    """Return ColumnBand list for a page. Single-column → 1 band
    covering the whole width. Multi-column → 2+ bands split at the
    detected valley(s).

    Today we detect at most 2 columns. 3+ column layouts (rare in VN
    business docs — mostly newspapers) fall back to single-column
    reading order; Pattern 4b can extend if needed.
    """
    if len(words) < _MIN_WORDS_FOR_DETECTION or page_width <= 0:
        return [ColumnBand(0.0, page_width)]

    hist = _x_histogram(words, page_width)
    peaks = _find_peaks_and_valley(hist)
    if peaks is None:
        return [ColumnBand(0.0, page_width)]

    _, valley_bin, _ = peaks
    bin_width = page_width / _X_HIST_BINS
    boundary = (valley_bin + 0.5) * bin_width   # mid-point of valley bin

    return [
        ColumnBand(0.0, boundary),
        ColumnBand(boundary, page_width),
    ]


# ─── Reorder ────────────────────────────────────────────────────────


def _words_to_lines(
    words:       list[_Word],
    page_height: float,
) -> list[str]:
    """Group words into lines by Y-position then sort each line by X.
    Returns a list[str] in top-to-bottom reading order."""
    if not words:
        return []
    line_tol = max(page_height * _LINE_GROUP_FRACTION, 2.0)

    # Sort by top Y (descending = page-top first in pdfplumber convention
    # where `top` measures from the page top).
    by_y = sorted(words, key=lambda w: w.top)

    lines: list[list[_Word]] = []
    current: list[_Word] = []
    current_top: Optional[float] = None

    for w in by_y:
        if current_top is None or abs(w.top - current_top) <= line_tol:
            current.append(w)
            # Anchor the line's Y to the FIRST word's top — subsequent
            # words can drift slightly without breaking the line.
            if current_top is None:
                current_top = w.top
        else:
            lines.append(current)
            current = [w]
            current_top = w.top
    if current:
        lines.append(current)

    return [
        " ".join(w.text for w in sorted(line, key=lambda x: x.x0))
        for line in lines
    ]


def reorder_page(
    words:       list[_Word],
    page_width:  float,
    page_height: float,
) -> tuple[str, int]:
    """Build the reading-order text for one page. Returns (text,
    column_count) where column_count is 1 (no reorder) or 2+
    (multi-column path taken)."""
    columns = detect_columns(words, page_width)
    if len(columns) == 1:
        # Single column — still group into lines so the output is
        # better than raw pdfplumber chars (some PDFs have wildly
        # interleaved word streams even in single-column pages).
        return "\n".join(_words_to_lines(words, page_height)), 1

    # Multi-column — bucket words by column then concatenate.
    bucket_lines: list[str] = []
    for col in columns:
        col_words = [w for w in words if col.contains(w.x_center)]
        bucket_lines.extend(_words_to_lines(col_words, page_height))
    return "\n".join(bucket_lines), len(columns)


# ─── Top-level API ──────────────────────────────────────────────────


def extract_reading_order_from_pdf(
    content: bytes,
) -> Optional[list[PageReadingOrder]]:
    """Pull reading-ordered text per page from PDF bytes via pdfplumber.

    Returns None when pdfplumber unavailable (caller falls back to
    pypdf output). On per-page parse failure, that page's entry is
    skipped — caller decides whether to use pypdf for that page or
    drop it.
    """
    try:
        import pdfplumber
    except ImportError:
        log.warning("reading_order.pdfplumber_unavailable")
        return None

    pages_out: list[PageReadingOrder] = []
    try:
        with pdfplumber.open(io.BytesIO(content)) as pdf:
            for page_idx, page in enumerate(pdf.pages):
                try:
                    raw_words = page.extract_words() or []
                except Exception as e:   # noqa: BLE001
                    log.warning("reading_order.page_extract_failed",
                                page_idx=page_idx, error=str(e))
                    continue
                words = [_Word(
                    text=w["text"],
                    x0=float(w["x0"]),
                    x1=float(w["x1"]),
                    top=float(w["top"]),
                    bottom=float(w["bottom"]),
                ) for w in raw_words if w.get("text")]
                if not words:
                    pages_out.append(PageReadingOrder(
                        page_idx=page_idx, text="",
                        column_count=1, word_count=0,
                    ))
                    continue
                text, ncols = reorder_page(
                    words,
                    page_width=float(page.width or 0),
                    page_height=float(page.height or 0),
                )
                pages_out.append(PageReadingOrder(
                    page_idx=page_idx, text=text,
                    column_count=ncols, word_count=len(words),
                ))
    except Exception as e:   # noqa: BLE001
        log.warning("reading_order.open_failed", error=str(e))
        return None

    return pages_out


def multi_column_page_count(pages: list[PageReadingOrder]) -> int:
    """Telemetry helper. Caller logs this so we can see whether
    Pattern 4 actually fires for real docs in prod."""
    return sum(1 for p in pages if p.column_count >= 2)
