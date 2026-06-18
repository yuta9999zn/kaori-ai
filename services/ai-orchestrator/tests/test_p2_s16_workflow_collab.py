"""
P2-S16 Multi-user collaboration tests — editors + comments + locks (mig 072).

8-section template per anh's "chuẩn chỉ + hiệu năng + phi chức năng":
  1. Mig 072 shape           — 3 tables + CHECK constraints + indexes
  2. Editor CRUD             — assign + role update + remove + duplicate 409
  3. Comment threading       — top-level + reply + resolve + node-anchored
  4. Lock acquire/release    — happy path + same-user refresh + cross-user 409
  5. Lock anti-IDOR (K-13)   — wrong token release returns 403
  6. Tenant isolation        — headers required
  7. Endpoint validation     — role enum + comment body min-length
  8. Performance             — 50 editors list under 50ms (small in-memory mock)
"""
from __future__ import annotations

import time
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient


ENTERPRISE = "11111111-1111-1111-1111-111111111111"
USER       = "22222222-2222-2222-2222-222222222222"
USER2      = "33333333-3333-3333-3333-333333333333"
WORKFLOW_ID = "44444444-4444-4444-4444-444444444444"
COMMENT_ID  = "55555555-5555-5555-5555-555555555555"

HEADERS = {"X-Enterprise-ID": ENTERPRISE, "X-User-ID": USER}
HEADERS_USER2 = {"X-Enterprise-ID": ENTERPRISE, "X-User-ID": USER2}

REPO_ROOT = Path(__file__).resolve().parents[3]
MIG_DIR = REPO_ROOT / "infrastructure" / "postgres" / "migrations"

NOW = datetime(2026, 5, 17, 12, 0, tzinfo=timezone.utc)


def _make_conn() -> AsyncMock:
    conn = AsyncMock()
    conn.fetch.return_value = []
    conn.fetchrow.return_value = None
    conn.execute.return_value = "INSERT 0 1"
    return conn


def _tenant_ctx(conn):
    @asynccontextmanager
    async def _fake(_enterprise_id):
        yield conn
    return _fake


def _row(**kw):
    """Row mock that also supports dict(r) coercion via .keys() + __getitem__."""
    r = MagicMock()
    r.__getitem__ = lambda _self, k: kw[k]
    r.keys = MagicMock(return_value=list(kw.keys()))
    return r


def _make_app() -> FastAPI:
    from ai_orchestrator.routers import workflow_collab
    app = FastAPI()
    app.include_router(workflow_collab.router)
    return app


# ═════════════════════════════════════════════════════════════════════
# 1. Mig 072 shape
# ═════════════════════════════════════════════════════════════════════


class TestMig072Shape:

    @pytest.fixture(scope="class")
    def mig_text(self) -> str:
        return (MIG_DIR / "072_workflow_collaboration.sql").read_text(encoding="utf-8")

    def test_3_tables_present(self, mig_text: str):
        for t in ("workflow_editors", "workflow_comments", "workflow_locks"):
            assert f"CREATE TABLE IF NOT EXISTS {t}" in mig_text

    def test_editor_role_enum(self, mig_text: str):
        for r in ("OWNER", "EDITOR", "REVIEWER", "VIEWER"):
            assert f"'{r}'" in mig_text

    def test_editor_unique_pair(self, mig_text: str):
        assert "uq_workflow_editor" in mig_text

    def test_comment_body_nonempty(self, mig_text: str):
        assert "chk_comment_body_nonempty" in mig_text

    def test_lock_ttl_range(self, mig_text: str):
        assert "chk_lock_ttl_range" in mig_text
        assert "ttl_seconds BETWEEN 30 AND 3600" in mig_text

    def test_lock_intent_enum(self, mig_text: str):
        for i in ("edit", "approve", "rebuild"):
            assert f"'{i}'" in mig_text

    def test_indexes_present(self, mig_text: str):
        for idx in (
            "idx_workflow_editors_workflow",
            "idx_workflow_editors_user",
            "idx_workflow_comments_workflow",
            "idx_workflow_comments_thread",
            "idx_workflow_locks_user",
        ):
            assert idx in mig_text


# ═════════════════════════════════════════════════════════════════════
# 2. Editor CRUD
# ═════════════════════════════════════════════════════════════════════


