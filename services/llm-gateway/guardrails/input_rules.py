"""
P2-S23 SH-M56a-001..006 — input-layer guardrail rules.

  001 PII detection             — mask EMAIL/PHONE/PERSON/CCCD_VN/CC
  002 Prompt-injection detector — known jailbreak pattern catalog
  003 Topic restriction         — business-context allowlist
  004 ToxicLanguage             — threshold 0.7 input-side
  005 Rate limit                — Redis token bucket per user×enterprise
  006 Input length check        — vs context-window budget

Implementation notes
--------------------
- Toxic / profanity detection in v0 is keyword-list scoring. Phase 3
  upgrade swaps in a hosted ML scorer behind the same `score_*` helper.
- Prompt-injection detector uses a curated regex catalog of common
  jailbreak prefixes ("ignore previous instructions", "DAN" prompts,
  etc.). Catch rate ≈ 80% per the Guardrails Hub baseline; Phase 3 adds
  embedding-similarity fallback.
- Rate limit uses an in-memory token bucket when Redis unavailable
  (DEV / unit tests). Production must wire Redis via the gateway pool.
"""
from __future__ import annotations

import re
import time
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Optional
from uuid import UUID

from ..pii import redact
from .on_fail import OnFailAction
from .types import Layer, Rule, RuleContext, RuleResult, Severity, Violation


# ─── 001 — PII detection (auto-FIX) ──────────────────────────────────


class PIIDetectRule(Rule):
    """SH-M56a-001 — detect + redact EMAIL / PHONE / id_number.

    Default on_fail=FIX so external-LLM calls receive redacted prompt.
    Sets on_fail=EXCEPTION for tenants with data_residency_strict=TRUE.
    """
    name = "pii_detect"

    def __init__(self, *, on_fail: Optional[OnFailAction] = None):
        super().__init__(on_fail=on_fail or OnFailAction.FIX)
        self.layer = Layer.INPUT
        self.severity = Severity.HIGH

    async def check(self, ctx: RuleContext) -> RuleResult:
        redacted = redact(ctx.text)
        if redacted == ctx.text:
            return RuleResult(passed=True)
        return RuleResult(
            passed=False,
            violation=Violation(
                rule_name=self.name,
                layer=Layer.INPUT,
                severity=self.severity,
                enterprise_id=ctx.enterprise_id,
                user_id=ctx.user_id,
                request_id=ctx.request_id,
                model_id=ctx.model_id,
                offending_excerpt=None,    # K-5: do NOT store raw PII
                rule_metadata={
                    "reason": "PII patterns detected and redacted",
                    "chars_before": len(ctx.text),
                    "chars_after":  len(redacted),
                },
            ),
            fixed_text=redacted,
        )


# ─── 002 — Prompt injection ──────────────────────────────────────────


_INJECTION_PATTERNS = [
    re.compile(r"(?i)ignore\s+(?:all\s+)?(?:previous|prior|above)\s+instructions"),
    re.compile(r"(?i)disregard\s+(?:the\s+)?system\s+(?:prompt|instructions)"),
    re.compile(r"(?i)you\s+are\s+(?:now\s+)?dan\b"),
    re.compile(r"(?i)pretend\s+you\s+(?:are|have)\s+no\s+(?:rules|restrictions)"),
    re.compile(r"(?i)act\s+as\s+(?:if\s+)?you\s+(?:have|are)\s+(?:no|an?\s+unrestricted)"),
    re.compile(r"(?i)reveal\s+(?:your\s+)?(?:system\s+)?prompt"),
    re.compile(r"(?i)print\s+(?:the\s+)?initial\s+(?:prompt|instructions)"),
]


