"""
Knowing-doing gap mitigation per arXiv 2605.14038 (Univ. of Maryland).

Paper finding: LLMs (incl. Qwen 2.5 / 3.x) recognize they NEED a tool
but the action layer fails to invoke it (~30-54% mismatch rate). The
paper's hidden-state probe shows cognition + execution vectors are
nearly orthogonal at the decision token.

Kaori's mitigation in chat tool-calling path:
  1. Run a cheap Vietnamese+English keyword heuristic over the user
     message to score "is this question likely to need a tool?".
  2. If score >= HIGH_CONFIDENCE → force tool_choice="required" so the
     LLM MUST emit a tool call (closes the knowing-doing gap at the
     protocol level, not via inference).
  3. If score in (LOW, HIGH) → tool_choice="auto" (default).
  4. Always log the decision via structlog (auditable).

This is a STRUCTURAL fix — we don't try to fix the LLM's internal gap;
we just remove the LLM's choice on questions where evidence overwhelm-
ingly says "tool needed". Honest trade-off: false-positive forcing on
chat-like questions ("xin chào") gets caught by HIGH_CONFIDENCE
threshold tuned to be conservative.

Why not LLM-based necessity pre-pass?
  - Doubles latency + LLM cost for every chat turn.
  - Paper's hidden-state probe shows cognition IS in the model, but
    even when model is "very sure", action layer drops it (Fig. 7).
    Asking the model what it thinks is the same mechanism, same gap.
  - Heuristic is transparent — anh can read the rule, not trust an
    opaque vector.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any, Mapping, Optional, Sequence

import structlog

log = structlog.get_logger()


# Confidence thresholds. Tuned conservatively per paper's 31-54% gap:
# we'd rather false-negative (auto mode) on borderline than false-
# positive (required mode) on conversational chitchat.
HIGH_CONFIDENCE = 0.7
LOW_CONFIDENCE  = 0.3


# Vietnamese + English markers indicating a data / lookup / computation
# question. Each marker carries a weight. Score = sum / cap-at-1.0.
# Keywords are LOWERCASE-matched against the lowercased user message.

_VI_TOOL_INDICATORS: dict[str, float] = {
    # data lookup
    "danh sách":       0.6,
    "liệt kê":         0.5,
    "tra cứu":         0.6,
    "tìm kiếm":        0.5,
    "hiển thị":        0.4,
    "xem":             0.2,
    "lấy":             0.3,
    "show":            0.4,
    # quantitative
    "bao nhiêu":       0.7,
    "có mấy":          0.7,
    "tổng":            0.5,
    "trung bình":      0.6,
    "phần trăm":       0.5,
    "tính":            0.5,
    "đo":              0.4,
    "thống kê":        0.6,
    "doanh thu":       0.5,
    "chi phí":         0.5,
    "lợi nhuận":       0.5,
    # specific lookups
    "khách":           0.3,
    "khách hàng":      0.4,
    "đơn hàng":        0.4,
    "workflow":        0.3,
    "quyết định":      0.4,
    "decision":        0.4,
    "audit":           0.4,
    "lịch sử":         0.4,
    "history":         0.4,
    # temporal scoping that implies DB query
    "tháng này":       0.4,
    "tuần này":        0.4,
    "hôm nay":         0.3,
    "quý":             0.4,
    # imperative verbs aimed at the system
    "cho tôi xem":     0.7,
    "cho tôi danh":    0.7,
    "show me":         0.7,
    "list ":           0.5,
    "get ":            0.4,
    "find ":           0.4,
    "fetch":           0.5,
    "query":           0.5,
}


# Conversational markers — reduce score (negative weight).
_VI_CHITCHAT_INDICATORS: dict[str, float] = {
    "xin chào":        -0.6,
    "chào":            -0.3,
    "cảm ơn":          -0.5,
    "hello":           -0.5,
    "hi ":             -0.4,
    "bạn là ai":       -0.7,
    "giới thiệu":      -0.5,
    "ý kiến":          -0.4,
    "nghĩ":            -0.3,    # "bạn nghĩ sao..."
    "what is":         -0.2,    # ambiguous — explanatory vs lookup
    "explain":         -0.3,
}


@dataclass(frozen=True)
class NecessityAssessment:
    """Output of needs_tool_heuristic()."""
    needs_tool:   bool
    confidence:   float
    fired_keywords: tuple[str, ...]
    suggested_tool_choice: str  # "required" | "auto" | "none"
    reason:       str


def needs_tool_heuristic(
    user_message: str,
    *,
    scope: str = "enterprise",
) -> NecessityAssessment:
    """Cheap pre-flight check on whether the user message needs a tool.

    `scope` is currently informational — both 'enterprise' and 'platform'
    chat surfaces use the same keyword set. Per-scope tuning can land
    in a follow-up once we measure baseline gap rate.
    """
    text = user_message.lower().strip()
    if not text:
        return NecessityAssessment(
            needs_tool=False, confidence=0.0,
            fired_keywords=(), suggested_tool_choice="auto",
            reason="empty message",
        )

    score = 0.0
    fired: list[str] = []
    for marker, weight in _VI_TOOL_INDICATORS.items():
        if marker in text:
            score += weight
            fired.append(marker)
    for marker, weight in _VI_CHITCHAT_INDICATORS.items():
        if marker in text:
            score += weight
            fired.append(f"chitchat:{marker}")

    score = max(0.0, min(1.0, score))

    if score >= HIGH_CONFIDENCE:
        choice = "required"
        needs = True
        reason = f"high tool-necessity score ({score:.2f}); forcing tool_choice=required"
    elif score >= LOW_CONFIDENCE:
        choice = "auto"
        needs = True
        reason = f"medium tool-necessity score ({score:.2f}); tool_choice=auto"
    else:
        choice = "auto"
        needs = False
        reason = f"low tool-necessity score ({score:.2f}); chat-like; tool_choice=auto"

    return NecessityAssessment(
        needs_tool=needs,
        confidence=score,
        fired_keywords=tuple(fired),
        suggested_tool_choice=choice,
        reason=reason,
    )


def log_necessity_decision(
    *,
    user_message: str,
    assessment: NecessityAssessment,
    tenant_id: Optional[str] = None,
    final_choice_used: Optional[str] = None,
) -> None:
    """Emit a structured log line per chat turn so we can measure how
    often the heuristic fires + whether the override changes behaviour."""
    log.info(
        "chat.tool_necessity",
        message_preview=user_message[:120],
        needs_tool=assessment.needs_tool,
        confidence=round(assessment.confidence, 3),
        suggested_tool_choice=assessment.suggested_tool_choice,
        final_choice_used=final_choice_used or assessment.suggested_tool_choice,
        fired_keywords=list(assessment.fired_keywords),
        reason=assessment.reason,
        tenant_id=tenant_id,
    )


# ═════════════════════════════════════════════════════════════════════
# Tool-call loop guardrail — DPEPO-style depth/width penalty pattern
# ─────────────────────────────────────────────────────────────────────
# ADR-0023 Alt 5: borrow the depth/width repetition-penalty pattern from
# DPEPO (LePanda026/Code-for-DPEPO, 2026) as a runtime anti-loop guard
# on tool-call history. Orthogonal to the knowing-doing-gap heuristic
# above — that one fires on hop 0 to encourage tool use; this one fires
# inside the hop loop to discourage runaway repetition.
#
# Mapping DPEPO → Kaori chat:
#   depth (DPEPO: revisit same action in same env)
#     ↔ same tool_name called consecutively across hops in this session
#   width (DPEPO: duplicate actions across parallel envs)
#     ↔ same (tool_name, args_fingerprint) anywhere in this session
#
# Penalty formula (geometric decay, same as DPEPO):
#   depth_penalty   = DEPTH_ALPHA  ** depth_count
#   width_penalty   = WIDTH_OMEGA  ** width_count
#   combined        = depth_penalty * width_penalty
#   should_abort    = combined < LOOP_ABORT_THRESHOLD
#
# Tuning rationale (tighter than DPEPO's 0.8/0.95 because Kaori chat
# loops are short — MAX_HOPS=3, MAX_TOOL_CALLS_PER_HOP=4 — so we need
# the penalty to bite fast):
#   DEPTH_ALPHA=0.7         → 3 consecutive revisits = 0.343 (trips abort)
#   WIDTH_OMEGA=0.8         → 4 cross-hop duplicates = 0.410 (warn band)
#   LOOP_ABORT_THRESHOLD=0.3 → leaves a guardrail margin
# ═════════════════════════════════════════════════════════════════════

DEPTH_ALPHA: float = 0.7
WIDTH_OMEGA: float = 0.8
LOOP_ABORT_THRESHOLD: float = 0.3


def args_fingerprint(args: Mapping[str, Any]) -> str:
    """Stable 16-char hex digest of tool args.

    Used to spot identical calls. `default=str` lets us hash args
    containing dates / UUIDs / Decimals without crashing — the
    string repr of those types is deterministic for fingerprinting
    purposes (we never decode the digest back, only compare).
    """
    canonical = json.dumps(
        dict(args), sort_keys=True, separators=(",", ":"), default=str,
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:16]


@dataclass(frozen=True)
class ToolCall:
    """A past tool-call entry in the chat session's history."""
    tool_name: str
    args_fingerprint: str
    hop: int


