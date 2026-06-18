"""Pure EU AI Act risk-tier -> Kaori control derivation (ADR-0041, K-22).

No I/O. Maps a risk_tier to the set of Kaori controls that MUST be active
for that tier. `prohibited` returns [] because the use is blocked entirely
(see workflow_builder prohibited-block); it never reaches runtime controls.
"""
from __future__ import annotations

RISK_TIERS: tuple[str, ...] = ("prohibited", "high", "limited", "minimal")

# Tier -> controls (invariant codes from ADR-0041 section 4).
_TIER_CONTROLS: dict[str, list[str]] = {
    "prohibited": [],
    "high":       ["K-23_HUMAN_OVERSIGHT", "K-25_MODEL_CARD",
                   "K-26_MONITORING", "K-6_AUDIT_LOG"],
    "limited":    ["K-24_TRANSPARENCY", "K-6_AUDIT_LOG"],
    "minimal":    [],
}


def validate_tier(tier: str) -> str:
    """Trim + lowercase; raise ValueError if not a known tier."""
    norm = (tier or "").strip().lower()
    if norm not in RISK_TIERS:
        raise ValueError(f"unknown risk_tier: {tier!r} (expected one of {RISK_TIERS})")
    return norm


def is_prohibited(tier: str) -> bool:
    return validate_tier(tier) == "prohibited"


def controls_for_tier(tier: str) -> list[str]:
    """Return a fresh list of control codes for the tier."""
    return list(_TIER_CONTROLS[validate_tier(tier)])


# ─── K-25 — Annex IV-lite model card completeness ────────────────────────
# The technical-documentation sections (EU AI Act Art 11 / Annex IV) a model
# card MUST cover, trimmed to what Kaori captures per (model, version). A
# `risk_tier = high` use requires this control (K-25_MODEL_CARD above); a card
# is "complete" when every required section is filled.
MODEL_CARD_REQUIRED_FIELDS: tuple[str, ...] = (
    "intended_purpose",       # Annex IV §1 — what the system is for
    "capabilities",           # Annex IV §1 — what it can do
    "limitations",            # Art 13 / Annex IV §3 — known limits
    "training_data_summary",  # Annex IV §2(d) — data provenance summary
    "evaluation_summary",     # Annex IV §2(g) — metrics / accuracy
    "risk_mitigations",       # Annex IV §2(e) — human oversight / guardrails
)


def model_card_completeness(card: dict) -> dict:
    """Which Annex IV-lite sections a model card is still missing. Pure, no I/O.

    A section counts as present when it is a non-empty, non-whitespace string.
    Returns ``{"complete": bool, "missing": list[str]}``; ``complete is True``
    means the card satisfies the K-25 control for its (model, version).
    """
    missing = [
        field for field in MODEL_CARD_REQUIRED_FIELDS
        if not str((card or {}).get(field) or "").strip()
    ]
    return {"complete": not missing, "missing": missing}
