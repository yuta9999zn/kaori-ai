"""
T-Cube transformer — produces 3 retrieval forms from one raw thinking trace.

Pipeline per row of `decision_audit_log`::

    ThinkingTrace
        ├── distill(Struct) ──┐
        ├── distill(Semantic) ┼──► TCubeOutput
        └── distill(Reflect)  ┘
                                   │
                                   ▼
                         3 × MemoryRecord (L4 PROCEDURAL)
                            tagged metadata.tcube_form
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional, Protocol
from uuid import UUID, uuid4

import structlog

from ..memory.types import MemoryRecord, MemoryTier, MemoryType
from . import prompts

log = structlog.get_logger()


@dataclass(frozen=True)
class ExtractedFact:
    """One fact returned by extract_facts(). subject-predicate-object
    triple with confidence + source snippet for traceability."""
    subject:        str
    predicate:      str
    object:         str
    confidence:     float
    source_snippet: str


class TCubeForm(str, Enum):
    STRUCT   = "struct"
    SEMANTIC = "semantic"
    REFLECT  = "reflect"


@dataclass
class ThinkingTrace:
    """One row of decision_audit_log mapped to distiller input.

    `raw_text` = the `reasoning` column.
    `problem_context` = decision_type + subject + alternatives summary
                        (NOT chosen_value — that's the answer, not the
                        question).
    """
    source_decision_id: UUID
    tenant_id:          UUID
    raw_text:           str
    problem_context:    str
    source_llm_provider: Optional[str] = None
    source_llm_version: Optional[str] = None  # K-20 pinned version
    occurred_at:        datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class TCubeOutput:
    """3 distilled forms — each ~500 tokens, embedding-ready."""
    struct:   str
    semantic: str
    reflect:  str
    distiller_model: str
    distiller_version: Optional[str] = None


class _LLMClient(Protocol):
    """Minimal contract for the LLM client. Real impl in llm-gateway
    adapter; tests mock this Protocol directly."""

    async def complete(
        self,
        *,
        tenant_id: UUID,
        prompt: str,
        max_tokens: int,
        model: Optional[str] = None,
    ) -> str:
        ...


class TCubeTransformer:
    """Distills one ThinkingTrace into 3 retrieval forms.

    Constructor takes the LLM client (so tests inject mocks) and an
    optional model pin (K-20). When `model` is None, the underlying
    llm-gateway adapter picks per tenant routing rules (default Qwen
    2.5 14B per K-4).
    """

    DEFAULT_MAX_TOKENS = 600  # per form — paper §3.2 used ~500
    DEFAULT_DISTILLER_MODEL = "qwen2.5:14b"  # K-4 default

    def __init__(
        self,
        llm_client: _LLMClient,
        *,
        distiller_model: Optional[str] = None,
        distiller_version: Optional[str] = None,
        max_tokens_per_form: int = DEFAULT_MAX_TOKENS,
    ):
        self._llm = llm_client
        self._model = distiller_model or self.DEFAULT_DISTILLER_MODEL
        self._version = distiller_version
        self._max_tokens = max_tokens_per_form

    async def transform(self, trace: ThinkingTrace) -> TCubeOutput:
        """Distill one trace → 3 forms via 3 parallel LLM calls."""
        rendered = {
            TCubeForm.STRUCT:   prompts.render(prompts.PROMPT_STRUCT,
                                               problem_context=trace.problem_context,
                                               raw_trace=trace.raw_text),
            TCubeForm.SEMANTIC: prompts.render(prompts.PROMPT_SEMANTIC,
                                               problem_context=trace.problem_context,
                                               raw_trace=trace.raw_text),
            TCubeForm.REFLECT:  prompts.render(prompts.PROMPT_REFLECT,
                                               problem_context=trace.problem_context,
                                               raw_trace=trace.raw_text),
        }
        # Parallel LLM calls — same tenant, same model pin
        results = await asyncio.gather(
            *[self._llm.complete(
                tenant_id=trace.tenant_id,
                prompt=p,
                max_tokens=self._max_tokens,
                model=self._model,
            ) for p in rendered.values()],
            return_exceptions=True,
        )
        # If any form failed, raise — partial distillation is unsafe to store
        for r in results:
            if isinstance(r, Exception):
                log.error("tcube.distill.failed",
                          decision_id=str(trace.source_decision_id),
                          error=str(r))
                raise r
        struct, semantic, reflect = results  # type: ignore[misc]
        log.info("tcube.distill.ok",
                 decision_id=str(trace.source_decision_id),
                 tenant_id=str(trace.tenant_id),
                 model=self._model)
        return TCubeOutput(
            struct=struct.strip(),         # type: ignore[union-attr]
            semantic=semantic.strip(),     # type: ignore[union-attr]
            reflect=reflect.strip(),       # type: ignore[union-attr]
            distiller_model=self._model,
            distiller_version=self._version,
        )

    async def transform_and_store(
        self,
        trace:          ThinkingTrace,
        memory_service: Any,   # MemoryService — late-bind to avoid circular import
    ) -> TCubeOutput:
        """Distill + persist 3 records into Memory L4 PROCEDURAL tier.

        Each MemoryRecord carries metadata:
          - tcube_form              : "struct" | "semantic" | "reflect"
          - source_decision_id      : UUID of original decision_audit_log row
          - source_llm_provider     : provider that produced raw trace
          - source_llm_version      : pinned version (K-20)
          - distiller_model         : model that did distillation
          - problem_context         : short context for retrieval reranking
        """
        out = await self.transform(trace)
        for form, content in (
            (TCubeForm.STRUCT,   out.struct),
            (TCubeForm.SEMANTIC, out.semantic),
            (TCubeForm.REFLECT,  out.reflect),
        ):
            await memory_service.write(
                tenant_id=trace.tenant_id,
                memory_type=MemoryType.PROCEDURAL,
                content=content,
                metadata={
                    "tcube_form":            form.value,
                    "source_decision_id":    str(trace.source_decision_id),
                    "source_llm_provider":   trace.source_llm_provider,
                    "source_llm_version":    trace.source_llm_version,
                    "distiller_model":       out.distiller_model,
                    "distiller_version":     out.distiller_version,
                    "problem_context":       trace.problem_context[:500],
                },
            )
        return out

    # ─── Mem0-inspired fact extraction (ship 2026-05-17) ─────────────

    async def extract_facts(
        self,
        text:            str,
        *,
        tenant_id,
        context:         str = "",
        max_tokens:      int = 800,
    ) -> list[ExtractedFact]:
        """Single LLM call → 0-5 subject-predicate-object facts.

        Inspired by mem0's `memory.add(text)` pattern, ported to Kaori's
        T-Cube infrastructure. Output writes to L3/L4 as MemoryType.SEMANTIC
        (vs. PROCEDURAL for full thinking-trace distillation).

        Returns empty list if LLM returns empty / unparseable JSON.
        Does NOT raise on bad JSON — fact extraction is opportunistic;
        a malformed turn just yields zero facts.
        """
        import json
        rendered = prompts.render(
            prompts.PROMPT_EXTRACT_FACTS,
            problem_context=context or "(no specific context)",
            raw_trace=text,
        )
        try:
            raw = await self._llm.complete(
                tenant_id=tenant_id,
                prompt=rendered,
                max_tokens=max_tokens,
                model=self._model,
            )
        except Exception as exc:  # noqa: BLE001
            log.warning("tcube.extract_facts.llm_failed",
                        tenant_id=str(tenant_id), error=str(exc))
            return []

        cleaned = raw.strip()
        # Some LLMs prefix with ```json fences
        if cleaned.startswith("```"):
            cleaned = cleaned.strip("`")
            if cleaned.lower().startswith("json"):
                cleaned = cleaned[4:]
        cleaned = cleaned.strip()

        try:
            arr = json.loads(cleaned)
        except json.JSONDecodeError:
            log.warning("tcube.extract_facts.bad_json",
                        tenant_id=str(tenant_id),
                        sample=cleaned[:200])
            return []
        if not isinstance(arr, list):
            return []

        facts: list[ExtractedFact] = []
        for item in arr[:10]:    # hard cap regardless of model's output
            if not isinstance(item, dict):
                continue
            try:
                conf = float(item.get("confidence", 0))
            except (TypeError, ValueError):
                continue
            if conf < 0.5:
                continue
            subj = str(item.get("subject", "")).strip()
            pred = str(item.get("predicate", "")).strip()
            obj  = str(item.get("object", "")).strip()
            if not (subj and pred and obj):
                continue
            facts.append(ExtractedFact(
                subject=subj[:200],
                predicate=pred[:200],
                object=obj[:500],
                confidence=min(1.0, conf),
                source_snippet=text[:300],
            ))
        log.info("tcube.extract_facts.ok",
                 tenant_id=str(tenant_id),
                 fact_count=len(facts),
                 raw_text_len=len(text))
        return facts

    async def extract_and_store_facts(
        self,
        text:           str,
        *,
        tenant_id,
        memory_service,        # MemoryService
        context:        str = "",
        session_id:     Optional[str] = None,
        source_ref:     Optional[str] = None,
    ) -> list[ExtractedFact]:
        """Extract + persist each high-confidence fact as a SEMANTIC
        memory record. SEMANTIC type lands in L4 by default (see
        MemoryService._DEFAULT_TIER) — durable + retrievable across
        sessions.
        """
        facts = await self.extract_facts(
            text, tenant_id=tenant_id, context=context,
        )
        for fact in facts:
            content = f"{fact.subject} — {fact.predicate} — {fact.object}"
            await memory_service.write(
                tenant_id=tenant_id,
                memory_type=MemoryType.SEMANTIC,
                content=content,
                session_id=session_id,
                metadata={
                    "source": "fact_extraction",
                    "subject":    fact.subject,
                    "predicate":  fact.predicate,
                    "object":     fact.object,
                    "confidence": fact.confidence,
                    "snippet":    fact.source_snippet,
                    "source_ref": source_ref,
                    "extractor_model": self._model,
                },
            )
        return facts
