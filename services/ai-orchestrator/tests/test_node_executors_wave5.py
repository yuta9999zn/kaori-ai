"""
Unit tests for wave 5 (commit 8) — final 11 executors.
"""
from __future__ import annotations

import pytest
from uuid import uuid4

from workflow_runtime.node_executor import NodeContext, NodeExecutorError, REGISTRY
from workflow_runtime.executors.wave5 import (
    DeduplicateExecutor,
    EnrichExecutor,
    ExportFileExecutor,
    MergeExecutor,
    ReadApiExecutor,
    ReadCalendarExecutor,
    ReadChatExecutor,
    ReadFileUploadExecutor,
    SendSmsExecutor,
    SortExecutor,
    WaitForConditionExecutor,
)
from workflow_runtime.side_effect import SideEffectClass


def _ctx(**overrides) -> NodeContext:
    defaults = dict(
        enterprise_id=uuid4(),
        workspace_id=None,
        workflow_id=uuid4(),
        run_id=uuid4(),
        node_id=uuid4(),
        user_id=None,
        input_data={},
        prior_outputs={},
    )
    defaults.update(overrides)
    return NodeContext(**defaults)


# ─── Registry / final coverage ───────────────────────────────────


class TestWave5Coverage:
    def test_all_11_registered(self):
        for k in (
            "sort", "merge", "deduplicate", "enrich", "wait_for_condition",
            "read_api", "read_calendar", "read_chat", "read_file_upload",
            "send_sms", "export_file",
        ):
            assert REGISTRY.has(k), f"{k} missing"

    def test_total_registry_48_full_coverage(self):
        """Catalog has 48 business keys; all registered. Plus 'noop' — an infra
        flow-marker executor for BPMN start/end/intermediate events (not a
        node_type_catalog row), added 2026-05-30. 'contract' added by ADR-0037
        Phase 3 (mig 125). 'loop_foreach' + 'loop_end' added by mig 128
        (for-each runner, B2)."""
        # 6 + 2 + 8 + 10 + 8 + 11 = 45 wave catalog + 2 loop (mig 128)
        #   + 1 contract (ADR-0037) = 48 catalog + 1 noop
        keys = REGISTRY.list_keys()
        assert "noop" in keys
        assert "contract" in keys
        assert "loop_foreach" in keys
        assert "loop_end" in keys
        assert len([k for k in keys if k != "noop"]) == 48


class TestWave5SideEffectClass:
    def test_pure(self):
        for cls in (SortExecutor, MergeExecutor, DeduplicateExecutor):
            assert cls.side_effect_class == SideEffectClass.PURE

    def test_read_only(self):
        for cls in (EnrichExecutor, WaitForConditionExecutor, ReadApiExecutor,
                     ReadCalendarExecutor, ReadChatExecutor, ReadFileUploadExecutor):
            assert cls.side_effect_class == SideEffectClass.READ_ONLY

    def test_external(self):
        assert SendSmsExecutor.side_effect_class == SideEffectClass.EXTERNAL

    def test_write_idempotent(self):
        assert ExportFileExecutor.side_effect_class == SideEffectClass.WRITE_IDEMPOTENT


# ─── sort ────────────────────────────────────────────────────────


class TestSort:
    @pytest.mark.asyncio
    async def test_single_column_asc(self):
        result = await SortExecutor().execute(_ctx(), {
            "rows": [{"x": 3}, {"x": 1}, {"x": 2}],
            "by": "x",
        })
        values = [r["x"] for r in result.output_data["rows"]]
        assert values == [1, 2, 3]

    @pytest.mark.asyncio
    async def test_desc(self):
        result = await SortExecutor().execute(_ctx(), {
            "rows": [{"x": 1}, {"x": 3}, {"x": 2}],
            "by": "x", "direction": "desc",
        })
        values = [r["x"] for r in result.output_data["rows"]]
        assert values == [3, 2, 1]

    @pytest.mark.asyncio
    async def test_missing_by_raises(self):
        with pytest.raises(NodeExecutorError):
            await SortExecutor().execute(_ctx(), {"rows": []})

    @pytest.mark.asyncio
    async def test_invalid_direction(self):
        with pytest.raises(NodeExecutorError):
            await SortExecutor().execute(_ctx(), {
                "rows": [], "by": "x", "direction": "random",
            })


