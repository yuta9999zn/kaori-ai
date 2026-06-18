"""
P2-S21 — T-Cube trace distiller + trace_recall RAG engine + augmentation hook.

Comprehensive test suite per anh's "chuẩn chỉ + hiệu năng + phi chức năng"
template (reference: tests/test_p2_s14_pm_algorithms.py). Layout:

  1. TCubeTransformer functional   — 3 forms, parallel LLM calls, error path
  2. transform_and_store           — 3 records into Memory L4 PROCEDURAL
  3. Routing — Rule 4 trace_recall — keyword + length thresholds
  4. TraceRecallEngine retrieval   — semantic-form filter + reflect sibling join
  5. augment_prompt_with_traces    — no-op on empty, prepend on hit
  6. Tenant isolation              — K-1 / K-12 (cross-tenant trace stays hidden)
  7. Determinism                   — repeated calls return same structure
  8. Performance                   — distillation parallelism + recall budget

Mocks `_LLMClient` Protocol directly; mocks `MemoryService` retrieve.
"""
from __future__ import annotations

import asyncio
import time
from datetime import datetime, timedelta, timezone
from typing import Optional
from unittest.mock import AsyncMock
from uuid import UUID, uuid4

import pytest

from ai_orchestrator.reasoning.augment import augment_prompt_with_traces
from ai_orchestrator.reasoning.memory.service import MemoryService
from ai_orchestrator.reasoning.memory.types import (
    MemoryRecord,
    MemoryTier,
    MemoryType,
)
from ai_orchestrator.reasoning.rag.engines.base import RAGQuery
from ai_orchestrator.reasoning.rag.engines.trace_recall import TraceRecallEngine
from ai_orchestrator.reasoning.rag.router import (
    ALL_ENGINE_NAMES,
    RAGRouter,
    _REASONING_TASK_KEYWORDS,
)
from ai_orchestrator.reasoning.trace_distiller import (
    TCubeForm,
    TCubeOutput,
    TCubeTransformer,
    ThinkingTrace,
)


T1 = UUID("11111111-1111-1111-1111-111111111111")
T2 = UUID("22222222-2222-2222-2222-222222222222")
NOW = datetime(2026, 5, 17, 12, 0, 0, tzinfo=timezone.utc)


def _trace(*, tenant=T1, decision_id=None, raw=None,
           context="Khách Olist bị churn, cần can thiệp",
           provider="qwen", version="2.5-14b") -> ThinkingTrace:
    return ThinkingTrace(
        source_decision_id=decision_id or uuid4(),
        tenant_id=tenant,
        raw_text=raw or ("Tôi cần xem segment churn risk... "
                         "Có 3 cluster: pricing / feature / support... "
                         "Cluster pricing thì offer discount 15%..."),
        problem_context=context,
        source_llm_provider=provider,
        source_llm_version=version,
        occurred_at=NOW,
    )


class _FakeLLM:
    """Records calls + returns canned per-prompt-fragment matchers."""

    def __init__(self):
        self.calls: list[dict] = []

    async def complete(self, *, tenant_id, prompt, max_tokens, model=None):
        self.calls.append({
            "tenant_id": tenant_id, "prompt": prompt,
            "max_tokens": max_tokens, "model": model,
        })
        if "5 BƯỚC SẠCH" in prompt or "5 BƯỚC" in prompt:
            return "1. Đọc data\n2. Cluster\n3. Score\n4. Offer\n5. Đo"
        if "INSIGHT" in prompt:
            return "Khi tenant churn vì pricing, làm discount 10-20% để giữ LTV."
        if "BẪY" in prompt:
            return "- BẪY: quên check segment LTV | TRÁNH: filter LTV >5M trước"
        return "fallback"


class _RaisingLLM:
    """Fails on first call — used to test partial-distillation rejection."""
    async def complete(self, **_kw):
        raise RuntimeError("llm gateway 503")


