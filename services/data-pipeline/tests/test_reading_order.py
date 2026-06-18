"""
Pattern 4 (MinerU borrow) — multi-column reading-order tests.

8-section template:
  1. _Word + ColumnBand + PageReadingOrder shapes
  2. _x_histogram bin assignment
  3. _find_peaks_and_valley — bimodal vs unimodal
  4. detect_columns — single / 2-column / sparse-page fallback
  5. _words_to_lines — line grouping by Y + sort by X
  6. reorder_page end-to-end on synthetic 2-column page
  7. extract_reading_order_from_pdf integration (pdfplumber-gated)
  8. ExtractResult.multi_column_pages_reordered telemetry surfaces
     in the docsage_extract wiring
"""
from __future__ import annotations

import io
from pathlib import Path

import pytest

from data_pipeline.data_plane.silver.reading_order import (
    ColumnBand,
    PageReadingOrder,
    _MIN_WORDS_FOR_DETECTION,
    _Word,
    _find_peaks_and_valley,
    _words_to_lines,
    _x_histogram,
    detect_columns,
    extract_reading_order_from_pdf,
    multi_column_page_count,
    reorder_page,
)


REPO = Path(__file__).resolve().parent.parent.parent.parent
VINFAST_PDF_DIR = REPO / "data" / "vinfast" / "vinfast_test_bundle" / "sample_documents"


# Page width / height in PDF user-space points (A4 = 595 × 842 ≈ ).
PAGE_W = 600.0
PAGE_H = 800.0


def _w(text: str, x0: float, x1: float, top: float, bottom: float = None) -> _Word:
    """Compact word factory for synthetic test pages."""
    return _Word(text=text, x0=x0, x1=x1, top=top,
                  bottom=bottom if bottom is not None else top + 10)


# ═════════════════════════════════════════════════════════════════════
# 1. Shape contracts
# ═════════════════════════════════════════════════════════════════════


class TestShapes:

    def test_word_x_center_midpoint(self):
        assert _w("hi", 100, 140, 50).x_center == 120.0

    def test_column_band_contains(self):
        col = ColumnBand(x_min=0.0, x_max=300.0)
        assert col.contains(150.0) is True
        assert col.contains(400.0) is False
        # Boundary inclusive
        assert col.contains(0.0) is True
        assert col.contains(300.0) is True
        assert col.width == 300.0

    def test_page_reading_order_dataclass(self):
        p = PageReadingOrder(page_idx=2, text="hello", column_count=2,
                              word_count=42)
        assert p.page_idx == 2
        assert p.column_count == 2
        assert p.word_count == 42


# ═════════════════════════════════════════════════════════════════════
# 2. X-histogram binning
# ═════════════════════════════════════════════════════════════════════


class TestXHistogram:

    def test_uniform_distribution_fills_bins(self):
        # 30 words spread evenly across page
        words = [_w("x", x0=20*i, x1=20*i + 5, top=100) for i in range(30)]
        hist = _x_histogram(words, page_width=600.0)
        # Every bin should have at least 1 word, sum = total words
        assert sum(hist) == 30

    def test_left_column_only(self):
        words = [_w("x", x0=50, x1=100, top=100) for _ in range(20)]
        hist = _x_histogram(words, page_width=600.0)
        # Concentrated in early bins; right half should be all 0
        assert sum(hist[:5]) == 20
        assert sum(hist[15:]) == 0

    def test_zero_width_safe(self):
        hist = _x_histogram([_w("x", 10, 20, 100)], page_width=0)
        assert hist == [0] * 30

    def test_out_of_range_x_clipped_to_last_bin(self):
        # A word extending beyond page_width must still land in a valid bin
        words = [_w("x", x0=599, x1=605, top=100)]
        hist = _x_histogram(words, page_width=600.0)
        assert sum(hist) == 1


# ═════════════════════════════════════════════════════════════════════
# 3. Peak + valley detection
# ═════════════════════════════════════════════════════════════════════