# ─── merge ────────────────────────────────────────────────────────


class TestMerge:
    @pytest.mark.asyncio
    async def test_concat(self):
        result = await MergeExecutor().execute(_ctx(), {
            "inputs": [[1, 2], [3, 4]],
        })
        assert result.output_data["rows"] == [1, 2, 3, 4]
        assert result.output_data["total"] == 4

    @pytest.mark.asyncio
    async def test_interleave(self):
        result = await MergeExecutor().execute(_ctx(), {
            "inputs": [[1, 3, 5], [2, 4]],
            "strategy": "interleave",
        })
        assert result.output_data["rows"] == [1, 2, 3, 4, 5]

    @pytest.mark.asyncio
    async def test_dedupe_keys(self):
        result = await MergeExecutor().execute(_ctx(), {
            "inputs": [
                [{"id": 1, "v": "a"}, {"id": 2, "v": "b"}],
                [{"id": 2, "v": "c"}, {"id": 3, "v": "d"}],
            ],
            "dedupe_keys": ["id"],
        })
        # id=2 appears twice; first wins
        rows = result.output_data["rows"]
        ids = [r["id"] for r in rows]
        assert ids == [1, 2, 3]
        # id=2 keeps 'b' (first occurrence)
        assert next(r for r in rows if r["id"] == 2)["v"] == "b"

    @pytest.mark.asyncio
    async def test_empty_inputs_raises(self):
        with pytest.raises(NodeExecutorError):
            await MergeExecutor().execute(_ctx(), {"inputs": []})


# ─── deduplicate ─────────────────────────────────────────────────


class TestDeduplicate:
    @pytest.mark.asyncio
    async def test_keep_first(self):
        rows = [
            {"email": "a@x.com", "name": "A"},
            {"email": "b@x.com", "name": "B"},
            {"email": "a@x.com", "name": "A2"},
        ]
        result = await DeduplicateExecutor().execute(_ctx(), {
            "rows": rows, "keys": ["email"], "keep": "first",
        })
        out = result.output_data["rows"]
        assert len(out) == 2
        # First a@x.com kept as "A"
        a_row = next(r for r in out if r["email"] == "a@x.com")
        assert a_row["name"] == "A"

    @pytest.mark.asyncio
    async def test_keep_last(self):
        rows = [
            {"email": "a@x.com", "name": "A"},
            {"email": "a@x.com", "name": "A2"},
        ]
        result = await DeduplicateExecutor().execute(_ctx(), {
            "rows": rows, "keys": ["email"], "keep": "last",
        })
        out = result.output_data["rows"]
        assert len(out) == 1
        assert out[0]["name"] == "A2"

    @pytest.mark.asyncio
    async def test_composite_key(self):
        rows = [
            {"a": 1, "b": "x"},
            {"a": 1, "b": "y"},  # different b — keep
            {"a": 1, "b": "x"},  # duplicate — drop
        ]
        result = await DeduplicateExecutor().execute(_ctx(), {
            "rows": rows, "keys": ["a", "b"],
        })
        assert len(result.output_data["rows"]) == 2

    @pytest.mark.asyncio
    async def test_missing_keys_raises(self):
        with pytest.raises(NodeExecutorError):
            await DeduplicateExecutor().execute(_ctx(), {"rows": [{}]})


# ─── enrich (DB-mocked) ──────────────────────────────────────────


