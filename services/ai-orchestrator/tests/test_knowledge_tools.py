"""F-061 knowledge tools — wiring + behaviour benchmark (step 1).

Proves the two read-side tools are registered in the agent registry and that
each returns structured evidence the critic can later gate on. Retrieval
QUALITY (real pgvector / BGE-M3) is out of scope here — these assert the
harness WIRING, which is what step 1 ships.
"""
from __future__ import annotations

from uuid import uuid4

import pytest

from ai_orchestrator.chat.tools.base import ToolContext
from ai_orchestrator.agents.tools import (
    ENTERPRISE_AGENT_TOOLS,
    RetrieveEvidenceTool,
    RecallMemoryTool,
)
from ai_orchestrator.agents.tools import knowledge_tools as kt
from ai_orchestrator.reasoning.memory.types import MemoryType

ENT = str(uuid4())


def _ctx():
    return ToolContext(scope="enterprise", enterprise_id=ENT, user_id=None,
                       role="MANAGER", dry_run=False)


def test_both_tools_registered():
    names = {t.name for t in ENTERPRISE_AGENT_TOOLS}
    assert "retrieve_evidence" in names
    assert "recall_memory" in names


def test_tools_expose_json_schema():
    for cls in (RetrieveEvidenceTool, RecallMemoryTool):
        assert cls.scope == "enterprise"
        assert cls.parameters["required"] == ["query"]
        # JWT identity must never be a tool arg (K-16)
        props = cls.parameters["properties"]
        assert "enterprise_id" not in props and "tenant_id" not in props


@pytest.mark.asyncio
async def test_retrieve_evidence_returns_structured_result():
    out = await RetrieveEvidenceTool().execute({"query": "khách hàng rủi ro cao"}, _ctx())
    # stub engines still return a shaped answer; assert the contract
    assert set(out) >= {"found", "engine", "answer", "citations"}
    assert isinstance(out["citations"], list)


@pytest.mark.asyncio
async def test_retrieve_evidence_rejects_empty_query():
    with pytest.raises(ValueError):
        await RetrieveEvidenceTool().execute({"query": ""}, _ctx())


@pytest.mark.asyncio
async def test_recall_memory_roundtrip(monkeypatch):
    # Force an in-memory MemoryService (the tool now defaults to Postgres L3,
    # which needs a live pool — out of scope for this unit test).
    from ai_orchestrator.reasoning.memory.service import MemoryService
    monkeypatch.setattr(kt, "_MEMORY", MemoryService())
    # write a memory into the SAME singleton the tool reads, then recall it
    await kt._memory().write(
        __import__("uuid").UUID(ENT),
        MemoryType.SEMANTIC,
        "Khách hàng VIP thường mua lại trong 30 ngày.",
    )
    out = await RecallMemoryTool().execute({"query": "khách hàng VIP mua lại"}, _ctx())
    assert "recalled" in out and isinstance(out["memories"], list)
    assert out["recalled"] >= 1
    assert any("VIP" in m["content"] for m in out["memories"])


@pytest.mark.asyncio
async def test_recall_memory_empty_tenant_isolated(monkeypatch):
    from ai_orchestrator.reasoning.memory.service import MemoryService
    monkeypatch.setattr(kt, "_MEMORY", MemoryService())
    other = ToolContext(scope="enterprise", enterprise_id=str(uuid4()),
                        role="MANAGER", dry_run=False)
    out = await RecallMemoryTool().execute({"query": "bất kỳ"}, other)
    # a fresh tenant has no memories — isolation holds
    assert out["recalled"] == 0
