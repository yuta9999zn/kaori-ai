"""Google Calendar + Outlook Calendar metadata connector — PM-EVT-005 (P15-S10 D2)."""

from .connector import (
    CalendarEventMeta,
    CalendarMetadataConnector,
    OAuthCalendarClient,
    StubOAuthCalendarClient,
)

__all__ = [
    "CalendarEventMeta",
    "CalendarMetadataConnector",
    "OAuthCalendarClient",
    "StubOAuthCalendarClient",
]
