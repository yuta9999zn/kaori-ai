"""
F-033 Multi-tier Analysis — service layer tests (PR A).

Mirrors test_frameworks_service.py: asyncpg + llm_router + the
existing wizard runner are mocked. Cases cover validation +
orchestration; no real DB / Kafka.

  * queue_basic: rejects empty templates, over-long template list;
    success inserts a row + emits started event.
  * queue_intermediate: rejects unknown framework, empty question,
    bad source_ids count + shape; success inserts a row.
  * run_intermediate: happy path marks done with parsed JSON +
    narrative; LLM failure marks error without raising; row missing
    is a no-op.
  * Tier dispatch: basic delegates to wizard runner; advanced raises
    501 at the router layer (tested via TierNotImplementedError-equivalent
    check on InvalidRequestError boundary).
"""
from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch
from uuid import UUID, uuid4

import pytest

from ai_orchestrator.multi_tier import service


_ENT_ID = "11111111-1111-1111-1111-111111111111"


def _fake_acquire(conn):
    @asynccontextmanager
    async def _cm(_enterprise_id):
        yield conn
    return _cm


def _intermediate_row(run_id: UUID, **overrides) -> dict:
    base = {
        "id":                 run_id,
        "enterprise_id":      UUID(_ENT_ID),
        "pipeline_run_id":    None,
        "tier":               "intermediate",
        "scope":              "multi",
        "templates":          [],
        "config":             {},
        "framework":          "swot",
        "question":           "Mảng bán lẻ Q3 mạnh ở đâu?",
        "source_ids":         [
            {"layer": "silver", "id": "ds-1", "label": "rfm_q3"},
            {"layer": "gold",   "id": "revenue_at_risk", "label": None},
        ],
        "workspace_ids":      [],
        "consent_external":   False,
        "requires_approval":  False,
        "approved_by":        None,
        "approved_at":        None,
        "status":             "queued",
        "overview":           None,
        "narrative":          None,
        "output_schema_repaired": None,
        "started_at":         None,
        "completed_at":       None,
        "created_by_user":    None,
        "created_at":         datetime(2026, 5, 4, tzinfo=timezone.utc),
    }
    base.update(overrides)
    return base


# ─── queue_basic ─────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_queue_basic_inserts_row_and_emits_started():
    conn = AsyncMock()
    new_id = uuid4()
    pipeline_id = uuid4()
    with patch("ai_orchestrator.multi_tier.service.acquire_for_tenant",
               side_effect=_fake_acquire(conn)), \
         patch("ai_orchestrator.multi_tier.service.repository.create_basic_run",
               AsyncMock(return_value=new_id)) as create_mock, \
         patch("ai_orchestrator.multi_tier.service.emit",
               AsyncMock()) as emit_mock:
        out = await service.queue_basic(
            enterprise_id=_ENT_ID,
            pipeline_run_id=pipeline_id,
            templates_=["summary_stats", "rfm_churn"],
            question="Khách rời nhiều nhất ở đâu?",
            config={"summary_stats": {}},
            consent_external=False,
            created_by_user=None,
        )
    assert out == new_id
    create_mock.assert_awaited_once()
    emit_mock.assert_awaited_once()
    topic, payload = emit_mock.await_args.args
    assert topic == "kaori.analysis.tier.started"
    assert payload["tier"] == "basic"
    assert payload["scope"] == "single"
    assert payload["framework"] is None


@pytest.mark.asyncio
async def test_queue_basic_empty_templates_rejected():
    pipeline_id = uuid4()
    with pytest.raises(service.InvalidRequestError, match="templates is required"):
        await service.queue_basic(
            enterprise_id=_ENT_ID,
            pipeline_run_id=pipeline_id,
            templates_=[],
            question=None,
            config=None,
            consent_external=False,
            created_by_user=None,
        )


