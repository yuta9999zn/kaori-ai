"""
K-23 EU AI Act human-oversight gate in the workflow runner (ADR-0041 Layer 3).

The gate sits in WorkflowRunner.run()'s per-node loop, right after the config
parse and BEFORE NODE_STARTED / executor.execute(). A high-risk workflow
(Layer 2 ai_use_risk_register.risk_tier == 'high') with an *impactful*
side-effect node (write_non_idempotent / external) and no granted oversight
row pauses the run (awaiting_approval) WITHOUT executing the node.

Test approach
=============
Cases 1-3 use the FULL runner harness (mirroring test_chaos_workflow_runner.py):
real WorkflowRunner.run() with state_store / state_machine / emit / append_event
stubbed, plus a fake acquire_for_tenant that dispatches by SQL text for the
oversight DB calls. This is the critical-property proof: the gate must fire
BEFORE execute(), and the node executor's execute() must NOT be called when
the run pauses. The test executors flip a module-level flag if executed.

Case 4 exercises _oversight_required directly with a faked dispatch-by-SQL
conn (the pattern from test_workflow_prohibited_block.py) — a full resume
through run() would only re-prove the predicate, so we assert the predicate
returns False when an approved oversight row is present.
"""
from __future__ import annotations

from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from ai_orchestrator.workflow_runtime.node_executor import (
    NodeContext, NodeExecutor, NodeResult, REGISTRY,
)
from ai_orchestrator.workflow_runtime.runner import WorkflowRunner
from ai_orchestrator.workflow_runtime.side_effect import SideEffectClass


# ─── Test executors — flip a flag on execute() so we can prove non-execution ──


class _ExternalRecordingExecutor(NodeExecutor):
    node_type_key = "_oversight_external"
    side_effect_class = SideEffectClass.EXTERNAL
    executed = False

    async def execute(self, ctx, config):
        type(self).executed = True
        return NodeResult(status="completed", output_data={"ok": True})


class _ReadOnlyRecordingExecutor(NodeExecutor):
    node_type_key = "_oversight_read_only"
    side_effect_class = SideEffectClass.READ_ONLY
    executed = False

    async def execute(self, ctx, config):
        type(self).executed = True
        return NodeResult(status="completed", output_data={"ok": True})


@pytest.fixture(scope="module", autouse=True)
def _register_executors():
    if not REGISTRY.has("_oversight_external"):
        REGISTRY.register(_ExternalRecordingExecutor())
    if not REGISTRY.has("_oversight_read_only"):
        REGISTRY.register(_ReadOnlyRecordingExecutor())
    yield


@pytest.fixture(autouse=True)
def _reset_exec_flags():
    _ExternalRecordingExecutor.executed = False
    _ReadOnlyRecordingExecutor.executed = False
    yield


# ─── Helpers (mirror chaos runner harness) ────────────────────────────────


def _stub_state_store(monkeypatch, *, nodes, workflow_id, enterprise_id):
    from ai_orchestrator.workflow_runtime import state_store as _store

    async def _load_workflow_def(eid, wf):
        return {
            "workflow_id":   workflow_id,
            "enterprise_id": enterprise_id,
            "workspace_id":  uuid4(),
            "nodes":         nodes,
            "edges":         [],
        }
    monkeypatch.setattr(_store, "load_workflow_definition", _load_workflow_def)

    async def _fetch_status(eid, rid):
        return "pending"
    monkeypatch.setattr(_store, "fetch_run_status", _fetch_status)

    async def _load_run(eid, rid):
        return {"workflow_id": workflow_id, "input_data": {}}
    monkeypatch.setattr(_store, "load_run", _load_run)

    async def _load_completed(eid, rid):
        return {}
    monkeypatch.setattr(_store, "load_completed_node_outputs", _load_completed)

    async def _load_approvals(eid, rid):
        return {}
    monkeypatch.setattr(_store, "load_resolved_approvals", _load_approvals)

    recorded = []

    async def _upsert_node(**kwargs):
        recorded.append(kwargs)
    monkeypatch.setattr(_store, "upsert_run_node", _upsert_node)

    async def _upsert_side(**kwargs):
        recorded.append({"_kind": "side_columns", **kwargs})
    monkeypatch.setattr(_store, "upsert_run_side_columns", _upsert_side)

    return recorded


