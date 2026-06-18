"""Test session→memory consolidation (RAG×harness step 3)."""
from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

import pytest

from ai_orchestrator.agents import orchestrator as orch
from ai_orchestrator.agents.schemas import CriticVerdict, Plan, PlanStep, TranscriptEntry
from ai_orchestrator.reasoning.memory.types import MemoryType

ENT = str(uuid4())


class _FakeMem:
    def __init__(self):
        self.written = []
        self.l3 = SimpleNamespace(set_embedding=self._set_embed)

    async def write(self, tenant_id, memory_type, content, *, metadata=None):
        rec = SimpleNamespace(record_id=uuid4(), content=content,
                              memory_type=memory_type, metadata=metadata)
        self.written.append(rec)
        return rec

    async def _set_embed(self, *a, **k):
        return True


@pytest.mark.asyncio
async def test_consolidate_writes_episodic_memory(monkeypatch):
    fake = _FakeMem()
    monkeypatch.setattr(orch, "_consolidate_session", orch._consolidate_session)  # keep real
    monkeypatch.setattr("ai_orchestrator.reasoning.memory.factory.build_memory_service",
                        lambda: fake)
    # embed_text → return a vector so set_embedding path runs
    async def _embed(text, *, enterprise_id):
        return [0.1] * 8
    monkeypatch.setattr("ai_orchestrator.reasoning.knowledge.embed.embed_text", _embed)

    plan = Plan(rationale="cứu khách rủi ro",
                steps=[PlanStep(tool_name="retrieve_evidence", args={})])
    verdict = CriticVerdict(action="accept", reason="ok", issues=[])
    transcripts = [
        TranscriptEntry(step_index=0, role="planner", reasoning="r"),
        TranscriptEntry(step_index=1, role="executor", tool_name="retrieve_evidence", tool_ok=True),
        TranscriptEntry(step_index=2, role="executor", tool_name="draft_followup_email", tool_ok=True),
    ]
    await orch._consolidate_session(
        workflow_id="insight-to-action", plan=plan, verdict=verdict,
        transcripts=transcripts, enterprise_id=ENT)

    assert len(fake.written) == 1
    rec = fake.written[0]
    assert rec.memory_type == MemoryType.OPERATIONAL
    assert "insight-to-action" in rec.content
    assert "retrieve_evidence" in rec.content  # actions captured
    assert rec.metadata["outcome"] == "accept"


@pytest.mark.asyncio
async def test_consolidate_carries_question_and_evidence(monkeypatch):
    """For recall to surface on a future *business* question, the memory must
    embed the original question + the grounding evidence, not just workflow
    metadata (audit 2026-06-02: recall_memory returned 0 on business queries
    because only "Workflow X → accept" was stored)."""
    fake = _FakeMem()
    monkeypatch.setattr("ai_orchestrator.reasoning.memory.factory.build_memory_service",
                        lambda: fake)
    async def _embed(text, *, enterprise_id):
        return [0.1] * 8
    monkeypatch.setattr("ai_orchestrator.reasoning.knowledge.embed.embed_text", _embed)

    plan = Plan(rationale="r", steps=[PlanStep(tool_name="retrieve_evidence", args={})])
    transcripts = [
        TranscriptEntry(step_index=0, role="planner", reasoning="r"),
        TranscriptEntry(step_index=1, role="executor", tool_name="retrieve_evidence",
                        tool_ok=True,
                        tool_result={"found": 1, "citations": [
                            {"snippet": "Cửa sổ rời bỏ ~90 ngày", "similarity": 0.6}]}),
    ]
    await orch._consolidate_session(
        workflow_id="grounded-advisory", plan=plan,
        verdict=CriticVerdict(action="accept", reason="ok", issues=[]),
        transcripts=transcripts, enterprise_id=ENT,
        input={"question": "Làm sao giảm churn?"})

    assert len(fake.written) == 1
    content = fake.written[0].content
    assert "giảm churn" in content          # question embedded → future match
    assert "Cửa sổ rời bỏ" in content       # grounding evidence carried
    assert fake.written[0].metadata.get("question") == "Làm sao giảm churn?"


@pytest.mark.asyncio
async def test_consolidate_skipped_under_dry_run(monkeypatch):
    """dry_run means "no side effects" — it must NOT persist episodic memory
    to L3. (Audit 2026-06-02: dry_run sessions were polluting memory_l3.)"""
    fake = _FakeMem()
    monkeypatch.setattr("ai_orchestrator.reasoning.memory.factory.build_memory_service",
                        lambda: fake)
    plan = Plan(rationale="r", steps=[PlanStep(tool_name="retrieve_evidence", args={})])
    await orch._consolidate_session(
        workflow_id="grounded-advisory", plan=plan, verdict=None,
        transcripts=[], enterprise_id=ENT, dry_run=True)
    assert fake.written == []   # nothing persisted under dry_run


@pytest.mark.asyncio
async def test_consolidate_is_non_fatal(monkeypatch):
    def _boom():
        raise RuntimeError("memory down")
    monkeypatch.setattr("ai_orchestrator.reasoning.memory.factory.build_memory_service", _boom)
    # must not raise
    await orch._consolidate_session(
        workflow_id="wf", plan=Plan(rationale="r", steps=[PlanStep(tool_name="x", args={})]),
        verdict=None, transcripts=[], enterprise_id=ENT)