@pytest.mark.asyncio
async def test_queue_basic_too_many_templates_rejected():
    pipeline_id = uuid4()
    with pytest.raises(service.InvalidRequestError, match="at most 10 templates"):
        await service.queue_basic(
            enterprise_id=_ENT_ID,
            pipeline_run_id=pipeline_id,
            templates_=[f"t{i}" for i in range(11)],
            question=None,
            config=None,
            consent_external=False,
            created_by_user=None,
        )


# ─── queue_intermediate ──────────────────────────────────────────


@pytest.mark.asyncio
async def test_queue_intermediate_inserts_row_and_emits_started():
    conn = AsyncMock()
    new_id = uuid4()
    sources = [
        {"layer": "silver", "id": "ds-1", "label": "rfm_q3"},
        {"layer": "gold",   "id": "revenue_at_risk"},
    ]
    with patch("ai_orchestrator.multi_tier.service.acquire_for_tenant",
               side_effect=_fake_acquire(conn)), \
         patch("ai_orchestrator.multi_tier.service.repository.create_intermediate_run",
               AsyncMock(return_value=new_id)) as create_mock, \
         patch("ai_orchestrator.multi_tier.service.emit",
               AsyncMock()) as emit_mock:
        out = await service.queue_intermediate(
            enterprise_id=_ENT_ID,
            framework="swot",
            question="Mảng bán lẻ Q3 mạnh ở đâu?",
            source_ids=sources,
            consent_external=False,
            created_by_user=None,
        )
    assert out == new_id
    create_mock.assert_awaited_once()
    emit_mock.assert_awaited_once()
    topic, payload = emit_mock.await_args.args
    assert topic == "kaori.analysis.tier.started"
    assert payload["tier"] == "intermediate"
    assert payload["framework"] == "swot"


@pytest.mark.asyncio
async def test_queue_intermediate_unknown_framework_rejected():
    sources = [
        {"layer": "silver", "id": "ds-1"},
        {"layer": "gold",   "id": "revenue_at_risk"},
    ]
    with pytest.raises(service.InvalidRequestError, match="unknown framework"):
        await service.queue_intermediate(
            enterprise_id=_ENT_ID,
            framework="5why",
            question="x",
            source_ids=sources,
            consent_external=False,
            created_by_user=None,
        )


@pytest.mark.asyncio
async def test_queue_intermediate_empty_question_rejected():
    sources = [
        {"layer": "silver", "id": "ds-1"},
        {"layer": "gold",   "id": "revenue_at_risk"},
    ]
    with pytest.raises(service.InvalidRequestError, match="question is required"):
        await service.queue_intermediate(
            enterprise_id=_ENT_ID,
            framework="swot",
            question="    ",
            source_ids=sources,
            consent_external=False,
            created_by_user=None,
        )


@pytest.mark.asyncio
async def test_queue_intermediate_too_few_sources_rejected():
    with pytest.raises(service.InvalidRequestError, match="2 to 5 items"):
        await service.queue_intermediate(
            enterprise_id=_ENT_ID,
            framework="swot",
            question="x",
            source_ids=[{"layer": "silver", "id": "ds-1"}],
            consent_external=False,
            created_by_user=None,
        )


@pytest.mark.asyncio
async def test_queue_intermediate_too_many_sources_rejected():
    sources = [{"layer": "silver", "id": f"ds-{i}"} for i in range(6)]
    with pytest.raises(service.InvalidRequestError, match="2 to 5 items"):
        await service.queue_intermediate(
            enterprise_id=_ENT_ID,
            framework="swot",
            question="x",
            source_ids=sources,
            consent_external=False,
            created_by_user=None,
        )


@pytest.mark.asyncio
async def test_queue_intermediate_bad_layer_rejected():
    with pytest.raises(service.InvalidRequestError, match="layer must be"):
        await service.queue_intermediate(
            enterprise_id=_ENT_ID,
            framework="swot",
            question="x",
            source_ids=[
                {"layer": "bronze", "id": "ds-1"},
                {"layer": "gold",   "id": "rar"},
            ],
            consent_external=False,
            created_by_user=None,
        )


