"""
AI node executors — wave 2 of workflow-gap closeout 2026-05-19.

8 executors wrapping llm-gateway (via engine.llm_router) and existing
reasoning / adoption / economics modules. Each is `read_only` per K-17
(LLM dispatch + DB SELECT, no DB mutation — caller persists results).

Unlocked templates after wave 2 (rough count from mig 069):
  classify_text         B.2 Churn Intervention, D.1 Ticket Triage,
                        D.5 Churn Save, F.2 Expense Reimbursement
  generate_narrative    B.1 Campaign Launch, B.5 A/B Test, E.1 Restock,
                        C.5 Pipeline Review, F.3 Monthly Close (partial)
  rag_query             B.3 VIP Onboarding
  call_insight_engine   B.4 Lead Nurture, C.1 Lead Qual, E.2 Supplier Audit
  call_risk_detection   B.2 Churn Intervention, C.3 Contract Renewal
  call_forecasting      C.5 Pipeline Review
  extract_entities      D.3 NPS Follow-up
  call_recommendation_engine  E.4 Shipment Dispatch
"""
from __future__ import annotations

import json
import os
from typing import Any, Optional

import httpx
import structlog

from ..node_executor import NodeContext, NodeExecutor, NodeExecutorError, NodeResult
from ..side_effect import SideEffectClass
from .pure import _resolve

log = structlog.get_logger()


# ─── helpers ────────────────────────────────────────────────────────


def _safe_json(text: str) -> dict:
    """Strip code fences + bracket-isolate + json.loads. Empty dict on
    any failure. Same heuristic as reasoning/document_classifier._parse_json_fallback
    but local to this module to avoid cross-package imports."""
    if not text:
        return {}
    s = text.strip()
    if s.startswith("```"):
        first_nl = s.find("\n")
        if first_nl > 0:
            s = s[first_nl + 1:]
        if s.endswith("```"):
            s = s[:-3]
        s = s.strip()
    if not s.startswith("{"):
        first = s.find("{")
        last = s.rfind("}")
        if first >= 0 and last > first:
            s = s[first:last + 1]
    try:
        parsed = json.loads(s)
        return parsed if isinstance(parsed, dict) else {}
    except Exception:  # noqa: BLE001
        return {}


def _resolve_text(value: Any, ctx: NodeContext) -> str:
    """Resolve + coerce to non-empty string."""
    resolved = _resolve(value, ctx)
    if resolved is None:
        return ""
    if isinstance(resolved, (dict, list)):
        try:
            return json.dumps(resolved, ensure_ascii=False)
        except Exception:  # noqa: BLE001
            return str(resolved)
    return str(resolved)


# ─── 1. classify_text ───────────────────────────────────────────────


