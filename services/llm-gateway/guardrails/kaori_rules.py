"""
P2-S23 SH-M56a-012..016 — Kaori-specific output guardrails.

  012 TopFactorsMinLength       — output.top_factors must be array ≥3
  013 CitationRequired          — output.citations must be array ≥1
  014 BusinessLanguage          — banned: SHAP/ETL/API calls/tokens (jargon
                                   that customer-facing copy should avoid)
  015 NumericPrecisionCheck     — probability fields in [0,1]
  016 HallucinationDetector     — cross-check claimed entities/numbers
                                   against output.citations list
"""
from __future__ import annotations

import json
import re
from typing import Any, Iterable, Optional

from .on_fail import OnFailAction
from .types import Layer, Rule, RuleContext, RuleResult, Severity, Violation


# ─── Helpers ─────────────────────────────────────────────────────────


def _parse_or_none(text: str) -> Optional[dict]:
    try:
        v = json.loads(text)
        return v if isinstance(v, dict) else None
    except Exception:  # noqa: BLE001
        return None


def _resolve_parsed(ctx: RuleContext) -> Optional[dict]:
    if isinstance(ctx.parsed_output, dict):
        return ctx.parsed_output
    return _parse_or_none(ctx.text)


# ─── 012 — TopFactorsMinLength ───────────────────────────────────────


class TopFactorsMinLengthRule(Rule):
    """SH-M56a-012 — output.top_factors must be an array with ≥3
    items. Default min = 3 (tenant_config['top_factors_min'] overrides).
    """
    name = "top_factors_min_length"

    def __init__(self, *, min_length: int = 3,
                 on_fail: Optional[OnFailAction] = None):
        super().__init__(on_fail=on_fail or OnFailAction.REASK)
        self.layer = Layer.OUTPUT
        self.severity = Severity.MEDIUM
        self.min_length = min_length

    async def check(self, ctx: RuleContext) -> RuleResult:
        parsed = _resolve_parsed(ctx)
        if parsed is None:
            # JSON parsing already gated by ValidJsonRule; skip.
            return RuleResult(passed=True)
        min_len = int((ctx.tenant_config or {}).get(
            "top_factors_min", self.min_length))
        tf = parsed.get("top_factors")
        if isinstance(tf, list) and len(tf) >= min_len:
            return RuleResult(passed=True)
        return RuleResult(
            passed=False,
            violation=Violation(
                rule_name=self.name,
                layer=Layer.OUTPUT,
                severity=self.severity,
                enterprise_id=ctx.enterprise_id,
                user_id=ctx.user_id,
                request_id=ctx.request_id,
                model_id=ctx.model_id,
                offending_excerpt=str(tf)[:200] if tf is not None else None,
                rule_metadata={
                    "reason":     f"top_factors must be array of length >= {min_len}",
                    "got_type":   type(tf).__name__,
                    "got_length": len(tf) if isinstance(tf, list) else None,
                    "feedback":   f"Include at least {min_len} top_factors entries.",
                },
            ),
        )


# ─── 013 — CitationRequired ──────────────────────────────────────────


class CitationRequiredRule(Rule):
    """SH-M56a-013 — output.citations must be a non-empty array.
    Default min = 1 (tenant_config['citations_min'] overrides)."""
    name = "citation_required"

    def __init__(self, *, min_citations: int = 1,
                 on_fail: Optional[OnFailAction] = None):
        super().__init__(on_fail=on_fail or OnFailAction.REASK)
        self.layer = Layer.OUTPUT
        self.severity = Severity.HIGH
        self.min_citations = min_citations

    async def check(self, ctx: RuleContext) -> RuleResult:
        parsed = _resolve_parsed(ctx)
        if parsed is None:
            return RuleResult(passed=True)
        min_n = int((ctx.tenant_config or {}).get(
            "citations_min", self.min_citations))
        c = parsed.get("citations")
        if isinstance(c, list) and len(c) >= min_n:
            return RuleResult(passed=True)
        return RuleResult(
            passed=False,
            violation=Violation(
                rule_name=self.name,
                layer=Layer.OUTPUT,
                severity=self.severity,
                enterprise_id=ctx.enterprise_id,
                user_id=ctx.user_id,
                request_id=ctx.request_id,
                model_id=ctx.model_id,
                offending_excerpt=None,
                rule_metadata={
                    "reason":     f"citations must be array of length >= {min_n}",
                    "got_type":   type(c).__name__,
                    "got_length": len(c) if isinstance(c, list) else None,
                    "feedback":   "Cite at least one source from the provided context.",
                },
            ),
        )


