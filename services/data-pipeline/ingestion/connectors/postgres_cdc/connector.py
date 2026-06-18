"""
Postgres CDC connector — PM-EVT-001 (Sprint P1-S3 skeleton, full impl P1-S7).

Reads logical-replication slots to capture INSERT/UPDATE/DELETE events
from a tenant's operational Postgres. Used by Process Mining v1 to
reconstruct workflows from state-machine logs (orders, tasks, approvals).

Config keys (all under ``connector.config``):
  dsn               — Postgres connection string (read from Vault, NOT inline)
  publication_name  — name of the CREATE PUBLICATION on source DB
  slot_name         — name of CREATE_REPLICATION_SLOT
  tables            — list of fully-qualified tables to capture (e.g. ['public.orders'])
  state_columns     — per-table column to treat as state machine value

Phase 1 v4 (this file): contract surface only — extract_events raises
NotImplementedError. Sprint P1-S7 wires the actual psycopg LogicalReplicationConnection
+ wal2json parser + emit loop.
"""
from __future__ import annotations

from datetime import datetime
from typing import AsyncIterator, Optional

from ...base import Connector, NormalizedEvent


class PostgresCdcConnector(Connector):
    """Logical-replication-based CDC capture for tenant Postgres."""

    source = "postgres_cdc"

    async def extract_events(
        self,
        *,
        since: Optional[datetime] = None,
        until: Optional[datetime] = None,
    ) -> AsyncIterator[NormalizedEvent]:
        raise NotImplementedError(
            "PostgresCdcConnector.extract_events lands Sprint P1-S7 "
            "(Process Mining v1 / PM-EVT-001 implementation). Phase 1 "
            "v4 P1-S3 ships skeleton only — see "
            "docs/strategic/WORKFLOW_SYSTEM.md PART IV Phần 11."
        )
        yield  # pragma: no cover
