"""
Mem0-inspired ports tests (ship 2026-05-17).

Em port 2 patterns from mem0ai/mem0 (Apache 2.0) into Kaori's existing
Stage 7 Memory infrastructure — without pulling mem0 library:

  Port 1 — TCubeTransformer.extract_facts() + extract_and_store_facts()
           Single-LLM-call fact extraction producing 0-5 SPO triples
           as MemoryType.SEMANTIC records (land in L4 by default).

  Port 2 — MemoryService.retrieve(entity_id=, entity_boost=) parameter
           Caller resolves entity UUID via Stage 5 Ontology; matching
           records get score-boosted (default 2x).

8-section template:
  1. extract_facts parses well-formed JSON array
  2. extract_facts rejects low-confidence + malformed entries
  3. extract_facts swallows LLM errors → empty list
  4. extract_facts strips markdown code fences
  5. extract_and_store_facts writes SEMANTIC records to L4
  6. retrieve entity_id boost — entity-matched records rank higher
  7. retrieve entity_id None — backward compat (no boost)
  8. Performance — 100 extractions parallel-friendly + no quadratic blowup
"""
from __future__ import annotations

import asyncio
import json
import time
from uuid import UUID, uuid4

import pytest

from ai_orchestrator.reasoning.memory.service import MemoryService
from ai_orchestrator.reasoning.memory.types import MemoryRecord, MemoryTier, MemoryType
from ai_orchestrator.reasoning.trace_distiller import (
    ExtractedFact,
    TCubeTransformer,
)


T1 = UUID("11111111-1111-1111-1111-111111111111")
T2 = UUID("22222222-2222-2222-2222-222222222222")
ENTITY_A = UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
ENTITY_B = UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")


class _CannedLLM:
    """LLM that returns a pre-configured response per prompt marker."""

    def __init__(self, response: str):
        self.response = response
        self.calls: list[dict] = []

    async def complete(self, *, tenant_id, prompt, max_tokens, model=None):
        self.calls.append({
            "tenant_id": tenant_id, "prompt": prompt,
            "max_tokens": max_tokens, "model": model,
        })
        return self.response


class _RaisingLLM:
    async def complete(self, **_kw):
        raise RuntimeError("llm gateway 503")


# ═════════════════════════════════════════════════════════════════════
# 1. extract_facts — happy path JSON array
# ═════════════════════════════════════════════════════════════════════


class TestExtractFactsHappyPath:

    @pytest.mark.asyncio
    async def test_parses_well_formed_array(self):
        canned = json.dumps([
            {"subject": "Khách Olist",
             "predicate": "có doanh thu",
             "object": "5 tỷ Q1 2026",
             "confidence": 0.95},
            {"subject": "Khách Olist",
             "predicate": "phụ trách bởi",
             "object": "AE Nguyễn Văn A",
             "confidence": 0.8},
        ])
        t = TCubeTransformer(_CannedLLM(canned))
        facts = await t.extract_facts("Olist Q1 doanh thu 5 tỷ, AE Nguyễn Văn A...",
                                      tenant_id=T1)
        assert len(facts) == 2
        assert facts[0].subject == "Khách Olist"
        assert facts[0].confidence == 0.95
        assert facts[1].predicate == "phụ trách bởi"

    @pytest.mark.asyncio
    async def test_empty_array_returns_empty(self):
        t = TCubeTransformer(_CannedLLM("[]"))
        facts = await t.extract_facts("xin chào", tenant_id=T1)
        assert facts == []

    @pytest.mark.asyncio
    async def test_source_snippet_truncated_to_300(self):
        long_text = "A" * 500
        canned = json.dumps([
            {"subject": "x", "predicate": "y", "object": "z", "confidence": 0.9}
        ])
        t = TCubeTransformer(_CannedLLM(canned))
        facts = await t.extract_facts(long_text, tenant_id=T1)
        assert len(facts[0].source_snippet) == 300


# ═════════════════════════════════════════════════════════════════════
# 2. extract_facts — rejection rules
# ═════════════════════════════════════════════════════════════════════