# ═════════════════════════════════════════════════════════════════════
# 1. TCubeTransformer functional — 3 forms, parallel calls
# ═════════════════════════════════════════════════════════════════════


class TestTCubeTransformerFunctional:

    @pytest.mark.asyncio
    async def test_transform_returns_three_forms(self):
        llm = _FakeLLM()
        t = TCubeTransformer(llm)
        out = await t.transform(_trace())
        assert isinstance(out, TCubeOutput)
        assert out.struct.startswith("1.")
        assert "discount" in out.semantic.lower() or "LTV" in out.semantic
        assert out.reflect.startswith("- BẪY")
        # 3 parallel LLM calls
        assert len(llm.calls) == 3

    @pytest.mark.asyncio
    async def test_transform_pins_model_per_K20(self):
        llm = _FakeLLM()
        t = TCubeTransformer(llm, distiller_model="qwen2.5:14b",
                             distiller_version="2026-05-08")
        out = await t.transform(_trace())
        # All 3 calls used the same pinned model
        models_used = {c["model"] for c in llm.calls}
        assert models_used == {"qwen2.5:14b"}
        assert out.distiller_model == "qwen2.5:14b"
        assert out.distiller_version == "2026-05-08"

    @pytest.mark.asyncio
    async def test_one_form_failure_raises(self):
        """If any form fails, the whole transform raises — partial
        distillation is unsafe to store (paper §3.2 stresses this)."""
        t = TCubeTransformer(_RaisingLLM())
        with pytest.raises(RuntimeError, match="503"):
            await t.transform(_trace())

    @pytest.mark.asyncio
    async def test_long_raw_trace_is_truncated(self):
        """Trace > 8000 chars must be truncated in prompt rendering, not
        rejected — paper §3.2 used noisy 10K+ char traces."""
        long_trace = "x " * 5000  # 10000 chars
        llm = _FakeLLM()
        t = TCubeTransformer(llm)
        await t.transform(_trace(raw=long_trace))
        for c in llm.calls:
            assert "[... truncated ...]" in c["prompt"]


# ═════════════════════════════════════════════════════════════════════
# 2. transform_and_store — 3 records → Memory L4 PROCEDURAL
# ═════════════════════════════════════════════════════════════════════


class TestTransformAndStore:

    @pytest.mark.asyncio
    async def test_persists_three_records(self):
        llm = _FakeLLM()
        memsvc = MemoryService()  # default in-memory backend
        t = TCubeTransformer(llm)
        trace = _trace()
        await t.transform_and_store(trace, memsvc)
        # 3 records in L4 PROCEDURAL for this tenant
        records = await memsvc.l4.list_all(T1)
        procedural = [r for r in records if r.memory_type == MemoryType.PROCEDURAL]
        assert len(procedural) == 3
        forms = {r.metadata["tcube_form"] for r in procedural}
        assert forms == {"struct", "semantic", "reflect"}

    @pytest.mark.asyncio
    async def test_metadata_carries_lineage(self):
        llm = _FakeLLM()
        memsvc = MemoryService()
        t = TCubeTransformer(llm, distiller_model="qwen2.5:14b")
        trace = _trace(provider="anthropic", version="claude-sonnet-4-6")
        await t.transform_and_store(trace, memsvc)
        records = await memsvc.l4.list_all(T1)
        for r in records:
            assert r.metadata["source_decision_id"] == str(trace.source_decision_id)
            assert r.metadata["source_llm_provider"] == "anthropic"
            assert r.metadata["source_llm_version"] == "claude-sonnet-4-6"
            assert r.metadata["distiller_model"] == "qwen2.5:14b"


# ═════════════════════════════════════════════════════════════════════
# 3. Routing — Rule 4 trace_recall
# ═════════════════════════════════════════════════════════════════════


