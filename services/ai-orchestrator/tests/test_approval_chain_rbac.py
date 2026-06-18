"""ADR-0037 Phase 2 — approval-chain engine + functional RBAC matrix (pure)."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from ai_orchestrator.workflow_runtime import approval_chain as ac
from ai_orchestrator.shared import doc_rbac as rb


# ─────────────────── chain: level evaluation ───────────────────
class TestEvaluateLevel:
    def test_one_passes_on_any_approve(self):
        assert ac.evaluate_level("one", ["approve"], 3) == ac.APPROVED

    def test_one_pending_until_someone_acts(self):
        assert ac.evaluate_level("one", [], 3) == ac.PENDING

    def test_one_rejected_only_when_all_reject(self):
        assert ac.evaluate_level("one", ["reject", "reject"], 3) == ac.PENDING
        assert ac.evaluate_level("one", ["reject", "reject", "reject"], 3) == ac.REJECTED

    def test_all_requires_everyone(self):
        assert ac.evaluate_level("all", ["approve", "approve"], 3) == ac.PENDING
        assert ac.evaluate_level("all", ["approve", "approve", "approve"], 3) == ac.APPROVED

    def test_all_fails_on_first_reject(self):
        assert ac.evaluate_level("all", ["approve", "reject"], 3) == ac.REJECTED

    def test_majority(self):
        assert ac.evaluate_level("majority", ["approve", "approve"], 3) == ac.APPROVED  # 2/3
        assert ac.evaluate_level("majority", ["approve"], 3) == ac.PENDING
        assert ac.evaluate_level("majority", ["reject", "reject"], 3) == ac.REJECTED   # 2 rejects → no majority

    def test_required_count_override(self):
        assert ac.evaluate_level("one", ["approve"], 5, required_count=2) == ac.PENDING
        assert ac.evaluate_level("one", ["approve", "approve"], 5, required_count=2) == ac.APPROVED

    def test_required_count_rejects_when_impossible(self):
        # need 2 of 3; two rejects leave only 1 possible approve → impossible.
        assert ac.evaluate_level("one", ["reject", "reject"], 3, required_count=2) == ac.REJECTED


class TestAdvanceDecision:
    def test_approve_non_final_advances(self):
        assert ac.advance_decision("approve", 1, [1, 2, 3]) == ("advance", 2)

    def test_approve_final_resumes(self):
        assert ac.advance_decision("approve", 3, [1, 2, 3]) == ("resume", None)

    def test_reject_fails_any_level(self):
        assert ac.advance_decision("reject", 1, [1, 2, 3]) == ("fail", None)
        assert ac.advance_decision("reject", 3, [1, 2, 3]) == ("fail", None)

    def test_non_chained_approve_resumes(self):
        assert ac.advance_decision("approve", None, []) == ("resume", None)


class TestChainNavigation:
    def test_next_level(self):
        assert ac.next_level_no([1, 2, 3], 1) == 2
        assert ac.next_level_no([1, 2, 3], 2) == 3

    def test_no_next_at_last(self):
        assert ac.next_level_no([1, 2, 3], 3) is None

    def test_handles_gaps_and_unordered(self):
        assert ac.next_level_no([3, 1, 5], 1) == 3


class TestEscalation:
    def test_due_after_sla(self):
        created = datetime(2026, 5, 30, 9, 0, tzinfo=timezone.utc)
        now = created + timedelta(minutes=61)
        assert ac.escalation_due(created, 60, now=now)

    def test_not_due_within_sla(self):
        created = datetime(2026, 5, 30, 9, 0, tzinfo=timezone.utc)
        assert not ac.escalation_due(created, 60, now=created + timedelta(minutes=30))

    def test_naive_datetime_treated_utc(self):
        created = datetime(2026, 5, 30, 9, 0)  # naive
        now = datetime(2026, 5, 30, 10, 1, tzinfo=timezone.utc)
        assert ac.escalation_due(created, 60, now=now)


# ─────────────────── RBAC matrix ───────────────────
class TestRbacMatrix:
    def test_executor_uploads_not_approves(self):
        assert rb.can(rb.EXECUTOR, rb.UPLOAD)
        assert not rb.can(rb.EXECUTOR, rb.APPROVE)
        assert not rb.can(rb.EXECUTOR, rb.DELETE)

    def test_reviewer_read_comment_only(self):
        assert rb.can(rb.REVIEWER, rb.VIEW) and rb.can(rb.REVIEWER, rb.COMMENT)
        assert not rb.can(rb.REVIEWER, rb.UPLOAD)
        assert not rb.can(rb.REVIEWER, rb.APPROVE)

    def test_approver_approves_not_uploads(self):
        assert rb.can(rb.APPROVER, rb.APPROVE)
        assert not rb.can(rb.APPROVER, rb.UPLOAD)

    def test_dept_manager_and_admin_full(self):
        for a in rb.ACTIONS:
            assert rb.can(rb.DEPT_MANAGER, a)
            assert rb.can(rb.ADMIN, a)

    def test_unknown_role_denied(self):
        assert not rb.can("nobody", rb.VIEW)

    def test_effective_role_picks_strongest(self):
        assert rb.effective_role([rb.EXECUTOR, rb.APPROVER, rb.REVIEWER]) == rb.APPROVER
        assert rb.effective_role([]) is None

    def test_can_any(self):
        assert rb.can_any([rb.EXECUTOR, rb.REVIEWER], rb.UPLOAD)   # executor can
        assert not rb.can_any([rb.REVIEWER], rb.APPROVE)

    def test_allowed_actions_executor(self):
        acts = set(rb.allowed_actions(rb.EXECUTOR))
        assert acts == {rb.VIEW, rb.DOWNLOAD, rb.UPLOAD, rb.COMMENT}


# ─────────────────── wiring ───────────────────
def test_approval_rbac_router_endpoints():
    from ai_orchestrator.routers.approval_rbac import router
    paths = {r.path for r in router.routes}
    assert "/approval-chains" in paths
    assert "/approval-chains/{chain_id}/levels" in paths
    assert "/user-department-roles" in paths
    assert "/approval-delegations" in paths
    assert "/approval-inbox" in paths   # cross-run approver inbox


def test_escalation_activity_registered():
    from ai_orchestrator.workflow_runtime.activities import (
        ALL_ACTIVITIES, escalate_stale_approvals_for_tenant)
    assert escalate_stale_approvals_for_tenant in ALL_ACTIVITIES


# ─────────────────── RBAC enforcement guard ───────────────────
import pytest  # noqa: E402
from uuid import uuid4  # noqa: E402
from fastapi import HTTPException  # noqa: E402
from ai_orchestrator.shared import rbac_guard  # noqa: E402


class _FakeConn:
    """Minimal asyncpg-conn double for assert_permission."""
    def __init__(self, roles: list[str], dept_has_config: bool = True):
        self._roles = roles
        self._has = dept_has_config

    async def fetch(self, *_a):
        return [{"functional_role": r} for r in self._roles]

    async def fetchval(self, *_a):
        return 1 if self._has else None


class TestAssertPermission:
    @pytest.mark.asyncio
    async def test_approver_may_approve(self):
        await rbac_guard.assert_permission(
            _FakeConn(["approver"]), user_id=uuid4(), department_id=uuid4(), action="approve")

    @pytest.mark.asyncio
    async def test_reviewer_may_not_approve(self):
        with pytest.raises(HTTPException) as e:
            await rbac_guard.assert_permission(
                _FakeConn(["reviewer"]), user_id=uuid4(), department_id=uuid4(), action="approve")
        assert e.value.status_code == 403

    @pytest.mark.asyncio
    async def test_unassigned_user_in_controlled_dept_denied(self):
        with pytest.raises(HTTPException) as e:
            await rbac_guard.assert_permission(
                _FakeConn([], dept_has_config=True), user_id=uuid4(), department_id=uuid4(), action="approve")
        assert e.value.status_code == 403

    @pytest.mark.asyncio
    async def test_unconfigured_dept_falls_through(self):
        # dept has no role config → opt-in not activated → allow (no raise).
        await rbac_guard.assert_permission(
            _FakeConn([], dept_has_config=False), user_id=uuid4(), department_id=uuid4(), action="approve")

    @pytest.mark.asyncio
    async def test_no_department_context_allows(self):
        await rbac_guard.assert_permission(
            _FakeConn(["reviewer"]), user_id=uuid4(), department_id=None, action="approve")