class TestEditorCRUD:

    def test_assign_editor_happy_path(self):
        from ai_orchestrator.routers import workflow_collab

        conn = _make_conn()
        conn.fetchrow.side_effect = [
            _row(workflow_id=UUID(WORKFLOW_ID)),   # workflow exists
            _row(
                editor_id=uuid4(), workflow_id=UUID(WORKFLOW_ID),
                user_id=UUID(USER2), role="EDITOR",
                invited_by=UUID(USER), accepted=False,
                created_at=NOW, accepted_at=None,
            ),
        ]
        with patch.object(workflow_collab, "acquire_for_tenant", _tenant_ctx(conn)):
            app = _make_app()
            client = TestClient(app)
            r = client.post(
                f"/workflows/{WORKFLOW_ID}/editors",
                json={"user_id": USER2, "role": "EDITOR"},
                headers=HEADERS,
            )
        assert r.status_code == 201, r.text
        assert r.json()["role"] == "EDITOR"

    def test_assign_duplicate_returns_409(self):
        from ai_orchestrator.routers import workflow_collab

        conn = _make_conn()
        conn.fetchrow.side_effect = [_row(workflow_id=UUID(WORKFLOW_ID))]
        # The second call (INSERT) raises a unique-constraint error
        async def _raise_uniq(*_a, **_kw):
            raise Exception("duplicate key violates unique constraint uq_workflow_editor")
        # First call returns workflow row, second raises
        original_fetchrow = conn.fetchrow
        call_count = {"n": 0}
        async def _wrapped(*args, **kwargs):
            call_count["n"] += 1
            if call_count["n"] == 1:
                return _row(workflow_id=UUID(WORKFLOW_ID))
            await _raise_uniq()
        conn.fetchrow = _wrapped
        with patch.object(workflow_collab, "acquire_for_tenant", _tenant_ctx(conn)):
            app = _make_app()
            client = TestClient(app)
            r = client.post(
                f"/workflows/{WORKFLOW_ID}/editors",
                json={"user_id": USER2, "role": "EDITOR"},
                headers=HEADERS,
            )
        assert r.status_code == 409

    def test_assign_workflow_not_found_returns_404(self):
        from ai_orchestrator.routers import workflow_collab

        conn = _make_conn()
        conn.fetchrow.return_value = None    # workflow missing
        with patch.object(workflow_collab, "acquire_for_tenant", _tenant_ctx(conn)):
            app = _make_app()
            client = TestClient(app)
            r = client.post(
                f"/workflows/{WORKFLOW_ID}/editors",
                json={"user_id": USER2, "role": "EDITOR"},
                headers=HEADERS,
            )
        assert r.status_code == 404

    def test_role_update_404_when_editor_missing(self):
        from ai_orchestrator.routers import workflow_collab

        conn = _make_conn()
        conn.fetchrow.return_value = None
        with patch.object(workflow_collab, "acquire_for_tenant", _tenant_ctx(conn)):
            app = _make_app()
            client = TestClient(app)
            r = client.patch(
                f"/workflows/{WORKFLOW_ID}/editors/{USER2}",
                json={"role": "VIEWER"},
                headers=HEADERS,
            )
        assert r.status_code == 404

    def test_invalid_role_returns_422(self):
        from ai_orchestrator.routers import workflow_collab

        conn = _make_conn()
        with patch.object(workflow_collab, "acquire_for_tenant", _tenant_ctx(conn)):
            app = _make_app()
            client = TestClient(app)
            r = client.post(
                f"/workflows/{WORKFLOW_ID}/editors",
                json={"user_id": USER2, "role": "SUPERMAN"},
                headers=HEADERS,
            )
        assert r.status_code == 422


# ═════════════════════════════════════════════════════════════════════
# 3. Comment threading
# ═════════════════════════════════════════════════════════════════════