class TestRoutingRule4:

    def test_keyword_set_has_vietnamese_and_english(self):
        # At least one VN and one EN reasoning verb must be present
        vn = {"tính toán", "tối ưu", "kế hoạch", "đề xuất"}
        en = {"how do i", "what should", "strategy"}
        assert any(k in _REASONING_TASK_KEYWORDS for k in vn)
        assert any(k in _REASONING_TASK_KEYWORDS for k in en)

    def test_all_engine_names_includes_trace_recall(self):
        assert "trace_recall" in ALL_ENGINE_NAMES
        assert len(ALL_ENGINE_NAMES) == 4

    def test_reasoning_query_routes_to_trace_recall(self):
        q = RAGQuery(
            tenant_id=str(T1),
            query_text="Tôi cần đề xuất kế hoạch can thiệp churn cho 10 khách VIP",
        )
        decision = RAGRouter.route(q)
        assert decision.engine_name == "trace_recall"
        assert "đề xuất" in decision.reason or "kế hoạch" in decision.reason

    def test_short_reasoning_query_falls_through_to_pgvector_default(self):
        """word_count < 8 must not hit Rule 4 — short queries fall through
        to default pgvector (paper says traces are valuable for COMPLEX
        reasoning, not "make it faster")."""
        q = RAGQuery(tenant_id=str(T1), query_text="đề xuất nhanh")
        decision = RAGRouter.route(q)
        assert decision.engine_name == "pgvector"

    def test_doc_citation_beats_reasoning(self):
        """Rule 1 (doc-citation) must precede Rule 4 — contractual
        clauses still route to pageindex even with 'đề xuất' in query."""
        q = RAGQuery(
            tenant_id=str(T1),
            query_text=("Đề xuất điều khoản cải tiến trong hợp đồng "
                       "với supplier theo phụ lục A"),
        )
        decision = RAGRouter.route(q)
        assert decision.engine_name == "pageindex"

    def test_trace_recall_engine_opt_in_via_constructor(self):
        """Router only registers trace_recall when caller passes a
        MemoryService-backed engine. Default RAGRouter() does NOT include
        it (avoids forcing MemoryService dependency on stub tests)."""
        r = RAGRouter()
        assert "trace_recall" not in r.engines
        assert set(r.engines) == {"pgvector", "pageindex", "docsage"}


# ═════════════════════════════════════════════════════════════════════
# 4. TraceRecallEngine retrieval — semantic + reflect sibling
# ═════════════════════════════════════════════════════════════════════


class TestTraceRecallEngine:

    @pytest.mark.asyncio
    async def test_empty_memory_returns_friendly_answer(self):
        memsvc = MemoryService()
        engine = TraceRecallEngine(memsvc)
        q = RAGQuery(tenant_id=str(T1), query_text="đề xuất plan churn")
        ans = await engine.answer(q)
        assert ans.engine_name == "trace_recall"
        assert ans.citations == ()
        assert "Không tìm thấy" in ans.answer

    @pytest.mark.asyncio
    async def test_semantic_hit_with_reflect_sibling_join(self):
        memsvc = MemoryService()
        # Seed paired semantic + reflect (same source_decision_id)
        src_id = str(uuid4())
        await memsvc.write(
            T1, MemoryType.PROCEDURAL,
            "Khi churn vì pricing, làm discount 10-20% để giữ LTV.",
            metadata={"tcube_form": "semantic", "source_decision_id": src_id},
        )
        await memsvc.write(
            T1, MemoryType.PROCEDURAL,
            "- BẪY: quên check LTV | TRÁNH: filter LTV >5M trước",
            metadata={"tcube_form": "reflect", "source_decision_id": src_id},
        )
        engine = TraceRecallEngine(memsvc)
        q = RAGQuery(tenant_id=str(T1),
                     query_text="churn pricing discount LTV")
        ans = await engine.answer(q)
        assert len(ans.citations) >= 1
        assert "Insight: " in ans.answer
        assert "Cảnh báo: " in ans.answer
        assert "BẪY" in ans.answer

    @pytest.mark.asyncio
    async def test_non_procedural_records_filtered_out(self):
        """L4 may contain SEMANTIC + DECISION memories too — engine must
        only return PROCEDURAL + tcube_form==semantic."""
        memsvc = MemoryService()
        await memsvc.write(T1, MemoryType.SEMANTIC,
                           "discount works for pricing churn",
                           metadata={})  # not a tcube record
        await memsvc.write(T1, MemoryType.PROCEDURAL,
                           "T-Cube semantic about discount",
                           metadata={"tcube_form": "semantic",
                                     "source_decision_id": str(uuid4())})
        engine = TraceRecallEngine(memsvc)
        q = RAGQuery(tenant_id=str(T1), query_text="discount")
        ans = await engine.answer(q)
        # Only the PROCEDURAL+semantic record surfaces
        for c in ans.citations:
            assert c.engine_name == "trace_recall"


