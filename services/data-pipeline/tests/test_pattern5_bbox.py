"""
Pattern 5 (BE foundation) — bbox citation tests.

8-section template:
  1. Bbox dataclass shape (width, height, area, as_tuple, frozen)
  2. Block.bbox optional default + backward-compat with old callers
  3. ExtractedTable.bbox optional default + backward-compat
  4. table_extractor zips find_tables bbox with extract_tables rows
  5. table_extractor falls through when find_tables raises
     (rows still emit; bbox=None)
  6. docsage_extract propagates table bbox onto TABLE Block
  7. docsage_extract gracefully handles table without bbox (bbox=None)
  8. data_plane_shim Bbox matches data-pipeline Bbox exactly
     (cross-service contract pin per Phase B-2)
"""
from __future__ import annotations

import io
from unittest.mock import MagicMock, patch

import pytest

from data_pipeline.data_plane.silver.blocks import (
    Bbox,
    Block,
    BlockType,
)
from data_pipeline.data_plane.silver.table_extractor import (
    ExtractedTable,
    extract_tables_from_pdf,
)


# ═════════════════════════════════════════════════════════════════════
# 1. Bbox dataclass shape
# ═════════════════════════════════════════════════════════════════════


class TestBbox:

    def test_width_height_area(self):
        b = Bbox(x0=10.0, top=20.0, x1=110.0, bottom=70.0)
        assert b.width == 100.0
        assert b.height == 50.0
        assert b.area == 5000.0

    def test_as_tuple_pdfplumber_order(self):
        b = Bbox(x0=1.0, top=2.0, x1=3.0, bottom=4.0)
        # pdfplumber convention: (x0, top, x1, bottom)
        assert b.as_tuple() == (1.0, 2.0, 3.0, 4.0)

    def test_frozen(self):
        b = Bbox(x0=0, top=0, x1=10, bottom=10)
        with pytest.raises(Exception):   # FrozenInstanceError
            b.x0 = 99   # type: ignore[misc]

    def test_zero_size_bbox(self):
        """Degenerate bbox (point) is still valid — width/height/area = 0."""
        b = Bbox(x0=5.0, top=5.0, x1=5.0, bottom=5.0)
        assert b.width == 0.0
        assert b.height == 0.0
        assert b.area == 0.0


# ═════════════════════════════════════════════════════════════════════
# 2. Block.bbox optional + backward-compat
# ═════════════════════════════════════════════════════════════════════


class TestBlockBboxOptional:

    def test_default_none(self):
        """Pre-Pattern-5 callers don't pass bbox; em default to None."""
        b = Block(
            type=BlockType.TEXT, page_idx=0,
            char_start=0, char_end=10, text="hello",
        )
        assert b.bbox is None

    def test_with_bbox(self):
        bbox = Bbox(x0=50.0, top=100.0, x1=550.0, bottom=200.0)
        b = Block(
            type=BlockType.TABLE, page_idx=2,
            char_start=100, char_end=500, text="| A | B |",
            metadata={"rows": [["A", "B"]]},
            bbox=bbox,
        )
        assert b.bbox is bbox
        assert b.bbox.width == 500.0

    def test_block_still_frozen_with_bbox(self):
        b = Block(
            type=BlockType.TEXT, page_idx=0,
            char_start=0, char_end=5, text="hi",
            bbox=Bbox(0, 0, 10, 10),
        )
        with pytest.raises(Exception):
            b.bbox = None   # type: ignore[misc]


# ═════════════════════════════════════════════════════════════════════
# 3. ExtractedTable.bbox optional + backward-compat
# ═════════════════════════════════════════════════════════════════════


class TestExtractedTableBbox:

    def test_default_none(self):
        t = ExtractedTable(
            page_idx=0, rows=[["A", "B"], ["1", "2"]],
            markdown="x", html="x",
        )
        assert t.bbox is None

    def test_with_bbox_tuple(self):
        t = ExtractedTable(
            page_idx=0, rows=[["A"]], markdown="x", html="x",
            bbox=(10.0, 20.0, 100.0, 200.0),
        )
        assert t.bbox == (10.0, 20.0, 100.0, 200.0)


