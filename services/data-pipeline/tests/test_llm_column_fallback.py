"""Stage 2B — LLM column-mapping fallback tests.

Mocks httpx; no llm-gateway running. Validates:
  * no_match rows replaced when LLM returns valid mappings
  * non-no_match rows untouched
  * gateway 500 → safe degradation (mappings unchanged)
  * unknown canonical from LLM kept as no_match + flag
  * overflow beyond MAX_BATCH stays passthrough
  * consent_external=False forwarded (K-4 invariant)
"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

import time

from data_pipeline.data_plane.bronze import llm_column_fallback as _fb
from data_pipeline.data_plane.bronze.llm_column_fallback import (
    MAX_BATCH,
    enrich_with_llm_fallback,
)


LANG_DICT = {
    "customer_id":   {"description": "Mã KH"},
    "order_amount":  {"description": "Số tiền đơn"},
    "order_date":    {"description": "Ngày đặt"},
}


@pytest.fixture(autouse=True)
def _enable_fallback(monkeypatch):
    """FALLBACK_ENABLED is resolved from env at import; the pilot sets
    SCHEMA_LLM_FALLBACK=0 so the test container imports it as False. Force it
    on for the gateway-path tests; the 'disabled' test flips it back off."""
    monkeypatch.setattr(_fb, "FALLBACK_ENABLED", True)


def _gateway_response(rows: list[dict]) -> dict:
    """Shape that complete_structured() / gateway returns under
    Issue #3 — output_validation.parsed_json carries the dict."""
    return {
        "completion": "...",
        "output_validation": {
            "parsed_json": {"mappings": rows},
        },
    }


def _ok_post(payload: dict):
    """Build a mock httpx.AsyncClient that returns 200 with payload."""
    client = AsyncMock()
    response = MagicMock()
    response.json = MagicMock(return_value=payload)
    response.raise_for_status = MagicMock()
    client.post = AsyncMock(return_value=response)
    client.__aenter__ = AsyncMock(return_value=client)
    client.__aexit__  = AsyncMock(return_value=None)
    return client


# ─── Happy path ─────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_no_match_rows_replaced():
    mappings = [
        {"source_column": "ma_kh",  "canonical_name": "ma_kh",
         "data_type": "text", "confidence": 0.0, "method": "no_match",
         "uncertainty_flags": []},
        {"source_column": "amount", "canonical_name": "amount",
         "data_type": "text", "confidence": 0.0, "method": "no_match",
         "uncertainty_flags": []},
    ]
    gateway_payload = _gateway_response([
        {"source_column": "ma_kh", "canonical_name": "customer_id",
         "data_type": "text", "confidence": 0.7},
        {"source_column": "amount", "canonical_name": "order_amount",
         "data_type": "numeric", "confidence": 0.65},
    ])

    with patch("data_pipeline.data_plane.bronze.llm_column_fallback.httpx.AsyncClient",
                return_value=_ok_post(gateway_payload)):
        out = await enrich_with_llm_fallback(
            mappings, LANG_DICT, "vi", enterprise_id="11111111-1111-1111-1111-111111111111",
        )

    assert out[0]["canonical_name"] == "customer_id"
    assert out[0]["method"] == "llm_fallback"
    assert out[0]["confidence"] == 0.7
    assert "LLM_FALLBACK_USED" in out[0]["uncertainty_flags"]

    assert out[1]["canonical_name"] == "order_amount"
    assert out[1]["data_type"] == "numeric"


# ─── Already-mapped rows untouched ──────────────────────────────────


@pytest.mark.asyncio
async def test_exact_and_fuzzy_rows_untouched():
    mappings = [
        {"source_column": "customer_id", "canonical_name": "customer_id",
         "data_type": "text", "confidence": 1.0, "method": "exact_match",
         "uncertainty_flags": []},
        {"source_column": "amount_x", "canonical_name": "order_amount",
         "data_type": "numeric", "confidence": 0.8, "method": "fuzzy_match",
         "uncertainty_flags": []},
    ]
    # No no_match rows — the function should NOT call the gateway at all.
    with patch("data_pipeline.data_plane.bronze.llm_column_fallback.httpx.AsyncClient") as ac:
        out = await enrich_with_llm_fallback(
            mappings, LANG_DICT, "vi", enterprise_id="x",
        )
    ac.assert_not_called()
    assert out[0]["method"] == "exact_match"
    assert out[1]["method"] == "fuzzy_match"


