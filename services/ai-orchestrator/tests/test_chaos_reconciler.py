"""
F3 chaos test — replay-driven reconciler.

When state_store.upsert_run_node exhausts retries (Gap 1 scenario),
runner logs + continues. The workflow_run_nodes row is missing but
the workflow_events log captured NODE_COMPLETED. This reconciler
re-INSERTs the missing rows.

Tests:
  F3.1  reconcile_run with all rows already present → 0 inserts
  F3.2  reconcile_run with one missing row → 1 insert
  F3.3  reconcile_run idempotent (ON CONFLICT DO NOTHING)
  F3.4  reconcile_run when events reference node not in workflow_nodes
        → log + skip + insert_errors counter
  F3.5  reconcile_run with no events → 0 inserts
  F3.6  reconcile_recent bounds check (hours / limit)
  F3.7  admin endpoint requires admin role
"""
from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from ai_orchestrator.workflow_runtime import reconciler
from ai_orchestrator.workflow_runtime.event_store import (
    EventType, NodeProjection, RunProjection, WorkflowEvent,
)


def _stub_acquire(monkeypatch, conn):
    @asynccontextmanager
    async def _fake(_eid):
        yield conn
    import ai_orchestrator.shared.db as _db
    monkeypatch.setattr(_db, "acquire_for_tenant", _fake)


def _evt(run_id, node_id, event_type, sequence_no=1):
    """Build a minimal WorkflowEvent for testing project_state."""
    return WorkflowEvent(
        event_id=uuid4(),
        enterprise_id=uuid4(),
        run_id=run_id,
        node_id=node_id,
        sequence_no=sequence_no,
        event_type=event_type,
        payload={"output_data": {"ok": True}} if event_type == EventType.NODE_COMPLETED else {},
        occurred_at=datetime.now(timezone.utc),
        actor_user_id=None,
    )


# ─── F3.1: nothing to reconcile ───────────────────────────────────────


@pytest.mark.asyncio
async def test_reconcile_run_all_present_zero_inserts(monkeypatch):
    """When workflow_run_nodes has all rows the events imply, the
    reconciler inserts nothing + returns clean counts."""
    run_id = uuid4()
    eid = uuid4()
    node_a = uuid4()

    # Project would expect node_a completed
    events = [
        _evt(run_id, None, EventType.WORKFLOW_CREATED, 1),
        _evt(run_id, None, EventType.WORKFLOW_STARTED, 2),
        _evt(run_id, node_a, EventType.NODE_STARTED, 3),
        _evt(run_id, node_a, EventType.NODE_COMPLETED, 4),
        _evt(run_id, None, EventType.WORKFLOW_COMPLETED, 5),
    ]

    async def _fake_load_events(*, enterprise_id, run_id):
        return events

    monkeypatch.setattr(reconciler, "load_event_stream", _fake_load_events)

    # workflow_run_nodes already has node_a
    conn = AsyncMock()
    conn.fetch = AsyncMock(side_effect=[
        [{"node_id": node_a}],            # existing rows
        [{"node_id": node_a, "node_type_catalog_key": "send_email",
            "sequence_order": 0}],         # node_meta
    ])
    conn.fetchrow = AsyncMock(return_value={"workflow_id": uuid4()})
    conn.execute = AsyncMock(return_value=None)
    _stub_acquire(monkeypatch, conn)

    result = await reconciler.reconcile_run(eid, run_id)
    assert result.nodes_inserted == 0
    assert result.nodes_already_present == 1
    assert result.events_walked == 5
    assert result.nodes_in_projection == 1


# ─── F3.2: one missing row → 1 insert ────────────────────────────────