class ClassifyTextExecutor(NodeExecutor):
    """classify_text — LLM categorisation of short text.

    Different from classify_document (which takes Block list with title
    surfacing); this takes a plain string + candidate categories.

    Config:
      text:        $.upstream.body  or literal string  (required)
      categories:  list[str]                            (required)
      min_confidence: 0.6                                (optional)
    Output:
      {category: str, confidence: float, reasoning: str,
       meets_threshold: bool}

    K-3: llm-gateway only. K-4: Qwen default. K-17: read_only.
    """
    node_type_key = "classify_text"
    side_effect_class = SideEffectClass.READ_ONLY

    async def execute(self, ctx: NodeContext, config: dict[str, Any]) -> NodeResult:
        text = _resolve_text(config.get("text"), ctx)
        if not text:
            raise NodeExecutorError("classify_text.text required (resolved to empty)")
        if len(text) > 4000:
            text = text[:4000]  # truncate, don't fail — keeps pipeline moving

        categories = config.get("categories")
        if not isinstance(categories, list) or not categories:
            raise NodeExecutorError("classify_text.categories required (non-empty list)")
        candidates = [str(c).strip().lower() for c in categories if str(c).strip()]
        if not candidates:
            raise NodeExecutorError("classify_text.categories all empty after normalisation")

        min_confidence = float(config.get("min_confidence") or 0.6)

        prompt = "\n".join([
            "Bạn phân loại văn bản tiếng Việt vào MỘT category trong danh sách:",
            "  " + ", ".join(candidates),
            "",
            "Văn bản:",
            text,
            "",
            "Trả về JSON: {category, confidence (0..1), reasoning (1 câu VN)}.",
            "category phải là 1 trong danh sách; nếu không chắc thì confidence < 0.5.",
        ])

        from ai_orchestrator.engine.llm_router import llm_router

        try:
            result = await llm_router.complete_structured(
                prompt=prompt,
                task="classify_text",
                output_schema={
                    "type": "object",
                    "required": ["category", "confidence", "reasoning"],
                    "properties": {
                        "category":   {"type": "string"},
                        "confidence": {"type": "number", "minimum": 0, "maximum": 1},
                        "reasoning":  {"type": "string", "maxLength": 300},
                    },
                },
                enterprise_id=str(ctx.enterprise_id),
                run_id=str(ctx.run_id),
                max_tokens=300,
            )
        except AttributeError:
            text_out = await llm_router.complete(
                prompt=prompt, task="classify_text",
                enterprise_id=str(ctx.enterprise_id),
                run_id=str(ctx.run_id), max_tokens=300,
            )
            result = _safe_json(text_out)

        cat = str(result.get("category", "")).strip().lower()
        confidence = float(result.get("confidence", 0.0))
        reasoning = str(result.get("reasoning", ""))[:300]

        if cat not in candidates:
            log.warning("classify_text.oov_category",
                         requested=cat, candidates=candidates)
            cat = "uncertain"
            confidence = 0.0

        return NodeResult(
            status="completed",
            output_data={
                "category":         cat,
                "confidence":       confidence,
                "reasoning":        reasoning,
                "meets_threshold":  confidence >= min_confidence and cat != "uncertain",
            },
        )


# ─── 2. generate_narrative ──────────────────────────────────────────


class GenerateNarrativeExecutor(NodeExecutor):
    """generate_narrative — LLM prose generation.

    Use cases (mig 069):
      B.1 Campaign Launch  — draft 2 A/B variants (subject + body)
      B.5 Email A/B Test   — generate variants
      E.1 Inventory Restock — auto-draft PO text
      C.5 Pipeline Review  — executive summary

    Config:
      template:    'Bạn là marketer. Sinh email subject + body cho ...'
                   (jinja-ish single-brace placeholders OR f-string {key}
                    referencing prior_outputs)
      variables:   {key: $.upstream.value, ...}  (optional — resolved
                                                    + interpolated into template)
      max_tokens:  500   (optional, default 500, max 2000)
      target_lang: 'vi' | 'en'   (default 'vi')
    Output:
      {text: str, char_count: int, model_used?: str}
    """
    node_type_key = "generate_narrative"
    side_effect_class = SideEffectClass.READ_ONLY

    async def execute(self, ctx: NodeContext, config: dict[str, Any]) -> NodeResult:
        template = config.get("template")
        if not isinstance(template, str) or not template.strip():
            raise NodeExecutorError("generate_narrative.template required (non-empty)")

        variables_raw = config.get("variables") or {}
        if not isinstance(variables_raw, dict):
            raise NodeExecutorError("generate_narrative.variables must be dict")
        resolved_vars = {k: _resolve(v, ctx) for k, v in variables_raw.items()}

        try:
            prompt = template.format(**{k: ("" if v is None else v) for k, v in resolved_vars.items()})
        except (KeyError, IndexError, ValueError) as e:
            raise NodeExecutorError(
                f"generate_narrative.template interpolation failed: {e}. "
                f"Provided keys: {sorted(resolved_vars.keys())}"
            )

        target_lang = (config.get("target_lang") or "vi").lower()
        if target_lang not in ("vi", "en"):
            target_lang = "vi"

        max_tokens = int(config.get("max_tokens") or 500)
        if max_tokens < 1 or max_tokens > 2000:
            raise NodeExecutorError("generate_narrative.max_tokens must be 1..2000")

        if target_lang == "en":
            prompt = prompt + "\n\nReply in English."
        else:
            prompt = prompt + "\n\nTrả lời bằng tiếng Việt."

        from ai_orchestrator.engine.llm_router import llm_router

        text = await llm_router.complete(
            prompt=prompt,
            task="generate_narrative",
            enterprise_id=str(ctx.enterprise_id),
            run_id=str(ctx.run_id),
            max_tokens=max_tokens,
        )

        return NodeResult(
            status="completed",
            output_data={
                "text":        text,
                "char_count":  len(text),
                "target_lang": target_lang,
            },
        )


