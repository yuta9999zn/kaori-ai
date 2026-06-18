"""Tests for the document repository slug helper (ADR-0039) — pure."""
from __future__ import annotations

from ai_orchestrator.routers.document_repository import _slug


def test_slug_strips_vietnamese_diacritics():
    assert _slug("Tài chính") == "tai_chinh"
    assert _slug("Quý 1") == "quy_1"


def test_slug_handles_dd():
    assert _slug("Đơn hàng") == "don_hang"


def test_slug_collapses_and_trims():
    assert _slug("  Hồ sơ —— 2024 !! ") == "ho_so_2024"


def test_slug_fallback_for_empty():
    assert _slug("") == "muc"
    assert _slug("———") == "muc"
