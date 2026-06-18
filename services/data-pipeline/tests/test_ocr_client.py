"""
Phase 2.5 — OCR client tests.

Mocks httpx.AsyncClient.post — no llm-gateway running. Validates the
contract: pre-flight checks, happy path, network failures, oversize
input, format gating.

8-section template:
  1. is_ocr_candidate gating (mime + ext + edge cases)
  2. Empty content short-circuit
  3. Oversize image rejected pre-flight
  4. Non-image mime/ext rejected pre-flight
  5. Happy path returns OcrResult with text + provenance
  6. Empty model response → 'empty_image' status
  7. Network failure → 'failed' status (no raise)
  8. Custom prompt + max_tokens forwarded
"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from data_pipeline.data_plane.silver.ocr_client import (
    MAX_OCR_BYTES,
    OcrResult,
    SUPPORTED_IMAGE_EXTS,
    SUPPORTED_IMAGE_MIMES,
    is_ocr_candidate,
    ocr_image_to_text,
)


ENT = "11111111-1111-1111-1111-111111111111"


def _png_bytes(size: int = 100) -> bytes:
    """Synthetic image bytes (size matters, content doesn't)."""
    return b"\x89PNG\r\n\x1a\n" + b"\x00" * (size - 8)


def _mock_post(text: str = "extracted text", char_count: int = None,
               model_used: str = "qwen2.5vl:7b", latency_ms: int = 1234):
    """Build a MagicMock that mimics httpx.AsyncClient.post response."""
    resp = MagicMock()
    resp.raise_for_status = MagicMock()
    resp.json = MagicMock(return_value={
        "text":       text,
        "char_count": char_count if char_count is not None else len(text),
        "model_used": model_used,
        "latency_ms": latency_ms,
    })
    return resp


# ═════════════════════════════════════════════════════════════════════
# 1. is_ocr_candidate gating
# ═════════════════════════════════════════════════════════════════════


class TestIsOcrCandidate:

    def test_supported_image_mimes(self):
        for mt in SUPPORTED_IMAGE_MIMES:
            assert is_ocr_candidate(mime_type=mt, ext="") is True

    def test_supported_exts_with_dot(self):
        for ext in SUPPORTED_IMAGE_EXTS:
            assert is_ocr_candidate(mime_type="", ext=ext) is True

    def test_supported_exts_without_dot(self):
        # The function normalises both "png" and ".png"
        assert is_ocr_candidate(mime_type="", ext="png") is True
        assert is_ocr_candidate(mime_type="", ext="jpg") is True

    def test_unsupported_mime(self):
        assert is_ocr_candidate(mime_type="application/pdf", ext="") is False
        assert is_ocr_candidate(mime_type="image/tiff", ext="") is False
        assert is_ocr_candidate(mime_type="image/gif", ext="") is False

    def test_unsupported_ext(self):
        assert is_ocr_candidate(mime_type="", ext=".pdf") is False
        assert is_ocr_candidate(mime_type="", ext=".tiff") is False

    def test_empty_inputs_reject(self):
        assert is_ocr_candidate(mime_type="", ext="") is False


# ═════════════════════════════════════════════════════════════════════
# 2-4. Pre-flight short-circuits
# ═════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
class TestPreflight:

    async def test_empty_content_short_circuits(self):
        """Don't burn a gateway call on empty bytes."""
        with patch("httpx.AsyncClient") as ac:
            result = await ocr_image_to_text(
                content=b"", enterprise_id=ENT,
                mime_type="image/png", ext=".png",
            )
        assert result.status == "empty_image"
        assert result.text == ""
        ac.assert_not_called()

    async def test_oversize_rejected_pre_flight(self):
        oversize = b"x" * (MAX_OCR_BYTES + 1)
        with patch("httpx.AsyncClient") as ac:
            result = await ocr_image_to_text(
                content=oversize, enterprise_id=ENT,
                mime_type="image/png", ext=".png",
            )
        assert result.status == "unsupported_today"
        assert "vượt giới hạn" in result.error_message
        ac.assert_not_called()

    async def test_non_image_mime_rejected_pre_flight(self):
        with patch("httpx.AsyncClient") as ac:
            result = await ocr_image_to_text(
                content=_png_bytes(), enterprise_id=ENT,
                mime_type="application/pdf", ext=".pdf",
            )
        assert result.status == "unsupported_today"
        assert "Định dạng ảnh chưa hỗ trợ" in result.error_message
        ac.assert_not_called()


# ═════════════════════════════════════════════════════════════════════
# 5. Happy path
# ═════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
class TestHappyPath:

    async def test_returns_text_and_provenance(self):
        fake_text = "Hóa đơn số 123 ngày 15/05/2026"

        ctx = MagicMock()
        ctx.__aenter__ = AsyncMock(return_value=ctx)
        ctx.__aexit__ = AsyncMock(return_value=False)
        ctx.post = AsyncMock(return_value=_mock_post(text=fake_text))

        with patch("httpx.AsyncClient", return_value=ctx):
            result = await ocr_image_to_text(
                content=_png_bytes(500), enterprise_id=ENT,
                mime_type="image/png", ext=".png",
            )

        assert result.status == "ok"
        assert result.text == fake_text
        assert result.char_count == len(fake_text)
        assert result.model_used == "qwen2.5vl:7b"
        assert result.latency_ms == 1234

    async def test_request_payload_carries_base64(self):
        """Bytes are base64-encoded before sending."""
        ctx = MagicMock()
        ctx.__aenter__ = AsyncMock(return_value=ctx)
        ctx.__aexit__ = AsyncMock(return_value=False)
        ctx.post = AsyncMock(return_value=_mock_post())

        with patch("httpx.AsyncClient", return_value=ctx):
            await ocr_image_to_text(
                content=_png_bytes(500), enterprise_id=ENT,
                mime_type="image/png", ext=".png",
            )

        # The POST should be called with json= body containing image_b64
        _, kwargs = ctx.post.call_args
        body = kwargs["json"]
        assert "image_b64" in body
        assert body["enterprise_id"] == ENT
        # Base64 of 500 bytes is ~668 chars
        assert len(body["image_b64"]) > 500


# ═════════════════════════════════════════════════════════════════════
# 6. Empty model response
# ═════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
class TestEmptyModelResponse:

    async def test_blank_text_becomes_empty_image(self):
        ctx = MagicMock()
        ctx.__aenter__ = AsyncMock(return_value=ctx)
        ctx.__aexit__ = AsyncMock(return_value=False)
        ctx.post = AsyncMock(return_value=_mock_post(text="   \n  "))

        with patch("httpx.AsyncClient", return_value=ctx):
            result = await ocr_image_to_text(
                content=_png_bytes(500), enterprise_id=ENT,
                mime_type="image/png", ext=".png",
            )

        assert result.status == "empty_image"
        assert result.text == ""
        assert "trắng" in result.error_message or "không nhận dạng" in result.error_message


# ═════════════════════════════════════════════════════════════════════
# 7. Network failure
# ═════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
class TestNetworkFailure:

    async def test_http_error_returns_failed_status_no_raise(self):
        import httpx

        ctx = MagicMock()
        ctx.__aenter__ = AsyncMock(return_value=ctx)
        ctx.__aexit__ = AsyncMock(return_value=False)
        ctx.post = AsyncMock(side_effect=httpx.ConnectError("gateway down"))

        with patch("httpx.AsyncClient", return_value=ctx):
            result = await ocr_image_to_text(
                content=_png_bytes(500), enterprise_id=ENT,
                mime_type="image/png", ext=".png",
            )

        # Caller relies on this NOT raising — they need to commit the
        # bronze_files row even when OCR fails.
        assert result.status == "failed"
        assert "ConnectError" in result.error_message

    async def test_unexpected_exception_returns_failed_no_raise(self):
        ctx = MagicMock()
        ctx.__aenter__ = AsyncMock(return_value=ctx)
        ctx.__aexit__ = AsyncMock(return_value=False)
        ctx.post = AsyncMock(side_effect=ValueError("malformed response"))

        with patch("httpx.AsyncClient", return_value=ctx):
            result = await ocr_image_to_text(
                content=_png_bytes(500), enterprise_id=ENT,
                mime_type="image/png", ext=".png",
            )

        assert result.status == "failed"
        assert "ValueError" in result.error_message


# ═════════════════════════════════════════════════════════════════════
# 8. Custom prompt forwarding
# ═════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
class TestPromptForwarding:

    async def test_custom_prompt_in_payload(self):
        ctx = MagicMock()
        ctx.__aenter__ = AsyncMock(return_value=ctx)
        ctx.__aexit__ = AsyncMock(return_value=False)
        ctx.post = AsyncMock(return_value=_mock_post(text="0312345678"))

        custom = "Chỉ trích xuất mã số thuế"
        with patch("httpx.AsyncClient", return_value=ctx):
            await ocr_image_to_text(
                content=_png_bytes(500), enterprise_id=ENT,
                mime_type="image/png", ext=".png",
                prompt=custom, max_tokens=300,
            )

        _, kwargs = ctx.post.call_args
        body = kwargs["json"]
        assert body["prompt"] == custom
        assert body["max_tokens"] == 300


# ═════════════════════════════════════════════════════════════════════
# OcrResult dataclass — defaults + freeze
# ═════════════════════════════════════════════════════════════════════


class TestOcrResultShape:

    def test_default_fields(self):
        r = OcrResult(text="hello", status="ok")
        assert r.char_count == 0
        assert r.model_used == ""
        assert r.latency_ms == 0
        assert r.error_message is None

    def test_frozen_immutable(self):
        r = OcrResult(text="x", status="ok")
        with pytest.raises(Exception):  # FrozenInstanceError
            r.text = "y"   # type: ignore[misc]
