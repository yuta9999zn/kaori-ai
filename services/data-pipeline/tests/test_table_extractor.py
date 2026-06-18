"""
Pattern 3 (MinerU borrow) — pdfplumber table extraction tests.

8-section template:
  1. Cell cleaning (None → "", whitespace collapse)
  2. Row filtering (empty rows + 1-cell tables dropped)
  3. ExtractedTable dataclass + counts
  4. Markdown rendering (header + body, pipe escaping, col padding)
  5. HTML rendering (entity escaping, structure)
  6. pdfplumber missing → graceful empty list
  7. pdfplumber raise on open → empty list, no crash
  8. Real PDF round-trip (synthetic fixture)
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from data_pipeline.data_plane.silver.table_extractor import (
    ExtractedTable,
    _clean_cell,
    _clean_rows,
    _is_useful_table,
    extract_tables_from_pdf,
    rows_to_html,
    rows_to_markdown,
)


# ═════════════════════════════════════════════════════════════════════
# 1. Cell cleaning
# ═════════════════════════════════════════════════════════════════════


class TestCleanCell:

    def test_none_becomes_empty(self):
        assert _clean_cell(None) == ""

    def test_strip_whitespace(self):
        assert _clean_cell("  hello  ") == "hello"

    def test_collapse_internal_whitespace(self):
        assert _clean_cell("foo\n\tbar   baz") == "foo bar baz"

    def test_non_string_coerced(self):
        assert _clean_cell(42) == "42"   # numbers get str()-ed

    def test_empty_string_stays(self):
        assert _clean_cell("") == ""


# ═════════════════════════════════════════════════════════════════════
# 2. Row filtering
# ═════════════════════════════════════════════════════════════════════


class TestCleanRows:

    def test_all_empty_row_dropped(self):
        rows = [["A", "B"], [None, None], ["1", "2"]]
        out = _clean_rows(rows)
        assert len(out) == 2
        assert out[0] == ["A", "B"]
        assert out[1] == ["1", "2"]

    def test_partial_empty_row_kept(self):
        """Row with at least 1 non-empty cell stays."""
        rows = [["A", "B"], ["", "v"]]
        out = _clean_rows(rows)
        assert len(out) == 2

    def test_none_row_dropped(self):
        rows = [["A"], None, ["B"]]   # type: ignore[list-item]
        out = _clean_rows(rows)
        assert len(out) == 2


class TestUsefulTable:

    def test_two_rows_two_cols_useful(self):
        assert _is_useful_table([["A", "B"], ["1", "2"]]) is True

    def test_one_row_one_cell_rejected(self):
        """Single cell in a single row — not a table, it's a textbox."""
        assert _is_useful_table([["just text"]]) is False

    def test_single_row_rejected(self):
        """A single row is a header without body — pdfplumber sometimes
        returns this from text blocks; drop."""
        assert _is_useful_table([["A", "B", "C"]]) is False

    def test_two_rows_one_col_rejected(self):
        """Two rows of one cell = vertical list, not a table."""
        assert _is_useful_table([["one"], ["two"]]) is False

    def test_empty_rejected(self):
        assert _is_useful_table([]) is False


# ═════════════════════════════════════════════════════════════════════
# 3. ExtractedTable counts
# ═════════════════════════════════════════════════════════════════════


class TestExtractedTable:

    def test_n_rows_and_cols(self):
        tbl = ExtractedTable(
            page_idx=2,
            rows=[["A", "B", "C"], ["1", "2", "3"], ["4", "5", "6"]],
            markdown="...",
            html="...",
        )
        assert tbl.n_rows == 3
        assert tbl.n_cols == 3

    def test_ragged_table_max_cols(self):
        """Some rows shorter than others — n_cols uses the max width."""
        tbl = ExtractedTable(
            page_idx=0,
            rows=[["A", "B"], ["1", "2", "3", "4"]],
            markdown="", html="",
        )
        assert tbl.n_cols == 4

    def test_empty_rows_zero_cols(self):
        tbl = ExtractedTable(page_idx=0, rows=[], markdown="", html="")
        assert tbl.n_rows == 0
        assert tbl.n_cols == 0