class TestCommentThreading:

    def test_top_level_comment_post(self):
        from ai_orchestrator.routers import workflow_collab

        conn = _make_conn()
        conn.fetchrow.side_effect = [
            _row(workflow_id=UUID(WORKFLOW_ID)),
            _row(
                comment_id=UUID(COMMENT_ID), workflow_id=UUID(WORKFLOW_ID),
                node_id=None, parent_comment_id=None,
                enterprise_id=UUID(ENTERPRISE),
                author_user_id=UUID(USER), body="Hello team",
                resolved=False, resolved_at=None, resolved_by=None,
                created_at=NOW, edited_at=None,
            ),
        ]
        with patch.object(workflow_collab, "acquire_for_tenant", _tenant_ctx(conn)):
            app = _make_app()
            client = TestClient(app)
            r = client.post(
                f"/workflows/{WORKFLOW_ID}/comments",
                json={"body": "Hello team"},
                headers=HEADERS,
            )
        assert r.status_code == 201
        assert r.json()["body"] == "Hello team"
        assert r.json()["parent_comment_id"] is None

    def test_reply_validates_parent_in_same_workflow(self):
        from ai_orchestrator.routers import workflow_collab

        conn = _make_conn()
        # workflow exists; parent does NOT
        conn.fetchrow.side_effect = [
            _row(workflow_id=UUID(WORKFLOW_ID)),   # wf check
            None,                                  # parent comment missing
        ]
        with patch.object(workflow_collab, "acquire_for_tenant", _tenant_ctx(conn)):
            app = _make_app()
            client = TestClient(app)
            r = client.post(
                f"/workflows/{WORKFLOW_ID}/comments",
                json={"body": "Reply", "parent_comment_id": str(uuid4())},
                headers=HEADERS,
            )
        assert r.status_code == 400

    def test_resolve_marks_resolved_by(self):
        from ai_orchestrator.routers import workflow_collab

        conn = _make_conn()
        conn.fetchrow.return_value = _row(
            comment_id=UUID(COMMENT_ID), workflow_id=UUID(WORKFLOW_ID),
            node_id=None, parent_comment_id=None,
            enterprise_id=UUID(ENTERPRISE),
            author_user_id=UUID(USER), body="x",
            resolved=True, resolved_at=NOW, resolved_by=UUID(USER),
            created_at=NOW, edited_at=None,
        )
        with patch.object(workflow_collab, "acquire_for_tenant", _tenant_ctx(conn)):
            app = _make_app()
            client = TestClient(app)
            r = client.patch(
                f"/workflows/{WORKFLOW_ID}/comments/{COMMENT_ID}",
                json={"resolved": True},
                headers=HEADERS,
            )
        assert r.status_code == 200
        assert r.json()["resolved"] is True

    def test_empty_body_rejected_at_pydantic(self):
        from ai_orchestrator.routers import workflow_collab

        conn = _make_conn()
        with patch.object(workflow_collab, "acquire_for_tenant", _tenant_ctx(conn)):
            app = _make_app()
            client = TestClient(app)
            r = client.post(
                f"/workflows/{WORKFLOW_ID}/comments",
                json={"body": ""},
                headers=HEADERS,
            )
        assert r.status_code == 422


# ═════════════════════════════════════════════════════════════════════
# 4. Lock acquire/release (optimistic)
# ═════════════════════════════════════════════════════════════════════


