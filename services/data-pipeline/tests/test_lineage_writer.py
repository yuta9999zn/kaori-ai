"""
Phase 2.7 P1 — data-pipeline lineage writer tests.

services/data-pipeline/shared/lineage.py is the write-side mirror of
ai-orchestrator's shared/lineage.py: data-pipeline emits edges; the
orch side handles reads/walks.

The local module uses data-pipeline's own acquire_for_tenant (G4a)
which sets app.enterprise_id GUC inside a txn so RLS passes for the
INSERT.
"""
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest


@pytest.mark.asyncio
async def test_record_edge_inserts_with_correct_args(monkeypatch):
    """Happy path: ON CONFLICT DO NOTHING INSERT into
    data_lineage_edges with the 9 column values in order."""
    from shared import lineage

    conn = AsyncMock()
    conn.execute = AsyncMock(return_value="INSERT 0 1")

    class _CM:
        async def __aenter__(self):  return conn
        async def __aexit__(self, *a): return False

    import shared.db as _db
    monkeypatch.setattr(_db, "acquire_for_tenant", lambda _e: _CM())

    eid = uuid4()
    rid = uuid4()
    out = await lineage.record_edge(
        enterprise_id=eid,
        from_kind="bronze_file",
        from_id=str(uuid4()),
        to_kind="silver_row",
        to_id=str(rid),
        transformation="stage4.clean.apply_rules",
        run_id=rid,
        metadata={"row_count": 42},
    )
    assert out is True

    conn.execute.assert_awaited_once()
    args = conn.execute.await_args.args
    sql = args[0]
    assert "INSERT INTO data_lineage_edges" in sql
    assert "ON CONFLICT" in sql
    # arg[1..9] = (ent, from_kind, from_id, to_kind, to_id, transform,
    #              run_id, node_id, metadata_json)
    assert args[2] == "bronze_file"
    assert args[4] == "silver_row"
    assert args[6] == "stage4.clean.apply_rules"
    assert "row_count" in args[9]  # metadata json string


@pytest.mark.asyncio
async def test_record_edge_unknown_kind_returns_false():
    """Unknown ObjectKind values skip the INSERT defensively."""
    from shared import lineage

    out = await lineage.record_edge(
        enterprise_id=uuid4(),
        from_kind="bronze_file",
        from_id="x",
        to_kind="not_a_real_kind",
        to_id="y",
        transformation="x",
    )
    assert out is False


@pytest.mark.asyncio
async def test_record_edge_empty_enterprise_skips():
    from shared import lineage
    out = await lineage.record_edge(
        enterprise_id="",
        from_kind="bronze_file",
        from_id="x",
        to_kind="silver_row",
        to_id="y",
        transformation="x",
    )
    assert out is False


@pytest.mark.asyncio
async def test_record_edge_db_error_returns_false(monkeypatch):
    """Best-effort: DB failure logs + returns False, NEVER raises."""
    from shared import lineage

    conn = AsyncMock()
    conn.execute = AsyncMock(side_effect=RuntimeError("conn refused"))

    class _CM:
        async def __aenter__(self):  return conn
        async def __aexit__(self, *a): return False

    import shared.db as _db
    monkeypatch.setattr(_db, "acquire_for_tenant", lambda _e: _CM())

    out = await lineage.record_edge(
        enterprise_id=uuid4(),
        from_kind="bronze_file",
        from_id="x",
        to_kind="silver_row",
        to_id="y",
        transformation="x",
    )
    assert out is False