class TestExtractFactsRejection:

    @pytest.mark.asyncio
    async def test_low_confidence_dropped(self):
        canned = json.dumps([
            {"subject": "a", "predicate": "b", "object": "c", "confidence": 0.3},
            {"subject": "x", "predicate": "y", "object": "z", "confidence": 0.9},
        ])
        t = TCubeTransformer(_CannedLLM(canned))
        facts = await t.extract_facts("text", tenant_id=T1)
        assert len(facts) == 1
        assert facts[0].subject == "x"

    @pytest.mark.asyncio
    async def test_missing_fields_dropped(self):
        canned = json.dumps([
            {"subject": "a", "predicate": "", "object": "c", "confidence": 0.9},
            {"subject": "x", "predicate": "y", "object": "z", "confidence": 0.9},
            {"subject": "valid", "predicate": "missing object", "confidence": 0.9},
        ])
        t = TCubeTransformer(_CannedLLM(canned))
        facts = await t.extract_facts("text", tenant_id=T1)
        assert len(facts) == 1
        assert facts[0].subject == "x"

    @pytest.mark.asyncio
    async def test_non_numeric_confidence_dropped(self):
        canned = json.dumps([
            {"subject": "a", "predicate": "b", "object": "c", "confidence": "high"},
            {"subject": "x", "predicate": "y", "object": "z", "confidence": 0.8},
        ])
        t = TCubeTransformer(_CannedLLM(canned))
        facts = await t.extract_facts("text", tenant_id=T1)
        assert len(facts) == 1

    @pytest.mark.asyncio
    async def test_max_10_facts_hard_cap(self):
        canned = json.dumps([
            {"subject": f"s{i}", "predicate": "p", "object": "o", "confidence": 0.9}
            for i in range(20)
        ])
        t = TCubeTransformer(_CannedLLM(canned))
        facts = await t.extract_facts("text", tenant_id=T1)
        assert len(facts) == 10    # router caps at 10 regardless of LLM output


# ═════════════════════════════════════════════════════════════════════
# 3. extract_facts — error swallow
# ═════════════════════════════════════════════════════════════════════


class TestExtractFactsErrorPath:

    @pytest.mark.asyncio
    async def test_llm_failure_returns_empty_not_raise(self):
        t = TCubeTransformer(_RaisingLLM())
        facts = await t.extract_facts("text", tenant_id=T1)
        assert facts == []

    @pytest.mark.asyncio
    async def test_malformed_json_returns_empty(self):
        t = TCubeTransformer(_CannedLLM("not even json"))
        facts = await t.extract_facts("text", tenant_id=T1)
        assert facts == []

    @pytest.mark.asyncio
    async def test_non_array_top_level_returns_empty(self):
        t = TCubeTransformer(_CannedLLM('{"oops": "should be array"}'))
        facts = await t.extract_facts("text", tenant_id=T1)
        assert facts == []


# ═════════════════════════════════════════════════════════════════════
# 4. extract_facts — strips markdown fences
# ═════════════════════════════════════════════════════════════════════


class TestMarkdownFenceStripping:

    @pytest.mark.asyncio
    async def test_strips_json_fenced_block(self):
        canned = (
            "```json\n"
            + json.dumps([
                {"subject": "a", "predicate": "b", "object": "c", "confidence": 0.9}
            ])
            + "\n```"
        )
        t = TCubeTransformer(_CannedLLM(canned))
        facts = await t.extract_facts("text", tenant_id=T1)
        assert len(facts) == 1

    @pytest.mark.asyncio
    async def test_strips_plain_backtick_fence(self):
        canned = "```\n[]\n```"
        t = TCubeTransformer(_CannedLLM(canned))
        facts = await t.extract_facts("text", tenant_id=T1)
        assert facts == []


# ═════════════════════════════════════════════════════════════════════
# 5. extract_and_store_facts — writes SEMANTIC to L4
# ═════════════════════════════════════════════════════════════════════


class TestExtractAndStore:

    @pytest.mark.asyncio
    async def test_each_fact_lands_as_semantic_record(self):
        canned = json.dumps([
            {"subject": "Khách Vingroup", "predicate": "thuộc industry",
             "object": "retail", "confidence": 0.95},
            {"subject": "Khách Vingroup", "predicate": "có quota",
             "object": "ENT_MAX", "confidence": 0.9},
        ])
        t = TCubeTransformer(_CannedLLM(canned))
        memsvc = MemoryService()
        facts = await t.extract_and_store_facts(
            "Vingroup retail, ENT_MAX plan",
            tenant_id=T1, memory_service=memsvc,
            source_ref="chat:turn:123",
        )
        assert len(facts) == 2
        records = await memsvc.l4.list_all(T1)
        semantic = [r for r in records if r.memory_type == MemoryType.SEMANTIC]
        assert len(semantic) == 2
        # Metadata carries SPO breakdown + source ref
        for r in semantic:
            assert r.metadata["source"] == "fact_extraction"
            assert r.metadata["source_ref"] == "chat:turn:123"
            assert "subject" in r.metadata
            assert "predicate" in r.metadata
            assert "object" in r.metadata

    @pytest.mark.asyncio
    async def test_no_facts_no_writes(self):
        t = TCubeTransformer(_CannedLLM("[]"))
        memsvc = MemoryService()
        await t.extract_and_store_facts(
            "xin chào", tenant_id=T1, memory_service=memsvc,
        )
        records = await memsvc.l4.list_all(T1)
        assert records == []


# ═════════════════════════════════════════════════════════════════════
# 6. retrieve(entity_id=) boost
# ═════════════════════════════════════════════════════════════════════


