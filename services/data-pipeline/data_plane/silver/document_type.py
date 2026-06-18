"""
Document type detection — first stage of bifurcated upload pipeline.

Splits uploads into STRUCTURED (CSV/XLSX/JSON) vs UNSTRUCTURED
(PDF/DOCX/image) so the downstream silver path knows whether to
parse directly (DataFrame route) or extract → block taxonomy →
DocSage Schema Discovery (LLM route).

Why magic bytes
---------------
Browsers + Office on Vietnamese laptops often send
`application/octet-stream` for Excel uploads. Filename extension
alone is unreliable when files come from Email attachments. We
combine mime + extension + magic bytes; magic wins on disagreement.

Why a dedicated enum
--------------------
Downstream code in `docsage_extract.py` / `bronze/ingestor.py` used
to inspect `mime_type.startswith(...)` strings — brittle. Returning a
typed enum from one detector keeps the branching logic in ONE place
and gives tests a clear contract.

See docs/specs/UPLOAD_PIPELINE_FLOW.md for the full pipeline diagram.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum
from typing import Optional


class DocumentType(str, Enum):
    # Structured — parse direct to DataFrame, skip Stage 6 extract
    STRUCTURED_CSV   = "structured_csv"
    STRUCTURED_TSV   = "structured_tsv"
    STRUCTURED_XLSX  = "structured_xlsx"
    STRUCTURED_XLS   = "structured_xls"      # legacy Excel; needs xlrd
    STRUCTURED_JSON  = "structured_json"

    # Unstructured — go through Stage 6 extraction + DocSage
    UNSTRUCTURED_PDF  = "unstructured_pdf"
    UNSTRUCTURED_DOCX = "unstructured_docx"
    UNSTRUCTURED_TXT  = "unstructured_txt"

    # Images — defer to Qwen2-VL adapter (Phase 2)
    IMAGE_RASTER = "image_raster"   # png/jpg/gif/bmp/tiff
    IMAGE_VECTOR = "image_vector"   # svg

    # Unknown / unsupported
    UNKNOWN = "unknown"

    @property
    def is_structured(self) -> bool:
        return self.value.startswith("structured_")

    @property
    def is_unstructured(self) -> bool:
        return self.value.startswith("unstructured_")

    @property
    def is_image(self) -> bool:
        return self.value.startswith("image_")


@dataclass(frozen=True)
class DetectionResult:
    """What the detector returns. `confidence` lets callers decide
    whether to log + fallback or trust outright; `evidence` describes
    which clue won (magic bytes > mime type > filename ext)."""
    document_type: DocumentType
    confidence:    float   # 0.0 .. 1.0
    evidence:      str     # 'magic_bytes' / 'mime_type' / 'filename_ext' / 'fallback'


# ─── Magic byte signatures ───────────────────────────────────────────


# (signature_bytes, document_type, evidence_note)
_MAGIC_SIGNATURES: list[tuple[bytes, DocumentType, str]] = [
    (b"%PDF",                            DocumentType.UNSTRUCTURED_PDF,  "PDF header"),
    (b"\x89PNG\r\n\x1a\n",              DocumentType.IMAGE_RASTER,      "PNG header"),
    (b"\xff\xd8\xff",                    DocumentType.IMAGE_RASTER,      "JPEG header"),
    (b"GIF87a",                          DocumentType.IMAGE_RASTER,      "GIF87 header"),
    (b"GIF89a",                          DocumentType.IMAGE_RASTER,      "GIF89 header"),
    (b"BM",                              DocumentType.IMAGE_RASTER,      "BMP header"),
    (b"II*\x00",                         DocumentType.IMAGE_RASTER,      "TIFF little-endian"),
    (b"MM\x00*",                         DocumentType.IMAGE_RASTER,      "TIFF big-endian"),
    (b"<svg",                            DocumentType.IMAGE_VECTOR,      "SVG content"),
    (b"<?xml",                           DocumentType.IMAGE_VECTOR,      "SVG with XML header (heuristic)"),
    # Legacy Excel (.xls) — Compound File Binary Format
    (b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1", DocumentType.STRUCTURED_XLS,    "OLE2 compound file"),
    # ZIP-based (XLSX/DOCX/PPTX) — content sniff required to disambiguate
    (b"PK\x03\x04",                      DocumentType.UNKNOWN,           "ZIP container (needs inner check)"),
]


def _detect_zip_inner(content: bytes) -> DocumentType:
    """For ZIP-based formats (PK signature), peek at the central
    directory for marker strings.

    Heuristic — proper unzip would be safer but we avoid the import
    cost for what's a 1-shot detection. Pretty robust because XLSX
    + DOCX + PPTX containers always include their marker paths."""
    head = content[:65536]   # first 64 KB is plenty for the directory
    if b"xl/workbook.xml" in head or b"xl/_rels" in head:
        return DocumentType.STRUCTURED_XLSX
    if b"word/document.xml" in head or b"word/_rels" in head:
        return DocumentType.UNSTRUCTURED_DOCX
    if b"ppt/presentation.xml" in head:
        return DocumentType.UNKNOWN     # PPTX — not supported yet
    return DocumentType.UNKNOWN


# ─── Mime-type map ───────────────────────────────────────────────────


_MIME_MAP: dict[str, DocumentType] = {
    "application/pdf":                                                       DocumentType.UNSTRUCTURED_PDF,
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": DocumentType.UNSTRUCTURED_DOCX,
    "application/msword":                                                    DocumentType.UNSTRUCTURED_DOCX,
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet":     DocumentType.STRUCTURED_XLSX,
    "application/vnd.ms-excel":                                              DocumentType.STRUCTURED_XLS,
    "text/csv":                                                              DocumentType.STRUCTURED_CSV,
    "text/tab-separated-values":                                             DocumentType.STRUCTURED_TSV,
    "application/json":                                                      DocumentType.STRUCTURED_JSON,
    "text/plain":                                                            DocumentType.UNSTRUCTURED_TXT,
    "image/png":                                                             DocumentType.IMAGE_RASTER,
    "image/jpeg":                                                            DocumentType.IMAGE_RASTER,
    "image/gif":                                                             DocumentType.IMAGE_RASTER,
    "image/bmp":                                                             DocumentType.IMAGE_RASTER,
    "image/tiff":                                                            DocumentType.IMAGE_RASTER,
    "image/svg+xml":                                                         DocumentType.IMAGE_VECTOR,
}


# ─── Filename-extension fallback ─────────────────────────────────────


_EXT_MAP: dict[str, DocumentType] = {
    ".pdf":   DocumentType.UNSTRUCTURED_PDF,
    ".docx":  DocumentType.UNSTRUCTURED_DOCX,
    ".doc":   DocumentType.UNSTRUCTURED_DOCX,
    ".xlsx":  DocumentType.STRUCTURED_XLSX,
    ".xls":   DocumentType.STRUCTURED_XLS,
    ".csv":   DocumentType.STRUCTURED_CSV,
    ".tsv":   DocumentType.STRUCTURED_TSV,
    ".json":  DocumentType.STRUCTURED_JSON,
    ".txt":   DocumentType.UNSTRUCTURED_TXT,
    ".md":    DocumentType.UNSTRUCTURED_TXT,
    ".png":   DocumentType.IMAGE_RASTER,
    ".jpg":   DocumentType.IMAGE_RASTER,
    ".jpeg":  DocumentType.IMAGE_RASTER,
    ".gif":   DocumentType.IMAGE_RASTER,
    ".bmp":   DocumentType.IMAGE_RASTER,
    ".tiff":  DocumentType.IMAGE_RASTER,
    ".tif":   DocumentType.IMAGE_RASTER,
    ".svg":   DocumentType.IMAGE_VECTOR,
}


# ─── CSV heuristic for octet-stream uploads ──────────────────────────


_CSV_PROBE_LIMIT = 4096      # only sample the first 4 KB for the heuristic


def _looks_like_csv(content: bytes) -> bool:
    """Last-resort heuristic for octet-stream uploads with no filename.

    Decodes the leading 4 KB as UTF-8 (fallback latin-1), then checks
    that ≥3 lines exist with the same comma count per line. False
    positives on prose-with-commas are accepted — caller can override
    with explicit mime_type.
    """
    sample = content[:_CSV_PROBE_LIMIT]
    try:
        text = sample.decode("utf-8")
    except UnicodeDecodeError:
        try:
            text = sample.decode("latin-1")
        except UnicodeDecodeError:
            return False
    lines = [ln for ln in text.splitlines() if ln.strip()]
    if len(lines) < 3:
        return False
    comma_counts = [ln.count(",") for ln in lines[:10]]
    if not comma_counts or max(comma_counts) < 2:
        return False
    # Most lines should agree within ±1 on comma count
    mode = max(set(comma_counts), key=comma_counts.count)
    agreement = sum(1 for c in comma_counts if abs(c - mode) <= 1)
    return agreement >= max(3, len(comma_counts) * 0.8)


# ─── Public API ──────────────────────────────────────────────────────


def detect_document_type(
    *,
    content:   bytes,
    mime_type: Optional[str] = None,
    filename:  Optional[str] = None,
) -> DetectionResult:
    """Detect the document type from bytes + optional metadata.

    Priority:
      1. Magic bytes (most reliable; immune to wrong mime + wrong ext)
      2. mime_type from upload (if recognised)
      3. Filename extension (last resort)
      4. CSV heuristic (octet-stream + no filename)

    Returns DetectionResult with confidence:
      1.00 — magic bytes match
      0.85 — mime + extension agree
      0.70 — mime only OR extension only
      0.50 — CSV heuristic
      0.00 — UNKNOWN
    """
    # 1. Magic bytes
    if content:
        for sig, doc_type, note in _MAGIC_SIGNATURES:
            if content.startswith(sig):
                if doc_type == DocumentType.UNKNOWN:    # ZIP container
                    inner = _detect_zip_inner(content)
                    if inner != DocumentType.UNKNOWN:
                        return DetectionResult(inner, 1.00, f"zip_inner ({note})")
                else:
                    return DetectionResult(doc_type, 1.00, note)

    # 2. Mime type
    mime_norm = (mime_type or "").lower().strip()
    mime_hit = _MIME_MAP.get(mime_norm)

    # 3. Filename ext
    ext_hit: Optional[DocumentType] = None
    if filename:
        fn_lower = filename.lower()
        for ext, doc_type in _EXT_MAP.items():
            if fn_lower.endswith(ext):
                ext_hit = doc_type
                break

    # 2 + 3 agree → high confidence
    if mime_hit and ext_hit and mime_hit == ext_hit:
        return DetectionResult(mime_hit, 0.85, "mime + ext agree")
    if mime_hit:
        return DetectionResult(mime_hit, 0.70, "mime_type")
    if ext_hit:
        return DetectionResult(ext_hit, 0.70, "filename_ext")

    # 4. CSV heuristic
    if content and _looks_like_csv(content):
        return DetectionResult(DocumentType.STRUCTURED_CSV, 0.50, "csv_heuristic")

    return DetectionResult(DocumentType.UNKNOWN, 0.0, "fallback")


def is_supported(doc_type: DocumentType) -> bool:
    """Phase 2 supports structured + most unstructured. Images defer
    until Qwen2-VL adapter (P2). SVG vector flagged but rejected for
    now."""
    if doc_type == DocumentType.UNKNOWN:
        return False
    if doc_type == DocumentType.IMAGE_VECTOR:
        return False
    if doc_type == DocumentType.IMAGE_RASTER:
        return False    # defer Phase 2 Qwen2-VL adapter
    if doc_type == DocumentType.STRUCTURED_XLS:
        return False    # legacy .xls needs xlrd; defer Phase 2
    return True
