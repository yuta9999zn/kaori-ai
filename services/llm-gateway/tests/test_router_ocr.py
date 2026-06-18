"""Tests for POST /v1/ocr (Phase 2.5 — Qwen2.5-VL local-only).

Mocks providers.ocr_image; no Ollama running. Validates:
  * happy path returns text + char_count + model_used + latency_ms
  * provider failure → 502
  * empty image_b64 short-circuits with proper validation
  * K-4 invariant: endpoint has no consent_external / prefer_external
  * input size cap enforced by Pydantic
  * default OCR prompt is Vietnamese
"""
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from llm_gateway.errors import register_problem_handlers
from llm_gateway.router import router as v1_router


@pytest.fixture(autouse=True)
def _stub_pool_and_governance():
    """Phase 2.7 P3: /v1/ocr now writes ai_decision_audit via the
    pool — these tests have no live pool, so stub both the pool
    accessor and the gov writer for every test in this module."""
    from unittest.mock import MagicMock
    with patch("llm_gateway.router.get_pool", return_value=MagicMock()), \
         patch("llm_gateway.router.ai_governance.record_ai_call",
                new=AsyncMock(return_value=None)):
        yield


@pytest.fixture
def client():
    app = FastAPI()
    register_problem_handlers(app)
    app.include_router(v1_router)
    return TestClient(app)


# Synthetic 4-char base64 — passes Pydantic min_length=4 + valid b64.
_TINY_B64 = "AAAA"


def _body(b64: str = _TINY_B64, **extra) -> dict:
    base = {"image_b64": b64, "enterprise_id": str(uuid4())}
    base.update(extra)
    return base


# ─── Happy path ─────────────────────────────────────────────────────


def test_ocr_happy_path(client):
    fake_text = "Hóa đơn số 123 ngày 15/05/2026 tổng tiền 1.500.000 đồng"
    with patch("llm_gateway.providers.ocr_image",
                new=AsyncMock(return_value=fake_text)):
        r = client.post("/v1/ocr", json=_body())
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["text"] == fake_text
    assert body["char_count"] == len(fake_text)
    assert body["model_used"]
    assert body["latency_ms"] >= 0


def test_ocr_empty_text_response_returns_zero_char_count(client):
    """Provider returns empty string → endpoint relays it (caller sees
    empty_image equivalent)."""
    with patch("llm_gateway.providers.ocr_image",
                new=AsyncMock(return_value="")):
        r = client.post("/v1/ocr", json=_body())
    assert r.status_code == 200
    body = r.json()
    assert body["text"] == ""
    assert body["char_count"] == 0


def test_ocr_custom_prompt_passed_through(client):
    """Caller can override the default Vietnamese OCR prompt."""
    custom_prompt = "Chỉ trích xuất mã số thuế"
    captured = {}

    async def fake_ocr(*, image_b64, prompt, max_tokens):
        captured["prompt"] = prompt
        captured["max_tokens"] = max_tokens
        return "0312345678"

    with patch("llm_gateway.providers.ocr_image", new=fake_ocr):
        r = client.post("/v1/ocr",
                         json=_body(prompt=custom_prompt, max_tokens=500))
    assert r.status_code == 200
    assert captured["prompt"] == custom_prompt
    assert captured["max_tokens"] == 500


# ─── Failure path ───────────────────────────────────────────────────


def test_ocr_provider_failure_returns_502(client):
    with patch("llm_gateway.providers.ocr_image",
                new=AsyncMock(side_effect=RuntimeError("Ollama vision model not pulled"))):
        r = client.post("/v1/ocr", json=_body())
    assert r.status_code == 502
    assert "ocr" in r.text.lower() or "upstream" in r.text.lower()


# ─── Validation ─────────────────────────────────────────────────────


def test_ocr_missing_enterprise_id_rejects(client):
    r = client.post("/v1/ocr", json={"image_b64": _TINY_B64})
    assert r.status_code == 422


def test_ocr_missing_image_rejects(client):
    r = client.post("/v1/ocr", json={"enterprise_id": str(uuid4())})
    assert r.status_code == 422


def test_ocr_oversize_image_rejects(client):
    """Pydantic max_length=15_000_000 cap rejects pre-flight."""
    huge_b64 = "A" * 15_000_001
    r = client.post("/v1/ocr",
                     json=_body(b64=huge_b64))
    assert r.status_code == 422


def test_ocr_too_short_image_rejects(client):
    """Pydantic min_length=4 to keep "" / 'A' / 'AB' / 'ABC' out."""
    r = client.post("/v1/ocr", json=_body(b64="AB"))
    assert r.status_code == 422


def test_ocr_max_tokens_lower_bound(client):
    r = client.post("/v1/ocr", json=_body(max_tokens=50))
    assert r.status_code == 422  # ge=100


def test_ocr_max_tokens_upper_bound(client):
    r = client.post("/v1/ocr", json=_body(max_tokens=9000))
    assert r.status_code == 422  # le=8000


# ─── K-4 invariant ──────────────────────────────────────────────────


def test_ocr_request_has_no_consent_external_field():
    """OCR endpoint MUST not accept consent_external — K-4 invariant
    for image bytes is enforced by the schema, not runtime checks.
    Image bytes carry PII that can't be byte-redacted; vendor vision
    requires a separate ADR (Phase 3)."""
    from llm_gateway.models import OcrRequest
    fields = set(OcrRequest.model_fields.keys())
    assert "consent_external" not in fields, \
        "OcrRequest must not accept consent_external — OCR is always local (K-4)."
    assert "prefer_external" not in fields, \
        "OcrRequest must not accept prefer_external (K-4)."


def test_ocr_default_prompt_is_vietnamese():
    """The default prompt biases toward Vietnamese first — em's
    primary market. Test pins this so a future English-default
    refactor needs explicit sign-off."""
    from llm_gateway.providers import DEFAULT_OCR_PROMPT
    # Pin a couple of Vietnamese-only words from the prompt.
    assert "Trích xuất" in DEFAULT_OCR_PROMPT
    assert "trái-phải" in DEFAULT_OCR_PROMPT
