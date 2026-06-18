"""Tests for the |OR| grounding gate in the agent critic (RAG×harness step 2)."""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from ai_orchestrator.agents.grounding_gate import assess_grounding


def _ev(citations=None, recalled=None, tool=None):
    """Fake executor TranscriptEntry-like object."""
    if citations is not None:
        return SimpleNamespace(role="executor", tool_name="retrieve_evidence",
                               tool_result={"citations": citations})
    if recalled is not None:
        return SimpleNamespace(role="executor", tool_name="recall_memory",
                               tool_result={"recalled": recalled, "memories": []})
    return SimpleNamespace(role=tool or "planner", tool_name=None, tool_result=None)


# ─── assess_grounding (pure) ─────────────────────────────────────────────

def test_no_evidence_is_insufficient():
    g = assess_grounding([_ev(tool="planner")])
    assert g["coverage"] == 0.0
    assert g["can_generalize"] is False
    assert g["band"] == "chưa đủ"
    assert g["evidence_count"] == 0


def test_strong_evidence_generalises():
    cites = [{"similarity": 0.7}, {"similarity": 0.65}, {"similarity": 0.6}]
    g = assess_grounding([_ev(citations=cites)])
    assert g["evidence_count"] == 3
    assert g["can_generalize"] is True        # best-hit + decayed tail → coverage ≈ 0.67 > 0.6
    assert g["band"] == "đủ"


def test_thin_evidence_is_cautious_or_insufficient():
    g = assess_grounding([_ev(citations=[{"similarity": 0.25}])])
    assert g["coverage"] < 0.6
    assert g["evidence_count"] == 1


def test_memory_hits_add_modest_mass():
    g0 = assess_grounding([_ev(tool="planner")])
    g1 = assess_grounding([_ev(recalled=3)])
    assert g1["coverage"] > g0["coverage"]
    assert g1["memory_hits"] == 3


def test_citations_without_similarity_ignored():
    g = assess_grounding([_ev(citations=[{"snippet": "x"}, {"similarity": None}])])
    assert g["evidence_count"] == 0
    assert g["coverage"] == 0.0


def test_many_weak_citations_do_not_generalise():
    """Quantity must not compensate for low per-citation relevance.

    An off-domain question still retrieves top-K docs, but every hit is a
    weak (~0.25) match. Summing 5 of them used to clear the caution band
    (~54%) and let the agent answer on noise — defeating the decline branch
    (K-3, "học 1 hiểu 10"). Below-floor citations must contribute no mass,
    so the gate declines.
    """
    cites = [{"similarity": s} for s in (0.29, 0.28, 0.26, 0.24, 0.23)]
    g = assess_grounding([_ev(citations=cites)])
    assert g["can_generalize"] is False
    assert g["band"] == "chưa đủ"
    assert g["evidence_count"] == 5   # transparency: all 5 still reported


def test_one_strong_citation_outweighs_weak_noise():
    """A single relevant hit (above floor) grounds cautiously; the weak
    siblings around it neither help nor inflate coverage."""
    cites = [{"similarity": 0.6}] + [{"similarity": s} for s in (0.25, 0.24, 0.22)]
    g = assess_grounding([_ev(citations=cites)])
    assert g["can_generalize"] is True
    assert g["band"] == "thận trọng"     # 0.6 alone → mid band, not "đủ"
    assert g["evidence_count"] == 4


def test_max_aggregation_caps_quantity_padding():
    """Max-aggregation (CDFL audit 2026-06-02 P1 — "còn nợ max-agg").

    The per-citation floor stops a CLEARLY off-domain query (all hits below the
    floor → 0 mass). But under a plain SUM, a query returning MANY citations
    JUST above the floor still piled up coverage (6×0.40 → ~76% "đủ"), so
    quantity bù chất lượng. Geometric-decay max-agg bounds the mass of N hits at
    similarity s by s/(1−decay), so no COUNT of just-above-floor hits can clear
    the generalise threshold — padding stays cautious, never confident.
    """
    pad6 = assess_grounding([_ev(citations=[{"similarity": 0.40}] * 6)])
    assert pad6["band"] != "đủ"              # was "đủ" under the old SUM
    assert pad6["band"] == "thận trọng"
    assert pad6["evidence_count"] == 6

    # Even a huge number of just-above-floor hits is capped below "đủ" (s/(1−decay)).
    pad20 = assess_grounding([_ev(citations=[{"similarity": 0.40}] * 20)])
    assert pad20["band"] != "đủ"
    assert pad20["coverage"] < 0.60

    # A genuinely strong multi-source on-KB answer (audit's on-KB row) still "đủ".
    onkb = assess_grounding([_ev(citations=[{"similarity": s}
                                            for s in (0.59, 0.56, 0.54, 0.51, 0.45)])])
    assert onkb["band"] == "đủ"
    assert onkb["can_generalize"] is True


# ─── critic override (mocked LLM) ────────────────────────────────────────

@pytest.mark.asyncio
async def test_critic_overrides_ungrounded_accept(monkeypatch):
    from ai_orchestrator.agents import critic as critic_mod
    from ai_orchestrator.agents.schemas import Plan, PlanStep

    async def _fake_llm(**kw):
        return {"action": "accept", "reason": "looks fine", "issues": []}
    monkeypatch.setattr(critic_mod.llm_router, "complete_structured", _fake_llm)

    wf = SimpleNamespace(
        workflow_id="grounded-test",
        requires_grounding=True,
        critic_prompt=lambda p, t, i: "review please",
    )
    plan = Plan(rationale="r", steps=[PlanStep(tool_name="recall_memory", args={})])
    verdict = await critic_mod.review_session(
        workflow=wf, input={}, plan=plan, transcripts=[], enterprise_id="e")
    # ungrounded (no evidence) + requires_grounding → accept downgraded to replan
    assert verdict.action == "replan"
    assert "|OR|" in verdict.reason or "cơ sở" in verdict.reason


@pytest.mark.asyncio
async def test_critic_keeps_accept_when_grounding_not_required(monkeypatch):
    from ai_orchestrator.agents import critic as critic_mod
    from ai_orchestrator.agents.schemas import Plan, PlanStep

    async def _fake_llm(**kw):
        return {"action": "accept", "reason": "fine", "issues": []}
    monkeypatch.setattr(critic_mod.llm_router, "complete_structured", _fake_llm)

    wf = SimpleNamespace(
        workflow_id="plain", requires_grounding=False,
        critic_prompt=lambda p, t, i: "review",
    )
    verdict = await critic_mod.review_session(
        workflow=wf, input={}, plan=Plan(rationale="r", steps=[PlanStep(tool_name="recall_memory", args={})]),
        transcripts=[], enterprise_id="e")
    assert verdict.action == "accept"   # no gate → unchanged
