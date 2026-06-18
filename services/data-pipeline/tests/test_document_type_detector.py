"""
Document type detector tests.

8-section template (compressed for a pure-python module):
  1. Enum + helper props
  2. Magic byte signatures
  3. ZIP-based inner content sniff
  4. Mime type map
  5. Filename extension fallback
  6. CSV heuristic
  7. Confidence + evidence reporting
  8. is_supported gate
"""
from __future__ import annotations

import pytest

from data_pipeline.data_plane.silver.document_type import (
    DetectionResult,
    DocumentType,
    detect_document_type,
    is_supported,
)


# ═════════════════════════════════════════════════════════════════════
# 1. Enum + helper props
# ═════════════════════════════════════════════════════════════════════


class TestEnum:

    def test_structured_helper(self):
        assert DocumentType.STRUCTURED_CSV.is_structured is True
        assert DocumentType.UNSTRUCTURED_PDF.is_structured is False

    def test_unstructured_helper(self):
        assert DocumentType.UNSTRUCTURED_PDF.is_unstructured is True
        assert DocumentType.STRUCTURED_CSV.is_unstructured is False

    def test_image_helper(self):
        assert DocumentType.IMAGE_RASTER.is_image is True
        assert DocumentType.STRUCTURED_CSV.is_image is False


# ═════════════════════════════════════════════════════════════════════
# 2. Magic bytes win
# ═════════════════════════════════════════════════════════════════════


class TestMagicBytes:

    def test_pdf_magic(self):
        r = detect_document_type(content=b"%PDF-1.7\n%\xe2\xe3...", mime_type=None)
        assert r.document_type == DocumentType.UNSTRUCTURED_PDF
        assert r.confidence == 1.00

    def test_png_magic(self):
        r = detect_document_type(content=b"\x89PNG\r\n\x1a\n\x00\x00\x00")
        assert r.document_type == DocumentType.IMAGE_RASTER

    def test_jpeg_magic(self):
        r = detect_document_type(content=b"\xff\xd8\xff\xe0\x00\x10JFIF")
        assert r.document_type == DocumentType.IMAGE_RASTER

    def test_magic_wins_over_wrong_mime(self):
        """Browser sends application/octet-stream for an .xlsx — but the
        ZIP magic + xl/ marker should still detect it correctly."""
        content = b"PK\x03\x04" + b"\x00" * 50 + b"xl/workbook.xml" + b"\x00" * 50
        r = detect_document_type(content=content, mime_type="application/octet-stream")
        assert r.document_type == DocumentType.STRUCTURED_XLSX


# ═════════════════════════════════════════════════════════════════════
# 3. ZIP inner content sniff
# ═════════════════════════════════════════════════════════════════════


class TestZipInner:

    def test_xlsx_via_xl_marker(self):
        content = b"PK\x03\x04" + b"x" * 100 + b"xl/workbook.xml" + b"y" * 100
        r = detect_document_type(content=content)
        assert r.document_type == DocumentType.STRUCTURED_XLSX

    def test_docx_via_word_marker(self):
        content = b"PK\x03\x04" + b"x" * 100 + b"word/document.xml" + b"y" * 100
        r = detect_document_type(content=content)
        assert r.document_type == DocumentType.UNSTRUCTURED_DOCX

    def test_unknown_zip_falls_back(self):
        """A ZIP without any office marker → UNKNOWN."""
        content = b"PK\x03\x04" + b"random binary data" * 50
        r = detect_document_type(content=content)
        assert r.document_type == DocumentType.UNKNOWN


# ═════════════════════════════════════════════════════════════════════
# 4. Mime type map
# ═════════════════════════════════════════════════════════════════════