# ─── 3. rag_query ───────────────────────────────────────────────────


class RagQueryExecutor(NodeExecutor):
    """rag_query — natural-language Q&A over tenant docs.

    Thin wrapper over POST /rag/answer (P15-S10 D6) — reuses the RAG
    router's 4-engine dispatch (pgvector / pageindex / docsage /
    trace_recall).

    Config:
      query:     $.upstream.question  or literal string  (required)
      top_k:     5   (optional, 1..20 — maps to /rag/answer max_citations)
    Output:
      {answer: str, citations: list[RAGCitationOut], trace_id: str|None,
       engine_name: str}

    K-3: HTTP call to ai-orchestrator's own /rag/answer endpoint —
         not a direct llm-gateway call (the endpoint itself routes via
         llm-gateway). K-17: read_only.
    """
    node_type_key = "rag_query"
    side_effect_class = SideEffectClass.READ_ONLY

    async def execute(self, ctx: NodeContext, config: dict[str, Any]) -> NodeResult:
        query = _resolve_text(config.get("query"), ctx)
        if not query.strip():
            raise NodeExecutorError("rag_query.query required (resolved to empty)")

        top_k = int(config.get("top_k") or 5)
        if top_k < 1 or top_k > 20:
            raise NodeExecutorError("rag_query.top_k must be 1..20")

        base_url = os.getenv("AI_ORCH_INTERNAL_URL", "http://localhost:8093")
        # /rag/answer contract (routers/rag.py RAGAnswerRequest) —
        # query_text + max_citations; the old query/top_k shape 422s.
        # task_type is not part of the endpoint (its router auto-dispatches),
        # so a configured task_type is accepted but not forwarded.
        body: dict[str, Any] = {
            "query_text": query,
            "max_citations": top_k,
            "locale": "vi",
        }

        # Pilot CPU: /rag/answer = embed + synthesis qua Ollama đang bận —
        # có thể >2 phút; 60s cứng từng giết node giữa run.
        timeout_s = float(os.getenv("KAORI_RAG_NODE_TIMEOUT_S", "300.0"))
        try:
            async with httpx.AsyncClient(timeout=timeout_s) as client:
                resp = await client.post(
                    f"{base_url}/rag/answer",
                    json=body,
                    headers={"X-Enterprise-Id": str(ctx.enterprise_id)},
                )
                resp.raise_for_status()
                payload = resp.json()
        except httpx.HTTPError as exc:
            raise NodeExecutorError(f"rag_query HTTP fail: {type(exc).__name__}: {exc}")

        return NodeResult(
            status="completed",
            output_data={
                "answer":      str(payload.get("answer") or ""),
                "citations":   payload.get("citations") or [],
                "trace_id":    payload.get("trace_id"),
                "engine_name": payload.get("engine_name"),
            },
        )


# ─── 4. call_insight_engine ─────────────────────────────────────────


