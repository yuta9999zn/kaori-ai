"""
Tests for P0.3 persistent idempotency store.

Pure unit tests for derive_key + integration tests with monkeypatched
DB for get_or_set + record_outcome.
"""
from __future__ import annotations

import pytest
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from workflow_runtime.idempotency_store import (
    IdempotencyHit,
    derive_key,
    get_or_set,
    record_outcome,
)


class TestDeriveKey:
    def test_deterministic_same_inputs(self):
        run, node = uuid4(), uuid4()
        k1 = derive_key(run_id=run, node_id=node, attempt=1)
        k2 = derive_key(run_id=run, node_id=node, attempt=1)
        assert k1 == k2

    def test_different_attempt_different_key(self):
        run, node = uuid4(), uuid4()
        k1 = derive_key(run_id=run, node_id=node, attempt=1)
        k2 = derive_key(run_id=run, node_id=node, attempt=2)
        assert k1 != k2

    def test_seed_discriminates(self):
        run, node = uuid4(), uuid4()
        k1 = derive_key(run_id=run, node_id=node, seed="POST|/refund")
        k2 = derive_key(run_id=run, node_id=node, seed="POST|/void")
        assert k1 != k2

    def test_hex_format(self):
        k = derive_key(run_id=uuid4(), node_id=uuid4())
        assert len(k) == 64
        assert all(c in "0123456789abcdef" for c in k)


class _FakeRow(dict):
    def __getitem__(self, key):
        return super().__getitem__(key)


@pytest.mark.asyncio
class TestGetOrSetMiss:
    """No existing row → INSERT placeholder, return cached=False."""
    async def test_inserts_new_record(self, monkeypatch):
        captured = {"select_count": 0, "insert_count": 0}

        class _Conn:
            async def fetchrow(self, sql, *args):
                if "SELECT record_id" in sql:
                    captured["select_count"] += 1
                    return None
                if "INSERT INTO workflow_idempotency_records" in sql:
                    captured["insert_count"] += 1
                    return _FakeRow(record_id=uuid4(),
                                      response_payload={},
                                      response_status="pending",
                                      attempt_count=1,
                                      inserted=True)
                return None
            async def execute(self, *a, **k): return "OK"
            def transaction(self): return _Tx()

        class _Tx:
            async def __aenter__(self): return self
            async def __aexit__(self, *a): return False

        class _CM:
            async def __aenter__(self): return _Conn()
            async def __aexit__(self, *a): return False

        import ai_orchestrator.shared.db as _db
        monkeypatch.setattr(_db, "acquire_for_tenant", lambda _: _CM())

        hit = await get_or_set(
            enterprise_id=uuid4(),
            key="abc123",
            side_effect_class="external",
        )
        assert hit.cached is False
        assert hit.attempt_count == 1
        assert captured["insert_count"] == 1


@pytest.mark.asyncio
class TestGetOrSetHit:
    """Existing row not expired → return cached=True with payload."""
    async def test_returns_cached_payload(self, monkeypatch):
        expires_at = datetime.now(timezone.utc) + timedelta(hours=1)
        existing = _FakeRow(
            record_id=uuid4(),
            response_payload={"status_code": 200, "response_body": {"ok": True}},
            response_status="completed",
            attempt_count=2,
            expires_at=expires_at,
        )

        execute_calls = []

        class _Conn:
            async def fetchrow(self, sql, *args):
                if "SELECT record_id" in sql:
                    return existing
                return None
            async def execute(self, sql, *args):
                execute_calls.append((sql, args))
                return "UPDATE 1"
            def transaction(self): return _Tx()

        class _Tx:
            async def __aenter__(self): return self
            async def __aexit__(self, *a): return False

        class _CM:
            async def __aenter__(self): return _Conn()
            async def __aexit__(self, *a): return False

        import ai_orchestrator.shared.db as _db
        monkeypatch.setattr(_db, "acquire_for_tenant", lambda _: _CM())

        hit = await get_or_set(
            enterprise_id=uuid4(),
            key="cached-key",
            side_effect_class="external",
        )
        assert hit.cached is True
        assert hit.attempt_count == 3   # bumped by 1
        assert hit.response_payload == {"status_code": 200, "response_body": {"ok": True}}
        # Should have updated attempt_count + last_seen_at
        assert any("UPDATE workflow_idempotency_records" in c[0] for c in execute_calls)


@pytest.mark.asyncio
class TestGetOrSetExpired:
    """Existing row past expires_at → overwrite + return cached=False."""
    async def test_expired_row_overwritten(self, monkeypatch):
        expires_at = datetime.now(timezone.utc) - timedelta(minutes=1)
        existing = _FakeRow(
            record_id=uuid4(),
            response_payload={"old": "value"},
            response_status="completed",
            attempt_count=99,
            expires_at=expires_at,
        )
        execute_calls = []

        class _Conn:
            async def fetchrow(self, sql, *args):
                return existing
            async def execute(self, sql, *args):
                execute_calls.append((sql, args))
            def transaction(self): return _Tx()

        class _Tx:
            async def __aenter__(self): return self
            async def __aexit__(self, *a): return False

        class _CM:
            async def __aenter__(self): return _Conn()
            async def __aexit__(self, *a): return False

        import ai_orchestrator.shared.db as _db
        monkeypatch.setattr(_db, "acquire_for_tenant", lambda _: _CM())

        hit = await get_or_set(
            enterprise_id=uuid4(),
            key="expired-key",
            side_effect_class="external",
        )
        assert hit.cached is False
        assert hit.attempt_count == 1
        # Verify an UPDATE was issued resetting the row
        assert any("response_status = 'pending'" in c[0] for c in execute_calls)


