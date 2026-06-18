"""Slack + Microsoft Teams audit-API connector — PM-EVT-006 (P2-S13).

Reads audit-log events from Slack Enterprise Grid + Microsoft Teams
admin APIs. Used by Process Mining to surface chat-driven workflows
(approvals via DM, project hand-offs in channels) that don't show up
in any transactional system.
"""
from .connector import (
    SlackTeamsAuditConnector,
    SlackTeamsAuditEvent,
    SlackTeamsAuditClient,
    StubSlackTeamsAuditClient,
)

__all__ = [
    "SlackTeamsAuditConnector",
    "SlackTeamsAuditEvent",
    "SlackTeamsAuditClient",
    "StubSlackTeamsAuditClient",
]
