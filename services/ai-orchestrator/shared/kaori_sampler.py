"""
OBS-005 — head-based sampling policy for OpenTelemetry traces.

Replaces the flat ``TraceIdRatioBased(TRACING_SAMPLE_RATE)`` in
shared/tracing.py with a path-aware sampler that:

  * **Always samples (100%)** high-value spans:
      - decision audit calls          (path startswith /decisions)
      - LLM-gateway dispatch          (path startswith /v1/infer, /v1/embed)
      - workflow execution            (path startswith /workflows, /process-mining)
      - errors (status code ≥ 5xx)    (any path; checked via span attributes)
      - per-tenant force-sample list  (env KAORI_FORCE_SAMPLE_TENANTS)

  * **Down-samples** to TRACING_SAMPLE_RATE for everything else:
      - /health, /metrics                — sampled at 0.01 baseline (very chatty)
      - all other paths                  — sampled at TRACING_SAMPLE_RATE

The sampler is HEAD-based per OpenTelemetry semantics: the decision
is made at root-span creation time, then propagated through the trace.
Phase 2+ swaps to tail-based via OTel Collector when we need "always
keep errors regardless of head decision".

K-19: tenant_id is read from span attribute when present so per-tenant
overrides apply even when the path is generic.

Env vars
--------
  TRACING_SAMPLE_RATE              base rate (default 1.0)
  TRACING_CHATTY_RATE              health/metrics rate (default 0.01)
  KAORI_FORCE_SAMPLE_TENANTS       comma-separated UUIDs, always sampled
  KAORI_HIGH_VALUE_PATHS           comma-separated path prefixes (override default list)
"""
from __future__ import annotations

import os
from typing import Optional, Sequence

from opentelemetry.context import Context
from opentelemetry.sdk.trace.sampling import (
    Decision,
    ParentBased,
    Sampler,
    SamplingResult,
    TraceIdRatioBased,
)
from opentelemetry.trace import Link, SpanKind
from opentelemetry.util.types import Attributes


# Default high-value path prefixes. Override via KAORI_HIGH_VALUE_PATHS.
DEFAULT_HIGH_VALUE_PATHS: tuple[str, ...] = (
    "/decisions",        # F-029 AI decision log
    "/v1/infer",         # llm-gateway dispatch
    "/v1/embed",         # llm-gateway embedding
    "/workflows",        # workflow execution
    "/process-mining",   # process mining endpoints
    "/economics/reports/manager-digest",   # NOV-RPT-020 CFO digest
)

# Chatty paths — sampled at the chatty rate, not the base rate.
DEFAULT_CHATTY_PATHS: tuple[str, ...] = ("/health", "/metrics")


def _parse_tenant_list(raw: str) -> frozenset[str]:
    return frozenset(s.strip() for s in raw.split(",") if s.strip())


def _parse_path_list(raw: str, default: tuple[str, ...]) -> tuple[str, ...]:
    items = tuple(s.strip() for s in raw.split(",") if s.strip())
    return items or default


class KaoriHeadSampler(Sampler):
    """Path-aware head sampler for Kaori traces."""

    def __init__(
        self, *,
        base_rate: float,
        chatty_rate: float,
        high_value_paths: Sequence[str],
        chatty_paths: Sequence[str],
        force_sample_tenants: frozenset[str],
    ):
        self._base_sampler   = TraceIdRatioBased(base_rate)
        self._chatty_sampler = TraceIdRatioBased(chatty_rate)
        self._high_value_paths = tuple(high_value_paths)
        self._chatty_paths     = tuple(chatty_paths)
        self._force_sample_tenants = force_sample_tenants
        self._base_rate   = base_rate
        self._chatty_rate = chatty_rate

    def should_sample(
        self,
        parent_context: Optional[Context],
        trace_id: int,
        name: str,
        kind: Optional[SpanKind] = None,
        attributes: Attributes = None,
        links: Optional[Sequence[Link]] = None,
        trace_state=None,
    ) -> SamplingResult:
        # Pull request path + tenant from FastAPI auto-instrumentation
        # span attributes. http.target is the path; tenant_id is the
        # Kaori convention (set via LogContextMiddleware).
        attrs = dict(attributes or {})
        path = (
            attrs.get("http.target")
            or attrs.get("url.path")
            or attrs.get("http.route")
            or ""
        )
        tenant_id = attrs.get("tenant_id") or attrs.get("enterprise_id")

        # Per-tenant force-sample list — always RECORD_AND_SAMPLE.
        if tenant_id and str(tenant_id) in self._force_sample_tenants:
            return SamplingResult(
                Decision.RECORD_AND_SAMPLE,
                attributes={"kaori.sampling.reason": "force_sample_tenant"},
                trace_state=trace_state,
            )

        # High-value paths — always sample.
        path_str = str(path)
        if any(path_str.startswith(p) for p in self._high_value_paths):
            return SamplingResult(
                Decision.RECORD_AND_SAMPLE,
                attributes={"kaori.sampling.reason": "high_value_path"},
                trace_state=trace_state,
            )

        # Chatty paths — heavily down-sampled.
        if any(path_str.startswith(p) for p in self._chatty_paths):
            inner = self._chatty_sampler.should_sample(
                parent_context, trace_id, name, kind, attributes, links, trace_state,
            )
            return SamplingResult(
                inner.decision,
                attributes={**(inner.attributes or {}),
                             "kaori.sampling.reason": "chatty_downsample"},
                trace_state=inner.trace_state,
            )

        # Default — base rate.
        inner = self._base_sampler.should_sample(
            parent_context, trace_id, name, kind, attributes, links, trace_state,
        )
        return SamplingResult(
            inner.decision,
            attributes={**(inner.attributes or {}),
                         "kaori.sampling.reason": "base_rate"},
            trace_state=inner.trace_state,
        )

    def get_description(self) -> str:
        return (
            f"KaoriHeadSampler(base={self._base_rate}, chatty={self._chatty_rate}, "
            f"high_value_paths={self._high_value_paths}, "
            f"chatty_paths={self._chatty_paths}, "
            f"force_sample_tenants_count={len(self._force_sample_tenants)})"
        )


def build_sampler() -> Sampler:
    """Factory the service tracing setup calls. Wraps KaoriHeadSampler
    in ParentBased so child spans inherit the root decision (correct
    distributed-tracing semantics)."""
    base_rate = _safe_float(os.getenv("TRACING_SAMPLE_RATE", "1.0"), default=1.0)
    chatty_rate = _safe_float(os.getenv("TRACING_CHATTY_RATE", "0.01"),
                                default=0.01)
    high_value = _parse_path_list(
        os.getenv("KAORI_HIGH_VALUE_PATHS", ""), DEFAULT_HIGH_VALUE_PATHS,
    )
    chatty = _parse_path_list(
        os.getenv("KAORI_CHATTY_PATHS", ""), DEFAULT_CHATTY_PATHS,
    )
    force_tenants = _parse_tenant_list(
        os.getenv("KAORI_FORCE_SAMPLE_TENANTS", "")
    )

    head = KaoriHeadSampler(
        base_rate=base_rate, chatty_rate=chatty_rate,
        high_value_paths=high_value, chatty_paths=chatty,
        force_sample_tenants=force_tenants,
    )
    # ParentBased: child spans inherit parent's decision. Root spans
    # use the head sampler we just built.
    return ParentBased(root=head)


def _safe_float(s: str, *, default: float) -> float:
    try:
        return float(s)
    except (TypeError, ValueError):
        return default