@pytest.mark.asyncio
async def test_queue_intermediate_missing_id_rejected():
    with pytest.raises(service.InvalidRequestError, match="missing id/feature"):
        await service.queue_intermediate(
            enterprise_id=_ENT_ID,
            framework="swot",
            question="x",
            source_ids=[
                {"layer": "silver"},
                {"layer": "gold", "id": "rar"},
            ],
            consent_external=False,
            created_by_user=None,
        )


# ─── run_intermediate ────────────────────────────────────────────


@pytest.mark.asyncio
async def test_run_intermediate_happy_path():
    conn = AsyncMock()
    run_id = uuid4()
    parsed = {
        "strengths":     {"items": [{"text": "A", "confidence": 0.8}, {"text": "B", "confidence": 0.7}]},
        "weaknesses":    {"items": [{"text": "C", "confidence": 0.6}, {"text": "D", "confidence": 0.5}]},
        "opportunities": {"items": [{"text": "E", "confidence": 0.7}, {"text": "F", "confidence": 0.6}]},
        "threats":       {"items": [{"text": "G", "confidence": 0.5}, {"text": "H", "confidence": 0.4}]},
        "summary":       "Hành động ưu tiên: tập trung phân khúc retail premium.",
    }
    with patch("ai_orchestrator.multi_tier.service.acquire_for_tenant",
               side_effect=_fake_acquire(conn)), \
         patch("ai_orchestrator.multi_tier.service.repository.fetch_run",
               AsyncMock(return_value=_intermediate_row(run_id))), \
         patch("ai_orchestrator.multi_tier.service.repository.mark_running",
               AsyncMock()), \
         patch("ai_orchestrator.multi_tier.service.repository.mark_done",
               AsyncMock()) as done_mock, \
         patch("ai_orchestrator.multi_tier.service.llm_router") as router_mock, \
         patch("ai_orchestrator.multi_tier.service.log_decision",
               AsyncMock()) as audit_mock, \
         patch("ai_orchestrator.multi_tier.service.emit",
               AsyncMock()) as emit_mock:
        router_mock.complete_structured = AsyncMock(return_value=parsed)
        await service.run_intermediate(enterprise_id=_ENT_ID, run_id=run_id)

    done_mock.assert_awaited_once()
    kwargs = done_mock.await_args.kwargs
    assert kwargs["overview"] == parsed
    assert kwargs["narrative"] == "Hành động ưu tiên: tập trung phân khúc retail premium."
    audit_mock.assert_awaited_once()
    # Should emit terminal event with status='done'.
    assert any(
        call.args[0] == "kaori.analysis.tier.completed"
        and call.args[1]["status"] == "done"
        for call in emit_mock.await_args_list
    )


@pytest.mark.asyncio
async def test_run_intermediate_llm_failure_marks_error():
    conn = AsyncMock()
    run_id = uuid4()
    with patch("ai_orchestrator.multi_tier.service.acquire_for_tenant",
               side_effect=_fake_acquire(conn)), \
         patch("ai_orchestrator.multi_tier.service.repository.fetch_run",
               AsyncMock(return_value=_intermediate_row(run_id))), \
         patch("ai_orchestrator.multi_tier.service.repository.mark_running",
               AsyncMock()), \
         patch("ai_orchestrator.multi_tier.service.repository.mark_error",
               AsyncMock()) as error_mock, \
         patch("ai_orchestrator.multi_tier.service.llm_router") as router_mock, \
         patch("ai_orchestrator.multi_tier.service.emit",
               AsyncMock()):
        router_mock.complete_structured = AsyncMock(
            side_effect=RuntimeError("gateway 502"),
        )
        # Must not re-raise — background task safety contract.
        await service.run_intermediate(enterprise_id=_ENT_ID, run_id=run_id)

    error_mock.assert_awaited_once()
    args, _ = error_mock.await_args
    assert "gateway 502" in args[2]


