"""
F-038 Reports — service layer tests.

asyncpg + llm_router + kafka_producer + outbox are all mocked. We're
testing the orchestration around them:

  * happy path: queued -> running -> ready, with parsed_json saved,
    narrative extracted, kafka emit fired, outbox row inserted.
  * unknown template_id at queue time -> TemplateNotFoundError (router
    converts to 404).
  * llm-gateway raises (consent denied / structured output failed) ->
    row marked failed, kafka emit fires with status='failed', no
    outbox notification.
  * background-task crash safety: any unhandled raise inside
    run_report still ends in a mark_failed write so the row never
    sits in 'running' forever.
"""
from __future__ import annotations

import json
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID, uuid4

import pytest

from ai_orchestrator.reports import service
from ai_orchestrator.reports.service import (
    InvalidDistributionError,
    ReportNotFoundError,
    ReportNotReadyError,
    TemplateNotFoundError,
)


# ─── Helpers ─────────────────────────────────────────────────────

_ENT_ID = "11111111-1111-1111-1111-111111111111"
_TEMPLATE_ID = UUID("00000000-0000-0000-0000-000000000001")  # built-in monthly_summary

_VALID_PARSED = {
    "kpi_overview": [
        {"label": "Doanh thu",     "value": "1,2 tỷ ₫", "trend": "up"},
        {"label": "Khách hàng mới","value": "143",       "trend": "up"},
    ],
    "trends": [
        {"title": "Doanh thu Q1 vượt kế hoạch 12%",
         "summary": "Tăng đều qua 3 tháng, mạnh nhất nhóm khách hàng SME."},
    ],
    "top_risks": [
        {"risk": "Tồn kho hàng theo mùa cao", "severity": "medium"},
    ],
    "recommendations": [
        {"action": "Khuyến mãi 5% cho dòng A trong 4 tuần",
         "owner_role": "Sales Manager",
         "deadline_relative": "trong 30 ngày"},
    ],
}

_TEMPLATE_ROW = {
    "template_id":   _TEMPLATE_ID,
    "enterprise_id": None,
    "name":          "Báo cáo tổng hợp tháng",
    "description":   "test",
    "system_prompt": "Tóm tắt cho {{enterprise_name}} kỳ {{period}}.",
    "output_schema": {"type": "object"},
    "is_built_in":   True,
}


def _fake_acquire(conn):
    """Build an async-context-manager that yields ``conn``. Mirrors
    services/data-pipeline/shared/db.acquire_for_tenant + the
    ai-orchestrator equivalent used inside service.py."""
    @asynccontextmanager
    async def _cm(_enterprise_id):
        yield conn
    return _cm


def _fake_pool(conn):
    """Same shape for shared.db.get_pool() — pool.acquire() yields
    ``conn`` as an async context manager."""
    @asynccontextmanager
    async def _cm():
        yield conn
    pool = MagicMock()
    pool.acquire = MagicMock(side_effect=_cm)
    return pool


# ─── queue_report ────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_queue_report_inserts_row_and_returns_id():
    conn = AsyncMock()
    new_id = uuid4()

    with patch("ai_orchestrator.reports.service.acquire_for_tenant",
               side_effect=_fake_acquire(conn)), \
         patch("ai_orchestrator.reports.service.repository.fetch_template",
               AsyncMock(return_value=_TEMPLATE_ROW)), \
         patch("ai_orchestrator.reports.service.repository.create_report",
               AsyncMock(return_value=new_id)) as create_mock:

        out_id = await service.queue_report(
            enterprise_id=_ENT_ID,
            template_id=_TEMPLATE_ID,
            title="Báo cáo demo",
            owner_email="user@kaori.io",
            params={"period": "2026-04"},
        )

    assert out_id == new_id
    create_mock.assert_awaited_once()
    kwargs = create_mock.await_args.kwargs
    assert kwargs["title"] == "Báo cáo demo"
    assert kwargs["owner_email"] == "user@kaori.io"
    assert kwargs["params"] == {"period": "2026-04"}


