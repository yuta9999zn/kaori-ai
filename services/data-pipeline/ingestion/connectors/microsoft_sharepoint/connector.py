"""
Microsoft SharePoint file-change connector — PM-EVT-007 (P2-S13).

Polls MS Graph for document library change events:
  GET /sites/{site-id}/drives/{drive-id}/root/delta
  (delegated scope: Files.Read.All; tenant admin consent typically required)

What we capture (metadata only):
  * file_id (Graph driveItem id)
  * action: 'created' / 'modified' / 'deleted' / 'renamed' / 'moved'
  * actor: SHA-256(lower(last_modified_by_email))
  * file_path (relative; no document content)
  * mime_type
  * file_size_bytes
  * occurred_at (Graph lastModifiedDateTime)

What we DO NOT capture:
  * file content (DocSage handles that on explicit upload)
  * sharing recipients (permissions API separate; PII-heavy)

PII budget per PM-PII-013: actor hash + path/mime/size only. File paths
can include employee names — the K-5 redactor masks those before publish.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, AsyncIterator, Optional, Protocol
from uuid import UUID

from ...base import Connector, NormalizedEvent


_VALID_ACTIONS = {"created", "modified", "deleted", "renamed", "moved"}


@dataclass(frozen=True)
class SharePointFileEvent:
    """Wire shape between Graph client + connector."""
    provider_event_id:     str
    action:                str
    file_id:               str
    file_path:             str
    mime_type:             Optional[str]
    file_size_bytes:       Optional[int]
    last_modified_by_email: str         # raw; hashed at connector boundary
    occurred_at:           datetime
    observed_at:           Optional[datetime] = None


class SharePointClient(Protocol):
    """OAuth-delegated SharePoint client (MSAL + MS Graph delta)."""

    async def list_file_changes(
        self, *, site_id: str, drive_id: str,
        since: Optional[datetime], until: Optional[datetime],
    ) -> AsyncIterator[SharePointFileEvent]:
        ...


class StubSharePointClient:
    """Default client. Raises on use so misconfigured deployment surfaces
    immediately. Real adapter lands when MS Graph OAuth onboarding +
    Tenant Admin consent ships."""

    async def list_file_changes(  # type: ignore[no-untyped-def]
        self, *, site_id, drive_id, since, until,
    ):
        raise NotImplementedError(
            "SharePointClient.list_file_changes — real MS Graph adapter "
            "lands when per-tenant OAuth + Tenant Admin consent onboarding "
            "ships (P2-S13+ follow-up, blocked on tenant providing the "
            "site_id / drive_id mapping)."
        )
        yield  # pragma: no cover


class SharePointConnector(Connector):
    """SharePoint document library change connector."""

    source = "microsoft_sharepoint"

    def __init__(self, *, tenant_id: UUID, config: dict[str, Any]) -> None:
        super().__init__(tenant_id=tenant_id, config=config)
        site_id = str(self.config.get("site_id", "")).strip()
        drive_id = str(self.config.get("drive_id", "")).strip()
        if not site_id:
            raise ValueError(
                "microsoft_sharepoint connector requires config['site_id'] "
                "(MS Graph site GUID or hostname-based site id)"
            )
        if not drive_id:
            raise ValueError(
                "microsoft_sharepoint connector requires config['drive_id'] "
                "(document library drive id; 'root' for default library)"
            )
        self.site_id  = site_id
        self.drive_id = drive_id
        self.client: SharePointClient = self.config.get(
            "client", StubSharePointClient(),
        )

    async def extract_events(
        self, *, since: Optional[datetime] = None, until: Optional[datetime] = None,
    ) -> AsyncIterator[NormalizedEvent]:
        import hashlib
        async for ev in self.client.list_file_changes(
            site_id=self.site_id, drive_id=self.drive_id,
            since=since, until=until,
        ):
            if ev.action not in _VALID_ACTIONS:
                # Skip unknown action labels; Graph occasionally surfaces
                # vendor-specific actions we haven't mapped yet. Better
                # to drop than to ship 'unknown' downstream.
                continue
            actor_hash = hashlib.sha256(
                ev.last_modified_by_email.strip().lower().encode("utf-8")
            ).hexdigest()
            yield NormalizedEvent(
                tenant_id=self.tenant_id,
                event_id=f"sharepoint:{ev.file_id}:{ev.provider_event_id}",
                source=self.source,
                event_type=f"sharepoint.file.{ev.action}",
                occurred_at=ev.occurred_at,
                actor=actor_hash,
                case_id=ev.file_id,
                payload={
                    "site_id":         self.site_id,
                    "drive_id":        self.drive_id,
                    "action":          ev.action,
                    "file_id":         ev.file_id,
                    "file_path":       ev.file_path,
                    "mime_type":       ev.mime_type,
                    "file_size_bytes": ev.file_size_bytes,
                    "actor_hash":      actor_hash,
                },
            )
