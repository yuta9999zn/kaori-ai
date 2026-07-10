"""
Unit tests for wave 2b (commit 5) AI node executors.

Strategy: monkey-patch llm_router.complete + complete_structured to return
canned payloads — verifies the executor's input validation, output coercion,
and edge-case handling without burning real LLM tokens.

call_forecasting is pure compute (no LLM) — tested without any mocks.
"""
from __future__ import annotations

import pytest
from typing import Any
from uuid import uuid4

from workflow_runtime.node_executor import NodeContext, NodeExecutorError, REGISTRY
from workflow_runtime.executors.ai import (
    CallForecastingExecutor,
    CallInsightEngineExecutor,
    CallRecommendationEngineExecutor,
    CallRiskDetectionExecutor,
    ClassifyTextExecutor,
    ExtractEntitiesExecutor,
    GenerateNarrativeExecutor,
    RagQueryExecutor,
)
from workflow_runtime.side_effect import SideEffectClass


def _ctx(prior_outputs=None, input_data=None, **overrides) -> NodeContext:
    defaults = dict(
        enterprise_id=uuid4(),
        workspace_id=None,
        workflow_id=uuid4(),
        run_id=uuid4(),
        node_id=uuid4(),
        user_id=None,
        input_data=input_data or {},
        prior_outputs=prior_outputs or {},
    )
    defaults.update(overrides)
    return NodeContext(**defaults)


def _patch_llm_router(monkeypatch, *, structured: dict | None = None,
                       text: str | None = None,
                       raises: Exception | None = None) -> None:
    """Patch the engine.llm_router singleton with stubbed responses."""
    import ai_orchestrator.engine.llm_router as _llm

    class _Stub:
        async def complete_structured(self, **kwargs) -> dict:
            if raises:
                raise raises
            return dict(structured or {})

        async def complete(self, **kwargs) -> str:
            if raises:
                raise raises
            return text or ""

    monkeypatch.setattr(_llm, "llm_router", _Stub())


# ─── Registry & side_effect class ───────────────────────────────────


class TestAIWaveRegistry:
    def test_all_8_ai_executors_registered(self):
        keys = (
            "classify_text", "generate_narrative", "rag_query",
            "call_insight_engine", "call_risk_detection", "call_forecasting",
            "extract_entities", "call_recommendation_engine",
        )
        for k in keys:
            assert REGISTRY.has(k), f"{k} missing from registry"

    def test_total_registry_includes_ai_wave(self):
        # 6 wave1 + 2 wave2a + 8 wave2b = 16 minimum after wave 2b.
        # Subsequent waves can add more; this test only pins the
        # lower bound + that all wave-2b keys are present.
        assert len(REGISTRY.list_keys()) >= 16

    def test_all_ai_executors_read_only(self):
        # Every AI executor MUST be read_only per K-17 — they emit LLM
        # output that the runner persists; the executor itself never writes.
        for cls in (
            ClassifyTextExecutor, GenerateNarrativeExecutor, RagQueryExecutor,
            CallInsightEngineExecutor, CallRiskDetectionExecutor,
            CallForecastingExecutor, ExtractEntitiesExecutor,
            CallRecommendationEngineExecutor,
        ):
            assert cls.side_effect_class == SideEffectClass.READ_ONLY, cls.__name__


# ─── classify_text ──────────────────────────────────────────────────


class TestClassifyText:
    @pytest.mark.asyncio
    async def test_empty_text_raises(self):
        ex = ClassifyTextExecutor()
        with pytest.raises(NodeExecutorError):
            await ex.execute(_ctx(), {"text": "", "categories": ["a", "b"]})

    @pytest.mark.asyncio
    async def test_missing_categories_raises(self):
        ex = ClassifyTextExecutor()
        with pytest.raises(NodeExecutorError):
            await ex.execute(_ctx(), {"text": "abc"})

    @pytest.mark.asyncio
    async def test_oversize_text_truncates(self, monkeypatch):
        _patch_llm_router(monkeypatch, structured={
            "category": "billing", "confidence": 0.9, "reasoning": "ok",
        })
        ex = ClassifyTextExecutor()
        result = await ex.execute(_ctx(), {
            "text": "x" * 10000,
            "categories": ["billing", "technical"],
        })
        # Should succeed (truncate to 4000, not fail)
        assert result.status == "completed"
        assert result.output_data["category"] == "billing"

    @pytest.mark.asyncio
    async def test_oov_category_coerced_to_uncertain(self, monkeypatch):
        _patch_llm_router(monkeypatch, structured={
            "category": "rocket_science", "confidence": 0.9, "reasoning": "uh",
        })
        ex = ClassifyTextExecutor()
        result = await ex.execute(_ctx(), {
            "text": "Please refund my order",
            "categories": ["billing", "technical"],
        })
        assert result.output_data["category"] == "uncertain"
        assert result.output_data["confidence"] == 0.0
        assert result.output_data["meets_threshold"] is False

    @pytest.mark.asyncio
    async def test_meets_threshold_logic(self, monkeypatch):
        _patch_llm_router(monkeypatch, structured={
            "category": "billing", "confidence": 0.85, "reasoning": "clear",
        })
        ex = ClassifyTextExecutor()
        result = await ex.execute(_ctx(), {
            "text": "refund",
            "categories": ["billing", "technical"],
            "min_confidence": 0.7,
        })
        assert result.output_data["meets_threshold"] is True