@pytest.mark.asyncio
async def test_reconcile_run_one_missing_inserts(monkeypatch):
    """workflow_run_nodes missing one node_id present in events → 1 INSERT."""
    run_id = uuid4()
    eid = uuid4()
    node_a, node_b = uuid4(), uuid4()
    wf_id = uuid4()

    events = [
        _evt(run_id, None, EventType.WORKFLOW_STARTED, 1),
        _evt(run_id, node_a, EventType.NODE_STARTED, 2),
        _evt(run_id, node_a, EventType.NODE_COMPLETED, 3),
        _evt(run_id, node_b, EventType.NODE_STARTED, 4),
        _evt(run_id, node_b, EventType.NODE_COMPLETED, 5),  # missing in cache
        _evt(run_id, None, EventType.WORKFLOW_COMPLETED, 6),
    ]

    async def _fake_load_events(*, enterprise_id, run_id):
        return events
    monkeypatch.setattr(reconciler, "load_event_stream", _fake_load_events)

    conn = AsyncMock()
    conn.fetch = AsyncMock(side_effect=[
        [{"node_id": node_a}],  # only node_a in workflow_run_nodes
        [
            {"node_id": node_a, "node_type_catalog_key": "send_email", "sequence_order": 0},
            {"node_id": node_b, "node_type_catalog_key": "publish_insight", "sequence_order": 1},
        ],
    ])
    conn.fetchrow = AsyncMock(return_value={"workflow_id": wf_id})
    conn.execute = AsyncMock(return_value=None)
    _stub_acquire(monkeypatch, conn)

    result = await reconciler.reconcile_run(eid, run_id)
    assert result.nodes_inserted == 1
    assert result.nodes_already_present == 1
    assert str(node_b) in result.inserted_node_ids


# ─── F3.3: idempotent — second run does nothing ──────────────────────


@pytest.mark.asyncio
async def test_reconcile_idempotent_via_on_conflict(monkeypatch):
    """SQL is INSERT ... ON CONFLICT DO NOTHING. Reconciler trusts the
    constraint to dedupe; second invocation just re-finds the row +
    skips."""
    run_id = uuid4()
    eid = uuid4()
    node_a = uuid4()

    events = [
        _evt(run_id, None, EventType.WORKFLOW_STARTED, 1),
        _evt(run_id, node_a, EventType.NODE_STARTED, 2),
        _evt(run_id, node_a, EventType.NODE_COMPLETED, 3),
    ]

    async def _fake_load_events(*, enterprise_id, run_id):
        return events
    monkeypatch.setattr(reconciler, "load_event_stream", _fake_load_events)

    # First call: no rows yet → 1 insert
    conn = AsyncMock()
    conn.fetch = AsyncMock(side_effect=[
        [],  # no rows
        [{"node_id": node_a, "node_type_catalog_key": "send_email", "sequence_order": 0}],
    ])
    conn.fetchrow = AsyncMock(return_value={"workflow_id": uuid4()})
    conn.execute = AsyncMock(return_value=None)
    _stub_acquire(monkeypatch, conn)

    r1 = await reconciler.reconcile_run(eid, run_id)
    assert r1.nodes_inserted == 1

    # Second call: row present (caller would have committed) → 0 inserts
    conn.fetch = AsyncMock(side_effect=[
        [{"node_id": node_a}],
        [{"node_id": node_a, "node_type_catalog_key": "send_email", "sequence_order": 0}],
    ])
    r2 = await reconciler.reconcile_run(eid, run_id)
    assert r2.nodes_inserted == 0


# ─── F3.4: orphan node (events reference unknown workflow_node) ──────


@pytest.mark.asyncio
async def test_reconcile_orphan_event_logs_skip(monkeypatch):
    """Events reference node_x but workflow_nodes doesn't have it
    (workflow edited after run started?). Log + skip + bump
    insert_errors counter (NOT raise)."""
    run_id = uuid4()
    eid = uuid4()
    node_x = uuid4()

    events = [
        _evt(run_id, None, EventType.WORKFLOW_STARTED, 1),
        _evt(run_id, node_x, EventType.NODE_STARTED, 2),
        _evt(run_id, node_x, EventType.NODE_COMPLETED, 3),
    ]

    async def _fake_load_events(*, enterprise_id, run_id):
        return events
    monkeypatch.setattr(reconciler, "load_event_stream", _fake_load_events)

    conn = AsyncMock()
    conn.fetch = AsyncMock(side_effect=[
        [],  # no rows
        [],  # node_meta empty — orphan
    ])
    conn.fetchrow = AsyncMock(return_value={"workflow_id": uuid4()})
    conn.execute = AsyncMock(return_value=None)
    _stub_acquire(monkeypatch, conn)

    result = await reconciler.reconcile_run(eid, run_id)
    assert result.nodes_inserted == 0
    assert result.insert_errors == 1


