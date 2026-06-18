"""Shapes for the Memory System: MemoryRecord + MemoryTier + MemoryType
+ importance scoring (PIPELINE_UNIFIED.md §7.5).

importance scoring rule:
  score  = 0.2 * recency_decay
         + 0.3 * min(1, session_appearance_count / 5)
         + 0.3 * (user_flagged_important ? 1 : 0)
         + 0.2 * (linked_outcome_value > 10M VND ? 1 : 0)
  capped at 1.0.

Promotion rule: score > 0.7 → L3 → L4; score < 0.3 after 90 days → forget.
"""
from __future__ import annotations

import math
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional
from uuid import UUID, uuid4


# Two ORTHOGONAL axes (ADR-0036 cleanup) — keep them distinct:
#   • MemoryTier = LIFECYCLE / storage stage (how long-lived, where stored):
#       L1_WORKING → L2_SHORT → L3_CONSOLIDATED → L4_LONG, driven by importance.
#       (L3 was historically "L3_EPISODIC", which overloaded the EPISODIC *type*;
#        renamed to L3_CONSOLIDATED so the tier axis is purely lifecycle.)
#   • MemoryType = COGNITIVE CATEGORY (what kind of content the memory holds).
#
# The classic cognitive taxonomy (working / semantic / procedural / episodic)
# is a VIEW over these axes, not a separate store (see classic_memory_class):
#       working    ≈ MemoryTier.L1_WORKING (a lifecycle stage, not a type)
#       episodic   ← MemoryType.EPISODIC, DECISION       (events / what happened)
#       semantic   ← MemoryType.SEMANTIC                 (learned domain facts)
#       procedural ← MemoryType.PROCEDURAL, OPERATIONAL  (how-to / recipes)
# Trust half-lives already encode the cognitive durability difference
# (semantic/procedural age slowly, episodic fast — see _HALFLIFE_DAYS).
class MemoryTier(str, Enum):
    """LIFECYCLE / storage stage (§7.1) — NOT a cognitive type. Importance
    promotes a memory up the chain; decay/forget removes it."""
    L1_WORKING      = "L1_WORKING"       # active turn (≈ working memory)
    L2_SHORT        = "L2_SHORT"         # recent session
    L3_CONSOLIDATED = "L3_CONSOLIDATED"  # distilled into the long-term store
    L4_LONG         = "L4_LONG"          # durable, validated


class MemoryType(str, Enum):
    """COGNITIVE CATEGORY (§7.2) of a memory's content."""
    EPISODIC    = "EPISODIC"
    SEMANTIC    = "SEMANTIC"
    PROCEDURAL  = "PROCEDURAL"
    OPERATIONAL = "OPERATIONAL"
    DECISION    = "DECISION"


# The classic 4-type taxonomy as a VIEW over MemoryType (working = the L1 tier).
CLASSIC_MEMORY_CLASS: dict[MemoryType, str] = {
    MemoryType.EPISODIC:    "episodic",
    MemoryType.DECISION:    "episodic",    # a recorded decision is an event
    MemoryType.SEMANTIC:    "semantic",
    MemoryType.PROCEDURAL:  "procedural",
    MemoryType.OPERATIONAL: "procedural",  # operational how-to
}


def classic_memory_class(memory_type: MemoryType) -> str:
    """Map a Kaori MemoryType onto the classic cognitive taxonomy
    (episodic / semantic / procedural). 'working' is the L1 tier, not a type —
    use the MemoryTier axis for that."""
    return CLASSIC_MEMORY_CLASS.get(memory_type, "semantic")


