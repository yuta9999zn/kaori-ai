"""ADR-0037 Phase 2 — multi-level approval-chain engine (pure).

Given a level's decision mode + the decisions collected for it, decide whether
the level is approved / rejected / still pending; find the next level; and decide
whether a pending level is past its SLA and must escalate. No DB, no I/O — the
router/executor/cron persist the result. Shared by Phase 3 (contracts reuse the
same chain semantics for multi-party signing).
"""
from __future__ import annotations

import math
from datetime import datetime, timedelta, timezone
from typing import Optional

APPROVED = "approved"
REJECTED = "rejected"
PENDING = "pending"

MODES = ("one", "all", "majority")


def evaluate_level(
    mode: str, decisions: list[str], n_approvers: int,
    required_count: Optional[int] = None,
) -> str:
    """Resolve a level from the decisions gathered ('approve' / 'reject').

    `n_approvers` = how many approvers the level expects (for all/majority math).
    `required_count` (optional) overrides the mode's implicit count: a level is
    approved once `required_count` approvals land, rejected once enough rejects
    make that impossible.

      one      → any approve passes; only all-reject (everyone decided, none
                 approved) fails.
      all      → every approver must approve; any reject fails immediately.
      majority → > half approve; once rejects make a majority impossible, fail.
    """
    approves = sum(1 for d in decisions if d == "approve")
    rejects = sum(1 for d in decisions if d == "reject")
    n = max(n_approvers, 1)

    if required_count is not None and required_count > 0:
        need = required_count
        if approves >= need:
            return APPROVED
        if rejects > n - need:        # remaining can't reach `need`
            return REJECTED
        return PENDING

    if mode == "all":
        if rejects >= 1:
            return REJECTED
        return APPROVED if approves >= n else PENDING

    if mode == "majority":
        need = n // 2 + 1
        if approves >= need:
            return APPROVED
        if rejects >= n - need + 1:   # majority approval now impossible
            return REJECTED
        return PENDING

    # mode == "one" (default)
    if approves >= 1:
        return APPROVED
    if rejects >= n:                  # everyone rejected
        return REJECTED
    return PENDING


def next_level_no(level_nos: list[int], current_no: int) -> Optional[int]:
    """The smallest level number strictly greater than current, or None if the
    current level is the last (→ the whole gate is approved)."""
    higher = sorted(n for n in level_nos if n > current_no)
    return higher[0] if higher else None


def advance_decision(
    decision: str, current_level_no: Optional[int], level_nos: list[int],
) -> tuple[str, Optional[int]]:
    """Decide what an approval decision does to a chained gate.

    Returns (action, next_level_no):
      'fail'    → a reject fails the whole gate (any level).
      'advance' → approve at a non-final level → open the next level (next_no).
      'resume'  → approve at the final level (or no chain) → gate passes, run resumes.

    A non-chained gate (current_level_no None / empty levels) resolves directly:
    approve → resume, reject → fail.
    """
    if decision != "approve":
        return ("fail", None)
    if current_level_no is None or not level_nos:
        return ("resume", None)
    nxt = next_level_no(level_nos, current_level_no)
    return ("advance", nxt) if nxt is not None else ("resume", None)


def escalation_due(
    created_at: datetime, sla_minutes: int, *, now: Optional[datetime] = None,
) -> bool:
    """True when a pending level has sat past its SLA window."""
    if now is None:
        now = datetime.now(timezone.utc)
    if created_at.tzinfo is None:
        created_at = created_at.replace(tzinfo=timezone.utc)
    return now >= created_at + timedelta(minutes=max(sla_minutes, 0))