class CallInsightEngineExecutor(NodeExecutor):
    """call_insight_engine — generic LLM scoring.

    Use cases (mig 069):
      B.4 Lead Nurture — score lead 0-100 by company/industry/engagement
      C.1 Lead Qualification — BANT scoring
      E.2 Supplier Audit — score supplier 0-100

    Config:
      subject:        $.upstream.row  (the entity to score — dict or string)
      dimensions:     ['budget', 'authority', 'need', 'timeline']
                      (required; LLM emits one score per dimension)
      score_range:    [0, 100]   (optional, default 0-100)
      composite_method: 'mean' | 'sum' | 'min'   (default 'mean')
    Output:
      {scores: {dim: number}, composite: number, reasoning: str,
       band: 'low' | 'medium' | 'high'}
    """
    node_type_key = "call_insight_engine"
    side_effect_class = SideEffectClass.READ_ONLY

    async def execute(self, ctx: NodeContext, config: dict[str, Any]) -> NodeResult:
        subject = _resolve(config.get("subject"), ctx)
        if subject is None:
            raise NodeExecutorError("call_insight_engine.subject resolved to None")

        dimensions = config.get("dimensions")
        if not isinstance(dimensions, list) or not dimensions:
            raise NodeExecutorError("call_insight_engine.dimensions required (non-empty list)")
        dims = [str(d).strip().lower() for d in dimensions if str(d).strip()]
        if not dims:
            raise NodeExecutorError("call_insight_engine.dimensions all empty")

        score_range_raw = config.get("score_range") or [0, 100]
        if (not isinstance(score_range_raw, list) or len(score_range_raw) != 2
                or score_range_raw[0] >= score_range_raw[1]):
            raise NodeExecutorError("call_insight_engine.score_range must be [low, high]")
        low, high = float(score_range_raw[0]), float(score_range_raw[1])

        method = (config.get("composite_method") or "mean").lower()
        if method not in ("mean", "sum", "min"):
            raise NodeExecutorError("call_insight_engine.composite_method invalid")

        subject_str = json.dumps(subject, ensure_ascii=False) if isinstance(subject, (dict, list)) else str(subject)

        prompt = "\n".join([
            "Bạn là analyst chấm điểm.",
            f"Hãy chấm điểm chủ thể sau theo các tiêu chí: {', '.join(dims)}.",
            f"Mỗi tiêu chí cho 1 điểm trong khoảng [{low}, {high}].",
            "",
            "Chủ thể:",
            subject_str[:3000],
            "",
            "Trả về JSON: {scores: {<tiêu chí>: <điểm>}, reasoning: 1-2 câu VN}.",
        ])

        from ai_orchestrator.engine.llm_router import llm_router

        schema = {
            "type": "object",
            "required": ["scores", "reasoning"],
            "properties": {
                "scores":    {"type": "object"},
                "reasoning": {"type": "string", "maxLength": 500},
            },
        }
        try:
            result = await llm_router.complete_structured(
                prompt=prompt, task="call_insight_engine",
                output_schema=schema,
                enterprise_id=str(ctx.enterprise_id),
                run_id=str(ctx.run_id), max_tokens=400,
            )
        except AttributeError:
            text = await llm_router.complete(
                prompt=prompt, task="call_insight_engine",
                enterprise_id=str(ctx.enterprise_id),
                run_id=str(ctx.run_id), max_tokens=400,
            )
            result = _safe_json(text)

        scores_raw = result.get("scores") or {}
        if not isinstance(scores_raw, dict):
            scores_raw = {}
        scores: dict[str, float] = {}
        for dim in dims:
            raw_score = scores_raw.get(dim, 0)
            try:
                v = float(raw_score)
            except (TypeError, ValueError):
                v = 0.0
            # Clamp to range
            scores[dim] = max(low, min(high, v))

        # Composite
        values = list(scores.values())
        if not values:
            composite = low
        elif method == "sum":
            composite = sum(values)
        elif method == "min":
            composite = min(values)
        else:
            composite = sum(values) / len(values)

        # Band by tercile
        span = high - low
        if composite >= low + 2 * span / 3:
            band = "high"
        elif composite >= low + span / 3:
            band = "medium"
        else:
            band = "low"

        return NodeResult(
            status="completed",
            output_data={
                "scores":    scores,
                "composite": composite,
                "band":      band,
                "reasoning": str(result.get("reasoning", ""))[:500],
            },
        )