# ─── generate_narrative ─────────────────────────────────────────────


class TestGenerateNarrative:
    @pytest.mark.asyncio
    async def test_missing_template_raises(self):
        ex = GenerateNarrativeExecutor()
        with pytest.raises(NodeExecutorError):
            await ex.execute(_ctx(), {})

    @pytest.mark.asyncio
    async def test_template_interpolation(self, monkeypatch):
        _patch_llm_router(monkeypatch, text="Generated copy.")
        ex = GenerateNarrativeExecutor()
        ctx = _ctx(prior_outputs={"u": {"product": "Kaori AI"}})
        result = await ex.execute(ctx, {
            "template": "Write campaign for {product} in Q2.",
            "variables": {"product": "$.u.product"},
        })
        assert result.status == "completed"
        assert result.output_data["text"] == "Generated copy."
        assert result.output_data["char_count"] == 15

    @pytest.mark.asyncio
    async def test_missing_variable_raises(self):
        ex = GenerateNarrativeExecutor()
        with pytest.raises(NodeExecutorError):
            await ex.execute(_ctx(), {
                "template": "Hi {name}, you bought {product}.",
                "variables": {"name": "An"},  # missing product
            })

    @pytest.mark.asyncio
    async def test_max_tokens_out_of_range(self):
        ex = GenerateNarrativeExecutor()
        with pytest.raises(NodeExecutorError):
            await ex.execute(_ctx(), {
                "template": "x", "max_tokens": 99999,
            })

    @pytest.mark.asyncio
    async def test_target_lang_en(self, monkeypatch):
        captured_prompts = []
        import ai_orchestrator.engine.llm_router as _llm

        class _Stub:
            async def complete(self, **kwargs):
                captured_prompts.append(kwargs.get("prompt"))
                return "OK"
            async def complete_structured(self, **kwargs):
                captured_prompts.append(kwargs.get("prompt"))
                return {}

        monkeypatch.setattr(_llm, "llm_router", _Stub())

        ex = GenerateNarrativeExecutor()
        result = await ex.execute(_ctx(), {
            "template": "Write a tagline.",
            "target_lang": "en",
        })
        assert "Reply in English." in captured_prompts[-1]
        assert result.output_data["target_lang"] == "en"


# ─── rag_query ──────────────────────────────────────────────────────


class TestRagQuery:
    @pytest.mark.asyncio
    async def test_empty_query_raises(self):
        ex = RagQueryExecutor()
        with pytest.raises(NodeExecutorError):
            await ex.execute(_ctx(), {"query": ""})

    @pytest.mark.asyncio
    async def test_top_k_out_of_range(self):
        ex = RagQueryExecutor()
        with pytest.raises(NodeExecutorError):
            await ex.execute(_ctx(), {"query": "abc", "top_k": 999})

    @pytest.mark.asyncio
    async def test_successful_call(self, monkeypatch):
        sent = {}

        class _Resp:
            def raise_for_status(self): pass
            def json(self): return {
                "answer": "VIP onboarded.",
                "citations": [{"doc_id": "X", "page": 1, "snippet": "..."}],
                "engine_name": "pgvector",
            }

        class _Client:
            def __init__(self, *a, **k): pass
            async def __aenter__(self): return self
            async def __aexit__(self, *a): return False
            async def post(self, *a, **k):
                sent.update(k.get("json") or {})
                return _Resp()

        import workflow_runtime.executors.ai as _ai_mod
        monkeypatch.setattr(_ai_mod, "httpx", type("M", (), {"AsyncClient": _Client, "HTTPError": Exception}))

        ex = RagQueryExecutor()
        result = await ex.execute(_ctx(), {"query": "Is VIP X activated?", "top_k": 3})
        assert result.output_data["answer"] == "VIP onboarded."
        assert len(result.output_data["citations"]) == 1
        assert result.output_data["engine_name"] == "pgvector"
        # /rag/answer contract — RAGAnswerRequest fields, not query/top_k
        assert sent == {"query_text": "Is VIP X activated?",
                        "max_citations": 3, "locale": "vi"}


# ─── call_insight_engine ────────────────────────────────────────────