# ─── Gateway failure ────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_gateway_500_keeps_no_match():
    mappings = [
        {"source_column": "x", "canonical_name": "x",
         "data_type": "text", "confidence": 0.0, "method": "no_match",
         "uncertainty_flags": []},
    ]
    client = AsyncMock()
    client.post = AsyncMock(side_effect=httpx.HTTPError("gateway down"))
    client.__aenter__ = AsyncMock(return_value=client)
    client.__aexit__  = AsyncMock(return_value=None)

    with patch("data_pipeline.data_plane.bronze.llm_column_fallback.httpx.AsyncClient",
                return_value=client):
        out = await enrich_with_llm_fallback(
            mappings, LANG_DICT, "vi", enterprise_id="x",
        )
    assert out[0]["method"] == "no_match"
    assert out[0]["canonical_name"] == "x"


@pytest.mark.asyncio
async def test_gateway_returns_no_parsed_json_keeps_no_match():
    mappings = [
        {"source_column": "x", "canonical_name": "x", "data_type": "text",
         "confidence": 0.0, "method": "no_match", "uncertainty_flags": []},
    ]
    with patch("data_pipeline.data_plane.bronze.llm_column_fallback.httpx.AsyncClient",
                return_value=_ok_post({"completion": "...", "output_validation": {}})):
        out = await enrich_with_llm_fallback(
            mappings, LANG_DICT, "vi", enterprise_id="x",
        )
    assert out[0]["method"] == "no_match"


# ─── LLM says unknown ───────────────────────────────────────────────


@pytest.mark.asyncio
async def test_llm_unknown_response_keeps_no_match_with_flag():
    mappings = [
        {"source_column": "weird_col", "canonical_name": "weird_col",
         "data_type": "text", "confidence": 0.0, "method": "no_match",
         "uncertainty_flags": []},
    ]
    payload = _gateway_response([
        {"source_column": "weird_col", "canonical_name": "unknown",
         "data_type": "text", "confidence": 0.0},
    ])
    with patch("data_pipeline.data_plane.bronze.llm_column_fallback.httpx.AsyncClient",
                return_value=_ok_post(payload)):
        out = await enrich_with_llm_fallback(
            mappings, LANG_DICT, "vi", enterprise_id="x",
        )
    assert out[0]["method"] == "no_match"
    assert "LLM_FALLBACK_UNKNOWN" in out[0]["uncertainty_flags"]


# ─── K-4 invariant ──────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_consent_external_always_false():
    mappings = [
        {"source_column": "x", "canonical_name": "x", "data_type": "text",
         "confidence": 0.0, "method": "no_match", "uncertainty_flags": []},
    ]
    sent_body: dict = {}

    async def _capture_post(url, json):
        sent_body.update(json)
        resp = MagicMock()
        resp.json = MagicMock(return_value=_gateway_response([
            {"source_column": "x", "canonical_name": "customer_id",
             "data_type": "text", "confidence": 0.6},
        ]))
        resp.raise_for_status = MagicMock()
        return resp

    client = AsyncMock()
    client.post = _capture_post
    client.__aenter__ = AsyncMock(return_value=client)
    client.__aexit__  = AsyncMock(return_value=None)

    with patch("data_pipeline.data_plane.bronze.llm_column_fallback.httpx.AsyncClient",
                return_value=client):
        await enrich_with_llm_fallback(
            mappings, LANG_DICT, "vi", enterprise_id="x",
        )

    # K-4: schema work NEVER goes external. Always consent_external=False.
    assert sent_body["consent_external"] is False
    assert sent_body["task"] == "schema.column_mapping_fallback"


