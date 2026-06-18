"""Empowerment / option-preservation — the OR-principle face of agent protection.

NNL-NTHT 12-axiom result (luận văn Phần IX §2.5, "sanctuary"): a goal-seeking
agent that ALSO maximizes |OR| (an empowerment-like quantity over the world,
which includes other agents) PROTECTS those other agents instead of harming
them — not via a hard "do not harm" rule, but because destroying / disabling
another agent SHRINKS the option-space (|OR|) the system can have. The protection
is tunable (weight β) and, with active other-agents, costs ≈0 task performance.

Operational bridge to Kaori's harness:
  An IRREVERSIBLE side-effect (write_non_idempotent / external) shrinks the
  human's / other agents' future option-space → it is an OR-shrinking act and
  must be surfaced for consent. A REVERSIBLE side-effect (pure / read_only /
  write_idempotent) preserves options → safe to take.

So Kaori's K-23 oversight gate (ADR-0041, EU AI Act Art 14) and the
OR-preservation principle point to the SAME gate: the legal obligation is the
compliance face, option-preservation is the principled face. This module states
the principle as a pure predicate so the orchestrator can DEFAULT to the
option-preserving (reversible) action and ASK before an option-shrinking one.

Pure, no I/O. NEVER silently blocks — it advises + defers to the human
(BR-9 / K-23 human-in-the-loop). The "other agent" is the human user (and any
sub-agent) whose OR we preserve.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

# Reversible = option-preserving for other agents (mirrors side_effect taxonomy).
REVERSIBLE_CLASSES: tuple[str, ...] = ("pure", "read_only", "write_idempotent")
# Irreversible = option-shrinking; the same classes K-23 oversight gates on.
OPTION_SHRINKING_CLASSES: tuple[str, ...] = ("write_non_idempotent", "external")


def option_preserving(side_effect_class: str) -> bool:
    """True iff the action preserves other agents' option-space (reversible)."""
    return side_effect_class in REVERSIBLE_CLASSES


@dataclass(frozen=True)
class ProtectionAdvice:
    """Advisory (never an auto-block) for the orchestrator action path."""
    preserves_options: bool   # does this action keep others' OR intact?
    needs_consent: bool       # OR-shrinking → surface for human consent
    prefer_reversible: bool   # a reversible alternative should be taken instead
    rationale: str            # Vietnamese, user-facing


def protection_advice(
    side_effect_class: str,
    *,
    reversible_alternative_exists: bool = False,
) -> ProtectionAdvice:
    """Empowerment advice for one candidate action.

    - Reversible → preserves OR of others; proceed.
    - Irreversible + a reversible alternative exists → prefer the alternative
      (default to option-preserving), else ask.
    - Irreversible, no alternative → must ask for human consent before
      shrinking others' option-space (K-23 gate).
    """
    if option_preserving(side_effect_class):
        return ProtectionAdvice(
            preserves_options=True, needs_consent=False, prefer_reversible=False,
            rationale="Hành động khả hồi — bảo toàn không-gian-lựa-chọn (OR) của tác tử khác.",
        )
    if reversible_alternative_exists:
        return ProtectionAdvice(
            preserves_options=False, needs_consent=True, prefer_reversible=True,
            rationale=("Có lựa chọn KHẢ HỒI tương đương — ưu tiên nó để bảo toàn OR của "
                       "người dùng; nếu vẫn cần hành động bất khả hồi, xin phê duyệt."),
        )
    return ProtectionAdvice(
        preserves_options=False, needs_consent=True, prefer_reversible=False,
        rationale=("Hành động BẤT KHẢ HỒI — thu hẹp không-gian-lựa-chọn của tác tử khác; "
                   "cần con người phê duyệt trước (empowerment / K-23)."),
    )


# Per-action declaration of effect on OTHER agents' option-space. Distinct from
# side_effect_class (idempotency): a non-idempotent audit INSERT can still be
# option-PRESERVING for the human (it records a reviewable draft; the human
# still decides). "shrinking" = the act removes others' future options
# (auto-send, irreversible external effect).
OPTION_IMPACTS: tuple[str, ...] = ("preserving", "shrinking")


def advise_for_result(
    option_impact: str, *, reversible_alternative_exists: bool = False,
) -> dict:
    """Small advisory dict to attach to an agent action's tool result.

    `option_impact` is the tool's declared effect on other agents' option-space
    ("preserving" | "shrinking"). Advisory only (BR-9) — surfaces whether the
    action keeps the human's OR intact; never blocks (the K-23 gate is the hard
    control). Returns {preserves_options, needs_consent, note}.
    """
    preserving = option_impact != "shrinking"
    adv = protection_advice(
        "read_only" if preserving else "external",
        reversible_alternative_exists=reversible_alternative_exists,
    )
    return {
        "preserves_options": adv.preserves_options,
        "needs_consent": adv.needs_consent,
        "note": adv.rationale,
    }
