"""ADR-0037 Tier-3 — the 7-state workflow-document status machine (pure).

A document attached to a workflow step moves through:

    cho_nop ─upload→ da_nop ─review→ dang_xem_xet ─┬─approve→ da_duyet
                       │                            ├─reject→  tu_choi
                       │                            └─more→    yeu_cau_bo_sung
                       ├─approve→ da_duyet  (review skipped)
                       ├─reject→  tu_choi
                       └─more→    yeu_cau_bo_sung
    tu_choi / yeu_cau_bo_sung ─re-upload(new version)→ da_nop
    (any non-terminal) ─system→ het_han  (past valid_until)

Kept dependency-free so the router AND any executor share one source of truth
for "is this transition allowed", and so it is trivially unit-testable. No DB,
no I/O — the caller persists the result.
"""
from __future__ import annotations

# Canonical states (match mig 120 CHECK).
CHO_NOP         = "cho_nop"          # 🔘 required, not yet uploaded
DA_NOP          = "da_nop"           # 📄 uploaded, awaiting review
DANG_XEM_XET    = "dang_xem_xet"     # 👀 under review
DA_DUYET        = "da_duyet"         # ✅ approved
TU_CHOI         = "tu_choi"          # ❌ rejected (reason required)
YEU_CAU_BO_SUNG = "yeu_cau_bo_sung"  # 🔄 needs more info (note required)
HET_HAN         = "het_han"          # ⚠️ expired

ALL_STATES = frozenset({
    CHO_NOP, DA_NOP, DANG_XEM_XET, DA_DUYET, TU_CHOI, YEU_CAU_BO_SUNG, HET_HAN,
})

# Business-Vietnamese labels (UI never shows the raw key).
STATUS_LABEL = {
    CHO_NOP: "Chờ nộp", DA_NOP: "Đã nộp", DANG_XEM_XET: "Đang xem xét",
    DA_DUYET: "Đã duyệt", TU_CHOI: "Từ chối", YEU_CAU_BO_SUNG: "Yêu cầu bổ sung",
    HET_HAN: "Hết hạn",
}

# Allowed manual transitions (from → {to}). het_han is system-set (expiry sweep),
# so it is reachable from any non-terminal state but never a manual target here.
_ALLOWED: dict[str, frozenset[str]] = {
    CHO_NOP:         frozenset({DA_NOP}),
    DA_NOP:          frozenset({DANG_XEM_XET, DA_DUYET, TU_CHOI, YEU_CAU_BO_SUNG}),
    DANG_XEM_XET:    frozenset({DA_DUYET, TU_CHOI, YEU_CAU_BO_SUNG}),
    YEU_CAU_BO_SUNG: frozenset({DA_NOP}),   # re-upload a new version
    TU_CHOI:         frozenset({DA_NOP}),   # re-upload a new version
    DA_DUYET:        frozenset(),           # terminal (only system expiry)
    HET_HAN:         frozenset({DA_NOP}),   # re-upload a fresh, in-date document
}

# Transitions that MUST carry a reviewer note (the "why").
_REQUIRES_NOTE = frozenset({TU_CHOI, YEU_CAU_BO_SUNG})

# Transitions that record a review decision (reviewed_by / reviewed_at set).
_REVIEW_DECISIONS = frozenset({DA_DUYET, TU_CHOI, YEU_CAU_BO_SUNG})


def can_transition(from_status: str, to_status: str) -> bool:
    """True if the manual status change from→to is permitted."""
    return to_status in _ALLOWED.get(from_status, frozenset())


def requires_note(to_status: str) -> bool:
    """Reject / request-more must carry a reason."""
    return to_status in _REQUIRES_NOTE


def is_review_decision(to_status: str) -> bool:
    """Whether reaching this state stamps reviewed_by / reviewed_at."""
    return to_status in _REVIEW_DECISIONS


def is_terminal(status: str) -> bool:
    """da_duyet (approved) is the only success terminal; het_han is an
    expiry sink. Both can still re-enter via a new version upload."""
    return status in (DA_DUYET, HET_HAN)


def allowed_targets(from_status: str) -> list[str]:
    """Manual targets reachable from a state — for the UI to render buttons."""
    return sorted(_ALLOWED.get(from_status, frozenset()))