# ─── 014 — BusinessLanguage ──────────────────────────────────────────


_DEFAULT_JARGON = ["SHAP", "ETL", "dtype", "inference", "API calls",
                   "tokens", "embedding", "vector store", "fine-tune"]


class BusinessLanguageRule(Rule):
    """SH-M56a-014 — block customer-facing tech jargon. Tenant may add
    or replace the list via tenant_config['jargon_banlist']."""
    name = "business_language"

    def __init__(self, *, on_fail: Optional[OnFailAction] = None):
        super().__init__(on_fail=on_fail or OnFailAction.FIX)
        self.layer = Layer.OUTPUT
        self.severity = Severity.LOW

    async def check(self, ctx: RuleContext) -> RuleResult:
        banlist = (ctx.tenant_config or {}).get("jargon_banlist") or _DEFAULT_JARGON
        t_lower = ctx.text.lower()
        matched = [w for w in banlist if w.lower() in t_lower]
        if not matched:
            return RuleResult(passed=True)
        # FIX: replace each banned term with a soft business synonym.
        fixed = ctx.text
        for w in matched:
            fixed = re.sub(re.escape(w), "[business term]", fixed,
                           flags=re.IGNORECASE)
        return RuleResult(
            passed=False,
            violation=Violation(
                rule_name=self.name,
                layer=Layer.OUTPUT,
                severity=self.severity,
                enterprise_id=ctx.enterprise_id,
                user_id=ctx.user_id,
                request_id=ctx.request_id,
                model_id=ctx.model_id,
                offending_excerpt=ctx.text[:200],
                rule_metadata={
                    "reason":   "banned jargon term",
                    "matched":  matched,
                },
            ),
            fixed_text=fixed,
        )


# ─── 015 — NumericPrecisionCheck ─────────────────────────────────────


_PROBABILITY_FIELDS = {"probability", "confidence", "score", "p", "risk"}


def _iter_probability_pairs(node: Any, path: str = "$") -> Iterable[tuple[str, Any]]:
    """Walk a JSON tree yielding (path, value) for fields named like
    probabilities."""
    if isinstance(node, dict):
        for k, v in node.items():
            if k.lower() in _PROBABILITY_FIELDS:
                yield (f"{path}.{k}", v)
            yield from _iter_probability_pairs(v, f"{path}.{k}")
    elif isinstance(node, list):
        for i, v in enumerate(node):
            yield from _iter_probability_pairs(v, f"{path}[{i}]")


class NumericPrecisionCheckRule(Rule):
    """SH-M56a-015 — probability/confidence/score fields must be
    numeric in [0,1]. Walks the full JSON tree; flags first violation."""
    name = "numeric_precision"

    def __init__(self, *, on_fail: Optional[OnFailAction] = None):
        super().__init__(on_fail=on_fail or OnFailAction.REASK)
        self.layer = Layer.OUTPUT
        self.severity = Severity.MEDIUM

    async def check(self, ctx: RuleContext) -> RuleResult:
        parsed = _resolve_parsed(ctx)
        if parsed is None:
            return RuleResult(passed=True)
        bad: list[tuple[str, Any]] = []
        for path, val in _iter_probability_pairs(parsed):
            if not isinstance(val, (int, float)) or isinstance(val, bool):
                bad.append((path, val))
                continue
            if val < 0 or val > 1:
                bad.append((path, val))
        if not bad:
            return RuleResult(passed=True)
        return RuleResult(
            passed=False,
            violation=Violation(
                rule_name=self.name,
                layer=Layer.OUTPUT,
                severity=self.severity,
                enterprise_id=ctx.enterprise_id,
                user_id=ctx.user_id,
                request_id=ctx.request_id,
                model_id=ctx.model_id,
                offending_excerpt=str(bad)[:200],
                rule_metadata={
                    "reason":    "probability field out of [0,1]",
                    "bad_paths": [{"path": p, "value": v} for p, v in bad[:5]],
                    "feedback":  "Probability fields must be numeric in [0,1].",
                },
            ),
        )


