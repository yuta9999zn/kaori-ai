"""
Tests for P1 lineage tracking — record + BFS walk.
"""
from __future__ import annotations

import pytest
from uuid import uuid4

from ai_orchestrator.shared.lineage import (
    LineageEdge,
    LineageWalk,
    ObjectKind,
    record_edge,
    record_edges_batch,
    walk_downstream,
    walk_upstream,
)


class TestObjectKind:
    def test_12_kinds_unique(self):
        values = [k.value for k in ObjectKind]
        assert len(values) == len(set(values))
        assert len(values) == 12

    def test_includes_canonical_kinds(self):
        for k in ("bronze_file", "silver_row", "ontology_entity",
                   "ai_decision", "workflow_run", "workflow_insight"):
            assert any(v.value == k for v in ObjectKind)


@pytest.mark.asyncio
class TestRecordEdge:
    async def test_inserts_edge(self, monkeypatch):
        execs = []

        class _Conn:
            async def execute(self, sql, *args):
                execs.append((sql, args))
                return "INSERT 0 1"

        class _CM:
            async def __aenter__(self): return _Conn()
            async def __aexit__(self, *a): return False

        import ai_orchestrator.shared.db as _db
        monkeypatch.setattr(_db, "acquire_for_tenant", lambda _: _CM())

        await record_edge(
            enterprise_id=uuid4(),
            from_kind=ObjectKind.BRONZE_FILE, from_id=str(uuid4()),
            to_kind=ObjectKind.SILVER_ROW, to_id=str(uuid4()),
            transformation="stage6.docsage_extract",
        )
        assert len(execs) == 1
        assert "INSERT INTO data_lineage_edges" in execs[0][0]
        assert "ON CONFLICT" in execs[0][0]

    async def test_metadata_serialised(self, monkeypatch):
        execs = []

        class _Conn:
            async def execute(self, sql, *args):
                execs.append(args)
                return "INSERT 0 1"

        class _CM:
            async def __aenter__(self): return _Conn()
            async def __aexit__(self, *a): return False

        import ai_orchestrator.shared.db as _db
        monkeypatch.setattr(_db, "acquire_for_tenant", lambda _: _CM())

        await record_edge(
            enterprise_id=uuid4(),
            from_kind=ObjectKind.SILVER_ROW, from_id="x",
            to_kind=ObjectKind.ONTOLOGY_ENTITY, to_id="y",
            transformation="stage5.mapper",
            metadata={"confidence": 0.9, "model": "qwen-2.5"},
        )
        # 9 args: ent_id, from_kind, from_id, to_kind, to_id, transform,
        #          run_id, node_id, metadata
        args = execs[0]
        assert len(args) == 9
        # Last arg is JSON string
        assert "confidence" in args[-1]


@pytest.mark.asyncio
class TestRecordEdgesBatch:
    async def test_empty_returns_zero(self, monkeypatch):
        result = await record_edges_batch(enterprise_id=uuid4(), edges=[])
        assert result == 0

    async def test_batch_inserts_multiple(self, monkeypatch):
        class _Conn:
            async def execute(self, *a, **k):
                return "INSERT 0 1"
            def transaction(self): return _Tx()
        class _Tx:
            async def __aenter__(self): return self
            async def __aexit__(self, *a): return False
        class _CM:
            async def __aenter__(self): return _Conn()
            async def __aexit__(self, *a): return False

        import ai_orchestrator.shared.db as _db
        monkeypatch.setattr(_db, "acquire_for_tenant", lambda _: _CM())

        result = await record_edges_batch(
            enterprise_id=uuid4(),
            edges=[
                {"from_kind": "bronze_file", "from_id": "1",
                  "to_kind": "silver_row", "to_id": "10",
                  "transformation": "stage6"},
                {"from_kind": "silver_row", "from_id": "10",
                  "to_kind": "ontology_entity", "to_id": "100",
                  "transformation": "stage5"},
            ],
        )
        assert result == 2


@pytest.mark.asyncio
class TestWalkValidation:
    async def test_invalid_direction_raises(self):
        from ai_orchestrator.shared.lineage import _walk
        with pytest.raises(ValueError):
            await _walk(enterprise_id=uuid4(), kind="x", object_id="y",
                          max_depth=5, max_nodes=100, direction="sideways")

    async def test_max_depth_out_of_range(self):
        with pytest.raises(ValueError):
            await walk_upstream(enterprise_id=uuid4(), kind="x",
                                  object_id="y", max_depth=99)

    async def test_max_nodes_out_of_range(self):
        with pytest.raises(ValueError):
            await walk_upstream(enterprise_id=uuid4(), kind="x",
                                  object_id="y", max_nodes=999_999)