def _stub_state_machine(monkeypatch):
    from ai_orchestrator.workflow_runtime import runner as _runner

    statuses = []

    async def _no_op_update(run_id, enterprise_id, *, status,
                            output_data=None, error_summary=None, ended=False):
        statuses.append(status)
    monkeypatch.setattr(_runner.WorkflowRunner, "_update_run_status",
                        staticmethod(_no_op_update))
    return statuses


def _stub_emit(monkeypatch):
    emitted = []

    async def _emit(run_id, enterprise_id, event_type, *,
                    node_id=None, payload=None, actor_user_id=None):
        emitted.append({"event_type": event_type.value,
                        "node_id": str(node_id) if node_id else None,
                        "payload": payload})
    from ai_orchestrator.workflow_runtime import runner as _runner
    monkeypatch.setattr(_runner.WorkflowRunner, "_emit", staticmethod(_emit))
    return emitted


def _stub_record_node(monkeypatch):
    """Replace _record_node so the synthesized pause doesn't hit the DB."""
    recorded = []

    async def _record(*, run_id, node, enterprise_id, side_effect_class,
                      status, input_data, output_data=None, error_message=None):
        recorded.append({"node_id": str(node["node_id"]), "status": status,
                         "side_effect_class": side_effect_class,
                         "input_data": input_data})
    from ai_orchestrator.workflow_runtime import runner as _runner
    monkeypatch.setattr(_runner.WorkflowRunner, "_record_node",
                        staticmethod(_record))
    return recorded


def _stub_record_ai_call(monkeypatch):
    calls = []

    async def _rec(**kwargs):
        calls.append(kwargs)
        return uuid4()
    import ai_orchestrator.shared.ai_governance as _gov
    monkeypatch.setattr(_gov, "record_ai_call", _rec)
    return calls


def _stub_acquire_for_tenant(monkeypatch, *, risk_tier, granted=False):
    """Fake acquire_for_tenant whose conn dispatches by SQL text:
      • SELECT risk_tier FROM ai_use_risk_register  -> {risk_tier} or None
      • SELECT EXISTS(... workflow_approvals ...)    -> granted bool (fetchval)
      • INSERT INTO workflow_approvals               -> 'INSERT 0 1'
    Returns the AsyncMock conn so the test can inspect execute() calls.
    """
    conn = AsyncMock()

    risk_row = MagicMock()
    risk_row.__getitem__ = lambda _s, k: {"risk_tier": risk_tier}[k]

    async def _fetchrow(sql, *args, **kwargs):
        s = str(sql)
        if "ai_use_risk_register" in s:
            return risk_row if risk_tier is not None else None
        return None
    conn.fetchrow.side_effect = _fetchrow

    async def _fetchval(sql, *args, **kwargs):
        if "workflow_approvals" in str(sql):
            return granted
        return None
    conn.fetchval.side_effect = _fetchval

    conn.execute.return_value = "INSERT 0 1"

    @asynccontextmanager
    async def _acquire(_eid):
        yield conn

    import ai_orchestrator.shared.db as _db
    monkeypatch.setattr(_db, "acquire_for_tenant", _acquire)
    return conn


# ─── 1. High-risk + external → pauses, executor NOT called ────────────────


@pytest.mark.asyncio
async def test_high_risk_external_node_pauses_for_oversight(monkeypatch):
    run_id, eid, wf_id, node_id = uuid4(), uuid4(), uuid4(), uuid4()
    nodes = [{
        "node_id":               node_id,
        "node_type_catalog_key": "_oversight_external",
        "config_json":           {},
    }]
    _stub_state_store(monkeypatch, nodes=nodes, workflow_id=wf_id, enterprise_id=eid)
    statuses = _stub_state_machine(monkeypatch)
    _stub_emit(monkeypatch)
    _stub_record_node(monkeypatch)
    _stub_record_ai_call(monkeypatch)
    conn = _stub_acquire_for_tenant(monkeypatch, risk_tier="high", granted=False)

    out = await WorkflowRunner().run(run_id=run_id, enterprise_id=eid)

    # Run paused for oversight.
    assert out["status"] == "awaiting_approval"
    assert out["paused_at_node"] == str(node_id)
    assert out["oversight"] is True
    assert "awaiting_approval" in statuses

    # CRITICAL PROPERTY: the impactful node was NOT executed.
    assert _ExternalRecordingExecutor.executed is False

    # A pending oversight INSERT was issued with the right gate_kind.
    insert_calls = [
        c for c in conn.execute.await_args_list
        if "INSERT INTO workflow_approvals" in str(c.args[0])
    ]
    assert len(insert_calls) == 1, "exactly one oversight INSERT expected"
    sql = str(insert_calls[0].args[0])
    assert "eu_ai_act_oversight" in sql
    assert "'pending'" in sql


