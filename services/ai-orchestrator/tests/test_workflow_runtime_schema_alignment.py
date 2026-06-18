"""Regression guard for the schema↔runtime column mismatch (mig 117).

The runner / state_store historically SELECTed columns that no migration ever
created — node_type_catalog_key, config_json, condition_expr — so the run path
could only ever pass against a mocked DB. mig 117 makes node_type_catalog_key a
real column and the runner aliases the real `config` / `condition` columns.

This test pins the SELECT to the REAL column names so a refactor can't silently
reintroduce the phantom columns.
"""
from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, patch
from uuid import uuid4

from ai_orchestrator.workflow_runtime import state_store


def test_load_definition_selects_real_columns():
    conn = AsyncMock()
    conn.fetchrow.return_value = {
        "workflow_id": uuid4(), "enterprise_id": uuid4(), "workspace_id": uuid4(),
    }
    conn.fetch.return_value = []

    @asynccontextmanager
    async def _fake(_enterprise_id):
        yield conn

    with patch("ai_orchestrator.shared.db.acquire_for_tenant", _fake):
        asyncio.run(state_store.load_workflow_definition(uuid4(), uuid4()))

    sqls = " ".join(str(c.args[0]) for c in conn.fetch.await_args_list)
    # Executor key is now a real column (mig 117).
    assert "node_type_catalog_key" in sqls
    # config / condition are the real columns — aliased to the runner's names,
    # never selected as standalone phantom columns. The builder writes
    # decision_config while the runner reads config, so load_definition MERGES
    # both real jsonb columns into the config_json the runner expects.
    assert "COALESCE(config," in sqls
    assert "COALESCE(decision_config," in sqls
    assert "AS config_json" in sqls
    assert "condition AS condition_expr" in sqls
    # `config_json` must only ever appear as an alias, never as a phantom
    # selected column.
    assert sqls.count("config_json") == sqls.count("AS config_json")


def test_control_flow_executors_registered():
    """Gateways the BPMN mapper resolves (if_else/switch/split/join) must each
    have a registered executor, otherwise a gateway-synced node would land as
    design-only. Importing the package triggers register_builtin_executors()."""
    from ai_orchestrator.workflow_runtime import executors  # noqa: F401 — registers
    from ai_orchestrator.workflow_runtime.node_executor import REGISTRY

    for key in ("if_else", "switch", "split", "join"):
        assert REGISTRY.has(key), f"control-flow executor {key!r} not registered"


def test_every_mapper_emitted_key_has_executor():
    """Every node_type the mapper's structural fallback can emit
    (BPMN_TO_NODETYPE values + the parallel 'join' refinement) must route to a
    real executor — so structural BPMN elements never silently fail at run."""
    from ai_orchestrator.workflow_runtime import executors  # noqa: F401
    from ai_orchestrator.workflow_runtime.node_executor import REGISTRY
    from ai_orchestrator.workflow_runtime.bpmn_mapper import BPMN_TO_NODETYPE

    emitted = set(BPMN_TO_NODETYPE.values()) | {"join"}
    missing = [k for k in emitted if not REGISTRY.has(k)]
    assert not missing, f"mapper emits keys with no executor: {missing}"