# ─── 5. call_risk_detection ─────────────────────────────────────────


class CallRiskDetectionExecutor(NodeExecutor):
    """call_risk_detection — wrap adoption signals composite score for
    a single tenant.

    Use cases:
      B.2 Churn Intervention — detect at-risk customers
      C.3 Contract Renewal   — health check before renewal proposal

    Config:
      target:       'tenant'  (only mode supported today; wraps
                                org_intel.adoption.compute_composite_score)
      window_days:  30   (optional)
    Output:
      {health_score: float, classification: str,
       band: 'healthy'|'stable'|'stretched'|'at_risk'|'churn_imminent',
       signal_count: int}
    """
    node_type_key = "call_risk_detection"
    side_effect_class = SideEffectClass.READ_ONLY

    async def execute(self, ctx: NodeContext, config: dict[str, Any]) -> NodeResult:
        target = (config.get("target") or "tenant").lower()
        if target != "tenant":
            raise NodeExecutorError(
                f"call_risk_detection.target={target!r} not supported "
                "(only 'tenant' today)"
            )
        window_days = int(config.get("window_days") or 30)
        if window_days < 1 or window_days > 365:
            raise NodeExecutorError("call_risk_detection.window_days must be 1..365")

        from ai_orchestrator.org_intel.adoption import (
            SignalExtractor,
            classify_health,
            compute_composite_score,
        )
        from ai_orchestrator.shared.db import acquire_for_tenant

        async with acquire_for_tenant(ctx.enterprise_id) as conn:
            extractor = SignalExtractor(
                conn=conn,
                enterprise_id=ctx.enterprise_id,
                window_days=window_days,
            )
            samples = await extractor.extract_all()
        composite = compute_composite_score(samples)
        classification = classify_health(composite.score)

        band_value = classification.value if hasattr(classification, "value") else str(classification)

        return NodeResult(
            status="completed",
            output_data={
                "health_score":   float(composite.score),
                "classification": band_value,
                "band":           band_value,
                "signal_count":   len(samples),
                "window_days":    window_days,
            },
        )


# ─── 6. call_forecasting ────────────────────────────────────────────


class CallForecastingExecutor(NodeExecutor):
    """call_forecasting — linear forecast on time-series.

    Wraps the same linear regression OBS-021 capacity_planning uses,
    but exposes it as a generic time-series forecast node.

    Use cases:
      C.5 Pipeline Review — forecast 30-day close revenue
      F.3 Monthly Close — forecast next-month aggregates

    Config:
      points:      $.upstream.series  (list of {ts, value} OR list[float])
      horizon:     30   (optional — periods to project ahead, default 30)
    Output:
      {forecast: list[float], slope: float, intercept: float, r_squared: float,
       trend: 'up'|'down'|'flat', confidence: 'high'|'low'}
    """
    node_type_key = "call_forecasting"
    side_effect_class = SideEffectClass.READ_ONLY

    async def execute(self, ctx: NodeContext, config: dict[str, Any]) -> NodeResult:
        raw_points = _resolve(config.get("points"), ctx)
        if not isinstance(raw_points, list) or not raw_points:
            raise NodeExecutorError("call_forecasting.points must resolve to non-empty list")

        # Accept either list[float] OR list[{ts, value}]
        values: list[float] = []
        for p in raw_points:
            if isinstance(p, (int, float)):
                values.append(float(p))
            elif isinstance(p, dict) and "value" in p:
                try:
                    values.append(float(p["value"]))
                except (TypeError, ValueError):
                    pass
        if len(values) < 3:
            raise NodeExecutorError(
                f"call_forecasting needs >=3 numeric points (got {len(values)})"
            )

        horizon = int(config.get("horizon") or 30)
        if horizon < 1 or horizon > 1000:
            raise NodeExecutorError("call_forecasting.horizon must be 1..1000")

        # Simple linear regression
        n = len(values)
        xs = list(range(n))
        x_mean = sum(xs) / n
        y_mean = sum(values) / n
        num = sum((xs[i] - x_mean) * (values[i] - y_mean) for i in range(n))
        den = sum((xs[i] - x_mean) ** 2 for i in range(n))
        slope = num / den if den > 0 else 0.0
        intercept = y_mean - slope * x_mean
        # R^2
        ss_tot = sum((values[i] - y_mean) ** 2 for i in range(n))
        ss_res = sum((values[i] - (intercept + slope * xs[i])) ** 2 for i in range(n))
        r_squared = 1 - (ss_res / ss_tot) if ss_tot > 0 else 0.0

        forecast = [intercept + slope * (n + h) for h in range(horizon)]
        trend = "up" if slope > 0.01 else ("down" if slope < -0.01 else "flat")
        confidence = "high" if r_squared >= 0.7 else "low"

        return NodeResult(
            status="completed",
            output_data={
                "forecast":   forecast,
                "slope":      slope,
                "intercept":  intercept,
                "r_squared":  r_squared,
                "trend":      trend,
                "confidence": confidence,
                "input_points": n,
                "horizon":    horizon,
            },
        )


