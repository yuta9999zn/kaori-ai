"""
Header / footer / page-number stripping — heuristic, pure Python.

A line is a header/footer candidate if:
  - It appears at the SAME relative position (top / bottom of page) on
    ≥3 pages (configurable via min_repeats).
  - Its text after normalisation (strip + lowercase + collapse runs of
    digits) repeats ≥min_repeats times.

The "normalisation" step is what catches page-number variations:
  "Page 1 of 12"  → "page N of N"
  "Page 2 of 12"  → "page N of N"  (same normalised form → matches)

False-positive guard: do NOT strip if a page has only 1-2 lines
(short pages = title pages / cover; their "header" might be the only
content).

Why heuristic instead of layout-based
-------------------------------------
True header/footer detection needs bbox + vertical position which
pypdf doesn't expose cleanly. The repeating-line heuristic catches
most real-world cases (page numbers, "© 2026 Kaori", document
title in header) at the cost of occasional misses on docs that
have unique content per page header. Phase 3 with pdfplumber's
bbox layer will give us bbox-based detection.

See docs/specs/MINERU_PATTERN_ANALYSIS.md Pattern 2.
"""
from __future__ import annotations

import re
from typing import Iterable


_DIGIT_RUN = re.compile(r"\d+")

# A line is "page-marker-like" if it's mostly a page indicator. We
# normalise digits ONLY on such lines so unrelated body lines that
# happen to differ by a single digit don't collide into the same
# normalised form and get false-positive stripped.
_PAGE_MARKER_PATTERNS = [
    re.compile(r"^\s*(page|trang|pg|pp)\b", re.IGNORECASE),       # English/Vietnamese page prefix
    re.compile(r"^\s*-?\s*\d+\s*-?\s*$"),                          # "12" or "- 12 -" standalone
    re.compile(r"^\s*\d+\s*/\s*\d+\s*$"),                          # "3/12"
    re.compile(r"^\s*\d+\s+of\s+\d+\s*$", re.IGNORECASE),          # "3 of 12"
]


def _is_page_marker_like(s: str) -> bool:
    """True if the line looks like a page number / "Trang X" marker.
    We're conservative — false negative is OK (header survives one
    more page); false positive (body line normalised to N) would
    silently strip body content which is WORSE."""
    for pat in _PAGE_MARKER_PATTERNS:
        if pat.match(s):
            return True
    return False


def _normalize(line: str) -> str:
    """Collapse the line into a comparable form. We normalise digits
    ONLY on page-marker-like lines, so "Body line 1B" + "Body line 2B"
    do NOT collide as the same form (which would false-strip them).
    Real page numbers ("Page 3 of 12" / "Trang 5 / 20") get the digit
    substitution they need to repeat-match across pages.
    """
    s = line.strip()
    if _is_page_marker_like(s):
        s = _DIGIT_RUN.sub("N", s)
    return s


def _candidate_lines(page_text: str, *, top_n: int, bottom_n: int) -> tuple[list[str], list[str]]:
    """Split a page's text into (top_lines, bottom_lines) for analysis.
    Only the first `top_n` non-empty lines + last `bottom_n` are
    candidates — body paragraphs in the middle of a page can't be
    headers/footers."""
    lines = [ln.strip() for ln in page_text.splitlines() if ln.strip()]
    if not lines:
        return [], []
    top = lines[:top_n]
    bottom = lines[-bottom_n:] if len(lines) > top_n else []
    return top, bottom


def detect_header_footer_lines(
    pages_text: list[str],
    *,
    min_repeats: int = 3,
    top_n:       int = 2,
    bottom_n:    int = 2,
) -> tuple[set[str], set[str]]:
    """Identify which line-strings to strip from the head + foot of
    each page. Returns (header_set, footer_set) of NORMALISED lines.

    A page can contribute at most `top_n` lines to header analysis +
    `bottom_n` to footer. The same physical line text can appear in
    both sets if it's symmetric (rare but possible).
    """
    if not pages_text or len(pages_text) < min_repeats:
        return set(), set()

    top_counts: dict[str, int] = {}
    bot_counts: dict[str, int] = {}

    for page in pages_text:
        top, bot = _candidate_lines(page, top_n=top_n, bottom_n=bottom_n)
        # Use a per-page set so a page repeating the same line in its
        # header twice still counts as 1 occurrence.
        for ln in set(_normalize(x) for x in top):
            top_counts[ln] = top_counts.get(ln, 0) + 1
        for ln in set(_normalize(x) for x in bot):
            bot_counts[ln] = bot_counts.get(ln, 0) + 1

    headers = {ln for ln, n in top_counts.items() if n >= min_repeats}
    footers = {ln for ln, n in bot_counts.items() if n >= min_repeats}
    return headers, footers


def strip_repeating_lines(
    pages_text: list[str],
    *,
    min_repeats:    int = 3,
    top_n:          int = 2,
    bottom_n:       int = 2,
    short_page_threshold: int = 3,
) -> list[str]:
    """Return a list of cleaned page texts with repeating header/footer
    lines removed. Pages that are too short (< short_page_threshold
    non-empty lines) are passed through untouched — their "header"
    might be the only content.

    Pure function — no I/O, no state. Safe to call on Bronze-side
    raw extracts before persisting.
    """
    if not pages_text or len(pages_text) < min_repeats:
        return list(pages_text)

    headers, footers = detect_header_footer_lines(
        pages_text,
        min_repeats=min_repeats,
        top_n=top_n,
        bottom_n=bottom_n,
    )
    if not headers and not footers:
        return list(pages_text)

    cleaned: list[str] = []
    for page in pages_text:
        lines = [ln for ln in page.splitlines()]
        non_empty = [ln for ln in lines if ln.strip()]
        if len(non_empty) < short_page_threshold:
            cleaned.append(page)
            continue

        # Strip header candidates from the top
        out_lines: list[str] = []
        body_started = False
        stripped_top_count = 0
        for ln in lines:
            if (not body_started
                    and stripped_top_count < top_n
                    and ln.strip()
                    and _normalize(ln) in headers):
                stripped_top_count += 1
                continue
            if ln.strip() and not (stripped_top_count < top_n and not body_started):
                body_started = True
            elif ln.strip():
                body_started = True
            out_lines.append(ln)

        # Strip footer candidates from the bottom — walk from the back
        # and drop matching lines until we hit a non-footer line.
        bottom_drop_count = 0
        while (out_lines
               and bottom_drop_count < bottom_n):
            tail = out_lines[-1]
            if tail.strip() and _normalize(tail) in footers:
                out_lines.pop()
                bottom_drop_count += 1
            elif not tail.strip():
                # Skip blank tail line but don't count it
                out_lines.pop()
            else:
                break

        cleaned.append("\n".join(out_lines))

    return cleaned