# ─── F3.5: no events → 0 inserts ──────────────────────────────────────


@pytest.mark.asyncio
async def test_reconcile_no_events(monkeypatch):
    async def _fake_load_events(*, enterprise_id, run_id):
        return []
    monkeypatch.setattr(reconciler, "load_event_stream", _fake_load_events)

    result = await reconciler.reconcile_run(uuid4(), uuid4())
    assert result.events_walked == 0
    assert result.nodes_inserted == 0


# ─── F3.6: bounds check on reconcile_recent ──────────────────────────


@pytest.mark.asyncio
async def test_reconcile_recent_rejects_out_of_range():
    with pytest.raises(ValueError):
        await reconciler.reconcile_recent(uuid4(), hours=0)
    with pytest.raises(ValueError):
        await reconciler.reconcile_recent(uuid4(), hours=500)
    with pytest.raises(ValueError):
        await reconciler.reconcile_recent(uuid4(), hours=24, limit=0)
    with pytest.raises(ValueError):
        await reconciler.reconcile_recent(uuid4(), hours=24, limit=10_000)


# ─── F3.7: admin endpoint authz ──────────────────────────────────────


def test_admin_reconcile_run_requires_admin_role():
    from ai_orchestrator.routers import admin_reconcile

    app = FastAPI()
    app.include_router(admin_reconcile.router)
    client = TestClient(app)

    headers = {
        "X-Enterprise-ID": str(uuid4()),
        # No X-User-Role → not admin → 403
    }
    r = client.post(f"/admin/workflow-runs/{uuid4()}/reconcile", headers=headers)
    assert r.status_code == 403

    headers["X-User-Role"] = "OPERATOR"   # non-admin role
    r = client.post(f"/admin/workflow-runs/{uuid4()}/reconcile", headers=headers)
    assert r.status_code == 403


def test_admin_reconcile_sweep_requires_admin_role():
    from ai_orchestrator.routers import admin_reconcile

    app = FastAPI()
    app.include_router(admin_reconcile.router)
    client = TestClient(app)

    headers = {
        "X-Enterprise-ID": str(uuid4()),
        "X-User-Role": "VIEWER",  # non-admin
    }
    r = client.post("/admin/reconcile/sweep?hours=24", headers=headers)
    assert r.status_code == 403


def test_admin_reconcile_run_admin_role_accepted(monkeypatch):
    """ADMIN role passes the authz check (reaches reconcile_run, which
    we stub to return a zero result)."""
    from ai_orchestrator.routers import admin_reconcile

    from ai_orchestrator.workflow_runtime.reconciler import ReconcileResult

    fake_result = ReconcileResult(
        run_id="x", events_walked=0, nodes_in_projection=0,
        nodes_already_present=0, nodes_inserted=0, insert_errors=0,
    )

    async def _fake_reconcile(eid, rid):
        return fake_result
    monkeypatch.setattr(
        "ai_orchestrator.workflow_runtime.reconciler.reconcile_run",
        _fake_reconcile,
    )

    app = FastAPI()
    app.include_router(admin_reconcile.router)
    client = TestClient(app)

    headers = {
        "X-Enterprise-ID": str(uuid4()),
        "X-User-Role": "ADMIN",
    }
    r = client.post(f"/admin/workflow-runs/{uuid4()}/reconcile", headers=headers)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["nodes_inserted"] == 0