@pytest.mark.asyncio
async def test_run_intermediate_row_missing_is_noop():
    conn = AsyncMock()
    run_id = uuid4()
    with patch("ai_orchestrator.multi_tier.service.acquire_for_tenant",
               side_effect=_fake_acquire(conn)), \
         patch("ai_orchestrator.multi_tier.service.repository.fetch_run",
               AsyncMock(return_value=None)), \
         patch("ai_orchestrator.multi_tier.service.repository.mark_running",
               AsyncMock()) as running_mock, \
         patch("ai_orchestrator.multi_tier.service.repository.mark_error",
               AsyncMock()) as error_mock, \
         patch("ai_orchestrator.multi_tier.service.emit",
               AsyncMock()):
        await service.run_intermediate(enterprise_id=_ENT_ID, run_id=run_id)

    running_mock.assert_not_awaited()
    error_mock.assert_not_awaited()


# ─── _format_sources helper ──────────────────────────────────────


def test_format_sources_handles_silver_and_gold():
    out = service._format_sources([
        {"layer": "silver", "id": "ds-1", "label": "rfm_q3"},
        {"layer": "gold",   "id": "revenue_at_risk", "label": None},
    ])
    assert "Silver dataset rfm_q3" in out
    assert "Gold feature revenue_at_risk" in out


def test_format_sources_empty_returns_placeholder():
    assert service._format_sources([]) == "(không có nguồn)"


# ─── queue_advanced (PR B) ──────────────────────────────────────


def _advanced_row(run_id: UUID, **overrides) -> dict:
    base = _intermediate_row(run_id)
    base.update({
        "tier":              "advanced",
        "scope":             "cross",
        "consent_external":  True,
        "requires_approval": True,
        "approved_by":       None,
        "approved_at":       None,
    })
    base.update(overrides)
    return base


@pytest.mark.asyncio
async def test_queue_advanced_strict_tenant_requires_approval():
    conn = AsyncMock()
    new_id = uuid4()
    sources = [
        {"layer": "silver", "id": "ds-1"},
        {"layer": "gold",   "id": "rar"},
    ]
    with patch("ai_orchestrator.multi_tier.service.acquire_for_tenant",
               side_effect=_fake_acquire(conn)), \
         patch("ai_orchestrator.multi_tier.service.repository.fetch_tenant_consent",
               AsyncMock(return_value=False)), \
         patch("ai_orchestrator.multi_tier.service.repository.create_advanced_run",
               AsyncMock(return_value=new_id)) as create_mock, \
         patch("ai_orchestrator.multi_tier.service.emit", AsyncMock()):
        out = await service.queue_advanced(
            enterprise_id=_ENT_ID,
            framework="swot",
            question="Cohort SMB Q1/Q2 churn?",
            source_ids=sources,
            workspace_ids=None,
            consent_external=True,
            created_by_user=None,
        )
    assert out["run_id"] == new_id
    assert out["requires_approval"] is True
    create_mock.assert_awaited_once()
    # requires_approval must be passed True to the repository
    assert create_mock.await_args.kwargs["requires_approval"] is True


@pytest.mark.asyncio
async def test_queue_advanced_consenting_tenant_skips_approval():
    conn = AsyncMock()
    new_id = uuid4()
    sources = [
        {"layer": "silver", "id": "ds-1"},
        {"layer": "gold",   "id": "rar"},
    ]
    with patch("ai_orchestrator.multi_tier.service.acquire_for_tenant",
               side_effect=_fake_acquire(conn)), \
         patch("ai_orchestrator.multi_tier.service.repository.fetch_tenant_consent",
               AsyncMock(return_value=True)), \
         patch("ai_orchestrator.multi_tier.service.repository.create_advanced_run",
               AsyncMock(return_value=new_id)) as create_mock, \
         patch("ai_orchestrator.multi_tier.service.emit", AsyncMock()):
        out = await service.queue_advanced(
            enterprise_id=_ENT_ID,
            framework="swot",
            question="x",
            source_ids=sources,
            workspace_ids=None,
            consent_external=True,
            created_by_user=None,
        )
    assert out["requires_approval"] is False
    assert create_mock.await_args.kwargs["requires_approval"] is False