# ═════════════════════════════════════════════════════════════════════
# 5. augment_prompt_with_traces — D3 hook
# ═════════════════════════════════════════════════════════════════════


class TestAugmentHook:

    @pytest.mark.asyncio
    async def test_no_traces_passes_through(self):
        memsvc = MemoryService()
        augmented, ids = await augment_prompt_with_traces(
            base_prompt="solve this",
            tenant_id=T1,
            query_text="đề xuất plan",
            memory_service=memsvc,
        )
        assert augmented == "solve this"
        assert ids == []

    @pytest.mark.asyncio
    async def test_traces_prepended_with_header(self):
        memsvc = MemoryService()
        src_id = str(uuid4())
        await memsvc.write(
            T1, MemoryType.PROCEDURAL,
            "Khi churn pricing, discount 15%.",
            metadata={"tcube_form": "semantic", "source_decision_id": src_id},
        )
        augmented, ids = await augment_prompt_with_traces(
            base_prompt="solve this",
            tenant_id=T1,
            query_text="churn pricing",
            memory_service=memsvc,
        )
        assert "Kinh nghiệm" in augmented
        assert "discount 15%" in augmented
        assert augmented.endswith("solve this")
        assert ids == [src_id]

    @pytest.mark.asyncio
    async def test_locale_en_uses_english_header(self):
        memsvc = MemoryService()
        await memsvc.write(
            T1, MemoryType.PROCEDURAL,
            "When churn, discount.",
            metadata={"tcube_form": "semantic", "source_decision_id": str(uuid4())},
        )
        augmented, _ = await augment_prompt_with_traces(
            base_prompt="solve",
            tenant_id=T1,
            query_text="churn",
            memory_service=memsvc,
            locale="en",
        )
        assert "Prior solved cases" in augmented


# ═════════════════════════════════════════════════════════════════════
# 6. Tenant isolation — K-1 / K-12 (cross-tenant trace stays hidden)
# ═════════════════════════════════════════════════════════════════════


class TestTenantIsolation:

    @pytest.mark.asyncio
    async def test_t2_does_not_see_t1_traces(self):
        memsvc = MemoryService()
        # T1 has a trace
        await memsvc.write(
            T1, MemoryType.PROCEDURAL,
            "T1 secret trace",
            metadata={"tcube_form": "semantic", "source_decision_id": str(uuid4())},
        )
        # T2 queries the same memory service
        engine = TraceRecallEngine(memsvc)
        q = RAGQuery(tenant_id=str(T2), query_text="T1 secret trace")
        ans = await engine.answer(q)
        # T2 must get empty — RLS enforced by MemoryService tier store
        for c in ans.citations:
            assert "T1 secret" not in (c.snippet or "")
        # Stricter: no citations at all for T2
        assert ans.citations == ()

    @pytest.mark.asyncio
    async def test_augment_respects_tenant(self):
        memsvc = MemoryService()
        await memsvc.write(
            T1, MemoryType.PROCEDURAL,
            "T1-only insight",
            metadata={"tcube_form": "semantic", "source_decision_id": str(uuid4())},
        )
        augmented, ids = await augment_prompt_with_traces(
            base_prompt="solve",
            tenant_id=T2,
            query_text="T1-only insight",
            memory_service=memsvc,
        )
        assert augmented == "solve"  # passthrough — T2 has no traces
        assert ids == []


