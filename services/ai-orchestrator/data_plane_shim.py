"""
Cross-service shim re-exporting Block + BlockType from data-pipeline.

ai-orchestrator + data-pipeline ship as separate services with separate
requirements + separate Docker images. They MUST NOT import each
other's packages at runtime — Phase B-2 internal-split contract.

But the Stage 6 Block taxonomy lives in data-pipeline (where the
extractor runs). ai-orchestrator's DocSage Schema Discovery + AI
classifier + structured extractor consume Block objects.

This shim DUPLICATES the Block + BlockType definitions (tiny, frozen
dataclasses; no logic) so ai-orchestrator can type its inputs without
importing across the service boundary. The cost: keep this file in
sync with data-pipeline's silver/blocks.py. Both files are <100 LOC
+ change rarely.

When Pattern 5 lands and the bbox shape extends, update BOTH files
in the same commit per the cross-service drift discipline.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional, Tuple


class BlockType(str, Enum):
    """MUST match data-pipeline/silver/blocks.py BlockType exactly."""
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
    """MUST match data-pipeline/silver/blocks.py Bbox exactly.

    PDF user-space points, (x0, top, x1, bottom) — pdfplumber convention.
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
        return (self.x0, self.top, self.x1, self.bottom)


@dataclass(frozen=True)
class Block:
    """MUST match data-pipeline/silver/blocks.py Block exactly."""
    type:        BlockType
    page_idx:    int
    char_start:  int
    char_end:    int
    text:        str
    metadata:    dict[str, Any] = field(default_factory=dict)
    bbox:        Optional[Bbox] = None    # Pattern 5 (BE foundation 2026-05-19)

    @property
    def char_length(self) -> int:
        return self.char_end - self.char_start
