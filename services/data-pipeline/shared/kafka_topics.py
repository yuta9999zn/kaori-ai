"""
Kafka topic name constants — single source of truth for the
data-pipeline service.

Topics are namespaced under ``kaori.*`` per CLAUDE.md §7 and
TARGET_ARCHITECTURE_1M.md §3.1. Producers and consumers must reference
these constants — never inline string literals (caught by arch-guards G2).

Migration note:
  Before this batch, topics used the bare ``pipeline.*`` namespace
  (``pipeline.upload.received``, ``pipeline.bronze.complete``, etc.) —
  inconsistent with the documented event backbone. The ``kaori.``
  prefix is added without changing the rest of the topic shape so any
  future MirrorMaker / Schema-Registry tooling can rely on a single
  prefix to recognise platform events.
"""

PIPELINE_UPLOAD_RECEIVED   = "kaori.pipeline.upload.received"
PIPELINE_BRONZE_COMPLETE   = "kaori.pipeline.bronze.complete"
PIPELINE_SILVER_COMPLETE   = "kaori.pipeline.silver.complete"
PIPELINE_ANALYSIS_COMPLETE = "kaori.pipeline.analysis.complete"

# K-6 audit stream — produced by services that wrap automated decisions
# (LLM router, schema column mapper, cleaning rule application, …).
AUDIT_DECISIONS            = "kaori.audit.decisions"