@pytest.mark.asyncio
async def test_queue_report_unknown_template_raises_template_not_found():
    """A typo'd template_id should fail at queue time, not silently
    leave a zombie 'queued' row no worker can resolve."""
    conn = AsyncMock()

    with patch("ai_orchestrator.reports.service.acquire_for_tenant",
               side_effect=_fake_acquire(conn)), \
         patch("ai_orchestrator.reports.service.repository.fetch_template",
               AsyncMock(return_value=None)), \
         patch("ai_orchestrator.reports.service.repository.create_report",
               AsyncMock()) as create_mock:

        with pytest.raises(TemplateNotFoundError):
            await service.queue_report(
                enterprise_id=_ENT_ID,
                template_id=uuid4(),
                title="x",
                owner_email="u@k.io",
                params={},
            )

    create_mock.assert_not_called()


# ─── run_report — happy path ─────────────────────────────────────

@pytest.mark.asyncio
async def test_run_report_happy_path_marks_ready_emits_event_and_enqueues_email():
    """End-to-end happy: running -> llm OK -> ready + Kafka emit
    'ready' + outbox row enqueued."""
    report_id = uuid4()
    conn = AsyncMock()
    conn.fetch = AsyncMock(return_value=[])  # no analysis_runs in context
    conn.execute = AsyncMock(return_value=None)

    report_row = {
        "report_id":    report_id,
        "template_id":  _TEMPLATE_ID,
        "title":        "Báo cáo demo",
        "owner_email":  "user@kaori.io",
        "status":       "queued",
        "narrative":    None,
        "created_at":   datetime(2026, 5, 2, tzinfo=timezone.utc),
        "completed_at": None,
        "last_error":   None,
        "content_json": None,
    }

    with patch("ai_orchestrator.reports.service.acquire_for_tenant",
               side_effect=_fake_acquire(conn)), \
         patch("ai_orchestrator.reports.service.get_pool",
               return_value=_fake_pool(conn)), \
         patch("ai_orchestrator.reports.service.repository.fetch_report",
               AsyncMock(return_value=report_row)), \
         patch("ai_orchestrator.reports.service.repository.fetch_template",
               AsyncMock(return_value=_TEMPLATE_ROW)), \
         patch("ai_orchestrator.reports.service.repository.mark_running",
               AsyncMock()) as mark_running, \
         patch("ai_orchestrator.reports.service.repository.mark_ready",
               AsyncMock()) as mark_ready, \
         patch("ai_orchestrator.reports.service.repository.mark_failed",
               AsyncMock()) as mark_failed, \
         patch("ai_orchestrator.reports.service.llm_router.complete_structured",
               AsyncMock(return_value=_VALID_PARSED)) as llm_call, \
         patch("ai_orchestrator.reports.service.emit",
               AsyncMock()) as emit_mock:

        await service.run_report(enterprise_id=_ENT_ID, report_id=report_id)

    mark_running.assert_awaited_once()
    llm_call.assert_awaited_once()
    # The structured call carries the template's output_schema and the
    # rendered system prompt + context block as the user prompt.
    llm_kwargs = llm_call.await_args.kwargs
    assert llm_kwargs["output_schema"] == _TEMPLATE_ROW["output_schema"]
    assert llm_kwargs["task"] == "reports.generate"
    assert "{{enterprise_name}}" not in llm_kwargs["prompt"], (
        "Jinja placeholders should be substituted before reaching the LLM"
    )

    mark_ready.assert_awaited_once()
    ready_kwargs = mark_ready.await_args.kwargs
    assert ready_kwargs["content_json"] == _VALID_PARSED
    # Narrative pulled from trends[0].title + summary (see _extract_narrative).
    assert ready_kwargs["narrative"]
    assert "vượt kế hoạch" in ready_kwargs["narrative"]

    mark_failed.assert_not_called()

    # Kafka emit fired with status='ready' and the canonical fields.
    emit_mock.assert_awaited_once()
    emit_args = emit_mock.await_args.args
    assert emit_args[0] == "kaori.reports.generated"
    payload = emit_args[1]
    assert payload["report_id"] == str(report_id)
    assert payload["status"] == "ready"
    assert payload["enterprise_id"] == _ENT_ID
    assert payload["title"] == "Báo cáo demo"

    # Outbox row inserted via the pool's connection.
    insert_calls = [c for c in conn.execute.await_args_list
                    if "INSERT INTO notification_outbox" in str(c.args[0])]
    assert len(insert_calls) == 1
    insert_args = insert_calls[0].args
    assert insert_args[2] == "report-ready"          # template
    assert insert_args[3] == "user@kaori.io"          # recipient
    ctx = json.loads(insert_args[4])                  # context jsonb
    assert ctx["report_title"] == "Báo cáo demo"


