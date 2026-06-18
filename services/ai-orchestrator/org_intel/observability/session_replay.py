"""
OBS-023 — Session replay PII helpers (P2-S18).

Two responsibilities:
  1. Define which event-stream fields are sensitive (REDACTABLE_FIELDS).
  2. Provide redact_recording_events() that masks them in-place before
     persistence — K-5 enforcement at the application layer.

The recording event format follows the rrweb convention:
  [
    {"type": 0, "data": {snapshot...}, "timestamp": 12345},
    {"type": 3, "data": {source: 2, text: "...", ...}, "timestamp": ...},
    ...
  ]

For text-input events (type=3, source=5), the `text` field is what
the user typed — most likely to contain PII (names, emails, addresses,
contract numbers). We mask those plus a configurable set of attribute
names that may appear in DOM snapshots.
"""
from __future__ import annotations

import re
from copy import deepcopy
from typing import Any


REDACTABLE_FIELDS: frozenset[str] = frozenset({
    # Generic
    "text", "value", "innerText", "innerHTML", "textContent",
    # PII attribute names that DOM snapshots may carry
    "email", "phone", "phoneNumber", "ssn", "nationalId", "passport",
    "address", "fullName", "name", "firstName", "lastName",
    "creditCard", "cardNumber", "cvv", "iban", "bankAccount",
})


# Vietnamese-aware PII regex (mirrors docsage.extraction)
_EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
_PHONE_RE = re.compile(r"\b0\d{9,10}\b|\+84\d{9,10}\b")
_NID_RE   = re.compile(r"\b\d{12}\b")


def _mask_string(s: str) -> str:
    """Apply regex masks. Used both for known-PII fields (always mask)
    and for generic text fields (mask any embedded PII patterns)."""
    s = _EMAIL_RE.sub("<EMAIL>", s)
    s = _PHONE_RE.sub("<PHONE>", s)
    s = _NID_RE.sub("<NID>", s)
    return s


def _redact_recursive(obj: Any) -> Any:
    """Walk a JSON-like structure; mask field values when key is in
    REDACTABLE_FIELDS, otherwise leave but still regex-scan string
    values for embedded PII."""
    if isinstance(obj, dict):
        out: dict[str, Any] = {}
        for k, v in obj.items():
            if k in REDACTABLE_FIELDS and isinstance(v, str):
                # Force-mask known-PII fields entirely
                if v:
                    out[k] = "<REDACTED>"
                else:
                    out[k] = v
            else:
                out[k] = _redact_recursive(v)
        return out
    if isinstance(obj, list):
        return [_redact_recursive(item) for item in obj]
    if isinstance(obj, str):
        return _mask_string(obj)
    return obj


def redact_recording_events(events: list[dict]) -> list[dict]:
    """Return a deep-copy of events with PII fields redacted.

    Non-destructive: caller's input is unchanged. Use this output
    directly as the JSONB value for user_session_recordings.recording_events.
    """
    if not events:
        return []
    cloned = deepcopy(events)
    return [_redact_recursive(e) for e in cloned]
