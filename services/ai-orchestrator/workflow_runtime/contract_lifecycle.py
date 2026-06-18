"""ADR-0037 Phase 3 — contract lifecycle + multi-party signing (pure).

Status machine:
    nhap ─send→ cho_ky ─┬─(đủ chữ ký)→ hieu_luc ─┬─expiry→ het_han
                        └─(1 bên từ chối)→ tu_choi  └─terminate→ thanh_ly

Signing reuses Phase-2 chain semantics: sign_order gives sequential vs parallel
(same order = parallel; ascending = a party can't sign before its predecessors),
sign_mode all/threshold decides completion. Pure — the router persists.
"""
from __future__ import annotations

from typing import Optional

NHAP = "nhap"           # draft
CHO_KY = "cho_ky"       # awaiting signatures
HIEU_LUC = "hieu_luc"   # in effect
HET_HAN = "het_han"     # expired
THANH_LY = "thanh_ly"   # terminated
TU_CHOI = "tu_choi"     # a party refused

STATUS_LABEL = {
    NHAP: "Nháp", CHO_KY: "Chờ ký", HIEU_LUC: "Hiệu lực",
    HET_HAN: "Hết hạn", THANH_LY: "Thanh lý", TU_CHOI: "Từ chối",
}

_ALLOWED = {
    NHAP:     {CHO_KY},
    CHO_KY:   {HIEU_LUC, TU_CHOI},
    HIEU_LUC: {HET_HAN, THANH_LY},
    HET_HAN:  set(),
    THANH_LY: set(),
    TU_CHOI:  {NHAP},        # renegotiate → back to draft
}


def can_transition(from_status: str, to_status: str) -> bool:
    return to_status in _ALLOWED.get(from_status, set())


def signing_complete(parties: list[dict], sign_mode: str,
                     required_signatures: Optional[int] = None) -> bool:
    """Have enough parties signed? `all` = every party; `threshold` = at least
    required_signatures (defaults to all when unset)."""
    signed = sum(1 for p in parties if p.get("has_signed"))
    total = len(parties)
    if total == 0:
        return False
    if sign_mode == "threshold" and required_signatures:
        return signed >= required_signatures
    return signed >= total


def next_signers(parties: list[dict]) -> list[dict]:
    """Parties eligible to sign NOW — the unsigned ones at the lowest pending
    sign_order (sequential gate). Parties sharing that order sign in parallel."""
    unsigned = [p for p in parties if not p.get("has_signed")]
    if not unsigned:
        return []
    nxt = min(p.get("sign_order", 1) for p in unsigned)
    return [p for p in unsigned if p.get("sign_order", 1) == nxt]


def is_party_turn(parties: list[dict], party_id: str) -> bool:
    """A party may sign only when it is among the current next_signers (can't
    jump ahead of an earlier sign_order)."""
    return any(str(p.get("party_id")) == str(party_id) for p in next_signers(parties))


def expiry_alert_due(expires_at, *, now, days_before: int = 30) -> bool:
    """True within `days_before` of expiry (for the renewal nudge — reuses the
    escalation cron). `expires_at`/`now` are datetimes."""
    from datetime import timedelta
    if expires_at is None:
        return False
    if expires_at.tzinfo is None:
        from datetime import timezone
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    return now >= expires_at - timedelta(days=days_before)