# ─── run_report — failure paths ──────────────────────────────────

@pytest.mark.asyncio
async def test_run_report_llm_failure_marks_failed_and_emits_failed_event():
    """llm-gateway raised (consent denied, structured output gave up).
    Row goes to 'failed' + Kafka 'failed' event + NO outbox email."""
    report_id = uuid4()
    conn = AsyncMock()
    conn.fetch = AsyncMock(return_value=[])
    conn.execute = AsyncMock(return_value=None)

    report_row = {
        "report_id":    report_id,
        "template_id":  _TEMPLATE_ID,
        "title":        "Doomed report",
        "owner_email":  "user@kaori.io",
        "status":       "queued",
        "narrative":    None,
        "created_at":   datetime(2026, 5, 2, tzinfo=timezone.utc),
        "completed_at": None,
        "last_error":   None,
        "content_json": None,
    }

    with patch("ai_orchestrator.reports.service.acquire_for_tenant",
               side_effect=_fake_acquire(conn)), \
         patch("ai_orchestrator.reports.service.get_pool",
               return_value=_fake_pool(conn)), \
         patch("ai_orchestrator.reports.service.repository.fetch_report",
               AsyncMock(return_value=report_row)), \
         patch("ai_orchestrator.reports.service.repository.fetch_template",
               AsyncMock(return_value=_TEMPLATE_ROW)), \
         patch("ai_orchestrator.reports.service.repository.mark_running",
               AsyncMock()), \
         patch("ai_orchestrator.reports.service.repository.mark_ready",
               AsyncMock()) as mark_ready, \
         patch("ai_orchestrator.reports.service.repository.mark_failed",
               AsyncMock()) as mark_failed, \
         patch("ai_orchestrator.reports.service.llm_router.complete_structured",
               AsyncMock(side_effect=RuntimeError("output validation failed after 2 attempts"))), \
         patch("ai_orchestrator.reports.service.emit",
               AsyncMock()) as emit_mock:

        await service.run_report(enterprise_id=_ENT_ID, report_id=report_id)

    mark_ready.assert_not_called()
    mark_failed.assert_awaited_once()
    fail_args = mark_failed.await_args.args
    assert "output validation failed" in fail_args[2]

    emit_mock.assert_awaited_once()
    payload = emit_mock.await_args.args[1]
    assert payload["status"] == "failed"

    # No outbox INSERT on the failure path — we don't email a broken report.
    notify_inserts = [c for c in conn.execute.await_args_list
                      if "notification_outbox" in str(c.args[0])]
    assert notify_inserts == []


