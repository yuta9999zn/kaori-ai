"""
Ingestion package — L1 of the Kaori stack (Pipeline Unified Stage 1).

Sources of bronze-tier raw events. Two flavours of connectors live here:

1. **File-based ingestion** (already exists in routers/upload.py) —
   user uploads CSV/Excel/JSON; the router writes Bronze rows directly.
   Wraps the existing data_plane/bronze/ingestor.py logic.

2. **Connector-based ingestion** (NEW Sprint P1-S3) — pull events from
   external systems on a schedule or stream. Each connector lives at
   ``ingestion/connectors/<source>/`` with a ``connector.py`` module
   exposing a class extending :class:`base.Connector`.

Phase 1 v4 ships skeleton-only connectors (postgres_cdc, excel_filesystem,
zalo_metadata) per RESTRUCTURE_PROPOSAL §3 Step 4 + BACKLOG_V4 P1-S3.
Full implementation lands Sprint P1-S7 alongside Process Mining v1
(PM-EVT-001..003).

See ``services/process-mining/`` for the Phase 2 extract target.
"""
