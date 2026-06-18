"""Generic webhook event-log connector — PM-EVT-008 (P2-S13).

Accepts arbitrary tenant-defined webhook payloads + maps them into the
NormalizedEvent schema via a tenant-supplied JSONPath mapping.
"""
from .connector import (
    GenericWebhookConnector,
    GenericWebhookEvent,
    WebhookMapping,
    map_payload,
)

__all__ = [
    "GenericWebhookConnector",
    "GenericWebhookEvent",
    "WebhookMapping",
    "map_payload",
]