class TestFindPeaks:

    def test_clear_bimodal(self):
        # 30 bins: peaks at idx 5 and 22; valley near 12-15
        hist = [0] * 30
        hist[5]  = 100   # left peak
        hist[22] = 100   # right peak
        for i in range(12, 16):
            hist[i] = 2   # very low valley
        result = _find_peaks_and_valley(hist)
        assert result is not None
        left, valley, right = result
        assert left < valley < right
        assert (left, right) == (5, 22)

    def test_unimodal_no_valley(self):
        hist = [0] * 30
        hist[10] = 100
        hist[11] = 80
        hist[12] = 60
        result = _find_peaks_and_valley(hist)
        assert result is None

    def test_two_adjacent_peaks_skipped(self):
        # Adjacent peaks → no real valley → single column
        hist = [0] * 30
        hist[10] = 100
        hist[11] = 100
        result = _find_peaks_and_valley(hist)
        assert result is None

    def test_high_valley_rejects(self):
        # Valley too tall relative to peaks → still treat as single column.
        # Fill the ENTIRE inter-peak range so there's no narrow 0-bin
        # gap right next to a peak; the min-of-valley is then 60.
        hist = [0] * 30
        hist[5]  = 100
        hist[22] = 100
        for i in range(6, 22):
            hist[i] = 60     # 60% of peak → above _VALLEY_RATIO threshold
        result = _find_peaks_and_valley(hist)
        assert result is None

    def test_empty_hist_safe(self):
        assert _find_peaks_and_valley([]) is None
        assert _find_peaks_and_valley([0] * 30) is None


# ═════════════════════════════════════════════════════════════════════
# 4. detect_columns
# ═════════════════════════════════════════════════════════════════════


class TestDetectColumns:

    def test_sparse_page_single_column(self):
        words = [_w("x", 100, 150, 50)]    # 1 word < threshold
        cols = detect_columns(words, page_width=PAGE_W)
        assert len(cols) == 1
        assert cols[0].x_min == 0.0
        assert cols[0].x_max == PAGE_W

    def test_genuine_single_column(self):
        # 20 words all in middle of page → single
        words = [_w(f"w{i}", 200, 260, 50 + i*15)
                  for i in range(20)]
        cols = detect_columns(words, page_width=PAGE_W)
        assert len(cols) == 1

    def test_two_columns_detected(self):
        # 20 words on left band + 20 on right band, no overlap
        left = [_w(f"L{i}", 50,  150, 50 + i*15) for i in range(20)]
        right = [_w(f"R{i}", 400, 500, 50 + i*15) for i in range(20)]
        cols = detect_columns(left + right, page_width=PAGE_W)
        assert len(cols) == 2
        # Boundary lies somewhere between the two clusters
        boundary = cols[0].x_max
        assert 150 < boundary < 400

    def test_zero_page_width_returns_single(self):
        cols = detect_columns([_w("x", 0, 10, 0)] * 20, page_width=0)
        assert len(cols) == 1


# ═════════════════════════════════════════════════════════════════════
# 5. _words_to_lines
# ═════════════════════════════════════════════════════════════════════


class TestWordsToLines:

    def test_empty_returns_empty(self):
        assert _words_to_lines([], page_height=800.0) == []

    def test_groups_same_y_into_one_line_sorted_by_x(self):
        words = [
            _w("third",  300, 350, 100),
            _w("first",  50,  100, 100),
            _w("second", 150, 200, 100),
        ]
        lines = _words_to_lines(words, page_height=800.0)
        assert lines == ["first second third"]

    def test_separate_lines_when_y_differs(self):
        words = [
            _w("topA", 50, 100, 50),
            _w("topB", 200, 250, 50),
            _w("botA", 50, 100, 200),
            _w("botB", 200, 250, 200),
        ]
        lines = _words_to_lines(words, page_height=800.0)
        assert lines == ["topA topB", "botA botB"]

    def test_close_y_still_one_line(self):
        # Within tolerance ≈ 800/200 = 4pt → tiny drift counts as same line
        words = [
            _w("a", 50, 100, 100),
            _w("b", 150, 200, 102),    # 2pt below
        ]
        lines = _words_to_lines(words, page_height=800.0)
        assert lines == ["a b"]


# ═════════════════════════════════════════════════════════════════════
# 6. reorder_page — end-to-end
# ═════════════════════════════════════════════════════════════════════


class TestReorderPage:

    def test_two_column_reorder(self):
        """Words appear in raw scan order interleaving columns; reorder
        must produce 'left col top → bottom' then 'right col top → bottom'."""
        # Simulate raw scan order: line1 left, line1 right, line2 left, ...
        words = [
            _w("L1a", 50, 100, 50),  _w("R1a", 400, 450, 50),
            _w("L1b", 110, 160, 50), _w("R1b", 460, 510, 50),
            _w("L2",  50,  150, 100), _w("R2",  400, 500, 100),
            _w("L3",  50,  150, 150), _w("R3",  400, 500, 150),
        ]
        # Pad to reach _MIN_WORDS_FOR_DETECTION
        for i in range(_MIN_WORDS_FOR_DETECTION):
            words.append(_w(f"L{4+i}", 50, 150, 200 + i*15))
            words.append(_w(f"R{4+i}", 400, 500, 200 + i*15))
        text, ncols = reorder_page(words, page_width=PAGE_W, page_height=PAGE_H)
        assert ncols == 2
        # Left column lines should appear BEFORE right column lines
        # in the reordered output
        left_pos = text.find("L1a")
        right_pos = text.find("R1a")
        assert left_pos >= 0 and right_pos >= 0
        assert left_pos < right_pos, (
            f"Left column should be reordered ahead of right; "
            f"got left={left_pos} right={right_pos}\n{text}"
        )

    def test_single_column_returns_one(self):
        words = [_w(f"w{i}", 200, 260, 50 + i*15) for i in range(20)]
        text, ncols = reorder_page(words, page_width=PAGE_W, page_height=PAGE_H)
        assert ncols == 1
        # Text still useful (line-grouped)
        assert "w0" in text and "w19" in text