class TestEnrich:
    @pytest.mark.asyncio
    async def test_unknown_lookup_table_raises(self):
        with pytest.raises(NodeExecutorError):
            await EnrichExecutor().execute(_ctx(), {
                "rows": [], "lookup_table": "pg_admin_users",
                "lookup_key": "id", "attach_columns": ["x"],
            })

    @pytest.mark.asyncio
    async def test_missing_attach_raises(self):
        with pytest.raises(NodeExecutorError):
            await EnrichExecutor().execute(_ctx(), {
                "rows": [{"customer_id": "C1"}],
                "lookup_table": "silver_customers",
                "lookup_key": "customer_id",
            })

    @pytest.mark.asyncio
    async def test_empty_keys_skips_db(self, monkeypatch):
        # Rows have no 'customer_id' values → no DB call needed.
        result = await EnrichExecutor().execute(_ctx(), {
            "rows": [{"other": 1}, {"other": 2}],
            "lookup_table": "silver_customers",
            "lookup_key": "customer_id",
            "from_column": "customer_id",
            "attach_columns": ["name"],
        })
        assert result.output_data["matched"] == 0
        assert result.output_data["missed"] == 2

    @pytest.mark.asyncio
    async def test_left_join_merges_master_columns(self, monkeypatch):
        from datetime import datetime

        class _Rec(dict):
            def __getitem__(self, k):
                return super().__getitem__(k)

        class _Conn:
            async def fetch(self, sql, *args):
                # Return master rows for customer_id IN ('C1', 'C2')
                return [
                    _Rec(customer_id="C1", name="Acme", tier="VIP"),
                    _Rec(customer_id="C2", name="Beta", tier="STD"),
                ]

        class _CM:
            async def __aenter__(self): return _Conn()
            async def __aexit__(self, *a): return False

        import ai_orchestrator.shared.db as _db
        monkeypatch.setattr(_db, "acquire_for_tenant", lambda _: _CM())

        result = await EnrichExecutor().execute(_ctx(), {
            "rows": [
                {"customer_id": "C1", "amount": 100},
                {"customer_id": "C2", "amount": 200},
                {"customer_id": "C99", "amount": 300},  # no match
            ],
            "lookup_table": "silver_customers",
            "lookup_key": "customer_id",
            "from_column": "customer_id",
            "attach_columns": ["name", "tier"],
        })
        assert result.output_data["matched"] == 2
        assert result.output_data["missed"] == 1
        out = result.output_data["rows"]
        c1 = next(r for r in out if r["customer_id"] == "C1")
        assert c1["name"] == "Acme"
        assert c1["tier"] == "VIP"


# ─── wait_for_condition ──────────────────────────────────────────


class TestWaitForCondition:
    @pytest.mark.asyncio
    async def test_table_not_in_whitelist_raises(self):
        with pytest.raises(NodeExecutorError):
            await WaitForConditionExecutor().execute(_ctx(), {
                "check_table": "silver_customers",
                "check_filter": {"id": 1},
            })

    @pytest.mark.asyncio
    async def test_empty_filter_raises(self):
        with pytest.raises(NodeExecutorError):
            await WaitForConditionExecutor().execute(_ctx(), {
                "check_table": "workflow_form_submissions",
                "check_filter": {},
            })

    @pytest.mark.asyncio
    async def test_immediate_match_returns(self, monkeypatch):
        from datetime import datetime
        class _Rec(dict):
            def __getitem__(self, k): return super().__getitem__(k)
        class _Conn:
            async def fetchrow(self, *a, **k):
                return _Rec(submission_id=str(uuid4()), form_key="x")
        class _CM:
            async def __aenter__(self): return _Conn()
            async def __aexit__(self, *a): return False
        import ai_orchestrator.shared.db as _db
        monkeypatch.setattr(_db, "acquire_for_tenant", lambda _: _CM())

        result = await WaitForConditionExecutor().execute(_ctx(), {
            "check_table": "workflow_form_submissions",
            "check_filter": {"form_key": "test"},
            "max_wait_seconds": 5,
            "poll_interval_seconds": 1,
        })
        assert result.output_data["found"] is True
        assert result.output_data["polls"] == 1

    @pytest.mark.asyncio
    async def test_timeout_returns_not_found(self, monkeypatch):
        class _Conn:
            async def fetchrow(self, *a, **k):
                return None
        class _CM:
            async def __aenter__(self): return _Conn()
            async def __aexit__(self, *a): return False
        import ai_orchestrator.shared.db as _db
        monkeypatch.setattr(_db, "acquire_for_tenant", lambda _: _CM())

        result = await WaitForConditionExecutor().execute(_ctx(), {
            "check_table": "workflow_form_submissions",
            "check_filter": {"form_key": "x"},
            "max_wait_seconds": 1,
            "poll_interval_seconds": 1,
        })
        assert result.output_data["found"] is False
        assert result.output_data["polls"] >= 1