# ═════════════════════════════════════════════════════════════════════
# 4. Markdown rendering
# ═════════════════════════════════════════════════════════════════════


class TestMarkdownRendering:

    def test_basic_table(self):
        rows = [["Khách hàng", "Doanh thu"], ["KH-001", "1.500.000"]]
        md = rows_to_markdown(rows)
        assert "| Khách hàng | Doanh thu |" in md
        assert "|---|---|" in md
        assert "| KH-001 | 1.500.000 |" in md

    def test_pipe_inside_cell_escaped(self):
        rows = [["col1|with|pipes", "col2"], ["data", "more"]]
        md = rows_to_markdown(rows)
        assert r"col1\|with\|pipes" in md

    def test_ragged_rows_padded(self):
        rows = [["A", "B"], ["1", "2", "3"]]
        md = rows_to_markdown(rows)
        # Max cols = 3, header padded to 3
        assert "|---|---|---|" in md

    def test_empty_rows_returns_empty(self):
        assert rows_to_markdown([]) == ""

    def test_single_row_renders_header_only(self):
        """Useful only as a debugging case — _is_useful_table filters
        these before rendering normally."""
        md = rows_to_markdown([["A", "B"]])
        assert "| A | B |" in md
        assert "|---|---|" in md


# ═════════════════════════════════════════════════════════════════════
# 5. HTML rendering
# ═════════════════════════════════════════════════════════════════════


class TestHtmlRendering:

    def test_basic_html(self):
        rows = [["KH", "Doanh thu"], ["KH-001", "1.500.000₫"]]
        html = rows_to_html(rows)
        assert "<table>" in html and "</table>" in html
        assert "<thead><tr>" in html
        assert "<th>KH</th>" in html
        assert "<td>KH-001</td>" in html

    def test_entity_escaping(self):
        rows = [["Header"], ["<script>alert('xss')</script>"]]
        html = rows_to_html(rows)
        assert "&lt;script&gt;" in html
        assert "<script>" not in html.replace("<table>", "").replace("<thead>", "").replace("<tbody>", "").replace("<tr>", "").replace("<th>", "").replace("<td>", "")

    def test_ampersand_escaping(self):
        rows = [["a&b"], ["c&d"]]
        html = rows_to_html(rows)
        assert "a&amp;b" in html
        assert "c&amp;d" in html

    def test_empty_rows_returns_empty(self):
        assert rows_to_html([]) == ""


# ═════════════════════════════════════════════════════════════════════
# 6. pdfplumber unavailable
# ═════════════════════════════════════════════════════════════════════


class TestPdfPlumberUnavailable:

    def test_import_error_returns_empty(self):
        """If pdfplumber is missing the dep, extractor returns [] not
        raise. Callers don't have to special-case the missing dep."""
        with patch.dict("sys.modules", {"pdfplumber": None}):
            # When sys.modules[name] = None, `import` raises ImportError
            tables = extract_tables_from_pdf(b"%PDF-1.4 fake content")
        assert tables == []


# ═════════════════════════════════════════════════════════════════════
# 7. pdfplumber open raises
# ═════════════════════════════════════════════════════════════════════