@dataclass
class MemoryRecord:
    """One memory entry. Mutable so importance / appearance count can
    be bumped on retrieve."""
    tenant_id:                  UUID
    memory_type:                MemoryType
    content:                    str
    record_id:                  UUID            = field(default_factory=uuid4)
    tier:                       MemoryTier      = MemoryTier.L1_WORKING
    occurred_at:                datetime        = field(default_factory=lambda: datetime.now(timezone.utc))
    session_id:                 Optional[str]   = None
    entity_id:                  Optional[UUID]  = None
    session_appearance_count:   int             = 0
    user_flagged_important:     bool            = False
    linked_outcome_value:       float           = 0.0
    metadata:                   dict[str, Any]  = field(default_factory=dict)
    # ADR-0030 trust layer — believability (distinct from importance/retention).
    confidence:                 float           = 0.70   # 0..1 self-scored at write
    trust_source:               Optional[str]   = None   # provenance: user/consolidate/rag/...
    last_verified_at:           Optional[datetime] = None  # NULL = never re-confirmed


def compute_importance(record: MemoryRecord, *, now: Optional[datetime] = None) -> float:
    """Importance score 0-1 per §7.5 formula."""
    if now is None:
        now = datetime.now(timezone.utc)
    days_old = max(0, (now - record.occurred_at).days)
    recency = max(0.0, 1 - days_old / 90.0)

    repeat = min(1.0, record.session_appearance_count / 5.0)

    flag   = 1.0 if record.user_flagged_important else 0.0
    outcome = 1.0 if record.linked_outcome_value > 10_000_000 else 0.0

    score = 0.2 * recency + 0.3 * repeat + 0.3 * flag + 0.2 * outcome
    return min(1.0, score)


# ─────────────────────────────────────────────────────────────────────────────
# ADR-0030 — TRUST (believability), distinct from importance (retention).
# trust = confidence × 0.5 ^ (age_days / half_life); age from last verification
# or, failing that, the memory's event time. Half-life is per memory_type:
# learned concepts (SEMANTIC/PROCEDURAL) age slowly; episodic noise ages fast.
# A "confident-but-unchecked" memory (was sure, never re-confirmed, now past one
# half-life) is surfaced as a HINT, not asserted fact. Ported from NNL-Harness.
# ─────────────────────────────────────────────────────────────────────────────
def _env_int(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, default))
    except (TypeError, ValueError):
        return default


# Per-type half-life (days) — env-configurable so the "forgetting" rate can be
# tuned per deployment. Learned concepts age slowly; episodic noise fast.
_HALFLIFE_DAYS: dict[MemoryType, int] = {
    MemoryType.SEMANTIC:    _env_int("KAORI_MEM_HALFLIFE_SEMANTIC", 365),
    MemoryType.PROCEDURAL:  _env_int("KAORI_MEM_HALFLIFE_PROCEDURAL", 365),
    MemoryType.DECISION:    _env_int("KAORI_MEM_HALFLIFE_DECISION", 60),
    MemoryType.OPERATIONAL: _env_int("KAORI_MEM_HALFLIFE_OPERATIONAL", 60),
    MemoryType.EPISODIC:    _env_int("KAORI_MEM_HALFLIFE_EPISODIC", 30),
}
_DEFAULT_HALFLIFE_DAYS = _env_int("KAORI_MEM_HALFLIFE_DEFAULT", 60)

TRUST_FRESH = 0.66
TRUST_AGING = 0.33


def halflife_days(memory_type: MemoryType) -> int:
    return _HALFLIFE_DAYS.get(memory_type, _DEFAULT_HALFLIFE_DAYS)


def compute_trust(record: MemoryRecord, *, now: Optional[datetime] = None) -> dict:
    """Believability of a memory right now. Returns score 0-1 + level + flags.

    `unchecked` marks the "confident but unchecked" failure mode — high
    confidence, never re-verified, already older than one half-life — so the
    prompt layer can render it as a hint instead of trusting it blindly.
    """
    if now is None:
        now = datetime.now(timezone.utc)
    base = record.last_verified_at or record.occurred_at
    age_days = max(0, (now - base).days)
    hl = halflife_days(record.memory_type)
    score = round(record.confidence * (0.5 ** (age_days / hl)), 3)
    level = ("fresh" if score >= TRUST_FRESH
             else "aging" if score >= TRUST_AGING else "stale")
    unchecked = (record.confidence >= 0.8
                 and record.last_verified_at is None
                 and age_days > hl)
    return {
        "age_days": age_days, "score": score, "level": level,
        "verified": record.last_verified_at is not None,
        "unchecked": unchecked, "halflife": hl,
    }


