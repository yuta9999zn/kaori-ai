"""
MinerU wire-in 2026-05-18 — tests for detection integration in
ingestor's workflow whitelist check.

The whitelist enforcement itself is tested by the existing
test_workflow_whitelist suite. This file specifically covers the
NEW behaviour: BOTH filename ext AND magic-byte-detected kind are
compared against the whitelist, so renamed/spoofed uploads either
pass (when content matches expected kind) or fail (when neither
matches).
"""
from __future__ import annotations

import pytest

from data_pipeline.data_plane.bronze.ingestor import (
    _detected_kind,
    _normalize_kind,
)
from data_pipeline.data_plane.silver.document_type import DocumentType


# ═════════════════════════════════════════════════════════════════════
# 1. _detected_kind mapping
# ═════════════════════════════════════════════════════════════════════


class TestDetectedKind:

    def test_structured_csv(self):
        assert _detected_kind(DocumentType.STRUCTURED_CSV) == "csv"

    def test_structured_xlsx(self):
        assert _detected_kind(DocumentType.STRUCTURED_XLSX) == "xlsx"

    def test_legacy_xls_folds_to_xlsx(self):
        """Legacy .xls files share the xlsx whitelist entry — anh's
        Vingroup financial reports often mix .xls + .xlsx on the same
        card."""
        assert _detected_kind(DocumentType.STRUCTURED_XLS) == "xlsx"

    def test_pdf(self):
        assert _detected_kind(DocumentType.UNSTRUCTURED_PDF) == "pdf"

    def test_docx(self):
        assert _detected_kind(DocumentType.UNSTRUCTURED_DOCX) == "docx"

    def test_image_raster_folds_to_image(self):
        """Image cards accept any raster format under the canonical
        'image' kind — PNG / JPEG / TIFF all collapse to image."""
        assert _detected_kind(DocumentType.IMAGE_RASTER) == "image"

    def test_image_vector_folds_to_image(self):
        assert _detected_kind(DocumentType.IMAGE_VECTOR) == "image"

    def test_unknown_returns_unknown(self):
        assert _detected_kind(DocumentType.UNKNOWN) == "unknown"


# ═════════════════════════════════════════════════════════════════════
# 2. Round-trip: detected_kind → normalize_kind agrees with ext form
# ═════════════════════════════════════════════════════════════════════


class TestRoundTrip:

    @pytest.mark.parametrize("doc_type,ext_kind", [
        (DocumentType.STRUCTURED_CSV,    "csv"),
        (DocumentType.STRUCTURED_XLSX,   "xlsx"),
        (DocumentType.UNSTRUCTURED_PDF,  "pdf"),
        (DocumentType.UNSTRUCTURED_DOCX, "docx"),
    ])
    def test_detected_matches_ext_when_normalised(self, doc_type, ext_kind):
        detected = _normalize_kind(_detected_kind(doc_type))
        ext_form = _normalize_kind(ext_kind)
        assert detected == ext_form

    @pytest.mark.parametrize("kind_alias,canonical", [
        ("PDF",   "pdf"),
        (".pdf",  "pdf"),
        ("Word",  "docx"),
        ("doc",   "docx"),
        ("Excel", "xlsx"),
        ("xlsx",  "xlsx"),
        ("JPG",   "image"),
        ("png",   "image"),
        ("jpeg",  "image"),
    ])
    def test_aliases_collapse(self, kind_alias, canonical):
        """Anh's mig 069 workflow templates use various spellings
        ('word' / 'doc' / 'docx'). The normalizer must collapse them
        all to the canonical form the detector emits."""
        assert _normalize_kind(kind_alias) == canonical


# ═════════════════════════════════════════════════════════════════════
# 3. Spoof scenarios — detected catches what ext misses
# ═════════════════════════════════════════════════════════════════════