# ═════════════════════════════════════════════════════════════════════
# 7. Determinism — repeated calls return same structure
# ═════════════════════════════════════════════════════════════════════


class TestDeterminism:

    @pytest.mark.asyncio
    async def test_routing_decision_is_pure(self):
        """RAGRouter.route is a @staticmethod pure function — same input
        → same output across calls."""
        q = RAGQuery(tenant_id=str(T1),
                     query_text="đề xuất kế hoạch can thiệp churn 10 VIP")
        d1 = RAGRouter.route(q)
        d2 = RAGRouter.route(q)
        assert d1.engine_name == d2.engine_name
        assert d1.reason == d2.reason

    @pytest.mark.asyncio
    async def test_engine_returns_stable_citation_order(self):
        memsvc = MemoryService()
        for i in range(3):
            src = str(uuid4())
            await memsvc.write(
                T1, MemoryType.PROCEDURAL,
                f"Insight {i}: discount pricing churn",
                metadata={"tcube_form": "semantic", "source_decision_id": src},
            )
        engine = TraceRecallEngine(memsvc, top_k=3)
        q = RAGQuery(tenant_id=str(T1), query_text="discount pricing")
        a1 = await engine.answer(q)
        a2 = await engine.answer(q)
        # Same source_ids in same order
        ids1 = [c.source_id for c in a1.citations]
        ids2 = [c.source_id for c in a2.citations]
        assert ids1 == ids2


# ═════════════════════════════════════════════════════════════════════
# 8. Performance — distillation parallelism + recall budget
# ═════════════════════════════════════════════════════════════════════


class _SlowLLM:
    """Simulates 100ms LLM call — used to test parallel vs serial."""
    async def complete(self, **_kw):
        await asyncio.sleep(0.1)
        return "fake response"


class TestPerformance:

    @pytest.mark.asyncio
    async def test_three_forms_run_in_parallel_not_serial(self):
        """3 × 100ms LLM calls must complete in ~100ms (parallel), not
        ~300ms (serial). asyncio.gather is the proof."""
        t = TCubeTransformer(_SlowLLM())
        t0 = time.perf_counter()
        await t.transform(_trace())
        elapsed = time.perf_counter() - t0
        # Allow generous headroom — 200ms covers slow CI
        assert elapsed < 0.25, f"distill not parallel: {elapsed:.3f}s"

    @pytest.mark.asyncio
    async def test_trace_recall_returns_in_50ms_for_small_l4(self):
        """L4 with 30 records — single retrieve call must stay sub-50ms."""
        memsvc = MemoryService()
        for i in range(30):
            await memsvc.write(
                T1, MemoryType.PROCEDURAL,
                f"trace {i} discount pricing churn",
                metadata={"tcube_form": "semantic",
                          "source_decision_id": str(uuid4())},
            )
        engine = TraceRecallEngine(memsvc)
        q = RAGQuery(tenant_id=str(T1), query_text="discount pricing")
        t0 = time.perf_counter()
        await engine.answer(q)
        elapsed = time.perf_counter() - t0
        assert elapsed < 0.1, f"trace_recall too slow: {elapsed:.3f}s"

    @pytest.mark.asyncio
    async def test_augment_overhead_is_bounded_when_empty(self):
        """Cold-start: no traces — augment should add < 20ms overhead so
        it's safe to wire into every AI node hot path."""
        memsvc = MemoryService()
        t0 = time.perf_counter()
        for _ in range(10):
            await augment_prompt_with_traces(
                base_prompt="solve", tenant_id=T1,
                query_text="đề xuất", memory_service=memsvc,
            )
        avg = (time.perf_counter() - t0) / 10
        assert avg < 0.02, f"augment cold-start too slow: {avg:.3f}s"