# ─── 2. High-risk + read_only → cheap short-circuit, no pause ─────────────


@pytest.mark.asyncio
async def test_high_risk_read_only_node_does_not_pause(monkeypatch):
    run_id, eid, wf_id, node_id = uuid4(), uuid4(), uuid4(), uuid4()
    nodes = [{
        "node_id":               node_id,
        "node_type_catalog_key": "_oversight_read_only",
        "config_json":           {},
    }]
    _stub_state_store(monkeypatch, nodes=nodes, workflow_id=wf_id, enterprise_id=eid)
    _stub_state_machine(monkeypatch)
    _stub_emit(monkeypatch)
    _stub_record_node(monkeypatch)
    _stub_record_ai_call(monkeypatch)
    # Even though risk is high, read_only is reversible — short-circuit before
    # touching the DB. Make the conn blow up if it IS touched, proving the
    # no-DB short-circuit.
    conn = _stub_acquire_for_tenant(monkeypatch, risk_tier="high")
    conn.fetchrow.side_effect = AssertionError(
        "read_only node must short-circuit before any oversight DB read")

    out = await WorkflowRunner().run(run_id=run_id, enterprise_id=eid)

    assert out["status"] == "completed"
    # The read_only node ran normally (no pause).
    assert _ReadOnlyRecordingExecutor.executed is True


# ─── 3. External but NOT high-risk → no pause ─────────────────────────────


@pytest.mark.asyncio
async def test_non_high_risk_external_node_does_not_pause(monkeypatch):
    run_id, eid, wf_id, node_id = uuid4(), uuid4(), uuid4(), uuid4()
    nodes = [{
        "node_id":               node_id,
        "node_type_catalog_key": "_oversight_external",
        "config_json":           {},
    }]
    _stub_state_store(monkeypatch, nodes=nodes, workflow_id=wf_id, enterprise_id=eid)
    _stub_state_machine(monkeypatch)
    _stub_emit(monkeypatch)
    _stub_record_node(monkeypatch)
    _stub_record_ai_call(monkeypatch)
    conn = _stub_acquire_for_tenant(monkeypatch, risk_tier="limited")

    out = await WorkflowRunner().run(run_id=run_id, enterprise_id=eid)

    assert out["status"] == "completed"
    # External node ran normally — limited risk does not trigger oversight.
    assert _ExternalRecordingExecutor.executed is True
    # No oversight INSERT was issued.
    insert_calls = [
        c for c in conn.execute.await_args_list
        if "INSERT INTO workflow_approvals" in str(c.args[0])
    ]
    assert insert_calls == []


# ─── 4. Already-granted oversight row → predicate returns False ───────────


@pytest.mark.asyncio
async def test_resume_executes_after_grant(monkeypatch):
    run_id, eid, wf_id, node_id = uuid4(), uuid4(), uuid4(), uuid4()
    _stub_acquire_for_tenant(monkeypatch, risk_tier="high", granted=True)

    required = await WorkflowRunner._oversight_required(
        run_id=run_id, enterprise_id=eid, workflow_id=wf_id,
        node_id=node_id, side_effect_class="external",
    )
    # An approved eu_ai_act_oversight row exists → no re-pause; node would run.
    assert required is False


# ─── Extra: fail-open on DB error (lean deployments) ──────────────────────


@pytest.mark.asyncio
async def test_oversight_fails_open_on_db_error(monkeypatch):
    run_id, eid, wf_id, node_id = uuid4(), uuid4(), uuid4(), uuid4()

    conn = AsyncMock()

    async def _boom(*a, **k):
        raise RuntimeError("relation ai_use_risk_register does not exist")
    conn.fetchrow.side_effect = _boom

    @asynccontextmanager
    async def _acquire(_eid):
        yield conn

    import ai_orchestrator.shared.db as _db
    monkeypatch.setattr(_db, "acquire_for_tenant", _acquire)

    required = await WorkflowRunner._oversight_required(
        run_id=run_id, enterprise_id=eid, workflow_id=wf_id,
        node_id=node_id, side_effect_class="external",
    )
    # Missing table / DB blip must fail-open (False) — never deadlock a run.
    assert required is False