def trust_factor(record: MemoryRecord, *, now: Optional[datetime] = None) -> float:
    """Retrieval-ranking multiplier in [0.4, 1.0]: low-trust/stale memories sink
    but a strong lexical/semantic match is never fully suppressed (NNL band)."""
    return 0.4 + 0.6 * compute_trust(record, now=now)["score"]


# ─────────────────────────────────────────────────────────────────────────────
# ADR-0032 — MATURATION ("càng nhiều tháng chạy càng biết nhiều"): the growth
# counterpart to decay. Decay makes UNUSED memories fade; maturation makes
# USED, validated memories — and the tenant's competence as a whole — grow over
# time, like a practitioner gaining experience across the months/years.
# ─────────────────────────────────────────────────────────────────────────────
def _env_float(name: str, default: float) -> float:
    try:
        return float(os.environ.get(name, default))
    except (TypeError, ValueError):
        return default


# Learning rate for confidence reinforcement (asymptotic approach to ceiling).
_LEARN_RATE = _env_float("KAORI_MEM_LEARN_RATE", 0.15)
# Per-source confidence ceiling — never 1.0 (epistemic humility); a derived
# guess can never become as certain as a user-stated fact.
_CONF_CEILING: dict[str, float] = {
    "user": 0.98, "consolidate": 0.90, "rag": 0.90, "derived": 0.85,
}
_DEFAULT_CEILING = 0.85
# Saturation rate of the tenant experience curve.
_EXPERIENCE_K = _env_float("KAORI_MEM_EXPERIENCE_K", 0.15)

# Experience bands (descending threshold → human label, "tuổi nghề").
EXPERIENCE_BANDS = [
    (0.80, "chuyên gia"), (0.55, "dày dạn"), (0.30, "thành thạo"),
    (0.10, "tập sự"), (0.0, "mới"),
]


def reinforce_confidence(record: MemoryRecord) -> float:
    """Validated-use bump: confidence climbs toward its per-source ceiling
    asymptotically (fast early, plateauing — a learning curve). A fact confirmed
    many times ends up trusted more than one confirmed once. Mutates + returns."""
    ceiling = _CONF_CEILING.get(record.trust_source, _DEFAULT_CEILING)
    record.confidence = round(
        min(ceiling, record.confidence + _LEARN_RATE * (ceiling - record.confidence)), 4)
    return record.confidence


def experience_level(records: list[MemoryRecord], *, now: Optional[datetime] = None) -> dict:
    """Tenant/domain maturation from accumulated STILL-TRUSTED knowledge.

    experience = 1 − exp(−k × Σ trust_score) over the records — saturating in
    [0,1): early learning is rapid, mastery asymptotic. Knowledge that stops
    being used decays out of the mass, so the score reflects MAINTAINED
    competence. The longer the system runs (more validated memories accumulate +
    reinforce), the higher it climbs — "càng nhiều tháng càng biết nhiều".
    `tenure_days` is the literal age since the first memory.
    """
    if now is None:
        now = datetime.now(timezone.utc)
    if not records:
        return {"experience": 0.0, "knowledge_mass": 0.0, "band": "mới",
                "n": 0, "tenure_days": 0}
    mass = sum(compute_trust(r, now=now)["score"] for r in records)
    score = round(1 - math.exp(-_EXPERIENCE_K * mass), 4)
    tenure_days = max(0, (now - min(r.occurred_at for r in records)).days)
    band = next(name for thr, name in EXPERIENCE_BANDS if score >= thr)
    return {"experience": score, "knowledge_mass": round(mass, 3),
            "band": band, "n": len(records), "tenure_days": tenure_days}
