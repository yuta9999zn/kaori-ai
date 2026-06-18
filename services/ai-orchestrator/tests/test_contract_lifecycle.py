"""ADR-0037 Phase 3 — contract lifecycle + multi-party signing (pure) + router mount."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from ai_orchestrator.workflow_runtime import contract_lifecycle as cl


def _party(pid, order, signed=False):
    return {"party_id": pid, "sign_order": order, "has_signed": signed}


class TestStatusMachine:
    def test_draft_to_signing_to_effective(self):
        assert cl.can_transition(cl.NHAP, cl.CHO_KY)
        assert cl.can_transition(cl.CHO_KY, cl.HIEU_LUC)
        assert cl.can_transition(cl.CHO_KY, cl.TU_CHOI)

    def test_cannot_skip_to_effective_from_draft(self):
        assert not cl.can_transition(cl.NHAP, cl.HIEU_LUC)

    def test_effective_expires_or_terminates(self):
        assert cl.can_transition(cl.HIEU_LUC, cl.HET_HAN)
        assert cl.can_transition(cl.HIEU_LUC, cl.THANH_LY)

    def test_rejected_can_renegotiate(self):
        assert cl.can_transition(cl.TU_CHOI, cl.NHAP)

    def test_every_status_labelled(self):
        for s in (cl.NHAP, cl.CHO_KY, cl.HIEU_LUC, cl.HET_HAN, cl.THANH_LY, cl.TU_CHOI):
            assert s in cl.STATUS_LABEL


class TestSigningCompletion:
    def test_all_mode_needs_everyone(self):
        parties = [_party("a", 1, True), _party("b", 2, False)]
        assert not cl.signing_complete(parties, "all")
        parties[1]["has_signed"] = True
        assert cl.signing_complete(parties, "all")

    def test_threshold_mode(self):
        parties = [_party("a", 1, True), _party("b", 1, False), _party("c", 1, False)]
        assert cl.signing_complete(parties, "threshold", required_signatures=1)
        assert not cl.signing_complete(parties, "threshold", required_signatures=2)

    def test_empty_never_complete(self):
        assert not cl.signing_complete([], "all")


class TestSigningOrder:
    def test_sequential_gate(self):
        # b (order 2) cannot sign before a (order 1)
        parties = [_party("a", 1, False), _party("b", 2, False)]
        assert cl.is_party_turn(parties, "a")
        assert not cl.is_party_turn(parties, "b")

    def test_parallel_same_order(self):
        parties = [_party("a", 1, False), _party("b", 1, False)]
        turn = {str(p["party_id"]) for p in cl.next_signers(parties)}
        assert turn == {"a", "b"}

    def test_advances_after_signing(self):
        parties = [_party("a", 1, True), _party("b", 2, False)]
        assert cl.is_party_turn(parties, "b")

    def test_no_next_when_all_signed(self):
        parties = [_party("a", 1, True), _party("b", 2, True)]
        assert cl.next_signers(parties) == []


class TestExpiryAlert:
    def test_due_within_window(self):
        now = datetime(2026, 6, 1, tzinfo=timezone.utc)
        expires = now + timedelta(days=20)
        assert cl.expiry_alert_due(expires, now=now, days_before=30)

    def test_not_due_far_out(self):
        now = datetime(2026, 6, 1, tzinfo=timezone.utc)
        assert not cl.expiry_alert_due(now + timedelta(days=60), now=now, days_before=30)

    def test_none_expiry(self):
        assert not cl.expiry_alert_due(None, now=datetime.now(timezone.utc))


def test_contracts_router_endpoints():
    from ai_orchestrator.routers.contracts import router
    paths = {r.path for r in router.routes}
    assert "/contracts" in paths
    assert "/contracts/{contract_id}/sign" in paths
    assert "/contracts/{contract_id}/send" in paths
    assert "/contracts/{contract_id}/reject" in paths


def test_contract_node_executor_registered():
    """The 'contract' node type resolves to an executor (workflow integration)."""
    from ai_orchestrator.workflow_runtime.executors import register_builtin_executors
    from ai_orchestrator.workflow_runtime.node_executor import REGISTRY
    register_builtin_executors()
    ex = REGISTRY.get("contract")
    assert ex is not None and ex.node_type_key == "contract"
