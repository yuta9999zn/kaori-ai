"""Gmail + Outlook metadata connector — PM-EVT-004 (P15-S10 D1)."""

from .connector import (
    EmailMessageMeta,
    GmailOutlookConnector,
    OAuthEmailClient,
    StubOAuthEmailClient,
)

__all__ = [
    "EmailMessageMeta",
    "GmailOutlookConnector",
    "OAuthEmailClient",
    "StubOAuthEmailClient",
]