class TestPdfPlumberOpenRaises:

    def test_open_failed_returns_empty(self):
        """Corrupted PDF that pdfplumber can't even open → empty list
        with logged warning, no crash."""
        fake_pdfplumber = MagicMock()
        fake_pdfplumber.open.side_effect = RuntimeError("malformed PDF")
        with patch.dict("sys.modules", {"pdfplumber": fake_pdfplumber}):
            tables = extract_tables_from_pdf(b"garbage")
        assert tables == []

    def test_per_page_failure_skips_page(self):
        """If page N's extract_tables() raises, skip THAT page but
        keep processing the rest."""
        from contextlib import contextmanager

        @contextmanager
        def fake_open(buf):
            class _Page:
                def __init__(self, ok):
                    self.ok = ok
                def extract_tables(self):
                    if not self.ok:
                        raise RuntimeError("page failed")
                    return [[["A", "B"], ["1", "2"]]]
            class _Pdf:
                pages = [_Page(True), _Page(False), _Page(True)]
            yield _Pdf()

        fake_pdfplumber = MagicMock()
        fake_pdfplumber.open = fake_open
        with patch.dict("sys.modules", {"pdfplumber": fake_pdfplumber}):
            tables = extract_tables_from_pdf(b"fake")
        # 2 successful pages (index 0 + 2), 1 skipped (index 1)
        assert len(tables) == 2
        assert tables[0].page_idx == 0
        assert tables[1].page_idx == 2


# ═════════════════════════════════════════════════════════════════════
# 8. End-to-end mock — extract one page with one table
# ═════════════════════════════════════════════════════════════════════


class TestEndToEnd:

    def test_single_table_extracted(self):
        from contextlib import contextmanager

        @contextmanager
        def fake_open(buf):
            class _Page:
                def extract_tables(self):
                    return [[
                        ["Mã KH",  "Doanh thu",   "Tháng"],
                        ["KH-001", "1.500.000",   "5"],
                        ["KH-002", "2.300.000",   "5"],
                    ]]
            class _Pdf:
                pages = [_Page()]
            yield _Pdf()

        fake_pdfplumber = MagicMock()
        fake_pdfplumber.open = fake_open
        with patch.dict("sys.modules", {"pdfplumber": fake_pdfplumber}):
            tables = extract_tables_from_pdf(b"fake-pdf")

        assert len(tables) == 1
        t = tables[0]
        assert t.page_idx == 0
        assert t.n_rows == 3
        assert t.n_cols == 3
        assert "| Mã KH | Doanh thu | Tháng |" in t.markdown
        assert "<th>Mã KH</th>" in t.html
        assert t.rows[1] == ["KH-001", "1.500.000", "5"]

    def test_filters_useless_tables(self):
        """pdfplumber sometimes returns 1-row "tables" from text in
        boxes — these get filtered by _is_useful_table."""
        from contextlib import contextmanager

        @contextmanager
        def fake_open(buf):
            class _Page:
                def extract_tables(self):
                    return [
                        [["just text in a box"]],     # 1-cell, dropped
                        [["A", "B"], ["1", "2"]],     # real 2x2, kept
                    ]
            class _Pdf:
                pages = [_Page()]
            yield _Pdf()

        fake_pdfplumber = MagicMock()
        fake_pdfplumber.open = fake_open
        with patch.dict("sys.modules", {"pdfplumber": fake_pdfplumber}):
            tables = extract_tables_from_pdf(b"fake")

        assert len(tables) == 1
        assert tables[0].rows == [["A", "B"], ["1", "2"]]

    def test_multi_page_multi_table(self):
        from contextlib import contextmanager

        @contextmanager
        def fake_open(buf):
            class _Page:
                def __init__(self, tbls):
                    self.tbls = tbls
                def extract_tables(self):
                    return self.tbls
            class _Pdf:
                pages = [
                    _Page([[["A", "B"], ["1", "2"]]]),
                    _Page([]),    # no tables on page 2
                    _Page([
                        [["X", "Y"], ["a", "b"]],
                        [["P", "Q"], ["c", "d"], ["e", "f"]],
                    ]),
                ]
            yield _Pdf()

        fake_pdfplumber = MagicMock()
        fake_pdfplumber.open = fake_open
        with patch.dict("sys.modules", {"pdfplumber": fake_pdfplumber}):
            tables = extract_tables_from_pdf(b"fake")

        # Page 0: 1 table, Page 1: 0, Page 2: 2 tables → 3 total
        assert len(tables) == 3
        assert [t.page_idx for t in tables] == [0, 2, 2]