# ─── read_api ────────────────────────────────────────────────────


class TestReadApi:
    @pytest.mark.asyncio
    async def test_missing_url_raises(self):
        with pytest.raises(NodeExecutorError):
            await ReadApiExecutor().execute(_ctx(), {})

    @pytest.mark.asyncio
    async def test_disallowed_host_raises(self):
        with pytest.raises(NodeExecutorError, match="allowlist"):
            await ReadApiExecutor().execute(_ctx(), {
                "url": "https://evil.example.com/x",
            })

    @pytest.mark.asyncio
    async def test_timeout_validation(self):
        with pytest.raises(NodeExecutorError):
            await ReadApiExecutor().execute(_ctx(), {
                "url": "http://localhost/health", "timeout_s": 999,
            })

    @pytest.mark.asyncio
    async def test_successful_call(self, monkeypatch):
        class _Resp:
            status_code = 200
            text = "OK"
            def json(self): return {"value": 42}
        class _Client:
            def __init__(self, *a, **k): pass
            async def __aenter__(self): return self
            async def __aexit__(self, *a): return False
            async def get(self, *a, **k): return _Resp()
        import workflow_runtime.executors.wave5 as _w5
        monkeypatch.setattr(_w5.httpx, "AsyncClient", _Client)

        result = await ReadApiExecutor().execute(_ctx(), {
            "url": "http://localhost/api/x",
        })
        assert result.output_data["status_code"] == 200
        assert result.output_data["response_body"]["value"] == 42


# ─── read_calendar / read_chat ───────────────────────────────────


class TestReadCalendarChat:
    @pytest.mark.asyncio
    async def test_calendar_missing_queue_key_raises(self):
        with pytest.raises(NodeExecutorError):
            await ReadCalendarExecutor().execute(_ctx(), {})

    @pytest.mark.asyncio
    async def test_chat_missing_queue_key_raises(self):
        with pytest.raises(NodeExecutorError):
            await ReadChatExecutor().execute(_ctx(), {})

    @pytest.mark.asyncio
    async def test_calendar_no_pending_returns_found_false(self, monkeypatch):
        class _Conn:
            async def fetchrow(self, *a, **k): return None
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

        result = await ReadCalendarExecutor().execute(_ctx(), {
            "queue_key": "team-cal",
        })
        assert result.output_data["found"] is False
        assert result.output_data["event_id"] is None


# ─── read_file_upload ────────────────────────────────────────────


class TestReadFileUpload:
    @pytest.mark.asyncio
    async def test_missing_file_id_raises(self):
        with pytest.raises(NodeExecutorError):
            await ReadFileUploadExecutor().execute(_ctx(), {})

    @pytest.mark.asyncio
    async def test_invalid_uuid_raises(self):
        with pytest.raises(NodeExecutorError):
            await ReadFileUploadExecutor().execute(_ctx(), {
                "file_id": "not-a-uuid",
            })

    @pytest.mark.asyncio
    async def test_picks_up_from_input_data(self, monkeypatch):
        class _Conn:
            async def fetchrow(self, *a, **k): return None
        class _CM:
            async def __aenter__(self): return _Conn()
            async def __aexit__(self, *a): return False
        import ai_orchestrator.shared.db as _db
        monkeypatch.setattr(_db, "acquire_for_tenant", lambda _: _CM())

        result = await ReadFileUploadExecutor().execute(
            _ctx(input_data={"file_id": str(uuid4())}),
            {},
        )
        # Found=False because mock returns None, but executor didn't raise
        assert result.output_data["found"] is False


