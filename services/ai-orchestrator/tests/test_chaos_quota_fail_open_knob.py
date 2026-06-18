"""
F2 chaos test — per-quota-type fail-open knob (mig 100).

Proves that `fail_open` column on tenant_quotas controls whether an
infra error during quota check fails-OPEN (return sentinel) or
fails-CLOSED (propagate original exception).

Pre-F2 (Gap 5): every infra error returned a sentinel — could mask
runaway concurrency for quotas that SHOULD be strict gates (e.g.
workflow_concurrent).

Tests:
  F2.1  Row with fail_open=TRUE + infra error → sentinel (fail-open)
  F2.2  Row with fail_open=FALSE + infra error → exception propagates
  F2.3  Caller passes fail_open_on_infra_error=False overrides DB → propagates
  F2.4  Caller passes fail_open_on_infra_error=True overrides DB → sentinel
  F2.5  Infra error BEFORE quota row read → defaults to TRUE (preserves uptime)
  F2.6  QuotaExceeded still propagates regardless of fail_open
"""
from __future__ import annotations

from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from ai_orchestrator.shared import tenant_quotas


def _stub_acquire(monkeypatch, conn):
    @asynccontextmanager
    async def _fake(_eid):
        yield conn
    import ai_orchestrator.shared.db as _db
    monkeypatch.setattr(_db, "acquire_for_tenant", _fake)


def _conn_with(rows, *, execute_raises_after_quota_read=False):
    """Mock conn returning `rows` in order from fetchrow. If
    execute_raises_after_quota_read=True, the SELECT FOR UPDATE step
    raises a connection error AFTER the quota row was read (so the
    policy_holder is populated)."""
    conn = AsyncMock()

    fetched = list(rows)
    fetchrow_count = {"n": 0}

    async def _fr(*a, **k):
        fetchrow_count["n"] += 1
        if execute_raises_after_quota_read and fetchrow_count["n"] == 2:
            # Quota row already returned (call #1); subsequent
            # SELECT FOR UPDATE on usage table errors out.
            raise ConnectionRefusedError("simulated mid-txn DB blip")
        return fetched.pop(0) if fetched else None

    conn.fetchrow = AsyncMock(side_effect=_fr)
    conn.execute = AsyncMock(return_value=None)

    txn = MagicMock()
    txn.__aenter__ = AsyncMock(return_value=txn)
    txn.__aexit__ = AsyncMock(return_value=False)
    conn.transaction = MagicMock(return_value=txn)
    return conn


# ─── F2.1: fail_open=TRUE column → sentinel on infra error ───────────


@pytest.mark.asyncio
async def test_fail_open_true_row_absorbs_infra_error(monkeypatch):
    conn = _conn_with(
        rows=[{"max_value": 1000, "period": "per_day", "fail_open": True}],
        execute_raises_after_quota_read=True,
    )
    _stub_acquire(monkeypatch, conn)

    result = await tenant_quotas.check_and_consume(
        enterprise_id=uuid4(),
        quota_type="llm_tokens_external",
        amount=100,
    )
    # Sentinel — policy from row.fail_open=TRUE applied.
    assert result.period == "infra_error"
    assert result.headroom == 2**31


# ─── F2.2: fail_open=FALSE column → propagates infra error ──────────


@pytest.mark.asyncio
async def test_fail_open_false_row_propagates_infra_error(monkeypatch):
    conn = _conn_with(
        rows=[{"max_value": 20, "period": "rolling", "fail_open": False}],
        execute_raises_after_quota_read=True,
    )
    _stub_acquire(monkeypatch, conn)

    with pytest.raises(ConnectionRefusedError):
        await tenant_quotas.check_and_consume(
            enterprise_id=uuid4(),
            quota_type="workflow_concurrent",
            amount=1,
        )


# ─── F2.3: caller-override fail_open=False wins over DB ─────────────


@pytest.mark.asyncio
async def test_caller_override_false_propagates_even_when_row_true(monkeypatch):
    """Operator script in strict mode wants ALL infra errors to surface,
    regardless of per-quota DB policy."""
    conn = _conn_with(
        rows=[{"max_value": 1000, "period": "per_day", "fail_open": True}],
        execute_raises_after_quota_read=True,
    )
    _stub_acquire(monkeypatch, conn)

    with pytest.raises(ConnectionRefusedError):
        await tenant_quotas.check_and_consume(
            enterprise_id=uuid4(),
            quota_type="llm_tokens_external",
            amount=100,
            fail_open_on_infra_error=False,
        )


# ─── F2.4: caller-override fail_open=True wins over DB ──────────────


@pytest.mark.asyncio
async def test_caller_override_true_absorbs_even_when_row_false(monkeypatch):
    """Dev path: caller knows a particular endpoint shouldn't 5xx on
    quota infra errors regardless of strict DB policy."""
    conn = _conn_with(
        rows=[{"max_value": 20, "period": "rolling", "fail_open": False}],
        execute_raises_after_quota_read=True,
    )
    _stub_acquire(monkeypatch, conn)

    result = await tenant_quotas.check_and_consume(
        enterprise_id=uuid4(),
        quota_type="workflow_concurrent",
        amount=1,
        fail_open_on_infra_error=True,
    )
    assert result.period == "infra_error"


# ─── F2.5: infra error BEFORE row read → defaults TRUE ──────────────


@pytest.mark.asyncio
async def test_infra_error_before_quota_read_defaults_open(monkeypatch):
    """When acquire_for_tenant itself fails, policy_holder is never
    populated. Wrapper defaults to TRUE → preserves uptime.

    This is the pre-F2 behavior; F2 only TIGHTENS via explicit
    fail_open=FALSE flags."""
    @asynccontextmanager
    async def _fail(_eid):
        raise ConnectionRefusedError("pool exhausted before any read")
        yield None  # unreachable
    import ai_orchestrator.shared.db as _db
    monkeypatch.setattr(_db, "acquire_for_tenant", _fail)

    # No caller override + connect fails immediately → policy unknown →
    # defaults to TRUE → sentinel.
    result = await tenant_quotas.check_and_consume(
        enterprise_id=uuid4(),
        quota_type="workflow_concurrent",  # would be strict if known
        amount=1,
    )
    assert result.period == "infra_error"


# ─── F2.6: QuotaExceeded still propagates regardless of policy ──────


@pytest.mark.asyncio
async def test_quota_exceeded_propagates_for_strict_quota(monkeypatch):
    """Strict workflow_concurrent quota actually being EXCEEDED should
    propagate as QuotaExceeded, NOT as infra error. fail_open=FALSE
    only affects INFRA errors."""
    conn = _conn_with(rows=[
        {"max_value": 20, "period": "rolling", "fail_open": False},
        {"usage_id": uuid4(), "current_value": 20},
    ])
    _stub_acquire(monkeypatch, conn)

    with pytest.raises(tenant_quotas.QuotaExceeded):
        await tenant_quotas.check_and_consume(
            enterprise_id=uuid4(),
            quota_type="workflow_concurrent",
            amount=1,
        )