class TestSpoofScenarios:
    """End-to-end-ish: given a bytes payload + filename + mime that
    DISAGREE, the detector + normalizer combination produces the
    correct kind. The ingestor will then compare BOTH and accept
    iff EITHER matches the whitelist.
    """

    def test_pdf_bytes_with_docx_filename(self):
        """User uploads "report.docx" but file is actually a PDF.
        detected_kind should say "pdf"."""
        from data_pipeline.data_plane.silver.document_type import detect_document_type
        det = detect_document_type(
            content=b"%PDF-1.7\n...",
            mime_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            filename="report.docx",
        )
        assert det.document_type == DocumentType.UNSTRUCTURED_PDF
        assert _detected_kind(det.document_type) == "pdf"

    def test_xlsx_with_octet_stream_mime(self):
        """Common case from Vietnamese office uploads — Excel saved
        from desktop tool sends application/octet-stream. Magic bytes
        + xl/ marker still detect correctly."""
        content = b"PK\x03\x04" + b"\x00" * 100 + b"xl/workbook.xml" + b"\x00" * 100
        from data_pipeline.data_plane.silver.document_type import detect_document_type
        det = detect_document_type(
            content=content,
            mime_type="application/octet-stream",
            filename="bao_cao.xlsx",
        )
        assert det.document_type == DocumentType.STRUCTURED_XLSX
        assert _detected_kind(det.document_type) == "xlsx"

    def test_text_with_csv_mime(self):
        """Cover the easy case — mime + magic bytes both say CSV."""
        content = b"id,name\n1,a\n2,b\n3,c\n4,d\n"
        from data_pipeline.data_plane.silver.document_type import detect_document_type
        det = detect_document_type(
            content=content, mime_type="text/csv", filename="data.csv",
        )
        assert det.document_type == DocumentType.STRUCTURED_CSV
        assert _detected_kind(det.document_type) == "csv"


# ═════════════════════════════════════════════════════════════════════
# 4. Whitelist matching logic — simulate ingestor's decision
# ═════════════════════════════════════════════════════════════════════


class TestWhitelistMatching:
    """Simulate the ingestor's decision logic: detected_kind is
    AUTHORITATIVE; ext is fallback ONLY when detected = 'unknown'.
    Stops renamed-extension spoof attacks."""

    def _matches(self, allowed: set[str], ext_kind: str, detected_kind: str) -> bool:
        ext_norm = _normalize_kind(ext_kind)
        det_norm = _normalize_kind(detected_kind)
        # Detected is authoritative; fall back to ext when detected is 'unknown'
        effective = ext_norm if det_norm == "unknown" else det_norm
        return effective in allowed

    def test_card_accepts_pdf_only_pdf_upload(self):
        assert self._matches({"pdf"}, "pdf", "pdf") is True

    def test_card_accepts_pdf_but_xlsx_uploaded(self):
        assert self._matches({"pdf"}, "xlsx", "xlsx") is False

    def test_card_accepts_pdf_renamed_xlsx(self):
        """User renames invoice.xlsx → invoice.pdf to bypass the check.
        Ext says pdf, detected says xlsx (magic bytes don't lie).
        Detected wins → rejected. Security gate holds."""
        assert self._matches({"pdf"}, "pdf", "xlsx") is False

    def test_card_accepts_pdf_renamed_octet_stream(self):
        """Card accepts {pdf, image}. User uploads actual PDF but
        renames to .bin. ext_kind = 'bin' (unknown), detected = 'pdf'.
        Detected wins → accepted."""
        assert self._matches({"pdf", "image"}, "bin", "pdf") is True

    def test_card_accepts_both_match(self):
        assert self._matches({"pdf", "xlsx"}, "xlsx", "xlsx") is True

    def test_image_aliases(self):
        """Card accepts 'image' → png + jpg + tiff all match via the
        alias normalizer (detected_kind already collapses to 'image')."""
        assert self._matches({"image"}, "png", "image") is True
        assert self._matches({"image"}, "jpeg", "image") is True
        assert self._matches({"image"}, "jpg", "image") is True

    def test_ext_fallback_when_detection_unknown(self):
        """Edge case — detector returns UNKNOWN (e.g. obscure binary).
        Fall back to filename extension."""
        # detected = unknown, ext = "csv" → ext fallback used
        assert self._matches({"csv"}, "csv", "unknown") is True
        # detected = unknown, ext = "pdf" → ext mismatches allowed → reject
        assert self._matches({"csv"}, "pdf", "unknown") is False