# ═════════════════════════════════════════════════════════════════════
# 4. table_extractor zips find_tables bbox with extract_tables rows
# ═════════════════════════════════════════════════════════════════════


def _mock_page(tables_rows: list, tables_bboxes: list, width: float = 600, height: float = 800):
    """Build a mock pdfplumber.Page that returns the given rows + bboxes."""
    page = MagicMock()
    page.width = width
    page.height = height
    page.extract_tables = MagicMock(return_value=tables_rows)
    # Each "table" in find_tables() exposes .bbox (and .rows but em don't
    # use that path). Build one MagicMock per bbox.
    table_objs = []
    for bbox in tables_bboxes:
        t = MagicMock()
        t.bbox = bbox
        table_objs.append(t)
    page.find_tables = MagicMock(return_value=table_objs)
    page.extract_words = MagicMock(return_value=[])
    return page


def _mock_pdf(pages):
    pdf = MagicMock()
    pdf.pages = pages
    ctx = MagicMock()
    ctx.__enter__ = MagicMock(return_value=pdf)
    ctx.__exit__ = MagicMock(return_value=False)
    return ctx


class TestTableExtractorBboxZip:

    def test_bbox_zipped_per_table(self):
        page = _mock_page(
            tables_rows=[
                [["A", "B"], ["1", "2"]],
                [["X", "Y"], ["3", "4"]],
            ],
            tables_bboxes=[
                (50.0, 100.0, 550.0, 200.0),
                (50.0, 250.0, 550.0, 400.0),
            ],
        )
        with patch("pdfplumber.open", return_value=_mock_pdf([page])):
            tables = extract_tables_from_pdf(b"%PDF-fake")
        assert len(tables) == 2
        assert tables[0].bbox == (50.0, 100.0, 550.0, 200.0)
        assert tables[1].bbox == (50.0, 250.0, 550.0, 400.0)

    def test_more_rows_than_bboxes_leaves_extras_as_none(self):
        """If find_tables returns fewer entries (rare; should match
        extract_tables), em set bbox=None for the trailing rows-only
        entries. Em refuses to fabricate."""
        page = _mock_page(
            tables_rows=[
                [["A", "B"], ["1", "2"]],
                [["X", "Y"], ["3", "4"]],
            ],
            tables_bboxes=[(10.0, 10.0, 100.0, 100.0)],   # only 1 bbox
        )
        with patch("pdfplumber.open", return_value=_mock_pdf([page])):
            tables = extract_tables_from_pdf(b"%PDF-fake")
        assert len(tables) == 2
        assert tables[0].bbox == (10.0, 10.0, 100.0, 100.0)
        assert tables[1].bbox is None


# ═════════════════════════════════════════════════════════════════════
# 5. table_extractor falls through when find_tables raises
# ═════════════════════════════════════════════════════════════════════


class TestTableExtractorBboxFallthrough:

    def test_find_tables_raise_keeps_rows_drops_bbox(self):
        page = MagicMock()
        page.width = 600
        page.height = 800
        page.extract_tables = MagicMock(return_value=[
            [["A", "B"], ["1", "2"]],
        ])
        page.find_tables = MagicMock(side_effect=RuntimeError("layout parser crashed"))
        page.extract_words = MagicMock(return_value=[])
        with patch("pdfplumber.open", return_value=_mock_pdf([page])):
            tables = extract_tables_from_pdf(b"%PDF-fake")
        # Rows still emit (table extraction = enrichment, not gate)
        assert len(tables) == 1
        # bbox dropped — em refuses to fabricate; FE will skip bbox highlight
        assert tables[0].bbox is None

    def test_bbox_non_numeric_drops_to_none(self):
        """If find_tables returns a bbox with garbage values (rare —
        e.g. weird PDF metadata), em coerce-fail and set None rather
        than emit corrupt coords."""
        page = _mock_page(
            tables_rows=[[["A", "B"], ["1", "2"]]],
            tables_bboxes=[("garbage", None, "nope", "bad")],
        )
        with patch("pdfplumber.open", return_value=_mock_pdf([page])):
            tables = extract_tables_from_pdf(b"%PDF-fake")
        assert len(tables) == 1
        assert tables[0].bbox is None


