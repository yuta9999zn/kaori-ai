"""Microsoft SharePoint file-change connector — PM-EVT-007 (P2-S13).

Watches SharePoint document libraries for file create/update/delete via
MS Graph delta query. Process Mining uses the stream to reconstruct
document-handover workflows (proposals reviewed → contract signed →
invoice archived).
"""
from .connector import (
    SharePointFileEvent,
    SharePointClient,
    SharePointConnector,
    StubSharePointClient,
)

__all__ = [
    "SharePointFileEvent",
    "SharePointClient",
    "SharePointConnector",
    "StubSharePointClient",
]