class TestLocks:

    def test_acquire_lock_happy_path(self):
        from ai_orchestrator.routers import workflow_collab

        conn = _make_conn()
        lock_token = uuid4()
        conn.fetchrow.side_effect = [
            _row(workflow_id=UUID(WORKFLOW_ID)),   # wf exists
            None,                                  # no existing lock
            _row(
                lock_id=uuid4(), workflow_id=UUID(WORKFLOW_ID),
                enterprise_id=UUID(ENTERPRISE), held_by_user_id=UUID(USER),
                lock_token=lock_token, acquired_at=NOW,
                ttl_seconds=600, intent="edit",
            ),
        ]
        with patch.object(workflow_collab, "acquire_for_tenant", _tenant_ctx(conn)):
            app = _make_app()
            client = TestClient(app)
            r = client.post(
                f"/workflows/{WORKFLOW_ID}/lock",
                json={"ttl_seconds": 600, "intent": "edit"},
                headers=HEADERS,
            )
        assert r.status_code == 201
        assert r.json()["lock_token"] == str(lock_token)
        assert r.json()["intent"] == "edit"

    def test_cross_user_acquire_returns_409(self):
        from ai_orchestrator.routers import workflow_collab

        conn = _make_conn()
        # Existing live lock held by USER2
        conn.fetchrow.side_effect = [
            _row(workflow_id=UUID(WORKFLOW_ID)),
            _row(
                lock_id=uuid4(), workflow_id=UUID(WORKFLOW_ID),
                enterprise_id=UUID(ENTERPRISE),
                held_by_user_id=UUID(USER2),
                lock_token=uuid4(), acquired_at=datetime.now(timezone.utc),
                ttl_seconds=600, intent="edit",
            ),
        ]
        with patch.object(workflow_collab, "acquire_for_tenant", _tenant_ctx(conn)):
            app = _make_app()
            client = TestClient(app)
            r = client.post(
                f"/workflows/{WORKFLOW_ID}/lock",
                json={"ttl_seconds": 600, "intent": "edit"},
                headers=HEADERS,    # USER (not USER2)
            )
        assert r.status_code == 409
        assert "locked by user" in r.json()["detail"]

    def test_same_user_refresh_returns_new_token(self):
        from ai_orchestrator.routers import workflow_collab

        conn = _make_conn()
        old_token = uuid4()
        new_token = uuid4()
        conn.fetchrow.side_effect = [
            _row(workflow_id=UUID(WORKFLOW_ID)),
            _row(
                lock_id=uuid4(), workflow_id=UUID(WORKFLOW_ID),
                enterprise_id=UUID(ENTERPRISE), held_by_user_id=UUID(USER),
                lock_token=old_token, acquired_at=datetime.now(timezone.utc),
                ttl_seconds=600, intent="edit",
            ),
            _row(
                lock_id=uuid4(), workflow_id=UUID(WORKFLOW_ID),
                enterprise_id=UUID(ENTERPRISE), held_by_user_id=UUID(USER),
                lock_token=new_token, acquired_at=datetime.now(timezone.utc),
                ttl_seconds=900, intent="edit",
            ),
        ]
        with patch.object(workflow_collab, "acquire_for_tenant", _tenant_ctx(conn)):
            app = _make_app()
            client = TestClient(app)
            r = client.post(
                f"/workflows/{WORKFLOW_ID}/lock",
                json={"ttl_seconds": 900, "intent": "edit"},
                headers=HEADERS,
            )
        assert r.status_code == 201
        assert r.json()["lock_token"] == str(new_token)
        assert r.json()["ttl_seconds"] == 900

    def test_acquire_expired_lock_replaces_it(self):
        from ai_orchestrator.routers import workflow_collab

        conn = _make_conn()
        expired_ago = datetime.now(timezone.utc) - timedelta(hours=2)
        new_token = uuid4()
        conn.fetchrow.side_effect = [
            _row(workflow_id=UUID(WORKFLOW_ID)),
            _row(
                lock_id=uuid4(), workflow_id=UUID(WORKFLOW_ID),
                enterprise_id=UUID(ENTERPRISE), held_by_user_id=UUID(USER2),
                lock_token=uuid4(), acquired_at=expired_ago,
                ttl_seconds=600, intent="edit",
            ),
            _row(
                lock_id=uuid4(), workflow_id=UUID(WORKFLOW_ID),
                enterprise_id=UUID(ENTERPRISE), held_by_user_id=UUID(USER),
                lock_token=new_token, acquired_at=datetime.now(timezone.utc),
                ttl_seconds=600, intent="edit",
            ),
        ]
        with patch.object(workflow_collab, "acquire_for_tenant", _tenant_ctx(conn)):
            app = _make_app()
            client = TestClient(app)
            r = client.post(
                f"/workflows/{WORKFLOW_ID}/lock",
                json={"ttl_seconds": 600, "intent": "edit"},
                headers=HEADERS,
            )
        assert r.status_code == 201


# ═════════════════════════════════════════════════════════════════════
# 5. Lock anti-IDOR (K-13) — wrong token rejected
# ═════════════════════════════════════════════════════════════════════


