"""
Kafka topic name constants — single source of truth for the
ai-orchestrator service.

Mirrors services/data-pipeline/shared/kafka_topics.py. Each service
owns its own copy so the modules can be imported without crossing
service package boundaries (consistent with how shared/db.py and
shared/kafka_producer.py are duplicated). Names must stay aligned —
arch-guards G2 lints both directories with the same regex.

See CLAUDE.md §7 and TARGET_ARCHITECTURE_1M.md §3.1 for the full topic
catalogue.
"""

PIPELINE_UPLOAD_RECEIVED   = "kaori.pipeline.upload.received"
PIPELINE_BRONZE_COMPLETE   = "kaori.pipeline.bronze.complete"
PIPELINE_SILVER_COMPLETE   = "kaori.pipeline.silver.complete"
PIPELINE_ANALYSIS_COMPLETE = "kaori.pipeline.analysis.complete"

# K-6 audit stream
AUDIT_DECISIONS            = "kaori.audit.decisions"

# F-038 Reports — emitted on terminal status (ready / failed). Schema
# in infrastructure/kafka/schemas/kaori.reports.generated.json.
REPORTS_GENERATED          = "kaori.reports.generated"

# F-036 Decision Override — emitted when a domain expert overrides an
# AI decision (or revokes a prior override). Future Sprint 7 PR D
# migration will also emit here for the is_actioned toggle. Schema in
# infrastructure/kafka/schemas/kaori.feedback.actions.json.
FEEDBACK_ACTIONS           = "kaori.feedback.actions"

# F-033 Multi-tier Analysis — fired when a tier run starts (queued
# row inserted) and completes (status terminal). Two topics let
# consumers subscribe to either the start signal (e.g., kicks off a
# tier-quota check) or the completion signal (e.g., notification fan-
# out, ops rollup) without re-deriving the lifecycle. Schemas at
# infrastructure/kafka/schemas/kaori.analysis.tier.{started,completed}.json.
ANALYSIS_TIER_STARTED      = "kaori.analysis.tier.started"
ANALYSIS_TIER_COMPLETED    = "kaori.analysis.tier.completed"