@pytest.mark.asyncio
async def test_run_report_template_disappeared_between_queue_and_run_marks_failed():
    """Edge: a tenant deletes the template between queue and run.
    Worker should mark the row failed instead of crashing on a None
    template lookup."""
    report_id = uuid4()
    conn = AsyncMock()
    conn.execute = AsyncMock(return_value=None)
    conn.fetch = AsyncMock(return_value=[])

    report_row = {
        "report_id":    report_id,
        "template_id":  _TEMPLATE_ID,
        "title":        "x",
        "owner_email":  "u@k.io",
        "status":       "queued",
        "narrative":    None,
        "created_at":   datetime(2026, 5, 2, tzinfo=timezone.utc),
        "completed_at": None,
        "last_error":   None,
        "content_json": None,
    }

    with patch("ai_orchestrator.reports.service.acquire_for_tenant",
               side_effect=_fake_acquire(conn)), \
         patch("ai_orchestrator.reports.service.get_pool",
               return_value=_fake_pool(conn)), \
         patch("ai_orchestrator.reports.service.repository.fetch_report",
               AsyncMock(return_value=report_row)), \
         patch("ai_orchestrator.reports.service.repository.fetch_template",
               AsyncMock(return_value=None)), \
         patch("ai_orchestrator.reports.service.repository.mark_failed",
               AsyncMock()) as mark_failed, \
         patch("ai_orchestrator.reports.service.repository.mark_running",
               AsyncMock()) as mark_running, \
         patch("ai_orchestrator.reports.service.llm_router.complete_structured",
               AsyncMock()) as llm_call:

        await service.run_report(enterprise_id=_ENT_ID, report_id=report_id)

    mark_running.assert_not_called()
    llm_call.assert_not_called()
    mark_failed.assert_awaited_once()
    assert "template no longer visible" in mark_failed.await_args.args[2]


@pytest.mark.asyncio
async def test_run_report_swallows_unhandled_exception_with_mark_failed_fallback():
    """Top-level safety net: a fire-and-forget asyncio.create_task
    must never lose a report to a stray raise. Even when fetch_report
    itself raises (DB down), the outer try/except writes a failure
    row before returning."""
    report_id = uuid4()
    conn = AsyncMock()

    fetch_call_count = {"n": 0}

    async def _flaky_fetch(c, _id):
        fetch_call_count["n"] += 1
        if fetch_call_count["n"] == 1:
            raise RuntimeError("DB pool exhausted")
        return None  # second call (from mark_failed retry context)

    with patch("ai_orchestrator.reports.service.acquire_for_tenant",
               side_effect=_fake_acquire(conn)), \
         patch("ai_orchestrator.reports.service.get_pool",
               return_value=_fake_pool(conn)), \
         patch("ai_orchestrator.reports.service.repository.fetch_report",
               side_effect=_flaky_fetch), \
         patch("ai_orchestrator.reports.service.repository.mark_failed",
               AsyncMock()) as mark_failed:

        # Must not raise.
        await service.run_report(enterprise_id=_ENT_ID, report_id=report_id)

    mark_failed.assert_awaited_once()


# ─── distribute_report (F-038 follow-up — migration 029) ─────────

def _ready_report_row(report_id):
    return {
        "report_id":    report_id,
        "template_id":  _TEMPLATE_ID,
        "title":        "Báo cáo demo",
        "owner_email":  "owner@kaori.io",
        "status":       "ready",
        "narrative":    "Doanh thu Q1 vượt 12%",
        "created_at":   datetime(2026, 5, 2, tzinfo=timezone.utc),
        "completed_at": datetime(2026, 5, 2, 10, tzinfo=timezone.utc),
        "last_error":   None,
        "content_json": _VALID_PARSED,
    }


