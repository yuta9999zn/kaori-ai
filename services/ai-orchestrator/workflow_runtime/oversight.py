"""Pure EU AI Act K-23 human-oversight trigger predicate (ADR-0041 Layer 3).

No I/O. A high-risk workflow must get human sign-off before an impactful
(hard-to-reverse / external) side-effect. Reversible classes
(pure/read_only/write_idempotent) never trigger; non-high tiers never
trigger; an already-granted oversight does not re-trigger.

NNL-NTHT framing (12-axiom): this gate IS the OR-preservation / empowerment
gate. An impactful side-effect is exactly an act that SHRINKS the human's (and
other agents') option-space (|OR|); pausing it for consent preserves their OR.
So the EU-AI-Act obligation (the legal face) and the NNL-NTHT empowerment
principle (don't shrink others' OR — luận văn Phần IX §2.5 "sanctuary") point
to the SAME gate. See `reasoning/cdfl/empowerment.py` for the principle stated
as a pure predicate + the action-result advisory.
"""
from __future__ import annotations

from typing import Optional

# The side-effect classes that are hard to reverse / leave the system —
# mirrors side_effect.needs_idempotency_dedup (write_non_idempotent + external).
IMPACTFUL_CLASSES: tuple[str, ...] = ("write_non_idempotent", "external")


def oversight_applies(
    side_effect_class: str,
    risk_tier: Optional[str],
    *,
    already_granted: bool,
) -> bool:
    """True iff this node needs human oversight before executing."""
    return (
        side_effect_class in IMPACTFUL_CLASSES
        and risk_tier == "high"
        and not already_granted
    )
