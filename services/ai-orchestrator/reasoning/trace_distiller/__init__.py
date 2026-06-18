"""
P2-S21 D1 — T-Cube Trace Distiller.

Implements arXiv 2605.03344 "RAG over Thinking Traces" (Arabzadeh,
Zaharia et al., UC Berkeley). Distills raw thinking traces from
`decision_audit_log` into 3 retrieval-friendly forms (Struct / Semantic
/ Reflect) → Memory L4 PROCEDURAL tier.

Public surface
--------------
    TCubeTransformer    — async transform of one trace into 3 forms
    ThinkingTrace       — input shape (wraps decision_audit_log row)
    TCubeOutput         — output shape (3 strings)
    TCubeForm           — enum literal: "struct" / "semantic" / "reflect"

K-rules touched
---------------
- K-3: All LLM calls via llm-gateway (no direct SDK).
- K-4: Default Qwen-only distillation; vendor opt-in via tenant flag.
- K-5: PII redaction before storing traces (mask first, distill second).
- K-20: LLM version pinning — distiller records source model + version
  in trace metadata so retrieval can filter by version compatibility.
"""
from .transformer import (
    ExtractedFact,
    TCubeForm,
    TCubeOutput,
    TCubeTransformer,
    ThinkingTrace,
)
from .worker import (
    DEFAULT_BATCH_SIZE,
    DEFAULT_CONFIDENCE_THRESHOLD,
    DEFAULT_MAX_RETRIES,
    TraceDistillerWorker,
    WorkerStats,
)

__all__ = [
    "ExtractedFact",
    "TCubeForm",
    "TCubeOutput",
    "TCubeTransformer",
    "ThinkingTrace",
    "TraceDistillerWorker",
    "WorkerStats",
    "DEFAULT_BATCH_SIZE",
    "DEFAULT_CONFIDENCE_THRESHOLD",
    "DEFAULT_MAX_RETRIES",
]