@pytest.mark.asyncio
async def test_queue_advanced_no_consent_rejected():
    """Service-layer K-4 guard — DB CHECK catches it too but the
    user-facing 400 is friendlier than a constraint error."""
    sources = [
        {"layer": "silver", "id": "ds-1"},
        {"layer": "gold",   "id": "rar"},
    ]
    with pytest.raises(service.InvalidRequestError, match="consent_external=true"):
        await service.queue_advanced(
            enterprise_id=_ENT_ID,
            framework="swot",
            question="x",
            source_ids=sources,
            workspace_ids=None,
            consent_external=False,
            created_by_user=None,
        )


@pytest.mark.asyncio
async def test_queue_advanced_unknown_framework_rejected():
    sources = [
        {"layer": "silver", "id": "ds-1"},
        {"layer": "gold",   "id": "rar"},
    ]
    with pytest.raises(service.InvalidRequestError, match="unknown framework"):
        await service.queue_advanced(
            enterprise_id=_ENT_ID,
            framework="5why",
            question="x",
            source_ids=sources,
            workspace_ids=None,
            consent_external=True,
            created_by_user=None,
        )


# ─── approve ─────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_approve_pending_run_flips_and_audits():
    conn = AsyncMock()
    run_id = uuid4()
    approver = uuid4()
    with patch("ai_orchestrator.multi_tier.service.acquire_for_tenant",
               side_effect=_fake_acquire(conn)), \
         patch("ai_orchestrator.multi_tier.service.repository.approve_run",
               AsyncMock(return_value={"id": run_id, "status": "queued"})) as approve_mock, \
         patch("ai_orchestrator.multi_tier.service.log_decision",
               AsyncMock()) as audit_mock:
        ok = await service.approve(
            enterprise_id=_ENT_ID,
            run_id=run_id,
            approver_user_id=approver,
        )
    assert ok is True
    approve_mock.assert_awaited_once()
    audit_mock.assert_awaited_once()


@pytest.mark.asyncio
async def test_approve_missing_or_already_approved_returns_false():
    conn = AsyncMock()
    run_id = uuid4()
    with patch("ai_orchestrator.multi_tier.service.acquire_for_tenant",
               side_effect=_fake_acquire(conn)), \
         patch("ai_orchestrator.multi_tier.service.repository.approve_run",
               AsyncMock(return_value=None)), \
         patch("ai_orchestrator.multi_tier.service.log_decision",
               AsyncMock()) as audit_mock:
        ok = await service.approve(
            enterprise_id=_ENT_ID,
            run_id=run_id,
            approver_user_id=uuid4(),
        )
    assert ok is False
    audit_mock.assert_not_awaited()


# ─── run_advanced ───────────────────────────────────────────────


@pytest.mark.asyncio
async def test_run_advanced_short_circuits_when_pending_approval():
    conn = AsyncMock()
    run_id = uuid4()
    pending_row = _advanced_row(run_id, requires_approval=True, approved_at=None)
    with patch("ai_orchestrator.multi_tier.service.acquire_for_tenant",
               side_effect=_fake_acquire(conn)), \
         patch("ai_orchestrator.multi_tier.service.repository.fetch_run",
               AsyncMock(return_value=pending_row)), \
         patch("ai_orchestrator.multi_tier.service.repository.mark_running",
               AsyncMock()) as running_mock, \
         patch("ai_orchestrator.multi_tier.service.llm_router") as router_mock, \
         patch("ai_orchestrator.multi_tier.service.emit", AsyncMock()):
        router_mock.complete_structured = AsyncMock()
        await service.run_advanced(enterprise_id=_ENT_ID, run_id=run_id)

    running_mock.assert_not_awaited()
    router_mock.complete_structured.assert_not_called()