# ─── 7. extract_entities ────────────────────────────────────────────


class ExtractEntitiesExecutor(NodeExecutor):
    """extract_entities — NER via LLM with strict output schema.

    Use case: D.3 NPS Follow-up — extract product/feature names from
    free-text feedback.

    Config:
      text:        $.upstream.body  or literal string  (required)
      entity_types: ['product', 'feature', 'person', 'date', 'amount']
                    (required; LLM emits entities grouped by type)
    Output:
      {entities: {type: list[str]}, count: int}
    """
    node_type_key = "extract_entities"
    side_effect_class = SideEffectClass.READ_ONLY

    async def execute(self, ctx: NodeContext, config: dict[str, Any]) -> NodeResult:
        text = _resolve_text(config.get("text"), ctx)
        if not text.strip():
            raise NodeExecutorError("extract_entities.text required (resolved to empty)")
        if len(text) > 6000:
            text = text[:6000]

        types_raw = config.get("entity_types")
        if not isinstance(types_raw, list) or not types_raw:
            raise NodeExecutorError("extract_entities.entity_types required (non-empty list)")
        entity_types = [str(t).strip().lower() for t in types_raw if str(t).strip()]
        if not entity_types:
            raise NodeExecutorError("extract_entities.entity_types all empty")

        prompt = "\n".join([
            "Bạn trích xuất thực thể (NER) từ văn bản tiếng Việt.",
            f"Hãy tìm các thực thể thuộc các loại: {', '.join(entity_types)}.",
            "",
            "Văn bản:",
            text,
            "",
            "Trả về JSON: {entities: {<loại>: [<thực thể 1>, ...], ...}}.",
            "Mỗi loại là 1 mảng (rỗng [] nếu không có). Không thêm loại ngoài danh sách.",
        ])

        from ai_orchestrator.engine.llm_router import llm_router

        schema = {
            "type": "object",
            "required": ["entities"],
            "properties": {
                "entities": {"type": "object"},
            },
        }
        try:
            result = await llm_router.complete_structured(
                prompt=prompt, task="extract_entities",
                output_schema=schema,
                enterprise_id=str(ctx.enterprise_id),
                run_id=str(ctx.run_id), max_tokens=600,
            )
        except AttributeError:
            text_out = await llm_router.complete(
                prompt=prompt, task="extract_entities",
                enterprise_id=str(ctx.enterprise_id),
                run_id=str(ctx.run_id), max_tokens=600,
            )
            result = _safe_json(text_out)

        ent_raw = result.get("entities") or {}
        if not isinstance(ent_raw, dict):
            ent_raw = {}
        entities: dict[str, list[str]] = {}
        total = 0
        for t in entity_types:
            vals = ent_raw.get(t) or []
            if not isinstance(vals, list):
                vals = []
            normalised = [str(v).strip() for v in vals if str(v).strip()]
            entities[t] = normalised
            total += len(normalised)

        return NodeResult(
            status="completed",
            output_data={"entities": entities, "count": total},
        )