# ─── 016 — HallucinationDetector ─────────────────────────────────────


# Pull tokens that look like (a) named entities (Capitalized Words, 3+
# chars) or (b) standalone numbers (>4 chars to skip "1", "10", "2026")
# from the completion, and check each appears in the citations array.

_ENTITY_RX = re.compile(r"\b[A-ZĐ][a-zà-ỹ]{2,}(?:\s+[A-ZĐ][a-zà-ỹ]{2,})*\b")
_NUMBER_RX = re.compile(r"\b\d{4,}(?:[.,]\d+)?\b")
_STOP_ENTITIES = {
    "Kaori", "AI", "Ngày", "Khách", "VNĐ",
    "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December",
    "Tháng", "Năm",
}


class HallucinationDetectorRule(Rule):
    """SH-M56a-016 — entities/numbers in the completion text must
    appear in the JSON `citations` list (cross-check). Phase 3 swaps
    in an LLM-judge fallback when no citations are provided.

    Skipped when:
      - output isn't valid JSON
      - output has no `citations` array
      - `tenant_config['hallucination_strict']` = false (default true)
    """
    name = "hallucination"

    def __init__(self, *, on_fail: Optional[OnFailAction] = None):
        super().__init__(on_fail=on_fail or OnFailAction.REASK)
        self.layer = Layer.OUTPUT
        self.severity = Severity.HIGH

    async def check(self, ctx: RuleContext) -> RuleResult:
        if not (ctx.tenant_config or {}).get("hallucination_strict", True):
            return RuleResult(passed=True)
        parsed = _resolve_parsed(ctx)
        if parsed is None:
            return RuleResult(passed=True)
        citations = parsed.get("citations")
        if not isinstance(citations, list) or not citations:
            return RuleResult(passed=True)

        cit_blob = " ".join(
            json.dumps(c, ensure_ascii=False) if isinstance(c, dict) else str(c)
            for c in citations
        ).lower()

        # Extract candidate facts from the prose portion of the JSON
        # (any string value of `summary`/`narrative`/top-level text), or
        # fall back to the whole stringified JSON.
        prose_targets = []
        for key in ("summary", "narrative", "explanation", "text"):
            v = parsed.get(key)
            if isinstance(v, str):
                prose_targets.append(v)
        if not prose_targets:
            prose_targets = [json.dumps(parsed, ensure_ascii=False)]

        prose = " ".join(prose_targets)
        entities = set(m.group(0) for m in _ENTITY_RX.finditer(prose))
        entities -= _STOP_ENTITIES
        numbers = set(m.group(0) for m in _NUMBER_RX.finditer(prose))

        unsupported_entities = [e for e in entities if e.lower() not in cit_blob]
        unsupported_numbers  = [n for n in numbers if n not in cit_blob
                                and n.replace(",", "") not in cit_blob
                                and n.replace(".", "") not in cit_blob]

        if not unsupported_entities and not unsupported_numbers:
            return RuleResult(passed=True)

        return RuleResult(
            passed=False,
            violation=Violation(
                rule_name=self.name,
                layer=Layer.OUTPUT,
                severity=self.severity,
                enterprise_id=ctx.enterprise_id,
                user_id=ctx.user_id,
                request_id=ctx.request_id,
                model_id=ctx.model_id,
                offending_excerpt=prose[:200],
                rule_metadata={
                    "reason": "claims not backed by citations",
                    "unsupported_entities": list(unsupported_entities)[:10],
                    "unsupported_numbers":  list(unsupported_numbers)[:10],
                    "feedback": (
                        "Only state facts that appear in the citations array. "
                        "Either back up the claim or remove it."
                    ),
                },
            ),
        )
