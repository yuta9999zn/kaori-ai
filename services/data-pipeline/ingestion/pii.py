"""
Vietnamese-aware PII detection + redaction (PM-PII-010..012 placeholder).

Phase 1 v4 ships interface only. Sprint P1-S7 (Process Mining v1) ships
the real detector with:
  * Email + phone (Vietnamese formats: +84, 0xxx)
  * Vietnamese names (full diacritics + ASCII variants)
  * CCCD / CMND (12-digit + 9-digit national IDs)
  * License plates (region codes + plate format)
  * Bank account numbers (region-specific patterns)
  * Tax codes (10-digit MST)
  * Coordinates (lat/long inside VN bounding box)

Why VN-aware: generic English-language PII detectors miss most VN
identifiers. ENTITLEMENT BAR for the Process Mining moat (BACKLOG_V4
PM-PII-010 ⭐ NEW v2.0).
"""
from __future__ import annotations

from typing import Any


_REDACTION_TOKEN = "[redacted]"


def redact_pii(text: str) -> str:
    """Return ``text`` with all detected PII replaced by ``[redacted]``.

    Phase 1 v4 stub: returns input unchanged. Sprint P1-S7 ships the
    real implementation. Callers MUST use this function (not their own
    regex) so when the real impl lands, every connector picks it up.
    """
    return text


def redact_event_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """Recursively redact PII inside a payload dict.

    Phase 1 v4 stub: shallow-copies the dict with no actual redaction.
    Sprint P1-S7 ships recursive walk with type-aware redaction.
    """
    return dict(payload)


def detect_pii_keys(payload: dict[str, Any]) -> list[str]:
    """Return list of payload keys that look like they hold PII.

    Used by the Process Mining session approval gate (PM-PII-013) to
    show the customer what fields will be masked before the session
    runs. Phase 1 v4 stub returns []; Sprint P1-S7 returns real list.
    """
    return []
