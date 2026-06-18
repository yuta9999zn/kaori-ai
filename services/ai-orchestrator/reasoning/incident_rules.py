"""Pure EU AI Act K-26 incident vocabulary + validation (ADR-0041 Layer 3).

No I/O. Severity 'serious' = Art 73-reportable. Used by the incidents router
to validate input before the DB write.
"""
from __future__ import annotations

SEVERITIES: tuple[str, ...] = ("low", "medium", "high", "serious")
INCIDENT_STATUSES: tuple[str, ...] = ("open", "investigating", "resolved")


def validate_severity(value: str) -> str:
    norm = (value or "").strip().lower()
    if norm not in SEVERITIES:
        raise ValueError(f"unknown severity: {value!r} (expected one of {SEVERITIES})")
    return norm


def validate_status(value: str) -> str:
    norm = (value or "").strip().lower()
    if norm not in INCIDENT_STATUSES:
        raise ValueError(f"unknown status: {value!r} (expected one of {INCIDENT_STATUSES})")
    return norm
