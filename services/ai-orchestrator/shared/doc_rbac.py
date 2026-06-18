"""ADR-0037 Phase 2 — functional-role permission matrix (pure, code-side policy).

The 5 functional roles a user plays in a department's workflows × the 7 document
actions. Kept in CODE (not a table) — it is policy, evaluated cheaply per request
and version-controlled. `user_department_roles` (mig 123) stores WHICH role a
user holds where; this decides WHAT each role may do.

Roles are ranked (executor < reviewer < approver < dept_manager < admin) so a
user with several roles in a department resolves to the strongest.
"""
from __future__ import annotations

from typing import Iterable

# Actions on a document / approval.
VIEW, DOWNLOAD, UPLOAD, EDIT, DELETE, APPROVE, COMMENT = (
    "view", "download", "upload", "edit", "delete", "approve", "comment")
ACTIONS = (VIEW, DOWNLOAD, UPLOAD, EDIT, DELETE, APPROVE, COMMENT)

EXECUTOR, REVIEWER, APPROVER, DEPT_MANAGER, ADMIN = (
    "executor", "reviewer", "approver", "dept_manager", "admin")

# Seniority order — a user with multiple roles resolves to the strongest.
_RANK = {EXECUTOR: 1, REVIEWER: 2, APPROVER: 3, DEPT_MANAGER: 4, ADMIN: 5}

# role → {action: allowed} (the prompt's RBAC matrix).
PERMISSION_MATRIX: dict[str, dict[str, bool]] = {
    EXECUTOR:     {VIEW: True, DOWNLOAD: True, UPLOAD: True,  EDIT: False, DELETE: False, APPROVE: False, COMMENT: True},
    REVIEWER:     {VIEW: True, DOWNLOAD: True, UPLOAD: False, EDIT: False, DELETE: False, APPROVE: False, COMMENT: True},
    APPROVER:     {VIEW: True, DOWNLOAD: True, UPLOAD: False, EDIT: False, DELETE: False, APPROVE: True,  COMMENT: True},
    DEPT_MANAGER: {VIEW: True, DOWNLOAD: True, UPLOAD: True,  EDIT: True,  DELETE: True,  APPROVE: True,  COMMENT: True},
    ADMIN:        {VIEW: True, DOWNLOAD: True, UPLOAD: True,  EDIT: True,  DELETE: True,  APPROVE: True,  COMMENT: True},
}


def can(role: str, action: str) -> bool:
    """Whether a single functional role may perform an action."""
    return PERMISSION_MATRIX.get(role, {}).get(action, False)


def effective_role(roles: Iterable[str]) -> str | None:
    """The strongest functional role from a set (None if empty/unknown)."""
    ranked = [(r, _RANK[r]) for r in roles if r in _RANK]
    return max(ranked, key=lambda x: x[1])[0] if ranked else None


def can_any(roles: Iterable[str], action: str) -> bool:
    """Whether ANY of a user's functional roles permits the action."""
    return any(can(r, action) for r in roles)


def allowed_actions(role: str) -> list[str]:
    """Actions a role may perform — for the UI to render controls."""
    return [a for a in ACTIONS if can(role, a)]