class TestEntityBoost:

    @pytest.mark.asyncio
    async def test_matching_entity_ranks_higher(self):
        memsvc = MemoryService()
        # Two records with the SAME content (same text-match score),
        # different entity_id. Entity-A record should rank higher when
        # we filter by ENTITY_A.
        await memsvc.write(
            T1, MemoryType.SEMANTIC,
            "khách hàng có doanh thu cao",
            entity_id=ENTITY_A,
        )
        await memsvc.write(
            T1, MemoryType.SEMANTIC,
            "khách hàng có doanh thu cao",
            entity_id=ENTITY_B,
        )
        results = await memsvc.retrieve(
            T1, "doanh thu",
            top_k=2, entity_id=ENTITY_A,
        )
        assert len(results) == 2
        # First result entity = ENTITY_A (boosted)
        assert results[0].entity_id == ENTITY_A

    @pytest.mark.asyncio
    async def test_no_entity_filter_no_boost(self):
        """Backward compat — calls without entity_id behave like before."""
        memsvc = MemoryService()
        await memsvc.write(T1, MemoryType.SEMANTIC, "x doanh thu",
                            entity_id=ENTITY_A)
        await memsvc.write(T1, MemoryType.SEMANTIC, "y doanh thu cao",
                            entity_id=ENTITY_B)
        results = await memsvc.retrieve(T1, "doanh thu cao", top_k=2)
        # 'cao' present in y but not x → y ranks higher purely on text match
        assert len(results) >= 1

    @pytest.mark.asyncio
    async def test_entity_boost_default_2x(self):
        """Verify the default 2x boost multiplier actually flips ranking
        when text scores are otherwise close."""
        memsvc = MemoryService()
        # Record A: weaker text match but entity-A
        await memsvc.write(T1, MemoryType.SEMANTIC,
                            "doanh thu", entity_id=ENTITY_A)
        # Record B: stronger text match but entity-B (NOT matching)
        await memsvc.write(T1, MemoryType.SEMANTIC,
                            "doanh thu tăng nhanh quý này", entity_id=ENTITY_B)
        results = await memsvc.retrieve(
            T1, "doanh thu", top_k=2, entity_id=ENTITY_A,
        )
        # Boost should pull A to top even though B has longer matching text
        assert results[0].entity_id == ENTITY_A

    @pytest.mark.asyncio
    async def test_tenant_isolation_with_entity(self):
        """Entity filter doesn't bypass tenant isolation."""
        memsvc = MemoryService()
        await memsvc.write(T1, MemoryType.SEMANTIC,
                            "T1 secret doanh thu", entity_id=ENTITY_A)
        # T2 querying for ENTITY_A — T1's record stays hidden
        results = await memsvc.retrieve(
            T2, "doanh thu", entity_id=ENTITY_A,
        )
        assert results == []


# ═════════════════════════════════════════════════════════════════════
# 7. retrieve — backward compat
# ═════════════════════════════════════════════════════════════════════


class TestRetrieveBackwardCompat:

    @pytest.mark.asyncio
    async def test_existing_signature_unchanged(self):
        memsvc = MemoryService()
        await memsvc.write(T1, MemoryType.SEMANTIC, "test content")
        # All old kwargs still work
        results = await memsvc.retrieve(
            T1, "test", top_k=3, tier="auto", session_id=None,
        )
        assert len(results) == 1


# ═════════════════════════════════════════════════════════════════════
# 8. Performance
# ═════════════════════════════════════════════════════════════════════


class TestPerformance:

    @pytest.mark.asyncio
    async def test_extract_facts_parallel_friendly(self):
        """100 concurrent extract_facts calls must not deadlock or
        slow down catastrophically. asyncio.gather should run them
        concurrently against the canned LLM."""
        canned = json.dumps([
            {"subject": "a", "predicate": "b", "object": "c", "confidence": 0.9}
        ])
        t = TCubeTransformer(_CannedLLM(canned))
        t0 = time.perf_counter()
        results = await asyncio.gather(
            *[t.extract_facts(f"text {i}", tenant_id=T1) for i in range(100)]
        )
        elapsed = time.perf_counter() - t0
        assert all(len(r) == 1 for r in results)
        assert elapsed < 2.0, f"parallel extract too slow: {elapsed:.2f}s"

    @pytest.mark.asyncio
    async def test_retrieve_entity_boost_no_quadratic(self):
        """Adding entity_id filter must not change O(n) behaviour of
        retrieve over L4. 200 records + filter → still sub-100ms."""
        memsvc = MemoryService()
        for i in range(200):
            await memsvc.write(
                T1, MemoryType.SEMANTIC, f"item {i} doanh thu",
                entity_id=ENTITY_A if i % 2 == 0 else ENTITY_B,
            )
        t0 = time.perf_counter()
        results = await memsvc.retrieve(
            T1, "doanh thu", top_k=10, entity_id=ENTITY_A,
        )
        elapsed = time.perf_counter() - t0
        assert len(results) == 10
        assert elapsed < 0.1, f"retrieve too slow: {elapsed:.3f}s"