# ═════════════════════════════════════════════════════════════════════
# 6. docsage_extract propagates table bbox onto TABLE Block
# ═════════════════════════════════════════════════════════════════════


class TestDocsageBboxPropagation:

    def test_table_block_carries_bbox(self):
        """End-to-end: pdfplumber bbox → ExtractedTable.bbox →
        Block.bbox on the emitted TABLE block."""
        from data_pipeline.data_plane.silver.docsage_extract import _extract_pdf

        # Build a real-ish pypdf-compatible byte stream is heavy; em
        # instead patch pypdf + extract_tables_from_pdf + reading_order
        # to land in the block-emission path.
        with patch("data_pipeline.data_plane.silver.docsage_extract.pypdf") as fake_pypdf, \
              patch("data_pipeline.data_plane.silver.docsage_extract.extract_tables_from_pdf") as fake_tables, \
              patch("data_pipeline.data_plane.silver.docsage_extract.extract_reading_order_from_pdf",
                    return_value=None):
            # Fake reader: 1 page returning some text so char_count > 0
            page_mock = MagicMock()
            page_mock.extract_text = MagicMock(return_value="page body text")
            reader_mock = MagicMock()
            reader_mock.pages = [page_mock]
            reader_mock.is_encrypted = False
            fake_pypdf.PdfReader = MagicMock(return_value=reader_mock)

            fake_tables.return_value = [
                ExtractedTable(
                    page_idx=0,
                    rows=[["A", "B"], ["1", "2"]],
                    markdown="| A | B |\n|---|---|\n| 1 | 2 |",
                    html="<table>...</table>",
                    bbox=(72.0, 100.0, 540.0, 250.0),
                ),
            ]

            result = _extract_pdf(b"%PDF-fake")

        # Find the TABLE block + verify its bbox
        table_blocks = [b for b in (result.blocks or []) if b.type == BlockType.TABLE]
        assert len(table_blocks) == 1
        tb = table_blocks[0]
        assert tb.bbox is not None
        assert tb.bbox.x0 == 72.0
        assert tb.bbox.top == 100.0
        assert tb.bbox.x1 == 540.0
        assert tb.bbox.bottom == 250.0
        # width / height derived correctly
        assert tb.bbox.width == 468.0
        assert tb.bbox.height == 150.0


# ═════════════════════════════════════════════════════════════════════
# 7. docsage_extract handles missing bbox gracefully
# ═════════════════════════════════════════════════════════════════════


class TestDocsageBboxOptional:

    def test_table_without_bbox_emits_block_with_none(self):
        from data_pipeline.data_plane.silver.docsage_extract import _extract_pdf

        with patch("data_pipeline.data_plane.silver.docsage_extract.pypdf") as fake_pypdf, \
              patch("data_pipeline.data_plane.silver.docsage_extract.extract_tables_from_pdf") as fake_tables, \
              patch("data_pipeline.data_plane.silver.docsage_extract.extract_reading_order_from_pdf",
                    return_value=None):
            page_mock = MagicMock()
            page_mock.extract_text = MagicMock(return_value="page text")
            reader_mock = MagicMock()
            reader_mock.pages = [page_mock]
            reader_mock.is_encrypted = False
            fake_pypdf.PdfReader = MagicMock(return_value=reader_mock)

            fake_tables.return_value = [
                ExtractedTable(
                    page_idx=0,
                    rows=[["A"], ["1"]],
                    markdown="| A |\n|---|\n| 1 |",
                    html="<table>...</table>",
                    bbox=None,    # find_tables failed; rows still extracted
                ),
            ]

            result = _extract_pdf(b"%PDF-fake")

        table_blocks = [b for b in (result.blocks or []) if b.type == BlockType.TABLE]
        assert len(table_blocks) == 1
        assert table_blocks[0].bbox is None

    def test_text_block_bbox_is_none_today(self):
        """TEXT blocks (pypdf-derived, 1-per-page coarse) don't carry
        bbox in v0 — page-level bbox would be useless for FE. Phase 2.6
        follow-up adds paragraph-level chunking + per-chunk bbox.

        This test pins the v0 contract so a future contributor knows
        the gap is deliberate."""
        from data_pipeline.data_plane.silver.docsage_extract import _extract_pdf

        with patch("data_pipeline.data_plane.silver.docsage_extract.pypdf") as fake_pypdf, \
              patch("data_pipeline.data_plane.silver.docsage_extract.extract_tables_from_pdf",
                    return_value=[]), \
              patch("data_pipeline.data_plane.silver.docsage_extract.extract_reading_order_from_pdf",
                    return_value=None):
            page_mock = MagicMock()
            page_mock.extract_text = MagicMock(return_value="page body text")
            reader_mock = MagicMock()
            reader_mock.pages = [page_mock]
            reader_mock.is_encrypted = False
            fake_pypdf.PdfReader = MagicMock(return_value=reader_mock)

            result = _extract_pdf(b"%PDF-fake")

        text_blocks = [b for b in (result.blocks or []) if b.type == BlockType.TEXT]
        assert len(text_blocks) == 1
        # v0 contract: TEXT blocks have bbox=None until paragraph
        # chunking lands as Phase 2.6 follow-up
        assert text_blocks[0].bbox is None