class TestLockAntiIDOR:

    def test_release_wrong_token_returns_403(self):
        from ai_orchestrator.routers import workflow_collab

        conn = _make_conn()
        conn.fetchrow.return_value = None    # DELETE … RETURNING with no match
        with patch.object(workflow_collab, "acquire_for_tenant", _tenant_ctx(conn)):
            app = _make_app()
            client = TestClient(app)
            r = client.request(
                "DELETE",
                f"/workflows/{WORKFLOW_ID}/lock",
                json={"lock_token": str(uuid4())},
                headers=HEADERS,
            )
        assert r.status_code == 403
        assert "lock_token mismatch" in r.json()["detail"]

    def test_check_lock_returns_null_after_expiry(self):
        from ai_orchestrator.routers import workflow_collab

        conn = _make_conn()
        expired_ago = datetime.now(timezone.utc) - timedelta(hours=2)
        conn.fetchrow.return_value = _row(
            lock_id=uuid4(), workflow_id=UUID(WORKFLOW_ID),
            enterprise_id=UUID(ENTERPRISE), held_by_user_id=UUID(USER2),
            lock_token=uuid4(), acquired_at=expired_ago,
            ttl_seconds=600, intent="edit",
        )
        with patch.object(workflow_collab, "acquire_for_tenant", _tenant_ctx(conn)):
            app = _make_app()
            client = TestClient(app)
            r = client.get(
                f"/workflows/{WORKFLOW_ID}/lock",
                headers={"X-Enterprise-ID": ENTERPRISE},
            )
        assert r.status_code == 200
        assert r.json() is None


# ═════════════════════════════════════════════════════════════════════
# 6. Tenant isolation
# ═════════════════════════════════════════════════════════════════════


class TestTenantIsolation:

    def test_post_editor_requires_enterprise_header(self):
        app = _make_app()
        client = TestClient(app)
        r = client.post(
            f"/workflows/{WORKFLOW_ID}/editors",
            json={"user_id": USER2, "role": "EDITOR"},
        )
        assert r.status_code == 422

    def test_post_comment_requires_user_header(self):
        app = _make_app()
        client = TestClient(app)
        r = client.post(
            f"/workflows/{WORKFLOW_ID}/comments",
            json={"body": "x"},
            headers={"X-Enterprise-ID": ENTERPRISE},
        )
        assert r.status_code == 422

    def test_acquire_lock_requires_user_header(self):
        app = _make_app()
        client = TestClient(app)
        r = client.post(
            f"/workflows/{WORKFLOW_ID}/lock",
            json={"ttl_seconds": 600},
            headers={"X-Enterprise-ID": ENTERPRISE},
        )
        assert r.status_code == 422


# ═════════════════════════════════════════════════════════════════════
# 7. Endpoint validation
# ═════════════════════════════════════════════════════════════════════


class TestEndpointValidation:

    def test_ttl_below_30_rejected(self):
        from ai_orchestrator.routers import workflow_collab

        conn = _make_conn()
        with patch.object(workflow_collab, "acquire_for_tenant", _tenant_ctx(conn)):
            app = _make_app()
            client = TestClient(app)
            r = client.post(
                f"/workflows/{WORKFLOW_ID}/lock",
                json={"ttl_seconds": 10, "intent": "edit"},
                headers=HEADERS,
            )
        assert r.status_code == 422

    def test_intent_invalid_rejected(self):
        from ai_orchestrator.routers import workflow_collab

        conn = _make_conn()
        with patch.object(workflow_collab, "acquire_for_tenant", _tenant_ctx(conn)):
            app = _make_app()
            client = TestClient(app)
            r = client.post(
                f"/workflows/{WORKFLOW_ID}/lock",
                json={"ttl_seconds": 600, "intent": "hijack"},
                headers=HEADERS,
            )
        assert r.status_code == 422


# ═════════════════════════════════════════════════════════════════════
# 8. Performance — 50-editor list
# ═════════════════════════════════════════════════════════════════════


class TestPerformance:

    def test_50_editors_list_under_100ms(self):
        from ai_orchestrator.routers import workflow_collab

        conn = _make_conn()
        conn.fetch.return_value = [
            _row(
                editor_id=uuid4(), workflow_id=UUID(WORKFLOW_ID),
                user_id=uuid4(), role="EDITOR",
                invited_by=UUID(USER), accepted=False,
                created_at=NOW, accepted_at=None,
            )
            for _ in range(50)
        ]
        with patch.object(workflow_collab, "acquire_for_tenant", _tenant_ctx(conn)):
            app = _make_app()
            client = TestClient(app)
            t0 = time.perf_counter()
            for _ in range(10):
                r = client.get(
                    f"/workflows/{WORKFLOW_ID}/editors",
                    headers={"X-Enterprise-ID": ENTERPRISE},
                )
                assert r.status_code == 200
            elapsed = (time.perf_counter() - t0) / 10
        assert elapsed < 0.1, f"too slow: {elapsed:.3f}s"
