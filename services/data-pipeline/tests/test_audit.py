"""
Tests for shared.audit (K-6 decision_audit_log helper).

Mirrors services/ai-orchestrator/tests/test_audit.py exactly. Verifies:
  - happy path INSERT goes through with the expected SQL + params;
  - missing / malformed enterprise_id is dropped with a warning,
    never raises;
  - DB error is swallowed (best-effort guarantee);
  - long text fields are truncated.
"""
from unittest.mock import AsyncMock, patch

import pytest

from data_pipeline.shared import audit


# ─── Happy path ──────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_inserts_row_with_normalised_uuids():
    pool = AsyncMock()
    pool.execute = AsyncMock(return_value=None)

    with patch("data_pipeline.shared.audit.get_pool", return_value=pool):
        await audit.log_decision(
            enterprise_id="aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
            run_id="bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb",
            decision_type="cleaning_rule",
            subject="trim_whitespace:name",
            chosen_value="applied",
            confidence=1.0,
            method="user_approved",
        )

    pool.execute.assert_awaited_once()
    args = pool.execute.await_args.args
    sql = args[0]
    assert "INSERT INTO decision_audit_log" in sql
    # enterprise_id and run_id are converted to UUID objects before SQL
    from uuid import UUID
    assert isinstance(args[1], UUID)
    assert isinstance(args[2], UUID)
    assert args[3] == "cleaning_rule"           # decision_type
    assert args[4] == "trim_whitespace:name"    # subject
    assert args[5] == "applied"                 # chosen_value


@pytest.mark.asyncio
async def test_run_id_is_optional_and_nulled():
    pool = AsyncMock()
    with patch("data_pipeline.shared.audit.get_pool", return_value=pool):
        await audit.log_decision(
            enterprise_id="aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
            decision_type="cleaning_rule",
            subject="x",
        )
    args = pool.execute.await_args.args
    assert args[2] is None  # run_id


# ─── Skip cases ──────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_skips_when_enterprise_id_missing():
    pool = AsyncMock()
    with patch("data_pipeline.shared.audit.get_pool", return_value=pool):
        await audit.log_decision(
            enterprise_id="",
            decision_type="cleaning_rule",
            subject="x",
        )
    pool.execute.assert_not_called()


@pytest.mark.asyncio
async def test_skips_when_enterprise_id_invalid_uuid():
    pool = AsyncMock()
    with patch("data_pipeline.shared.audit.get_pool", return_value=pool):
        await audit.log_decision(
            enterprise_id="not-a-uuid",
            decision_type="cleaning_rule",
            subject="x",
        )
    pool.execute.assert_not_called()


@pytest.mark.asyncio
async def test_skips_when_pool_uninitialised():
    """If get_pool() raises (lifespan never started), the audit call must
    still return cleanly — never propagate the error."""
    def _fail():
        raise RuntimeError("DB pool not initialized")
    with patch("data_pipeline.shared.audit.get_pool", side_effect=_fail):
        await audit.log_decision(
            enterprise_id="aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
            decision_type="cleaning_rule",
            subject="x",
        )
    # Returns None, no exception — test passes by reaching this line.


# ─── Best-effort guarantee ───────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_db_error_is_swallowed():
    """K-6 audit must never break the caller's primary path."""
    pool = AsyncMock()
    pool.execute = AsyncMock(side_effect=Exception("connection refused"))

    with patch("data_pipeline.shared.audit.get_pool", return_value=pool):
        # Should NOT raise.
        await audit.log_decision(
            enterprise_id="aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
            decision_type="cleaning_rule",
            subject="x",
        )


# ─── Truncation ──────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_long_chosen_value_is_truncated():
    pool = AsyncMock()
    big = "x" * 10_000
    with patch("data_pipeline.shared.audit.get_pool", return_value=pool):
        await audit.log_decision(
            enterprise_id="aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
            decision_type="cleaning_rule",
            subject="big",
            chosen_value=big,
        )
    chosen_value = pool.execute.await_args.args[5]
    assert len(chosen_value) <= 4100  # 4000 + truncation marker
    assert chosen_value.endswith("...[truncated]")