class TestCallInsightEngine:
    @pytest.mark.asyncio
    async def test_subject_none_raises(self):
        ex = CallInsightEngineExecutor()
        with pytest.raises(NodeExecutorError):
            await ex.execute(_ctx(), {"dimensions": ["a"]})

    @pytest.mark.asyncio
    async def test_dimensions_required(self):
        ex = CallInsightEngineExecutor()
        with pytest.raises(NodeExecutorError):
            await ex.execute(_ctx(), {"subject": "abc"})

    @pytest.mark.asyncio
    async def test_score_range_validation(self):
        ex = CallInsightEngineExecutor()
        with pytest.raises(NodeExecutorError):
            await ex.execute(_ctx(), {
                "subject": "abc", "dimensions": ["x"],
                "score_range": [100, 0],  # inverted
            })

    @pytest.mark.asyncio
    async def test_clamps_scores_to_range(self, monkeypatch):
        _patch_llm_router(monkeypatch, structured={
            "scores": {"budget": 150, "authority": -50, "need": 70, "timeline": 50},
            "reasoning": "decent",
        })
        ex = CallInsightEngineExecutor()
        result = await ex.execute(_ctx(), {
            "subject": {"company": "Acme"},
            "dimensions": ["budget", "authority", "need", "timeline"],
            "score_range": [0, 100],
        })
        assert result.output_data["scores"]["budget"] == 100   # clamped from 150
        assert result.output_data["scores"]["authority"] == 0  # clamped from -50
        assert result.output_data["composite"] == (100 + 0 + 70 + 50) / 4

    @pytest.mark.asyncio
    async def test_band_high(self, monkeypatch):
        _patch_llm_router(monkeypatch, structured={
            "scores": {"x": 90}, "reasoning": "great",
        })
        ex = CallInsightEngineExecutor()
        result = await ex.execute(_ctx(), {
            "subject": "abc", "dimensions": ["x"], "score_range": [0, 100],
        })
        assert result.output_data["band"] == "high"

    @pytest.mark.asyncio
    async def test_composite_method_min(self, monkeypatch):
        _patch_llm_router(monkeypatch, structured={
            "scores": {"a": 30, "b": 70}, "reasoning": "x",
        })
        ex = CallInsightEngineExecutor()
        result = await ex.execute(_ctx(), {
            "subject": "x", "dimensions": ["a", "b"],
            "composite_method": "min",
        })
        assert result.output_data["composite"] == 30.0


# ─── call_risk_detection ────────────────────────────────────────────


class TestCallRiskDetection:
    @pytest.mark.asyncio
    async def test_unsupported_target_raises(self):
        ex = CallRiskDetectionExecutor()
        with pytest.raises(NodeExecutorError):
            await ex.execute(_ctx(), {"target": "user"})

    @pytest.mark.asyncio
    async def test_window_days_validation(self):
        ex = CallRiskDetectionExecutor()
        with pytest.raises(NodeExecutorError):
            await ex.execute(_ctx(), {"window_days": 9999})


# ─── call_forecasting (pure compute — no LLM) ───────────────────────


class TestCallForecasting:
    @pytest.mark.asyncio
    async def test_too_few_points_raises(self):
        ex = CallForecastingExecutor()
        with pytest.raises(NodeExecutorError):
            await ex.execute(_ctx(), {"points": [1.0, 2.0]})

    @pytest.mark.asyncio
    async def test_horizon_validation(self):
        ex = CallForecastingExecutor()
        with pytest.raises(NodeExecutorError):
            await ex.execute(_ctx(), {"points": [1, 2, 3, 4], "horizon": 9999})

    @pytest.mark.asyncio
    async def test_linear_trend_up(self):
        ex = CallForecastingExecutor()
        result = await ex.execute(_ctx(), {
            "points": [10, 12, 14, 16, 18, 20],  # +2/period
            "horizon": 3,
        })
        assert result.output_data["trend"] == "up"
        assert result.output_data["slope"] == pytest.approx(2.0)
        assert result.output_data["r_squared"] == pytest.approx(1.0)
        assert len(result.output_data["forecast"]) == 3
        # Next 3 should be 22, 24, 26
        assert result.output_data["forecast"][0] == pytest.approx(22.0)
        assert result.output_data["forecast"][2] == pytest.approx(26.0)

    @pytest.mark.asyncio
    async def test_flat_trend(self):
        ex = CallForecastingExecutor()
        result = await ex.execute(_ctx(), {
            "points": [50, 50, 50, 50, 50],
        })
        assert result.output_data["trend"] == "flat"
        assert abs(result.output_data["slope"]) < 0.01

    @pytest.mark.asyncio
    async def test_dict_input(self):
        ex = CallForecastingExecutor()
        result = await ex.execute(_ctx(), {
            "points": [
                {"ts": "2026-01", "value": 100},
                {"ts": "2026-02", "value": 200},
                {"ts": "2026-03", "value": 300},
            ],
        })
        assert result.output_data["trend"] == "up"
        assert result.output_data["input_points"] == 3

    @pytest.mark.asyncio
    async def test_high_noise_low_confidence(self):
        ex = CallForecastingExecutor()
        # Noisy data — R^2 will be low
        result = await ex.execute(_ctx(), {
            "points": [10, 50, 5, 80, 3, 100, 1],
        })
        assert result.output_data["confidence"] == "low"


