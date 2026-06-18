"""K-13 coverage Phase 2.9 sprint closeout — smoke tests for the
9 newly-wired endpoints (OKR + LLM-ops + field-key).

PR #206 established the K-13 pattern with full coverage matrix (cached
hit / first-call records / no-header skip) on dlq_console + auth_security
MFA endpoints. This PR (Phase 2.9 K-13 sprint close) wires 9 more
endpoints via a shared helper module (`shared/idempotency_helper.py`).

These smoke tests verify the SHARED helper integration works in each
new router — full matrix already proven in test_dlq_console.py +
test_p2_s25_mfa_and_encryption.py. 1 smoke per cluster keeps signal
high without duplicating PR #206's matrix.
"""
from __future__ import annotations

from uuid import uuid4

import pytest

# ────────────────────────────────────────────────────────────────────
# OKR cluster — create_okr smoke
# ────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
class TestK13OkrCluster:
    """Smoke: K-13 helper wired correctly on POST /okr (create_okr)."""

    async def test_create_okr_returns_cached_on_duplicate_key(self, monkeypatch):
        from ai_orchestrator.routers.okr import create_okr
        from ai_orchestrator.routers.okr import OKRCreate

        cached_payload = {
            "okr_id": str(uuid4()),
            "enterprise_id": str(uuid4()),
            "workspace_id": str(uuid4()),
            "department_id": None,
            "objective_text": "Cached objective",
            "objective_text_vi": None,
            "period_label": "Q2-2026",
            "period_start": "2026-04-01",
            "period_end": "2026-06-30",
            "owner_user_id": None,
            "status": "DRAFT",
            "progress": "0.0000",
            "notes": None,
            "key_results": [],
            "linked_workflows": [],
        }

        class _Hit:
            cached = True
            response_payload = cached_payload

        async def _fake_get_or_set(**kwargs):
            return _Hit()

        from ai_orchestrator.workflow_runtime import idempotency_store as _idem
        monkeypatch.setattr(_idem, "get_or_set", _fake_get_or_set)

        # DB must NOT be touched on cache hit
        class _CM:
            async def __aenter__(self):
                raise AssertionError("DB should not be touched on cache hit")
            async def __aexit__(self, *a): return False

        import ai_orchestrator.routers.okr as _r
        monkeypatch.setattr(_r, "acquire_for_tenant", lambda _: _CM())

        body = OKRCreate(
            workspace_id=uuid4(),
            objective_text="dummy",
            period_label="Q2-2026",
            period_start="2026-04-01",
            period_end="2026-06-30",
            key_results=[],
        )
        out = await create_okr(
            body=body,
            x_enterprise_id=uuid4(),
            idempotency_key="TEST-IDEMPOTENCY-OKR-CREATE-DUP",
        )
        assert out.objective_text == "Cached objective"


# ────────────────────────────────────────────────────────────────────
# LLM-ops cluster — promote_upgrade_test smoke (most irreversible)
# ────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
class TestK13LlmOpsCluster:
    """Smoke: K-13 helper wired on POST /llm-ops/versions/upgrade-test/
    {id}/promote — most irreversible op in the cluster."""

    async def test_promote_returns_cached_on_duplicate(self, monkeypatch):
        from ai_orchestrator.routers.llm_ops import promote_upgrade_test

        cached_payload = {
            "test_id": str(uuid4()),
            "provider_key": "anthropic",
            "current_model": "claude-sonnet-4-6",
            "current_version": "2026-01-01",
            "candidate_model": "claude-sonnet-4-7",
            "candidate_version": "2026-05-01",
            "status": "PROMOTED",
            "started_at": "2026-04-01T00:00:00+00:00",
            "ends_at": "2026-06-30T00:00:00+00:00",
            "shadow_call_count": 1000,
            "agreement_rate": "0.9500",
            "avg_cost_delta_usd": "-0.0010",
            "notes": "cached",
        }

        class _Hit:
            cached = True
            response_payload = cached_payload

        async def _fake_get_or_set(**kwargs):
            return _Hit()

        from ai_orchestrator.workflow_runtime import idempotency_store as _idem
        monkeypatch.setattr(_idem, "get_or_set", _fake_get_or_set)

        class _CM:
            async def __aenter__(self):
                raise AssertionError("DB untouched on cache hit")
            async def __aexit__(self, *a): return False

        import ai_orchestrator.routers.llm_ops as _r
        monkeypatch.setattr(_r, "acquire_for_tenant", lambda _: _CM())

        out = await promote_upgrade_test(
            test_id=uuid4(),
            x_enterprise_id=uuid4(),
            x_user_id=uuid4(),
            idempotency_key="TEST-IDEMPOTENCY-PROMOTE-DUP",
        )
        assert out.status == "PROMOTED"
        assert out.notes == "cached"


# ────────────────────────────────────────────────────────────────────
# Field-key cluster — rotate_field_key smoke
# ────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
class TestK13FieldKeyCluster:
    """Smoke: K-13 helper wired on POST /p2/auth/field-key/rotate.
    Critical because rotation writes to Vault under prod profile —
    double-fire would litter the secret store."""

    async def test_rotate_returns_cached_on_duplicate(self, monkeypatch):
        from ai_orchestrator.routers.auth_security import rotate_field_key

        tenant = uuid4()
        cached_payload = {
            "enterprise_id": str(tenant),
            "old_version": 1,
            "new_version": 2,
            "rotated_at": "2026-05-22T14:00:00+00:00",
        }

        class _Hit:
            cached = True
            response_payload = cached_payload

        async def _fake_get_or_set(**kwargs):
            return _Hit()

        from ai_orchestrator.workflow_runtime import idempotency_store as _idem
        monkeypatch.setattr(_idem, "get_or_set", _fake_get_or_set)

        class _CM:
            async def __aenter__(self):
                raise AssertionError("DB + Vault untouched on cache hit")
            async def __aexit__(self, *a): return False

        import ai_orchestrator.routers.auth_security as _r
        monkeypatch.setattr(_r, "acquire_for_tenant", lambda _: _CM())

        out = await rotate_field_key(
            x_enterprise_id=tenant,
            idempotency_key="TEST-IDEMPOTENCY-ROTATE-DUP",
        )
        assert out.new_version == 2
        assert out.old_version == 1
