"""
Zalo Business API metadata connector — PM-EVT-003 (CRITICAL Vietnam).

Reads message metadata (NOT content) from a tenant's Zalo Business
account to detect who-talked-to-whom and timing — without ingesting
private message bodies. Process Mining uses this to surface
order-confirmation and customer-service workflows that happen entirely
in Zalo (the dominant ops channel for Vietnamese SMEs).

What we capture (metadata only):
  - sender / recipient ids (after PII normalization)
  - timestamp of message
  - message type (text / image / file / sticker / call)
  - thread id (for sequence reconstruction)
  - reply-to id
  - read receipt timestamps

What we DO NOT capture:
  - message body / file content
  - profile photos
  - location data
  - payment intents

Why metadata-only: Vietnam law on personal communication + customer
trust. PM-PII-013 (Mining session approval gates) makes this scope
explicit before the customer enables this connector.

Config keys:
  zalo_app_id           — OA app id
  oauth_credential_path — Vault path for refresh token
  poll_interval_seconds — how often to pull (default 300s)

Phase 1 v4 (this file): skeleton only. Sprint P1-S7 ships OAuth +
Zalo OA REST API client.
"""
from __future__ import annotations

from datetime import datetime
from typing import AsyncIterator, Optional

from ...base import Connector, NormalizedEvent


class ZaloMetadataConnector(Connector):
    """Zalo Business API metadata-only reader. Vietnam-critical."""

    source = "zalo_metadata"

    async def extract_events(
        self,
        *,
        since: Optional[datetime] = None,
        until: Optional[datetime] = None,
    ) -> AsyncIterator[NormalizedEvent]:
        raise NotImplementedError(
            "ZaloMetadataConnector.extract_events lands Sprint P1-S7 "
            "(Process Mining v1 / PM-EVT-003 implementation). Phase 1 "
            "v4 P1-S3 ships skeleton only — see "
            "docs/strategic/WORKFLOW_SYSTEM.md PART IV Phần 11."
        )
        yield  # pragma: no cover