# ─── 8. call_recommendation_engine ──────────────────────────────────


class CallRecommendationEngineExecutor(NodeExecutor):
    """call_recommendation_engine — rank items by criteria, return top-N.

    Use case: E.4 Shipment Dispatch — choose carrier by zone/size/cost/SLA.

    Config:
      items:    $.upstream.options   (list of dicts to rank)
      criteria: 'minimise cost while meeting SLA <=24h'  (string)
      top_n:    1   (default 1)
    Output:
      {ranked: list[{item, score, reasoning}], top: <item>, count: int}
    """
    node_type_key = "call_recommendation_engine"
    side_effect_class = SideEffectClass.READ_ONLY

    async def execute(self, ctx: NodeContext, config: dict[str, Any]) -> NodeResult:
        items = _resolve(config.get("items"), ctx)
        if not isinstance(items, list) or not items:
            raise NodeExecutorError("call_recommendation_engine.items must resolve to non-empty list")
        if len(items) > 50:
            raise NodeExecutorError("call_recommendation_engine.items > 50 — pre-filter caller")

        criteria = config.get("criteria")
        if not isinstance(criteria, str) or not criteria.strip():
            raise NodeExecutorError("call_recommendation_engine.criteria required (string)")

        top_n = int(config.get("top_n") or 1)
        if top_n < 1 or top_n > len(items):
            top_n = min(max(1, top_n), len(items))

        items_str = json.dumps(items, ensure_ascii=False)[:5000]
        prompt = "\n".join([
            "Bạn xếp hạng các lựa chọn theo tiêu chí cho trước.",
            "",
            "Tiêu chí:",
            criteria,
            "",
            "Lựa chọn (JSON list):",
            items_str,
            "",
            "Trả về JSON: {ranked: [{index: <0-based>, score (0..1), reasoning (1 câu VN)}, ...]}.",
            "Xếp tất cả lựa chọn, sort theo score giảm dần. score=1 = phù hợp nhất.",
        ])

        from ai_orchestrator.engine.llm_router import llm_router

        schema = {
            "type": "object",
            "required": ["ranked"],
            "properties": {
                "ranked": {
                    "type":  "array",
                    "items": {
                        "type": "object",
                        "required": ["index", "score"],
                        "properties": {
                            "index":     {"type": "integer", "minimum": 0},
                            "score":     {"type": "number", "minimum": 0, "maximum": 1},
                            "reasoning": {"type": "string", "maxLength": 300},
                        },
                    },
                },
            },
        }
        try:
            result = await llm_router.complete_structured(
                prompt=prompt, task="call_recommendation_engine",
                output_schema=schema,
                enterprise_id=str(ctx.enterprise_id),
                run_id=str(ctx.run_id), max_tokens=900,
            )
        except AttributeError:
            text = await llm_router.complete(
                prompt=prompt, task="call_recommendation_engine",
                enterprise_id=str(ctx.enterprise_id),
                run_id=str(ctx.run_id), max_tokens=900,
            )
            result = _safe_json(text)

        ranked_raw = result.get("ranked") or []
        if not isinstance(ranked_raw, list):
            ranked_raw = []
        ranked: list[dict[str, Any]] = []
        for r in ranked_raw:
            if not isinstance(r, dict):
                continue
            try:
                idx = int(r.get("index"))
            except (TypeError, ValueError):
                continue
            if idx < 0 or idx >= len(items):
                continue
            ranked.append({
                "item":       items[idx],
                "index":      idx,
                "score":      float(r.get("score") or 0.0),
                "reasoning":  str(r.get("reasoning") or "")[:300],
            })
        ranked.sort(key=lambda r: r["score"], reverse=True)
        top = ranked[0]["item"] if ranked else None

        return NodeResult(
            status="completed",
            output_data={
                "ranked":  ranked[:top_n],
                "top":     top,
                "count":   len(ranked),
                "criteria": criteria,
            },
        )
