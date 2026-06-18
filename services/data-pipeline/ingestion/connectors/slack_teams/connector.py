"""
Slack/Teams audit-API connector — PM-EVT-006 (P2-S13).

Reads workspace-level audit events:
  * Slack: ``audit.logs.v1.list`` (Enterprise Grid OAuth scope `auditlogs:read`)
  * MS Teams: ``GET /auditLogs/directoryAudits`` + Teams Compliance API
    (delegated permission ``AuditLog.Read.All``)

What we capture (metadata only):
  * actor: SHA-256(lower(user_email))
  * action: 'channel_message_posted' / 'file_shared' / 'channel_member_added'
    / 'meeting_started' / etc.  (mapped from provider event name)
  * channel_or_team: workspace/channel/team id (NOT the name; names can
    leak PII when employees use them as labels)
  * timestamp
  * thread/case grouping when the provider exposes it

What we DO NOT capture:
  * message body / file contents
  * private channel rosters (compliance gate)
  * reactions / emoji (not signal for process mining)

PII budget per PM-PII-013: actor + workspace IDs only. Bodies are
shipped through PageIndex / DocSage (with full audit + redaction)
only when an Analyst explicitly attaches them to a session.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, AsyncIterator, Optional, Protocol
from uuid import UUID

from ...base import Connector, NormalizedEvent


_VALID_CHANNELS = {"slack", "teams"}


@dataclass(frozen=True)
class SlackTeamsAuditEvent:
    """Wire shape between OAuth client + connector. Bridge between the
    provider event JSON and our NormalizedEvent."""
    provider_event_id: str
    actor_email:       str           # raw; hashed at connector boundary
    action_name:       str
    workspace_id:      str
    channel_or_team_id: Optional[str] = None
    thread_id:         Optional[str] = None
    occurred_at:       datetime = datetime.min   # provider timestamp
    observed_at:       Optional[datetime] = None


class SlackTeamsAuditClient(Protocol):
    """OAuth client protocol — real adapters land when Slack Enterprise
    Grid / Teams Compliance API onboarding settles per-tenant."""

    async def list_audit_events(
        self, *, since: Optional[datetime], until: Optional[datetime],
    ) -> AsyncIterator[SlackTeamsAuditEvent]:
        ...


class StubSlackTeamsAuditClient:
    """Default client when no real adapter injected. Raises on use so a
    misconfigured deployment surfaces immediately (vs silently emitting
    zero events forever)."""

    async def list_audit_events(  # type: ignore[no-untyped-def]
        self, *, since: Optional[datetime], until: Optional[datetime],
    ):
        raise NotImplementedError(
            "SlackTeamsAuditClient.list_audit_events — real Slack Enterprise "
            "Grid + Teams Compliance API adapters land when per-tenant OAuth "
            "onboarding completes (P2-S13+ follow-up, blocked on tenant "
            "providing the Enterprise Grid admin token / Tenant Admin consent)."
        )
        yield  # pragma: no cover


class SlackTeamsAuditConnector(Connector):
    """Provider-agnostic chat-audit connector. Channel discriminates."""

    source = "slack_teams"

    def __init__(self, *, tenant_id: UUID, config: dict[str, Any]) -> None:
        super().__init__(tenant_id=tenant_id, config=config)
        channel = str(self.config.get("channel", "")).lower()
        if channel not in _VALID_CHANNELS:
            raise ValueError(
                f"slack_teams connector requires config['channel'] in "
                f"{sorted(_VALID_CHANNELS)}; got {channel!r}"
            )
        workspace_id = str(self.config.get("workspace_id", "")).strip()
        if not workspace_id:
            raise ValueError(
                "slack_teams connector requires config['workspace_id'] "
                "(Slack T<id> for Enterprise Grid; Teams tenant_id for MS)"
            )
        self.channel = channel
        self.workspace_id = workspace_id
        self.client: SlackTeamsAuditClient = self.config.get(
            "client", StubSlackTeamsAuditClient(),
        )

    async def extract_events(
        self, *, since: Optional[datetime] = None, until: Optional[datetime] = None,
    ) -> AsyncIterator[NormalizedEvent]:
        import hashlib
        async for ev in self.client.list_audit_events(since=since, until=until):
            actor_hash = hashlib.sha256(
                ev.actor_email.strip().lower().encode("utf-8")
            ).hexdigest()
            yield NormalizedEvent(
                tenant_id=self.tenant_id,
                event_id=f"slack_teams:{self.channel}:{ev.provider_event_id}",
                source=self.source,
                event_type=f"chat.{ev.action_name}",
                occurred_at=ev.occurred_at,
                actor=actor_hash,
                case_id=ev.thread_id or ev.channel_or_team_id,
                payload={
                    "channel":             self.channel,
                    "workspace_id":        self.workspace_id,
                    "channel_or_team_id":  ev.channel_or_team_id,
                    "thread_id":           ev.thread_id,
                    "action_name":         ev.action_name,
                    "actor_hash":          actor_hash,
                },
            )
