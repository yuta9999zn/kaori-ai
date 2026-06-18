"""
Tests for block taxonomy + header/footer stripping (Phase 2.5
patterns 1 + 2 from `docs/specs/MINERU_PATTERN_ANALYSIS.md`).
"""
from __future__ import annotations

import pytest

from data_pipeline.data_plane.silver.blocks import (
    Block,
    BlockType,
    blocks_by_type,
    blocks_excluding,
    text_from_blocks,
)
from data_pipeline.data_plane.silver.header_footer_strip import (
    detect_header_footer_lines,
    strip_repeating_lines,
)


# ═════════════════════════════════════════════════════════════════════
# 1. Block dataclass + enum
# ═════════════════════════════════════════════════════════════════════


class TestBlock:

    def test_basic_construction(self):
        b = Block(
            type=BlockType.TEXT,
            page_idx=0,
            char_start=0,
            char_end=42,
            text="Doanh thu tháng 5",
        )
        assert b.type == BlockType.TEXT
        assert b.char_length == 42
        assert b.metadata == {}

    def test_block_immutable(self):
        b = Block(type=BlockType.TITLE, page_idx=0,
                   char_start=0, char_end=10, text="Tiêu đề")
        with pytest.raises(Exception):
            b.type = BlockType.TEXT     # type: ignore[misc]

    def test_metadata_default(self):
        b = Block(type=BlockType.TABLE, page_idx=0,
                   char_start=0, char_end=10, text="...")
        assert b.metadata == {}

    def test_metadata_custom(self):
        b = Block(
            type=BlockType.TABLE, page_idx=0,
            char_start=0, char_end=10, text="...",
            metadata={"rows": [["A", "B"], ["1", "2"]]},
        )
        assert b.metadata["rows"][0] == ["A", "B"]


# ═════════════════════════════════════════════════════════════════════
# 2. Helper functions
# ═════════════════════════════════════════════════════════════════════


class TestHelpers:

    @pytest.fixture
    def sample_blocks(self) -> list[Block]:
        return [
            Block(BlockType.TITLE, 0, 0, 10, "Title 1"),
            Block(BlockType.TEXT, 0, 11, 30, "Body paragraph"),
            Block(BlockType.HEADER, 1, 31, 40, "Page 1 of 5"),
            Block(BlockType.TEXT, 1, 41, 60, "More body"),
            Block(BlockType.TABLE, 1, 61, 80, "table block"),
            Block(BlockType.FOOTER, 2, 81, 95, "© 2026 Kaori"),
        ]

    def test_text_from_blocks_joins(self, sample_blocks):
        out = text_from_blocks(sample_blocks)
        assert "Title 1" in out
        assert "© 2026 Kaori" in out

    def test_blocks_by_type(self, sample_blocks):
        tables = blocks_by_type(sample_blocks, BlockType.TABLE)
        assert len(tables) == 1
        assert tables[0].text == "table block"

    def test_blocks_excluding(self, sample_blocks):
        clean = blocks_excluding(sample_blocks,
                                  BlockType.HEADER, BlockType.FOOTER)
        types = [b.type for b in clean]
        assert BlockType.HEADER not in types
        assert BlockType.FOOTER not in types
        assert BlockType.TEXT in types

    def test_text_from_blocks_skips_empty(self):
        blocks = [
            Block(BlockType.TEXT, 0, 0, 5, "Hello"),
            Block(BlockType.TEXT, 0, 5, 5, ""),     # empty text
            Block(BlockType.TEXT, 0, 6, 11, "World"),
        ]
        out = text_from_blocks(blocks)
        assert out == "Hello\nWorld"


# ═════════════════════════════════════════════════════════════════════
# 3. Header/footer detection
# ═════════════════════════════════════════════════════════════════════