class TestMimeMap:

    def test_pdf_mime(self):
        r = detect_document_type(content=b"random not magic", mime_type="application/pdf")
        assert r.document_type == DocumentType.UNSTRUCTURED_PDF

    def test_csv_mime(self):
        r = detect_document_type(content=b"random not magic", mime_type="text/csv")
        assert r.document_type == DocumentType.STRUCTURED_CSV

    def test_xlsx_mime_no_magic(self):
        r = detect_document_type(
            content=b"random not magic not zip",
            mime_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        assert r.document_type == DocumentType.STRUCTURED_XLSX


# ═════════════════════════════════════════════════════════════════════
# 5. Filename extension
# ═════════════════════════════════════════════════════════════════════


class TestFilenameExt:

    def test_pdf_ext(self):
        r = detect_document_type(content=b"random", filename="report.pdf")
        assert r.document_type == DocumentType.UNSTRUCTURED_PDF

    def test_csv_ext_upper(self):
        r = detect_document_type(content=b"random", filename="DATA.CSV")
        assert r.document_type == DocumentType.STRUCTURED_CSV

    def test_no_clue_returns_unknown(self):
        r = detect_document_type(content=b"random bytes", filename="data.xyz")
        assert r.document_type == DocumentType.UNKNOWN
        assert r.confidence == 0.0


# ═════════════════════════════════════════════════════════════════════
# 6. CSV heuristic
# ═════════════════════════════════════════════════════════════════════


class TestCsvHeuristic:

    def test_csv_heuristic_detects(self):
        content = (
            b"customer_id,name,revenue,month\n"
            b"KH001,Acme,1500000,2026-05\n"
            b"KH002,Beta,2300000,2026-05\n"
            b"KH003,Gamma,890000,2026-05\n"
        )
        r = detect_document_type(content=content)
        assert r.document_type == DocumentType.STRUCTURED_CSV
        assert r.evidence == "csv_heuristic"

    def test_random_text_not_csv(self):
        content = b"This is a plain prose sentence.\nAnother sentence.\nThird line."
        r = detect_document_type(content=content)
        assert r.document_type == DocumentType.UNKNOWN


# ═════════════════════════════════════════════════════════════════════
# 7. Confidence + evidence
# ═════════════════════════════════════════════════════════════════════


class TestConfidenceEvidence:

    def test_magic_high_confidence(self):
        r = detect_document_type(content=b"%PDF-")
        assert r.confidence == 1.00

    def test_mime_plus_ext_agree(self):
        r = detect_document_type(
            content=b"not magic",
            mime_type="application/pdf",
            filename="report.pdf",
        )
        assert r.confidence == 0.85
        assert "agree" in r.evidence

    def test_mime_only(self):
        r = detect_document_type(content=b"random", mime_type="text/csv")
        assert r.confidence == 0.70
        assert r.evidence == "mime_type"

    def test_ext_only(self):
        r = detect_document_type(content=b"random", filename="data.csv")
        assert r.confidence == 0.70
        assert r.evidence == "filename_ext"


# ═════════════════════════════════════════════════════════════════════
# 8. is_supported gate
# ═════════════════════════════════════════════════════════════════════


class TestSupportedGate:

    def test_supported_structured(self):
        assert is_supported(DocumentType.STRUCTURED_CSV) is True
        assert is_supported(DocumentType.STRUCTURED_XLSX) is True

    def test_supported_unstructured(self):
        assert is_supported(DocumentType.UNSTRUCTURED_PDF) is True
        assert is_supported(DocumentType.UNSTRUCTURED_DOCX) is True

    def test_image_not_yet_supported(self):
        """Phase 2 defers images to Qwen2-VL adapter; is_supported=False
        so the upload router can return a friendly 415 message."""
        assert is_supported(DocumentType.IMAGE_RASTER) is False
        assert is_supported(DocumentType.IMAGE_VECTOR) is False

    def test_legacy_xls_deferred(self):
        assert is_supported(DocumentType.STRUCTURED_XLS) is False

    def test_unknown_unsupported(self):
        assert is_supported(DocumentType.UNKNOWN) is False