@pytest.mark.asyncio
async def test_distribute_report_happy_path_dedups_and_enqueues_per_recipient():
    """Two distinct recipients → 2 outbox rows + 2 audit rows. The
    case-insensitive duplicate (Lan@Acme.vn vs lan@acme.vn) is
    silently merged."""
    report_id = uuid4()
    conn = AsyncMock()

    # _enqueue_distribution_outbox does conn.fetchrow on the pool conn;
    # return synthetic outbox_ids.
    outbox_ids = [uuid4(), uuid4()]
    fetchrow_calls: list = []

    async def fake_fetchrow(_sql, *_args):
        outbox_id = outbox_ids[len(fetchrow_calls)]
        fetchrow_calls.append(_args)
        return {"outbox_id": outbox_id}

    conn.fetchrow = AsyncMock(side_effect=fake_fetchrow)

    create_dist_mock = AsyncMock(side_effect=[uuid4(), uuid4()])

    with patch("ai_orchestrator.reports.service.acquire_for_tenant",
               side_effect=_fake_acquire(conn)), \
         patch("ai_orchestrator.reports.service.get_pool",
               return_value=_fake_pool(conn)), \
         patch("ai_orchestrator.reports.service.repository.fetch_report",
               AsyncMock(return_value=_ready_report_row(report_id))), \
         patch("ai_orchestrator.reports.service.repository.create_distribution",
               create_dist_mock):

        result = await service.distribute_report(
            enterprise_id=_ENT_ID,
            report_id=report_id,
            recipients=["lan@acme.vn", "Lan@Acme.vn", "huy@acme.vn"],
            custom_message="Anh chị xem giùm em ạ",
        )

    assert result["recipient_count"] == 2     # de-duped
    assert result["success_count"] == 2
    assert result["failure_count"] == 0
    assert len(result["distributions"]) == 2
    # First-seen casing preserved.
    assert result["distributions"][0]["recipient"] == "lan@acme.vn"
    assert result["distributions"][1]["recipient"] == "huy@acme.vn"
    # Both got outbox_ids.
    assert all(d["outbox_id"] is not None for d in result["distributions"])
    assert all(d["status"] == "pending" for d in result["distributions"])

    # 2 outbox INSERTs + 2 audit rows.
    assert len(fetchrow_calls) == 2
    assert create_dist_mock.await_count == 2


@pytest.mark.asyncio
async def test_distribute_report_404_when_report_not_found():
    conn = AsyncMock()
    with patch("ai_orchestrator.reports.service.acquire_for_tenant",
               side_effect=_fake_acquire(conn)), \
         patch("ai_orchestrator.reports.service.repository.fetch_report",
               AsyncMock(return_value=None)):
        with pytest.raises(ReportNotFoundError):
            await service.distribute_report(
                enterprise_id=_ENT_ID,
                report_id=uuid4(),
                recipients=["a@b.com"],
            )


@pytest.mark.asyncio
async def test_distribute_report_409_when_status_not_ready():
    """Distributing a still-running report would send half-baked content;
    409 short-circuits before any enqueue."""
    report_id = uuid4()
    conn = AsyncMock()
    not_ready = _ready_report_row(report_id) | {"status": "running"}

    with patch("ai_orchestrator.reports.service.acquire_for_tenant",
               side_effect=_fake_acquire(conn)), \
         patch("ai_orchestrator.reports.service.repository.fetch_report",
               AsyncMock(return_value=not_ready)):
        with pytest.raises(ReportNotReadyError):
            await service.distribute_report(
                enterprise_id=_ENT_ID,
                report_id=report_id,
                recipients=["a@b.com"],
            )


@pytest.mark.asyncio
async def test_distribute_report_400_when_recipients_empty_or_blank():
    """Empty list, list of empty strings, list of whitespace — all
    reduce to no recipients. Surface as 400 so the FE can show a
    proper validation error."""
    for bad in [[], ["", "   ", None], [" ", "\t"]]:
        with pytest.raises(InvalidDistributionError):
            await service.distribute_report(
                enterprise_id=_ENT_ID,
                report_id=uuid4(),
                recipients=bad,  # type: ignore[arg-type]
            )


@pytest.mark.asyncio
async def test_distribute_report_400_when_over_recipient_cap():
    too_many = [f"u{i}@acme.vn" for i in range(60)]  # cap is 50
    with pytest.raises(InvalidDistributionError):
        await service.distribute_report(
            enterprise_id=_ENT_ID,
            report_id=uuid4(),
            recipients=too_many,
        )