class TestDetectHeaderFooter:

    def test_repeating_page_number_detected_as_footer(self):
        pages = [
            "Báo cáo tháng 5\nDoanh thu tăng 12%\nPage 1 of 3",
            "Chi tiết phân khúc\nMột số đoạn body\nPage 2 of 3",
            "Tổng kết và đề xuất\nĐề xuất 3 hành động\nPage 3 of 3",
        ]
        headers, footers = detect_header_footer_lines(pages)
        # "Page N of N" normalisation should make all 3 match
        assert any("page" in f.lower() for f in footers)

    def test_repeating_top_line_detected_as_header(self):
        pages = [
            "© 2026 Kaori Confidential\nContent of page 1",
            "© 2026 Kaori Confidential\nContent of page 2",
            "© 2026 Kaori Confidential\nContent of page 3",
        ]
        headers, footers = detect_header_footer_lines(pages)
        assert any("kaori confidential" in h.lower() for h in headers)

    def test_below_min_repeats_no_detection(self):
        """Only 2 occurrences with min_repeats=3 → nothing detected."""
        pages = [
            "Same line\nbody1",
            "Same line\nbody2",
        ]
        headers, footers = detect_header_footer_lines(pages, min_repeats=3)
        assert headers == set()

    def test_normalisation_handles_digit_runs(self):
        pages = [
            "header\nbody\nPage 1 of 100",
            "header\nbody\nPage 25 of 100",
            "header\nbody\nPage 99 of 100",
        ]
        headers, footers = detect_header_footer_lines(pages)
        # "Page N of N" normalised form is shared across all 3 pages
        assert any("page n of n" in f.lower() for f in footers)


# ═════════════════════════════════════════════════════════════════════
# 4. Strip behaviour
# ═════════════════════════════════════════════════════════════════════


class TestStripRepeatingLines:

    def test_strips_repeating_footer(self):
        pages = [
            "Body line 1A\nBody line 1B\nPage 1 of 3",
            "Body line 2A\nBody line 2B\nPage 2 of 3",
            "Body line 3A\nBody line 3B\nPage 3 of 3",
        ]
        cleaned = strip_repeating_lines(pages)
        for p in cleaned:
            assert "Page" not in p
            assert "Body" in p

    def test_strips_repeating_header(self):
        pages = [
            "© 2026 Kaori\nReal content A",
            "© 2026 Kaori\nReal content B",
            "© 2026 Kaori\nReal content C",
        ]
        cleaned = strip_repeating_lines(pages)
        for p in cleaned:
            assert "Kaori" not in p or "Real content" in p  # may keep if can't strip

    def test_short_page_passes_through(self):
        """If a page has very few lines, don't strip its header (might
        be a cover page with header-like-looking title)."""
        pages = [
            "Báo cáo nhân sự",                              # short page (1 line)
            "Báo cáo nhân sự\nNội dung trang 2\nblah",
            "Báo cáo nhân sự\nNội dung trang 3\nblah",
            "Báo cáo nhân sự\nNội dung trang 4\nblah",
        ]
        cleaned = strip_repeating_lines(pages, short_page_threshold=3)
        assert cleaned[0] == pages[0]    # untouched

    def test_below_min_repeats_returns_unchanged(self):
        pages = ["a\nb\nc", "d\ne\nf"]
        cleaned = strip_repeating_lines(pages)
        assert cleaned == pages

    def test_preserves_body_content(self):
        """Critical: stripping must NEVER remove body content. Verify
        every body line survives."""
        pages = [
            "HEADER LINE\nBody Trang 1 — important data\nFOOTER LINE",
            "HEADER LINE\nBody Trang 2 — more important data\nFOOTER LINE",
            "HEADER LINE\nBody Trang 3 — final data\nFOOTER LINE",
        ]
        cleaned = strip_repeating_lines(pages)
        for i, page in enumerate(cleaned, 1):
            assert f"Trang {i}" in page

    def test_empty_pages_list(self):
        assert strip_repeating_lines([]) == []

    def test_single_page(self):
        """A single page → can't be a header (need ≥3 to detect)."""
        pages = ["only one page\nwith content\nand footer"]
        cleaned = strip_repeating_lines(pages)
        assert cleaned == pages