# ═════════════════════════════════════════════════════════════════════
# 8. Cross-service shim contract — data-pipeline Bbox == ai-orch shim Bbox
# ═════════════════════════════════════════════════════════════════════


class TestCrossServiceShim:

    def test_shim_bbox_fields_match(self):
        """data-pipeline owns the canonical Bbox; ai-orchestrator dupes
        for compile-independence per Phase B-2 boundary. Drift between
        them = bugs the type checker can't catch (different identities,
        same shape). Em pin the shape match here."""
        # Import the ai-orch shim's Bbox via path manipulation (the
        # shim lives in a sibling service tree). Em make the test
        # robust to ai-orch not being importable in data-pipeline's
        # test environment — skip when sibling tree not on sys.path.
        import importlib.util, sys
        from pathlib import Path

        # parents: [0]=tests, [1]=data-pipeline, [2]=services, [3]=repo root
        shim_path = (
            Path(__file__).resolve().parents[2]
            / "ai-orchestrator" / "data_plane_shim.py"
        )
        if not shim_path.exists():
            pytest.skip(f"ai-orch shim not found at {shim_path}")

        spec = importlib.util.spec_from_file_location(
            "ai_orch_shim_for_test", str(shim_path),
        )
        if spec is None or spec.loader is None:
            pytest.skip("could not load ai-orch shim spec")
        mod = importlib.util.module_from_spec(spec)
        sys.modules["ai_orch_shim_for_test"] = mod
        try:
            spec.loader.exec_module(mod)
        except Exception as e:
            pytest.skip(f"ai-orch shim failed to import: {e}")

        ShimBbox = mod.Bbox
        from dataclasses import fields
        canonical = {(f.name, f.type) for f in fields(Bbox)}
        shimmed = {(f.name, f.type) for f in fields(ShimBbox)}
        assert canonical == shimmed, (
            "data-pipeline Bbox and ai-orchestrator data_plane_shim Bbox "
            "drifted. Update BOTH files in the same commit (Phase B-2 "
            "cross-service drift discipline)."
        )

    def test_shim_block_has_bbox_field(self):
        """ai-orch Block mirror must carry the new bbox field too."""
        import importlib.util, sys
        from pathlib import Path

        # parents: [0]=tests, [1]=data-pipeline, [2]=services, [3]=repo root
        shim_path = (
            Path(__file__).resolve().parents[2]
            / "ai-orchestrator" / "data_plane_shim.py"
        )
        if not shim_path.exists():
            pytest.skip(f"ai-orch shim not found at {shim_path}")
        spec = importlib.util.spec_from_file_location(
            "ai_orch_shim_for_test2", str(shim_path),
        )
        mod = importlib.util.module_from_spec(spec)
        sys.modules["ai_orch_shim_for_test2"] = mod
        try:
            spec.loader.exec_module(mod)   # type: ignore[union-attr]
        except Exception as e:
            pytest.skip(f"ai-orch shim failed to import: {e}")

        from dataclasses import fields
        shim_block_fields = {f.name for f in fields(mod.Block)}
        assert "bbox" in shim_block_fields, (
            "ai-orch shim Block missing bbox field — update mirror "
            "in same commit as data-pipeline Block change."
        )
