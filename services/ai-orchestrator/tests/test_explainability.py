"""
F-041 Explainability — service + router tests.

Mocks asyncpg + llm_router; we exercise the orchestration:
  * tenant scope read → 404 when row absent
  * happy path returns parsed schema + writes K-6 audit row
  * llm failure raises ExplanationFailedError (router 502)
  * prompt rendering pulls every audit field
"""
from __future__ import annotations

from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID, uuid4

import pytest

from ai_orchestrator.explainability import service
from ai_orchestrator.explainability.service import (
    DecisionNotFoundError,
    ExplanationFailedError,
)


_ENT_ID = "11111111-1111-1111-1111-111111111111"


def _fake_acquire(conn):
    @asynccontextmanager
    async def _cm(_enterprise_id):
        yield conn
    return _cm


def _audit_row(decision_id: UUID, **overrides) -> dict:
    base = {
        "decision_id":       decision_id,
        "decision_type":     "schema.column_map",
        "subject":            "doanh_thu",
        "chosen_value":       "revenue",
        "confidence":         0.92,
        "method":             "fuzzy",
        "llm_provider":       None,
        "reasoning":          "Levenshtein 0.92 với 'revenue' trong language_dictionary VI.",
        "alternatives":       [{"value": "sales", "score": 0.71}],
        "uncertainty_flags":  [],
    }
    base.update(overrides)

    class FakeRow:
        def __getitem__(self, key):
            return base[key]
        def __contains__(self, key):
            return key in base

    return FakeRow()


_PARSED_OK = {
    "top_factors": [
        {"factor_name": "Khớp ngữ nghĩa Levenshtein cao", "direction": "positive", "weight": 0.7,
         "evidence": "Khoảng cách edit-distance 0.92 với 'revenue' trong dictionary VI."},
        {"factor_name": "Không có ứng viên cạnh tranh", "direction": "positive", "weight": 0.2,
         "evidence": "Lựa chọn thay thế 'sales' chỉ đạt 0.71 — kém xa 'revenue'."},
        {"factor_name": "Không có cờ uncertainty", "direction": "positive", "weight": 0.1,
         "evidence": "uncertainty_flags rỗng."},
    ],
    "narrative": "Kaori chọn map cột 'doanh_thu' sang 'revenue' vì độ khớp ngữ nghĩa rất cao và không có lựa chọn cạnh tranh đáng kể.",
    "confidence_explanation": "Confidence 0.92 phản ánh khoảng cách edit-distance gần 1.0 — rất ít rủi ro nhầm.",
}


# ─── DecisionNotFound ────────────────────────────────────────────


@pytest.mark.asyncio
async def test_explain_missing_row_raises_not_found():
    decision_id = uuid4()
    conn = AsyncMock()
    conn.fetchrow = AsyncMock(return_value=None)
    with patch("ai_orchestrator.explainability.service.acquire_for_tenant",
               side_effect=_fake_acquire(conn)):
        with pytest.raises(DecisionNotFoundError):
            await service.explain(decision_id=decision_id, enterprise_id=_ENT_ID)


# ─── Happy path ──────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_explain_happy_path_returns_parsed_and_audits():
    decision_id = uuid4()
    conn = AsyncMock()
    conn.fetchrow = AsyncMock(return_value=_audit_row(decision_id))
    with patch("ai_orchestrator.explainability.service.acquire_for_tenant",
               side_effect=_fake_acquire(conn)), \
         patch("ai_orchestrator.explainability.service.llm_router") as router_mock, \
         patch("ai_orchestrator.explainability.service.log_decision",
               AsyncMock()) as audit_mock:
        router_mock.complete_structured = AsyncMock(return_value=_PARSED_OK)
        out = await service.explain(decision_id=decision_id, enterprise_id=_ENT_ID)

    assert out == _PARSED_OK
    audit_mock.assert_awaited_once()
    assert audit_mock.await_args.kwargs["decision_type"] == "explainability.explain"
    assert audit_mock.await_args.kwargs["subject"] == str(decision_id)


@pytest.mark.asyncio
async def test_explain_consent_external_tags_provider_external():
    decision_id = uuid4()
    conn = AsyncMock()
    conn.fetchrow = AsyncMock(return_value=_audit_row(decision_id))
    with patch("ai_orchestrator.explainability.service.acquire_for_tenant",
               side_effect=_fake_acquire(conn)), \
         patch("ai_orchestrator.explainability.service.llm_router") as router_mock, \
         patch("ai_orchestrator.explainability.service.log_decision",
               AsyncMock()) as audit_mock:
        router_mock.complete_structured = AsyncMock(return_value=_PARSED_OK)
        await service.explain(
            decision_id=decision_id, enterprise_id=_ENT_ID, consent_external=True,
        )

    assert audit_mock.await_args.kwargs["llm_provider"] == "external"
    # llm_router got the consent flag through.
    assert router_mock.complete_structured.await_args.kwargs["consent_external"] is True


# ─── LLM failure → ExplanationFailedError ────────────────────────


@pytest.mark.asyncio
async def test_explain_llm_failure_raises():
    decision_id = uuid4()
    conn = AsyncMock()
    conn.fetchrow = AsyncMock(return_value=_audit_row(decision_id))
    with patch("ai_orchestrator.explainability.service.acquire_for_tenant",
               side_effect=_fake_acquire(conn)), \
         patch("ai_orchestrator.explainability.service.llm_router") as router_mock, \
         patch("ai_orchestrator.explainability.service.log_decision",
               AsyncMock()) as audit_mock:
        router_mock.complete_structured = AsyncMock(
            side_effect=RuntimeError("gateway 502 LLM.OUTPUT_VALIDATION_FAILED"),
        )
        with pytest.raises(ExplanationFailedError, match="gateway 502"):
            await service.explain(decision_id=decision_id, enterprise_id=_ENT_ID)

    # Audit row NOT written when LLM fails — explainability call itself
    # failed, no decision to log.
    audit_mock.assert_not_awaited()


# ─── Prompt rendering pulls every field ──────────────────────────


def test_render_prompt_includes_audit_fields():
    decision_id = uuid4()
    row = _audit_row(decision_id, reasoning="My reasoning text.", confidence=0.65,
                     method="llm", llm_provider="external",
                     uncertainty_flags=["sample_size_small"])
    rendered = service._render_prompt(row)
    assert "schema.column_map" in rendered
    assert "doanh_thu" in rendered  # subject
    assert "revenue" in rendered    # chosen_value
    assert "0.65" in rendered       # confidence
    assert "sample_size_small" in rendered
    assert "My reasoning text." in rendered
    assert "sales" in rendered      # alternative


def test_render_prompt_handles_string_alternatives():
    """alternatives column can be JSONB — asyncpg may return either a
    parsed list or a raw string. Both code paths must work."""
    decision_id = uuid4()
    row = _audit_row(decision_id, alternatives='[{"value":"X","score":0.5}]')
    rendered = service._render_prompt(row)
    assert "X" in rendered