@pytest.mark.asyncio
class TestWalk:
    async def test_no_edges_returns_root_only(self, monkeypatch):
        class _Conn:
            async def fetch(self, *a, **k): return []
        class _CM:
            async def __aenter__(self): return _Conn()
            async def __aexit__(self, *a): return False
        import ai_orchestrator.shared.db as _db
        monkeypatch.setattr(_db, "acquire_for_tenant", lambda _: _CM())

        result = await walk_upstream(
            enterprise_id=uuid4(), kind="bronze_file", object_id="x",
        )
        assert len(result.edges) == 0
        assert ("bronze_file", "x") in result.nodes
        assert result.max_depth == 0

    async def test_single_edge_upstream(self, monkeypatch):
        # silver_row 10 came from bronze_file 1
        edge_id = uuid4()
        ent_id = uuid4()

        class _Conn:
            async def fetch(self, sql, kind, oid):
                # First call: to_kind=silver_row, to_id=10
                if kind == "silver_row" and oid == "10":
                    return [{
                        "edge_id": edge_id, "enterprise_id": ent_id,
                        "from_kind": "bronze_file", "from_id": "1",
                        "to_kind": "silver_row", "to_id": "10",
                        "transformation": "stage6",
                        "run_id": None, "node_id": None,
                        "metadata": "{}",
                    }]
                # Bronze file has no upstream
                return []

        class _CM:
            async def __aenter__(self): return _Conn()
            async def __aexit__(self, *a): return False

        import ai_orchestrator.shared.db as _db
        monkeypatch.setattr(_db, "acquire_for_tenant", lambda _: _CM())

        result = await walk_upstream(
            enterprise_id=ent_id, kind="silver_row", object_id="10",
        )
        assert len(result.edges) == 1
        assert result.edges[0].from_kind == "bronze_file"
        assert ("bronze_file", "1") in result.nodes
        assert ("silver_row", "10") in result.nodes
        assert result.max_depth == 1

    async def test_downstream_walk(self, monkeypatch):
        # bronze_file 1 → silver_row 10
        ent_id = uuid4()

        class _Conn:
            async def fetch(self, sql, kind, oid):
                if kind == "bronze_file" and oid == "1":
                    return [{
                        "edge_id": uuid4(), "enterprise_id": ent_id,
                        "from_kind": "bronze_file", "from_id": "1",
                        "to_kind": "silver_row", "to_id": "10",
                        "transformation": "stage6",
                        "run_id": None, "node_id": None,
                        "metadata": "{}",
                    }]
                return []

        class _CM:
            async def __aenter__(self): return _Conn()
            async def __aexit__(self, *a): return False

        import ai_orchestrator.shared.db as _db
        monkeypatch.setattr(_db, "acquire_for_tenant", lambda _: _CM())

        result = await walk_downstream(
            enterprise_id=ent_id, kind="bronze_file", object_id="1",
        )
        assert result.direction == "downstream"
        assert ("silver_row", "10") in result.nodes

    async def test_truncated_at_max_depth(self, monkeypatch):
        # Endless chain — each silver_row points to another silver_row.
        ent_id = uuid4()

        class _Conn:
            async def fetch(self, sql, kind, oid):
                next_oid = str(int(oid) + 1) if oid.isdigit() else "999"
                return [{
                    "edge_id": uuid4(), "enterprise_id": ent_id,
                    "from_kind": kind, "from_id": oid,
                    "to_kind": kind, "to_id": next_oid,
                    "transformation": "chain",
                    "run_id": None, "node_id": None,
                    "metadata": "{}",
                }]

        class _CM:
            async def __aenter__(self): return _Conn()
            async def __aexit__(self, *a): return False

        import ai_orchestrator.shared.db as _db
        monkeypatch.setattr(_db, "acquire_for_tenant", lambda _: _CM())

        result = await walk_downstream(
            enterprise_id=ent_id, kind="silver_row", object_id="0",
            max_depth=3,
        )
        assert result.truncated is True
        assert result.max_depth == 3

    async def test_cycle_doesnt_infinite_loop(self, monkeypatch):
        """A → B → A — visited set must prevent re-visit."""
        ent_id = uuid4()
        call_count = {"n": 0}

        class _Conn:
            async def fetch(self, sql, kind, oid):
                call_count["n"] += 1
                if call_count["n"] > 50:
                    raise AssertionError("infinite loop detected")
                if oid == "A":
                    return [{
                        "edge_id": uuid4(), "enterprise_id": ent_id,
                        "from_kind": "x", "from_id": "A",
                        "to_kind": "x", "to_id": "B",
                        "transformation": "f",
                        "run_id": None, "node_id": None,
                        "metadata": "{}",
                    }]
                if oid == "B":
                    return [{
                        "edge_id": uuid4(), "enterprise_id": ent_id,
                        "from_kind": "x", "from_id": "B",
                        "to_kind": "x", "to_id": "A",
                        "transformation": "g",
                        "run_id": None, "node_id": None,
                        "metadata": "{}",
                    }]
                return []

        class _CM:
            async def __aenter__(self): return _Conn()
            async def __aexit__(self, *a): return False

        import ai_orchestrator.shared.db as _db
        monkeypatch.setattr(_db, "acquire_for_tenant", lambda _: _CM())

        result = await walk_downstream(
            enterprise_id=ent_id, kind="x", object_id="A",
            max_depth=20,
        )
        # Should visit A + B exactly once
        assert ("x", "A") in result.nodes
        assert ("x", "B") in result.nodes
        # Total nodes == 2 (visited set)
        assert len(result.nodes) == 2