@dataclass(frozen=True)
class LoopPenaltyAssessment:
    """Output of assess_tool_call_loop()."""
    depth_count:        int
    width_count:        int
    depth_penalty:      float
    width_penalty:      float
    combined_penalty:   float
    should_abort:       bool
    reason:             str


def _count_consecutive_revisits(
    tool_name: str, history: Sequence[ToolCall],
) -> int:
    """Count immediately-prior same-tool entries (depth dimension)."""
    count = 0
    for entry in reversed(history):
        if entry.tool_name == tool_name:
            count += 1
        else:
            break
    return count


def _count_args_duplicates(
    tool_name: str, fingerprint: str, history: Sequence[ToolCall],
) -> int:
    """Count any-position entries with same tool + same args (width dimension)."""
    return sum(
        1 for entry in history
        if entry.tool_name == tool_name and entry.args_fingerprint == fingerprint
    )


def assess_tool_call_loop(
    *,
    tool_name: str,
    args: Mapping[str, Any],
    history: Sequence[ToolCall],
    depth_alpha: float = DEPTH_ALPHA,
    width_omega: float = WIDTH_OMEGA,
    abort_threshold: float = LOOP_ABORT_THRESHOLD,
) -> LoopPenaltyAssessment:
    """Score a proposed tool call against this session's history.

    Returns a LoopPenaltyAssessment whose `should_abort=True` means the
    caller must NOT dispatch the tool — surface a guardrail error back
    to the LLM instead so it can change its strategy.

    Pure function; no I/O, no logging.
    """
    fingerprint = args_fingerprint(args)
    depth = _count_consecutive_revisits(tool_name, history)
    width = _count_args_duplicates(tool_name, fingerprint, history)

    depth_penalty = depth_alpha ** depth
    width_penalty = width_omega ** width
    combined = depth_penalty * width_penalty
    should_abort = combined < abort_threshold

    if should_abort:
        reason = (
            f"loop guardrail tripped: tool='{tool_name}' "
            f"depth={depth} (α={depth_alpha}, p={depth_penalty:.3f}) · "
            f"width={width} (ω={width_omega}, p={width_penalty:.3f}) · "
            f"combined={combined:.3f} < {abort_threshold}"
        )
    else:
        reason = (
            f"tool call OK: depth={depth} width={width} "
            f"combined={combined:.3f}"
        )

    return LoopPenaltyAssessment(
        depth_count=depth,
        width_count=width,
        depth_penalty=depth_penalty,
        width_penalty=width_penalty,
        combined_penalty=combined,
        should_abort=should_abort,
        reason=reason,
    )


def log_loop_guardrail(
    *,
    tool_name: str,
    assessment: LoopPenaltyAssessment,
    tenant_id: Optional[str] = None,
    hop: Optional[int] = None,
) -> None:
    """Structured log line each time the guardrail fires (abort or warn).

    Only emit when `should_abort=True` OR penalty < 0.6 (warn band). On
    fully-clean calls (combined ≥ 0.6) we skip to keep log volume sane.
    """
    if not assessment.should_abort and assessment.combined_penalty >= 0.6:
        return
    log.warning(
        "chat.tool_call_loop_guardrail",
        tool_name=tool_name,
        hop=hop,
        depth_count=assessment.depth_count,
        width_count=assessment.width_count,
        depth_penalty=round(assessment.depth_penalty, 3),
        width_penalty=round(assessment.width_penalty, 3),
        combined_penalty=round(assessment.combined_penalty, 3),
        should_abort=assessment.should_abort,
        reason=assessment.reason,
        tenant_id=tenant_id,
    )