# ─── extract_entities ──────────────────────────────────────────────


class TestExtractEntities:
    @pytest.mark.asyncio
    async def test_empty_text_raises(self):
        ex = ExtractEntitiesExecutor()
        with pytest.raises(NodeExecutorError):
            await ex.execute(_ctx(), {"text": "", "entity_types": ["product"]})

    @pytest.mark.asyncio
    async def test_missing_types_raises(self):
        ex = ExtractEntitiesExecutor()
        with pytest.raises(NodeExecutorError):
            await ex.execute(_ctx(), {"text": "abc"})

    @pytest.mark.asyncio
    async def test_normal_extraction(self, monkeypatch):
        _patch_llm_router(monkeypatch, structured={
            "entities": {
                "product": ["Kaori AI", "Studio"],
                "person":  ["Nguyễn Văn An"],
                "date":    [],
            },
        })
        ex = ExtractEntitiesExecutor()
        result = await ex.execute(_ctx(), {
            "text": "Khách Nguyễn Văn An mua Kaori AI hôm qua.",
            "entity_types": ["product", "person", "date"],
        })
        assert result.output_data["count"] == 3
        assert "Kaori AI" in result.output_data["entities"]["product"]
        assert result.output_data["entities"]["date"] == []

    @pytest.mark.asyncio
    async def test_drops_unknown_type_keys(self, monkeypatch):
        _patch_llm_router(monkeypatch, structured={
            "entities": {
                "product": ["A"],
                "rogue_type": ["should not appear"],
            },
        })
        ex = ExtractEntitiesExecutor()
        result = await ex.execute(_ctx(), {
            "text": "x",
            "entity_types": ["product"],
        })
        assert list(result.output_data["entities"].keys()) == ["product"]


# ─── call_recommendation_engine ────────────────────────────────────


class TestCallRecommendationEngine:
    @pytest.mark.asyncio
    async def test_empty_items_raises(self):
        ex = CallRecommendationEngineExecutor()
        with pytest.raises(NodeExecutorError):
            await ex.execute(_ctx(), {"items": [], "criteria": "x"})

    @pytest.mark.asyncio
    async def test_missing_criteria_raises(self):
        ex = CallRecommendationEngineExecutor()
        with pytest.raises(NodeExecutorError):
            await ex.execute(_ctx(), {"items": [{"x": 1}]})

    @pytest.mark.asyncio
    async def test_too_many_items_raises(self):
        ex = CallRecommendationEngineExecutor()
        with pytest.raises(NodeExecutorError):
            await ex.execute(_ctx(), {
                "items": [{"x": i} for i in range(100)],
                "criteria": "any",
            })

    @pytest.mark.asyncio
    async def test_ranking_picks_top(self, monkeypatch):
        _patch_llm_router(monkeypatch, structured={
            "ranked": [
                {"index": 1, "score": 0.95, "reasoning": "best"},
                {"index": 0, "score": 0.40, "reasoning": "ok"},
                {"index": 2, "score": 0.10, "reasoning": "weak"},
            ],
        })
        ex = CallRecommendationEngineExecutor()
        items = [
            {"name": "Cheap, slow"},
            {"name": "Mid cost, fast"},
            {"name": "Expensive, fast"},
        ]
        result = await ex.execute(_ctx(), {
            "items": items, "criteria": "balance cost+speed", "top_n": 2,
        })
        assert len(result.output_data["ranked"]) == 2
        assert result.output_data["top"]["name"] == "Mid cost, fast"

    @pytest.mark.asyncio
    async def test_invalid_index_ignored(self, monkeypatch):
        _patch_llm_router(monkeypatch, structured={
            "ranked": [
                {"index": 99, "score": 1.0, "reasoning": "out of range"},
                {"index": 0, "score": 0.5, "reasoning": "valid"},
            ],
        })
        ex = CallRecommendationEngineExecutor()
        items = [{"a": 1}]
        result = await ex.execute(_ctx(), {
            "items": items, "criteria": "x", "top_n": 1,
        })
        # The out-of-range index dropped silently; only valid item remains
        assert result.output_data["count"] == 1
        assert result.output_data["top"] == {"a": 1}