# ═════════════════════════════════════════════════════════════════════
# 7. extract_reading_order_from_pdf — integration on real PDF
# ═════════════════════════════════════════════════════════════════════


class TestExtractReadingOrderFromPdf:

    @pytest.fixture
    def vinfast_po_bytes(self) -> bytes:
        path = VINFAST_PDF_DIR / "PO_VF-WO-26057_DealerPurchaseOrder.pdf"
        if not path.exists():
            pytest.skip(f"VinFast PDF fixture not found at {path}")
        return path.read_bytes()

    def test_returns_list_when_pdfplumber_available(self, vinfast_po_bytes):
        result = extract_reading_order_from_pdf(vinfast_po_bytes)
        # On systems where pdfplumber is installed, this returns
        # a list; otherwise None (skip).
        if result is None:
            pytest.skip("pdfplumber not installed in this environment")
        assert isinstance(result, list)
        assert all(isinstance(p, PageReadingOrder) for p in result)

    def test_returns_none_on_corrupt_bytes(self):
        result = extract_reading_order_from_pdf(b"NOT A PDF AT ALL")
        # Either None (open_failed) or empty list — both are safe
        assert result is None or result == []

    def test_multi_column_page_count_helper(self):
        pages = [
            PageReadingOrder(page_idx=0, text="x", column_count=1, word_count=10),
            PageReadingOrder(page_idx=1, text="y", column_count=2, word_count=40),
            PageReadingOrder(page_idx=2, text="z", column_count=2, word_count=35),
        ]
        assert multi_column_page_count(pages) == 2


# ═════════════════════════════════════════════════════════════════════
# 8. ExtractResult.multi_column_pages_reordered telemetry surfaces
# ═════════════════════════════════════════════════════════════════════


class TestDocsageExtractWiring:

    @pytest.fixture
    def vinfast_po_bytes(self) -> bytes:
        path = VINFAST_PDF_DIR / "PO_VF-WO-26057_DealerPurchaseOrder.pdf"
        if not path.exists():
            pytest.skip(f"VinFast PDF fixture not found at {path}")
        return path.read_bytes()

    def test_field_present_default_zero(self):
        """ExtractResult initialises new field to 0 (backward compat)."""
        from data_pipeline.data_plane.silver.docsage_extract import ExtractResult
        r = ExtractResult(text="", page_offsets=[0], status="failed")
        assert r.multi_column_pages_reordered == 0

    def test_invoice_pdf_zero_or_low_count(self, vinfast_po_bytes):
        """VinFast PO is a single-column document — telemetry stays at 0."""
        from data_pipeline.data_plane.silver.docsage_extract import extract_text
        r = extract_text(content=vinfast_po_bytes, mime_type="application/pdf")
        # Single-column doc; 0 or 1 (false positive tolerance) expected.
        assert r.multi_column_pages_reordered <= 1

    def test_docx_path_field_zero(self):
        """DOCX path doesn't apply Pattern 4 (no bbox); field stays 0."""
        from io import BytesIO
        from docx import Document
        from data_pipeline.data_plane.silver.docsage_extract import extract_text
        doc = Document()
        doc.add_paragraph("Sample paragraph.")
        buf = BytesIO()
        doc.save(buf)
        r = extract_text(
            content=buf.getvalue(),
            mime_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            filename="x.docx",
        )
        # DOCX path bypasses _extract_pdf entirely; default 0 is fine
        assert r.multi_column_pages_reordered == 0

    def test_corrupt_pdf_field_zero(self):
        """Failure path keeps field at default 0 (no crash on access)."""
        from data_pipeline.data_plane.silver.docsage_extract import extract_text
        r = extract_text(content=b"not a pdf", mime_type="application/pdf")
        assert r.status == "failed"
        assert r.multi_column_pages_reordered == 0