@pytest.mark.asyncio
class TestRecordOutcome:
    async def test_updates_existing(self, monkeypatch):
        execute_calls = []

        class _Conn:
            async def execute(self, sql, *args):
                execute_calls.append(args)
                return "UPDATE 1"

        class _CM:
            async def __aenter__(self): return _Conn()
            async def __aexit__(self, *a): return False

        import ai_orchestrator.shared.db as _db
        monkeypatch.setattr(_db, "acquire_for_tenant", lambda _: _CM())

        await record_outcome(
            enterprise_id=uuid4(),
            key="x",
            response_payload={"result": "ok"},
            response_status="completed",
        )
        assert len(execute_calls) == 1
        args = execute_calls[0]
        # payload serialised to JSON
        assert '"result"' in args[0]
        assert "ok" in args[0]
        assert args[1] == "completed"

    async def test_missing_key_logs_warning(self, monkeypatch):
        class _Conn:
            async def execute(self, *a, **k):
                return "UPDATE 0"

        class _CM:
            async def __aenter__(self): return _Conn()
            async def __aexit__(self, *a): return False

        import ai_orchestrator.shared.db as _db
        monkeypatch.setattr(_db, "acquire_for_tenant", lambda _: _CM())

        # Should NOT raise; just log
        await record_outcome(
            enterprise_id=uuid4(),
            key="never-existed",
            response_payload={"x": 1},
        )


# ─── call_api persistent dedup integration ─────────────────────


@pytest.mark.asyncio
class TestCallApiPersistentDedup:
    """Verify call_api executor actually uses the persistent ledger."""
    async def test_persistent_dedup_short_circuits(self, monkeypatch):
        from workflow_runtime.executors.action import CallApiExecutor
        from workflow_runtime.node_executor import NodeContext

        # Clear in-process cache so persistent path is exercised
        CallApiExecutor._DEDUP_CACHE.clear()

        # First call patches: idempotency miss, HTTP fires, record_outcome.
        # Second call: idempotency hit (cached=True), no HTTP fired.
        call_log: list[str] = []

        from workflow_runtime.idempotency_store import IdempotencyHit
        idem_hits = [
            # First call: miss
            IdempotencyHit(cached=False, record_id=uuid4(),
                            response_payload={}, response_status="pending",
                            attempt_count=1),
            # Second call: hit
            IdempotencyHit(cached=True, record_id=uuid4(),
                            response_payload={"status_code": 200,
                                                "response_body": {"first": True},
                                                "method": "GET",
                                                "url": "http://localhost/x"},
                            response_status="completed",
                            attempt_count=2),
        ]
        idem_cursor = {"i": 0}

        async def fake_get_or_set(**kwargs):
            call_log.append(f"get_or_set:{kwargs.get('key')[:8]}")
            hit = idem_hits[idem_cursor["i"]]
            idem_cursor["i"] += 1
            return hit

        async def fake_record_outcome(**kwargs):
            call_log.append(f"record_outcome:{kwargs.get('key')[:8]}")

        import workflow_runtime.idempotency_store as _is
        monkeypatch.setattr(_is, "get_or_set", fake_get_or_set)
        monkeypatch.setattr(_is, "record_outcome", fake_record_outcome)

        # Mock httpx for first call
        class _Resp:
            status_code = 200
            text = "OK"
            def json(self): return {"first": True}

        class _Client:
            def __init__(self, *a, **k): pass
            async def __aenter__(self): return self
            async def __aexit__(self, *a): return False
            async def get(self, *a, **k):
                call_log.append("http.get")
                return _Resp()
            async def delete(self, *a, **k): return _Resp()
            async def request(self, *a, **k): return _Resp()

        import workflow_runtime.executors.action as _action
        monkeypatch.setattr(_action.httpx, "AsyncClient", _Client)

        ctx = NodeContext(
            enterprise_id=uuid4(),
            workspace_id=None,
            workflow_id=uuid4(),
            run_id=uuid4(),
            node_id=uuid4(),
            user_id=None,
            input_data={},
            prior_outputs={},
        )

        # First call — fires HTTP + persists
        r1 = await CallApiExecutor().execute(ctx, {
            "url": "http://llm-gateway/x", "method": "GET",
        })
        assert r1.output_data["dedup_hit"] is False

        # Clear in-process cache to force persistent path on 2nd call
        CallApiExecutor._DEDUP_CACHE.clear()

        r2 = await CallApiExecutor().execute(ctx, {
            "url": "http://llm-gateway/x", "method": "GET",
        })
        assert r2.output_data["dedup_hit"] is True

        # Verify HTTP only fired once + persistent ledger consulted both times
        http_calls = [c for c in call_log if c == "http.get"]
        assert len(http_calls) == 1, f"HTTP fired {len(http_calls)} times: {call_log}"
        get_or_set_calls = [c for c in call_log if c.startswith("get_or_set")]
        assert len(get_or_set_calls) == 2