@pytest.mark.asyncio
async def test_distribute_report_partial_failure_continues_loop():
    """First recipient's outbox INSERT raises; second succeeds. Result
    surfaces both: success_count=1, failure_count=1."""
    report_id = uuid4()
    conn = AsyncMock()

    call_count = {"n": 0}

    async def flaky_fetchrow(_sql, *_args):
        call_count["n"] += 1
        if call_count["n"] == 1:
            raise RuntimeError("connection reset by peer")
        return {"outbox_id": uuid4()}

    conn.fetchrow = AsyncMock(side_effect=flaky_fetchrow)

    with patch("ai_orchestrator.reports.service.acquire_for_tenant",
               side_effect=_fake_acquire(conn)), \
         patch("ai_orchestrator.reports.service.get_pool",
               return_value=_fake_pool(conn)), \
         patch("ai_orchestrator.reports.service.repository.fetch_report",
               AsyncMock(return_value=_ready_report_row(report_id))), \
         patch("ai_orchestrator.reports.service.repository.create_distribution",
               AsyncMock(side_effect=[uuid4(), uuid4()])):

        result = await service.distribute_report(
            enterprise_id=_ENT_ID,
            report_id=report_id,
            recipients=["a@acme.vn", "b@acme.vn"],
        )

    assert result["recipient_count"] == 2
    assert result["success_count"] == 1
    assert result["failure_count"] == 1
    statuses = [d["status"] for d in result["distributions"]]
    assert statuses == ["failed", "pending"]
    # Failed entry has no outbox_id; successful one does.
    assert result["distributions"][0]["outbox_id"] is None
    assert result["distributions"][1]["outbox_id"] is not None


@pytest.mark.asyncio
async def test_distribute_report_custom_message_trimmed_to_500_chars():
    """Long custom messages get clipped before storage so we don't
    blow past the column limit (2000) and don't render essay-length
    prefaces in the email."""
    report_id = uuid4()
    conn = AsyncMock()
    conn.fetchrow = AsyncMock(return_value={"outbox_id": uuid4()})
    create_dist_mock = AsyncMock(return_value=uuid4())

    long_message = "x" * 1000

    with patch("ai_orchestrator.reports.service.acquire_for_tenant",
               side_effect=_fake_acquire(conn)), \
         patch("ai_orchestrator.reports.service.get_pool",
               return_value=_fake_pool(conn)), \
         patch("ai_orchestrator.reports.service.repository.fetch_report",
               AsyncMock(return_value=_ready_report_row(report_id))), \
         patch("ai_orchestrator.reports.service.repository.create_distribution",
               create_dist_mock):

        await service.distribute_report(
            enterprise_id=_ENT_ID,
            report_id=report_id,
            recipients=["one@acme.vn"],
            custom_message=long_message,
        )

    create_kwargs = create_dist_mock.await_args.kwargs
    assert len(create_kwargs["custom_message"]) == 500


def test_dedup_emails_handles_blank_and_case():
    out = service._dedup_emails([
        "  lan@acme.vn  ",
        "Lan@Acme.vn",
        "",
        None,                    # type: ignore[list-item]
        "huy@acme.vn",
        "huy@acme.vn",
    ])
    assert out == ["lan@acme.vn", "huy@acme.vn"]


# ─── list_distributions ──────────────────────────────────────────

@pytest.mark.asyncio
async def test_list_distributions_404_when_report_not_found():
    conn = AsyncMock()
    with patch("ai_orchestrator.reports.service.acquire_for_tenant",
               side_effect=_fake_acquire(conn)), \
         patch("ai_orchestrator.reports.service.repository.fetch_report",
               AsyncMock(return_value=None)):
        with pytest.raises(ReportNotFoundError):
            await service.list_distributions(
                enterprise_id=_ENT_ID,
                report_id=uuid4(),
            )


@pytest.mark.asyncio
async def test_list_distributions_returns_repo_rows():
    report_id = uuid4()
    conn = AsyncMock()
    fake_rows = [
        {"distribution_id": uuid4(), "recipient_email": "a@b.com"},
        {"distribution_id": uuid4(), "recipient_email": "c@d.com"},
    ]
    with patch("ai_orchestrator.reports.service.acquire_for_tenant",
               side_effect=_fake_acquire(conn)), \
         patch("ai_orchestrator.reports.service.repository.fetch_report",
               AsyncMock(return_value=_ready_report_row(report_id))), \
         patch("ai_orchestrator.reports.service.repository.list_distributions",
               AsyncMock(return_value=fake_rows)):
        rows = await service.list_distributions(
            enterprise_id=_ENT_ID, report_id=report_id,
        )
    assert rows == fake_rows
