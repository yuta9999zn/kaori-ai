"""
Formal state machine for workflow + node transitions (P0.2 of
operational-correctness hardening per anh's 2026-05-19 review).

Why
---
Pre-P0.2, runner code could UPDATE workflow_runs.status to any value
without enforcement (the CHECK constraint allowed the enum but no rule
on the FROM→TO transition). A bug could move a run from 'pending'
straight to 'completed' bypassing 'running' — destroying the audit
trail.

This module declares ALLOWED_TRANSITIONS as a frozen graph and exposes
`transition()` + `validate_transition()` that the runner + endpoint
handlers MUST call instead of raw UPDATE. The transition function:
  1. fetches current status (SELECT FOR UPDATE — serialise concurrent
     mutations of the same run)
  2. checks `(from_state, to_state) in ALLOWED_TRANSITIONS`
  3. UPDATEs only if valid
  4. raises StateTransitionDenied if invalid

The same enum + rules drive node-level transitions on workflow_run_nodes.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional
from uuid import UUID

import structlog

log = structlog.get_logger()


class WorkflowRunState(str, Enum):
    PENDING            = "pending"
    RUNNING            = "running"
    AWAITING_APPROVAL  = "awaiting_approval"
    COMPLETED          = "completed"
    FAILED             = "failed"
    CANCELLED          = "cancelled"


class NodeRunState(str, Enum):
    PENDING            = "pending"
    RUNNING            = "running"
    AWAITING_APPROVAL  = "awaiting_approval"
    COMPLETED          = "completed"
    FAILED             = "failed"
    SKIPPED            = "skipped"


# Workflow-run transition graph. (from_state, to_state) tuples.
# Terminal states (completed, failed, cancelled) have NO outgoing edges
# — once terminal, the run is immutable.
_ALLOWED_WORKFLOW: frozenset[tuple[str, str]] = frozenset({
    # initial fan-out
    ("pending", "running"),
    ("pending", "cancelled"),
    # from running
    ("running", "awaiting_approval"),
    ("running", "completed"),
    ("running", "failed"),
    ("running", "cancelled"),
    # pause/resume
    ("awaiting_approval", "running"),
    ("awaiting_approval", "failed"),
    ("awaiting_approval", "cancelled"),
    # idempotent re-entries — running may UPDATE to running on the
    # resume path (no-op semantically, deliberate to avoid raise on
    # double-call). NodeRunState is stricter; runs benefit from
    # this looser invariant for the in-process runner's resume flow.
    ("running", "running"),
})


# Per-node transition graph. Same general shape but with skipped
# instead of cancelled.
_ALLOWED_NODE: frozenset[tuple[str, str]] = frozenset({
    ("pending", "running"),
    ("pending", "skipped"),
    ("running", "awaiting_approval"),
    ("running", "completed"),
    ("running", "failed"),
    ("running", "skipped"),
    ("awaiting_approval", "running"),
    ("awaiting_approval", "completed"),
    ("awaiting_approval", "failed"),
    # Resume idempotency: existing-completed re-emitted as completed
    ("completed", "completed"),
    ("failed", "failed"),
    ("skipped", "skipped"),
})


class StateTransitionDenied(Exception):
    """Raised when a (from, to) pair is not in the allowed graph."""

    def __init__(self, from_state: str, to_state: str, *, entity: str):
        super().__init__(
            f"K-17 / state-machine: {entity} transition "
            f"{from_state!r} -> {to_state!r} is not in the allowed graph."
        )
        self.from_state = from_state
        self.to_state = to_state
        self.entity = entity


def validate_workflow_transition(from_state: str, to_state: str) -> None:
    """Pure check — raises if illegal, returns None if OK.

    `from_state=None` (workflow row not yet INSERTed) is treated as
    'pending' so the initial seed path works the same as a fresh DB row.
    """
    if from_state is None or from_state == "":
        from_state = "pending"
    if to_state not in WorkflowRunState.__members__.values() and \
       to_state not in {s.value for s in WorkflowRunState}:
        raise StateTransitionDenied(from_state, to_state, entity="workflow_run")
    if (from_state, to_state) not in _ALLOWED_WORKFLOW:
        raise StateTransitionDenied(from_state, to_state, entity="workflow_run")


def validate_node_transition(from_state: str, to_state: str) -> None:
    if from_state is None or from_state == "":
        from_state = "pending"
    if (from_state, to_state) not in _ALLOWED_NODE:
        raise StateTransitionDenied(from_state, to_state, entity="workflow_run_node")


def is_terminal_workflow(state: str) -> bool:
    return state in ("completed", "failed", "cancelled")


def is_terminal_node(state: str) -> bool:
    return state in ("completed", "failed", "skipped")


# ─── DB transition helpers (atomic via SELECT FOR UPDATE) ────────


@dataclass(frozen=True)
class TransitionOutcome:
    """Return value: caller decides whether to act on the result.
    For an idempotent re-entry the from + to may be equal."""
    from_state: str
    to_state:   str
    applied:    bool   # True = UPDATE fired; False = idempotent no-op


async def transition_workflow_status(
    conn,
    *,
    run_id:        UUID,
    new_status:    str,
) -> TransitionOutcome:
    """Atomic transition — caller passes an active asyncpg connection
    (usually inside a transaction). The runner can wrap multiple calls
    in one transaction to compose multi-step state changes.

    Raises StateTransitionDenied if (current, new_status) is not allowed.
    Returns TransitionOutcome with applied=True if a row was updated,
    applied=False if current == new_status (idempotent no-op).
    """
    row = await conn.fetchrow(
        "SELECT status FROM workflow_runs WHERE run_id = $1 FOR UPDATE",
        run_id,
    )
    if row is None:
        raise StateTransitionDenied("none", new_status, entity="workflow_run_missing")
    current = row["status"]
    if current == new_status:
        # Idempotent no-op (runner's resume flow may re-set 'running').
        return TransitionOutcome(current, new_status, applied=False)
    validate_workflow_transition(current, new_status)
    await conn.execute(
        "UPDATE workflow_runs SET status = $1 WHERE run_id = $2",
        new_status, run_id,
    )
    log.debug("workflow.transition",
                run_id=str(run_id),
                from_state=current, to_state=new_status)
    return TransitionOutcome(current, new_status, applied=True)


async def transition_node_status(
    conn,
    *,
    run_id:   UUID,
    node_id:  UUID,
    new_status: str,
) -> TransitionOutcome:
    """Same shape as workflow transition, scoped to a (run, node) row."""
    row = await conn.fetchrow(
        "SELECT status FROM workflow_run_nodes "
        "WHERE run_id = $1 AND node_id = $2 FOR UPDATE",
        run_id, node_id,
    )
    if row is None:
        # Implicit 'pending' — runner's first record_node call for this
        # node is allowed to set any FROM=pending transition.
        validate_node_transition("pending", new_status)
        return TransitionOutcome("pending", new_status, applied=True)
    current = row["status"]
    if current == new_status:
        return TransitionOutcome(current, new_status, applied=False)
    validate_node_transition(current, new_status)
    await conn.execute(
        "UPDATE workflow_run_nodes SET status = $1 "
        "WHERE run_id = $2 AND node_id = $3",
        new_status, run_id, node_id,
    )
    log.debug("workflow_node.transition",
                run_id=str(run_id), node_id=str(node_id),
                from_state=current, to_state=new_status)
    return TransitionOutcome(current, new_status, applied=True)


# ─── Public introspection (admin tools / FE state diagram) ───────


def allowed_workflow_transitions() -> list[tuple[str, str]]:
    """For SH-03 trace UI or FE state-diagram rendering."""
    return sorted(_ALLOWED_WORKFLOW)


def allowed_node_transitions() -> list[tuple[str, str]]:
    return sorted(_ALLOWED_NODE)