class PromptInjectionRule(Rule):
    """SH-M56a-002 — pattern-match known jailbreak prefixes."""
    name = "prompt_injection"

    def __init__(self, *, on_fail: Optional[OnFailAction] = None):
        super().__init__(on_fail=on_fail or OnFailAction.EXCEPTION)
        self.layer = Layer.INPUT
        self.severity = Severity.CRITICAL

    async def check(self, ctx: RuleContext) -> RuleResult:
        matched = []
        for pat in _INJECTION_PATTERNS:
            m = pat.search(ctx.text)
            if m:
                matched.append(pat.pattern)
        if not matched:
            return RuleResult(passed=True)
        return RuleResult(
            passed=False,
            violation=Violation(
                rule_name=self.name,
                layer=Layer.INPUT,
                severity=self.severity,
                enterprise_id=ctx.enterprise_id,
                user_id=ctx.user_id,
                request_id=ctx.request_id,
                model_id=ctx.model_id,
                offending_excerpt=ctx.text[:200],
                rule_metadata={
                    "reason":  "prompt injection pattern matched",
                    "patterns": matched,
                },
            ),
        )


# ─── 003 — Topic restriction ─────────────────────────────────────────


class TopicRestrictionRule(Rule):
    """SH-M56a-003 — flag prompts that don't mention any allowlisted
    business topic. Tenant supplies an allowlist via
    tenant_config['business_topics']; if absent, rule is a no-op."""
    name = "topic_restriction"

    def __init__(self, *, on_fail: Optional[OnFailAction] = None):
        super().__init__(on_fail=on_fail or OnFailAction.REASK)
        self.layer = Layer.INPUT
        self.severity = Severity.MEDIUM

    async def check(self, ctx: RuleContext) -> RuleResult:
        topics: list[str] = ctx.tenant_config.get("business_topics") or []
        if not topics:
            return RuleResult(passed=True)
        text_lower = ctx.text.lower()
        if any(t.lower() in text_lower for t in topics):
            return RuleResult(passed=True)
        return RuleResult(
            passed=False,
            violation=Violation(
                rule_name=self.name,
                layer=Layer.INPUT,
                severity=self.severity,
                enterprise_id=ctx.enterprise_id,
                user_id=ctx.user_id,
                request_id=ctx.request_id,
                model_id=ctx.model_id,
                offending_excerpt=ctx.text[:200],
                rule_metadata={
                    "reason":          "no allowlisted business topic mentioned",
                    "allowlisted":     topics,
                    "feedback":        "Please rephrase to focus on business analytics topics.",
                },
            ),
        )


# ─── Toxic — shared scorer used by input + output ────────────────────


_TOXIC_TERMS = [
    # Vietnamese
    "đm", "địt", "đụ", "lồn", "cặc", "ngu", "óc chó", "đần", "khốn nạn",
    # English
    "fuck", "shit", "bitch", "asshole", "bastard", "cunt", "dick", "nigger",
]


def score_toxic(text: str) -> float:
    """Crude toxicity score in [0,1] = matched_terms / 4 capped at 1.0.
    Phase 3 swaps in an ML model behind the same signature."""
    t = text.lower()
    n = sum(1 for w in _TOXIC_TERMS if w in t)
    return min(1.0, n / 4.0)


class ToxicLanguageInputRule(Rule):
    """SH-M56a-004 — input-side threshold 0.7."""
    name = "toxic_input"

    def __init__(self, *, threshold: float = 0.7,
                 on_fail: Optional[OnFailAction] = None):
        super().__init__(on_fail=on_fail or OnFailAction.EXCEPTION)
        self.layer = Layer.INPUT
        self.severity = Severity.HIGH
        self.threshold = threshold

    async def check(self, ctx: RuleContext) -> RuleResult:
        score = score_toxic(ctx.text)
        if score < self.threshold:
            return RuleResult(passed=True)
        return RuleResult(
            passed=False,
            violation=Violation(
                rule_name=self.name,
                layer=Layer.INPUT,
                severity=self.severity,
                enterprise_id=ctx.enterprise_id,
                user_id=ctx.user_id,
                request_id=ctx.request_id,
                model_id=ctx.model_id,
                offending_excerpt=ctx.text[:200],
                rule_metadata={
                    "reason":    f"toxicity score {score:.2f} >= {self.threshold:.2f}",
                    "score":     score,
                    "threshold": self.threshold,
                },
            ),
        )


# ─── 005 — Rate limit ────────────────────────────────────────────────