# ─── send_sms ────────────────────────────────────────────────────


class TestSendSms:
    @pytest.mark.asyncio
    async def test_missing_target_raises(self):
        with pytest.raises(NodeExecutorError):
            await SendSmsExecutor().execute(_ctx(), {"message": "hi"})

    @pytest.mark.asyncio
    async def test_invalid_phone_format_raises(self):
        with pytest.raises(NodeExecutorError):
            await SendSmsExecutor().execute(_ctx(), {
                "target": "not-a-phone-abc", "message": "x",
            })

    @pytest.mark.asyncio
    async def test_oversize_message_raises(self):
        with pytest.raises(NodeExecutorError):
            await SendSmsExecutor().execute(_ctx(), {
                "target": "+84912345678", "message": "x" * 600,
            })

    @pytest.mark.asyncio
    async def test_enqueues(self, monkeypatch):
        class _Row(dict):
            def __getitem__(self, k): return super().__getitem__(k)
        class _Conn:
            async def fetchrow(self, sql, *args):
                if "SELECT outbox_id" in sql:
                    return None
                return _Row(outbox_id=uuid4())
        class _CM:
            async def __aenter__(self): return _Conn()
            async def __aexit__(self, *a): return False
        import ai_orchestrator.shared.db as _db
        monkeypatch.setattr(_db, "acquire_for_tenant", lambda _: _CM())

        result = await SendSmsExecutor().execute(_ctx(), {
            "target": "+84912345678", "message": "OTP 123456",
        })
        assert result.output_data["queued"] is True
        assert result.output_data["dedup_hit"] is False


# ─── export_file ─────────────────────────────────────────────────


class TestExportFile:
    @pytest.mark.asyncio
    async def test_missing_key_raises(self):
        with pytest.raises(NodeExecutorError):
            await ExportFileExecutor().execute(_ctx(), {
                "file_format": "csv", "filename": "x.csv",
            })

    @pytest.mark.asyncio
    async def test_invalid_format_raises(self):
        with pytest.raises(NodeExecutorError):
            await ExportFileExecutor().execute(_ctx(), {
                "export_key": "k", "file_format": "exe", "filename": "x.exe",
            })

    @pytest.mark.asyncio
    async def test_enqueues_with_schema_capture(self, monkeypatch):
        spy = {"args": None}
        class _Row(dict):
            def __getitem__(self, k): return super().__getitem__(k)
        class _Conn:
            async def fetchrow(self, sql, *args):
                spy["args"] = args
                return _Row(export_id=uuid4(), inserted=True)
        class _CM:
            async def __aenter__(self): return _Conn()
            async def __aexit__(self, *a): return False
        import ai_orchestrator.shared.db as _db
        monkeypatch.setattr(_db, "acquire_for_tenant", lambda _: _CM())

        result = await ExportFileExecutor().execute(_ctx(), {
            "export_key": "invoice-batch-2026-05",
            "file_format": "csv",
            "filename": "invoices.csv",
            "rows": [{"id": "I1", "amount": 100}, {"id": "I2", "amount": 200}],
        })
        assert result.output_data["status"] == "queued"
        assert result.output_data["row_count"] == 2
        # Schema captured in metadata payload
        args = spy["args"]
        meta_json = next((a for a in args if isinstance(a, str) and "schema" in a), None)
        assert meta_json is not None
        assert "id" in meta_json and "amount" in meta_json