# ─── Overflow ───────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_overflow_beyond_max_batch():
    """Beyond MAX_BATCH (20) we cap the LLM call; remainder stays
    passthrough. Don't blow Qwen's context window."""
    mappings = [
        {"source_column": f"col_{i}", "canonical_name": f"col_{i}",
         "data_type": "text", "confidence": 0.0, "method": "no_match",
         "uncertainty_flags": []}
        for i in range(MAX_BATCH + 5)
    ]
    payload = _gateway_response([
        {"source_column": f"col_{i}", "canonical_name": "customer_id",
         "data_type": "text", "confidence": 0.5}
        for i in range(MAX_BATCH)
    ])
    with patch("data_pipeline.data_plane.bronze.llm_column_fallback.httpx.AsyncClient",
                return_value=_ok_post(payload)):
        out = await enrich_with_llm_fallback(
            mappings, LANG_DICT, "vi", enterprise_id="x",
        )
    # First MAX_BATCH spliced; remainder unchanged.
    for i in range(MAX_BATCH):
        assert out[i]["method"] == "llm_fallback", f"row {i} not spliced"
    for i in range(MAX_BATCH, MAX_BATCH + 5):
        assert out[i]["method"] == "no_match", f"overflow row {i} accidentally spliced"


# ─── Pilot guard: disabled / skip-empty / deadline ──────────────────


@pytest.mark.asyncio
async def test_disabled_skips_gateway(monkeypatch):
    """SCHEMA_LLM_FALLBACK off (pilot) → never touches the gateway."""
    monkeypatch.setattr(_fb, "FALLBACK_ENABLED", False)
    mappings = [
        {"source_column": "x", "canonical_name": "x", "data_type": "text",
         "confidence": 0.0, "method": "no_match", "uncertainty_flags": []},
    ]
    with patch("data_pipeline.data_plane.bronze.llm_column_fallback.httpx.AsyncClient") as ac:
        out = await enrich_with_llm_fallback(mappings, LANG_DICT, "vi", enterprise_id="x")
    ac.assert_not_called()
    assert out[0]["method"] == "no_match"


@pytest.mark.asyncio
async def test_empty_and_unnamed_columns_skipped(monkeypatch):
    """Blank / Unnamed columns are never sent — nothing to name, and they
    dominate the batch on real workbooks. All-empty batch → no gateway call."""
    monkeypatch.setattr(_fb, "FALLBACK_ENABLED", True)
    mappings = [
        {"source_column": "Unnamed: 3", "canonical_name": "unnamed:_3",
         "data_type": "text", "confidence": 0.0, "method": "no_match",
         "uncertainty_flags": [], "looks_unnamed": True, "is_empty": False},
        {"source_column": "blank_col", "canonical_name": "blank_col",
         "data_type": "text", "confidence": 0.0, "method": "no_match",
         "uncertainty_flags": [], "looks_unnamed": False, "is_empty": True},
    ]
    with patch("data_pipeline.data_plane.bronze.llm_column_fallback.httpx.AsyncClient") as ac:
        out = await enrich_with_llm_fallback(mappings, LANG_DICT, "vi", enterprise_id="x")
    ac.assert_not_called()
    assert all(m["method"] == "no_match" for m in out)


@pytest.mark.asyncio
async def test_deadline_exceeded_skips_gateway(monkeypatch):
    """Past the shared cross-sheet deadline → skip (passthrough) so a
    multi-sheet workbook can't blow the gateway timeout."""
    monkeypatch.setattr(_fb, "FALLBACK_ENABLED", True)
    mappings = [
        {"source_column": "x", "canonical_name": "x", "data_type": "text",
         "confidence": 0.0, "method": "no_match", "uncertainty_flags": []},
    ]
    with patch("data_pipeline.data_plane.bronze.llm_column_fallback.httpx.AsyncClient") as ac:
        out = await enrich_with_llm_fallback(
            mappings, LANG_DICT, "vi", enterprise_id="x",
            deadline=time.monotonic() - 1.0,   # already past
        )
    ac.assert_not_called()
    assert out[0]["method"] == "no_match"
