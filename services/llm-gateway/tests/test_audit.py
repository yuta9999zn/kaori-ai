"""
Tests for K-6 audit log helper (services/llm-gateway/audit.py).

Invariant K-6: every automated decision (LLM dispatch in this service)
writes a row to ``decision_audit_log``. The contract is **best-effort**
on the write itself — a downed audit table or pool exhaustion must
never break the primary LLM path. The reverse — silent audit gap — is
recoverable; a 500 on the LLM path is not.

These tests differ from ai-orchestrator/tests/test_audit.py in one
important way: llm-gateway's ``log_decision`` takes the pool as an
*explicit positional argument* (the gateway is system-wide, not
tenant-scoped at the connection layer), so we don't patch ``get_pool``.
"""
from unittest.mock import AsyncMock
from uuid import UUID

import pytest

from llm_gateway import audit  # noqa: E402  registered in conftest.py


# ─── Happy path ──────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_inserts_row_with_normalised_uuids():
    pool = AsyncMock()
    pool.execute = AsyncMock(return_value=None)

    await audit.log_decision(
        pool,
        enterprise_id="aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
        run_id="bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb",
        decision_type="llm_call",
        subject="schema_mapping",
        chosen_value="some completion",
        method="internal",
        llm_provider="qwen2.5:14b",
        reasoning="prompt_chars=42 response_chars=137 latency_ms=210",
    )

    pool.execute.assert_awaited_once()
    args = pool.execute.await_args.args
    sql = args[0]
    assert "INSERT INTO decision_audit_log" in sql
    assert isinstance(args[1], UUID)        # enterprise_id
    assert isinstance(args[2], UUID)        # run_id
    assert args[3] == "llm_call"            # decision_type
    assert args[4] == "schema_mapping"      # subject
    assert args[5] == "some completion"     # chosen_value
    assert args[7] == "internal"            # method (slot 7 because slot 6 is confidence=None)
    assert args[10] == "qwen2.5:14b"        # llm_provider
    assert "latency_ms=210" in args[11]     # reasoning


@pytest.mark.asyncio
async def test_run_id_is_optional_and_nulled():
    pool = AsyncMock()
    pool.execute = AsyncMock(return_value=None)

    await audit.log_decision(
        pool,
        enterprise_id="aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
        run_id=None,
        decision_type="llm_call",
        subject="x",
        chosen_value="y",
        method="internal",
        llm_provider="qwen2.5:14b",
    )

    args = pool.execute.await_args.args
    assert args[2] is None  # run_id slot


# ─── Skip cases ──────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_skips_when_enterprise_id_is_empty_string():
    """FK to enterprises is NOT NULL — drop the row instead of insert
    garbage. A debug log is emitted; no exception."""
    pool = AsyncMock()
    pool.execute = AsyncMock(return_value=None)

    await audit.log_decision(
        pool,
        enterprise_id="",
        run_id=None,
        decision_type="llm_call",
        subject="x",
        chosen_value="y",
        method="internal",
        llm_provider="qwen2.5:14b",
    )

    pool.execute.assert_not_called()


@pytest.mark.asyncio
async def test_skips_when_enterprise_id_is_none():
    pool = AsyncMock()
    pool.execute = AsyncMock(return_value=None)

    await audit.log_decision(
        pool,
        enterprise_id=None,
        run_id=None,
        decision_type="llm_call",
        subject="x",
        chosen_value="y",
        method="internal",
        llm_provider="qwen2.5:14b",
    )

    pool.execute.assert_not_called()


# ─── Best-effort guarantee ───────────────────────────────────────────

@pytest.mark.asyncio
async def test_db_error_is_swallowed_so_primary_path_lives():
    """K-6 best-effort: a DB failure during audit MUST NOT raise — the
    LLM response should still reach the caller."""
    pool = AsyncMock()
    pool.execute = AsyncMock(side_effect=Exception("connection refused"))

    # Reaching the line after the call without an exception = pass.
    await audit.log_decision(
        pool,
        enterprise_id="aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
        run_id=None,
        decision_type="llm_call",
        subject="x",
        chosen_value="y",
        method="internal",
        llm_provider="qwen2.5:14b",
    )


@pytest.mark.asyncio
async def test_invalid_enterprise_uuid_raises_only_at_uuid_parse():
    """Non-UUID strings are caller bugs, not transient infra errors —
    we let UUID() raise so the violation surfaces during dev rather
    than getting silently dropped along with audit-table outages."""
    pool = AsyncMock()
    pool.execute = AsyncMock(return_value=None)

    with pytest.raises(ValueError):
        await audit.log_decision(
            pool,
            enterprise_id="not-a-uuid",
            run_id=None,
            decision_type="llm_call",
            subject="x",
            chosen_value="y",
            method="internal",
            llm_provider="qwen2.5:14b",
        )

    pool.execute.assert_not_called()


# ─── Truncation ──────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_long_chosen_value_is_truncated_to_8000_plus_marker():
    pool = AsyncMock()
    pool.execute = AsyncMock(return_value=None)
    big = "x" * 12_000

    await audit.log_decision(
        pool,
        enterprise_id="aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
        run_id=None,
        decision_type="llm_call",
        subject="big",
        chosen_value=big,
        method="internal",
        llm_provider="qwen2.5:14b",
    )

    chosen_value = pool.execute.await_args.args[5]
    assert chosen_value.endswith("...[truncated]")
    assert len(chosen_value) == 8000 + len("...[truncated]")


@pytest.mark.asyncio
async def test_short_chosen_value_passes_through_untruncated():
    pool = AsyncMock()
    pool.execute = AsyncMock(return_value=None)

    await audit.log_decision(
        pool,
        enterprise_id="aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
        run_id=None,
        decision_type="llm_call",
        subject="small",
        chosen_value="hello",
        method="internal",
        llm_provider="qwen2.5:14b",
    )

    assert pool.execute.await_args.args[5] == "hello"


@pytest.mark.asyncio
async def test_none_chosen_value_passes_through_as_none():
    pool = AsyncMock()
    pool.execute = AsyncMock(return_value=None)

    await audit.log_decision(
        pool,
        enterprise_id="aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
        run_id=None,
        decision_type="llm_call",
        subject="empty",
        chosen_value=None,
        method="internal",
        llm_provider="qwen2.5:14b",
    )

    assert pool.execute.await_args.args[5] is None