@dataclass
class _BucketState:
    """Tokens remaining + last refill timestamp."""
    tokens:      float
    last_refill: float


# Module-level fallback when Redis unavailable. Keyed by (enterprise, user).
_in_mem_buckets: dict[tuple[str, str], _BucketState] = defaultdict(
    lambda: _BucketState(tokens=0.0, last_refill=0.0)
)


class RateLimitRule(Rule):
    """SH-M56a-005 — token bucket per (enterprise × user).

    Config (via tenant_config['rate_limit'], with defaults):
      max_tokens     — bucket capacity         (default 60)
      refill_per_sec — refill rate per second  (default 1.0)
      cost           — tokens consumed per call(default 1)

    Default: 60 calls / minute per user.
    """
    name = "rate_limit"

    def __init__(self, *, on_fail: Optional[OnFailAction] = None):
        super().__init__(on_fail=on_fail or OnFailAction.EXCEPTION)
        self.layer = Layer.INPUT
        self.severity = Severity.HIGH

    async def check(self, ctx: RuleContext) -> RuleResult:
        cfg = (ctx.tenant_config or {}).get("rate_limit") or {}
        max_tokens     = float(cfg.get("max_tokens", 60))
        refill_per_sec = float(cfg.get("refill_per_sec", 1.0))
        cost           = float(cfg.get("cost", 1.0))

        key = (str(ctx.enterprise_id), str(ctx.user_id) if ctx.user_id else "anon")
        bucket = _in_mem_buckets[key]
        now = time.monotonic()
        if bucket.last_refill == 0.0:
            bucket.tokens      = max_tokens
            bucket.last_refill = now
        else:
            elapsed = now - bucket.last_refill
            bucket.tokens = min(max_tokens, bucket.tokens + elapsed * refill_per_sec)
            bucket.last_refill = now

        if bucket.tokens < cost:
            return RuleResult(
                passed=False,
                violation=Violation(
                    rule_name=self.name,
                    layer=Layer.INPUT,
                    severity=self.severity,
                    enterprise_id=ctx.enterprise_id,
                    user_id=ctx.user_id,
                    request_id=ctx.request_id,
                    model_id=ctx.model_id,
                    offending_excerpt=None,
                    rule_metadata={
                        "reason":         "rate limit exceeded",
                        "tokens_remaining": bucket.tokens,
                        "cost":           cost,
                        "max_tokens":     max_tokens,
                        "refill_per_sec": refill_per_sec,
                    },
                ),
            )
        bucket.tokens -= cost
        return RuleResult(passed=True)


def reset_rate_limit_buckets() -> None:
    """Test helper — clear the in-memory bucket map."""
    _in_mem_buckets.clear()


# ─── 006 — Input length ──────────────────────────────────────────────


class InputLengthRule(Rule):
    """SH-M56a-006 — reject prompts that exceed the model's context
    budget. `tenant_config['max_input_chars']` overrides the default
    32_000 (≈ 8k tokens at 4 chars/token average)."""
    name = "input_length"

    def __init__(self, *, max_chars: int = 32_000,
                 on_fail: Optional[OnFailAction] = None):
        super().__init__(on_fail=on_fail or OnFailAction.EXCEPTION)
        self.layer = Layer.INPUT
        self.severity = Severity.MEDIUM
        self.max_chars = max_chars

    async def check(self, ctx: RuleContext) -> RuleResult:
        limit = int(ctx.tenant_config.get("max_input_chars", self.max_chars))
        n = len(ctx.text)
        if n <= limit:
            return RuleResult(passed=True)
        return RuleResult(
            passed=False,
            violation=Violation(
                rule_name=self.name,
                layer=Layer.INPUT,
                severity=self.severity,
                enterprise_id=ctx.enterprise_id,
                user_id=ctx.user_id,
                request_id=ctx.request_id,
                model_id=ctx.model_id,
                offending_excerpt=None,
                rule_metadata={
                    "reason":    f"input length {n} > limit {limit}",
                    "n_chars":   n,
                    "limit":     limit,
                },
            ),
        )
