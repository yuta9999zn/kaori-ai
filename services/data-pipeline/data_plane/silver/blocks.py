"""
Block taxonomy — MinerU-inspired data model for Stage 6 doc extraction.

A Block is one logical unit of content (paragraph / title / table /
header / footer / list / image-ref / caption) at a specific page +
offset range. The taxonomy mirrors `opendatalab/MinerU` content_list
schema so future tooling that consumes MinerU JSON also speaks our
schema, but the implementation is pure-Python native (no vendor lib
per `docs/specs/MINERU_PATTERN_ANALYSIS.md`).

Why a typed dataclass + enum
----------------------------
1. Backwards compat with the old `text=str` ExtractResult — callers
   that never touch `blocks` keep working. New code (DocSage Schema
   Discovery v2, FE bbox highlights, table extraction Pattern 3)
   reads `blocks` to get structural signal.
2. Reading order is implicit in list position — no separate sort key
   needed. The extractor produces blocks in reading order; callers
   iterate the list.
3. `metadata` JSON-able dict for type-specific fields (table cells,
   list markers, image alt-text). Keeps the dataclass slim.

See docs/specs/UPLOAD_PIPELINE_FLOW.md §"What this commit ships".
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional, Tuple


class BlockType(str, Enum):
    """Taxonomy borrowed from MinerU + extended for Kaori needs.

    `text`         — paragraph prose
    `title`        — heading (h1 / h2 / h3 levels stored in metadata)
    `list`         — bulleted/numbered list (markers in metadata)
    `table`        — tabular data; rows in metadata['rows']
    `header`       — page header (repeats across pages — strip candidate)
    `footer`       — page footer (repeats — strip candidate)
    `page_number`  — folio (strip candidate)
    `image_ref`    — image extracted to separate storage (path in metadata)
    `caption`      — caption text for table/image (linked via metadata['parent_id'])
    `code`         — preformatted block (monospace)
    `quote`        — block quote
    `equation`     — math (LaTeX in metadata['latex']) — Phase 3 only
    """
    TEXT        = "text"
    TITLE       = "title"
    LIST        = "list"
    TABLE       = "table"
    HEADER      = "header"
    FOOTER      = "footer"
    PAGE_NUMBER = "page_number"
    IMAGE_REF   = "image_ref"
    CAPTION     = "caption"
    CODE        = "code"
    QUOTE       = "quote"
    EQUATION    = "equation"


@dataclass(frozen=True)
class Bbox:
    """Bounding box in PDF user-space points (origin = top-left of
    page per pdfplumber convention; x grows right, y grows down).

    Fields match pdfplumber's word/object bbox shape so populated
    values can flow through without coordinate transforms:
      x0    — left edge
      top   — top edge (distance from page top)
      x1    — right edge
      bottom — bottom edge (distance from page top, > top)

    Em normalise on (x0, top, x1, bottom) — same order pdfplumber
    returns from `page.find_tables()[i].bbox` and from
    `page.extract_words()[i]`. FE bbox highlight (Pattern 5 FE half
    when restructure resumes) consumes this shape directly.
    """
    x0:     float
    top:    float
    x1:     float
    bottom: float

    @property
    def width(self) -> float:
        return self.x1 - self.x0

    @property
    def height(self) -> float:
        return self.bottom - self.top

    @property
    def area(self) -> float:
        return self.width * self.height

    def as_tuple(self) -> Tuple[float, float, float, float]:
        """Return (x0, top, x1, bottom) — compatible with PIL.Image.crop
        + pdfplumber's bbox tuple convention so callers can pass straight
        through to image cropping for FE preview generation."""
        return (self.x0, self.top, self.x1, self.bottom)


@dataclass(frozen=True)
class Block:
    """One unit of content in a document. The 5 mandatory fields are
    enough for DocSage Schema Discovery; richer extractors fill
    `metadata` for table cells, list markers, etc."""
    type:        BlockType
    page_idx:    int          # 0-indexed page number
    char_start:  int          # offset into ExtractResult.text
    char_end:    int          # exclusive
    text:        str          # plain-text snippet of this block
    metadata:    dict[str, Any] = field(default_factory=dict)
    # Pattern 5 (BE foundation 2026-05-19). Optional — populated by
    # extractors that have bbox source (pdfplumber-driven TABLE blocks
    # today; per-paragraph TEXT blocks when chunking lands as Phase 2.6
    # follow-up). Backward-compat: existing callers + tests that don't
    # care about bbox keep working because em default to None.
    bbox:        Optional[Bbox] = None

    @property
    def char_length(self) -> int:
        return self.char_end - self.char_start


def text_from_blocks(blocks: list[Block]) -> str:
    """Re-assemble plain text from a block list. Returns the same
    string as walking blocks in order + joining their `.text` with
    '\\n' (matches the old `text=str` shape callers expect).

    Useful for tests + for callers that DON'T want the block detail
    but still want the readable text.
    """
    return "\n".join(b.text for b in blocks if b.text)


def blocks_by_type(blocks: list[Block], block_type: BlockType) -> list[Block]:
    """Filter helper — typical use: `tables = blocks_by_type(blocks,
    BlockType.TABLE)`. Pure list-comprehension wrap to give readable
    call sites."""
    return [b for b in blocks if b.type == block_type]


def blocks_excluding(blocks: list[Block], *excluded: BlockType) -> list[Block]:
    """Strip header/footer/page_number from a block list. Common
    pre-DocSage step:
        clean = blocks_excluding(blocks, BlockType.HEADER,
                                          BlockType.FOOTER,
                                          BlockType.PAGE_NUMBER)
    """
    excluded_set = set(excluded)
    return [b for b in blocks if b.type not in excluded_set]