@pytest.mark.asyncio
async def test_run_advanced_dispatches_when_consenting_tenant():
    conn = AsyncMock()
    run_id = uuid4()
    parsed = {
        "strengths":     {"items": [{"text": "S1", "confidence": 0.8}, {"text": "S2", "confidence": 0.7}]},
        "weaknesses":    {"items": [{"text": "W1", "confidence": 0.5}, {"text": "W2", "confidence": 0.4}]},
        "opportunities": {"items": [{"text": "O1", "confidence": 0.7}, {"text": "O2", "confidence": 0.6}]},
        "threats":       {"items": [{"text": "T1", "confidence": 0.5}, {"text": "T2", "confidence": 0.4}]},
        "summary":       "Strategy summary.",
    }
    consenting_row = _advanced_row(
        run_id,
        requires_approval=False, approved_at=None,
    )
    with patch("ai_orchestrator.multi_tier.service.acquire_for_tenant",
               side_effect=_fake_acquire(conn)), \
         patch("ai_orchestrator.multi_tier.service.repository.fetch_run",
               AsyncMock(return_value=consenting_row)), \
         patch("ai_orchestrator.multi_tier.service.repository.mark_running",
               AsyncMock()) as running_mock, \
         patch("ai_orchestrator.multi_tier.service.repository.mark_done",
               AsyncMock()) as done_mock, \
         patch("ai_orchestrator.multi_tier.service.llm_router") as router_mock, \
         patch("ai_orchestrator.multi_tier.service.log_decision", AsyncMock()) as audit_mock, \
         patch("ai_orchestrator.multi_tier.service.emit", AsyncMock()):
        router_mock.complete_structured = AsyncMock(return_value=parsed)
        await service.run_advanced(enterprise_id=_ENT_ID, run_id=run_id)

    running_mock.assert_awaited_once()
    done_mock.assert_awaited_once()
    # llm_router must be called with consent_external=True
    router_mock.complete_structured.assert_awaited_once()
    assert router_mock.complete_structured.await_args.kwargs["consent_external"] is True
    # audit row tagged llm_provider='external'
    audit_mock.assert_awaited_once()
    assert audit_mock.await_args.kwargs["llm_provider"] == "external"


@pytest.mark.asyncio
async def test_run_advanced_dispatches_after_approval():
    conn = AsyncMock()
    run_id = uuid4()
    approved_row = _advanced_row(
        run_id,
        requires_approval=True,
        approved_by=uuid4(),
        approved_at=datetime(2026, 5, 4, tzinfo=timezone.utc),
    )
    parsed = {
        "strengths":     {"items": [{"text": "x", "confidence": 0.8}, {"text": "y", "confidence": 0.7}]},
        "weaknesses":    {"items": [{"text": "x", "confidence": 0.5}, {"text": "y", "confidence": 0.4}]},
        "opportunities": {"items": [{"text": "x", "confidence": 0.7}, {"text": "y", "confidence": 0.6}]},
        "threats":       {"items": [{"text": "x", "confidence": 0.5}, {"text": "y", "confidence": 0.4}]},
        "summary":       "ok",
    }
    with patch("ai_orchestrator.multi_tier.service.acquire_for_tenant",
               side_effect=_fake_acquire(conn)), \
         patch("ai_orchestrator.multi_tier.service.repository.fetch_run",
               AsyncMock(return_value=approved_row)), \
         patch("ai_orchestrator.multi_tier.service.repository.mark_running",
               AsyncMock()) as running_mock, \
         patch("ai_orchestrator.multi_tier.service.repository.mark_done",
               AsyncMock()) as done_mock, \
         patch("ai_orchestrator.multi_tier.service.llm_router") as router_mock, \
         patch("ai_orchestrator.multi_tier.service.log_decision", AsyncMock()), \
         patch("ai_orchestrator.multi_tier.service.emit", AsyncMock()):
        router_mock.complete_structured = AsyncMock(return_value=parsed)
        await service.run_advanced(enterprise_id=_ENT_ID, run_id=run_id)

    running_mock.assert_awaited_once()
    done_mock.assert_awaited_once()
