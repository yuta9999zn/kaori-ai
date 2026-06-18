"""
K-5 PII redaction for prompts before external LLM calls.

Internal (on-prem Ollama) calls run with the original prompt — data
never leaves the server. External providers (Anthropic, OpenAI) only
ever see the redacted form.

Patterns ported verbatim from the original llm_router.py so behavior
during the cutover is unchanged. They cover the high-frequency
Vietnamese-context PII the platform handles: email addresses, VN
phone numbers, and 9–12 digit identifier numbers (CCCD/CMND).

Conservative by design: better to over-redact a numeric column than
leak a citizen-id to a third-party API.
"""
from __future__ import annotations

import re
from typing import Final

_PII_PATTERNS: Final = [
    (re.compile(r"\b[\w.+-]+@[\w.-]+\.[a-zA-Z]{2,}\b"), "[email]"),
    (re.compile(r"\b(\+84|84|0)[3-9]\d{8}\b"),         "[phone]"),
    (re.compile(r"\b\d{9,12}\b"),                       "[id_number]"),
]


def redact(text: str) -> str:
    """Return a copy of ``text`` with PII tokens replaced. Idempotent."""
    for pattern, replacement in _PII_PATTERNS:
        text = pattern.sub(replacement, text)
    return text
