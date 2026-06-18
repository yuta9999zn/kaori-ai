"""
Unit tests for wave 4 utility executors:
  scheduled_trigger / filter / transform / split / join / log /
  send_chat_message / read_webhook

Mostly pure compute (filter/transform/split/join/log/scheduled_trigger);
send_chat_message + read_webhook hit DB and use monkeypatched fakes.
"""
from __future__ import annotations

import pytest
from datetime import datetime, timezone
from uuid import uuid4

from workflow_runtime.node_executor import NodeContext, NodeExecutorError, REGISTRY
from workflow_runtime.executors.utility import (
    FilterExecutor,
    JoinExecutor,
    LogExecutor,
    ReadWebhookExecutor,
    ScheduledTriggerExecutor,
    SendChatMessageExecutor,
    SplitExecutor,
    TransformExecutor,
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


# ─── Registry / classes ───────────────────────────────────────────


class TestWave4Registry:
    def test_all_8_wave4_executors_registered(self):
        keys = (
            "scheduled_trigger", "filter", "transform", "split",
            "join", "log", "send_chat_message", "read_webhook",
        )
        for k in keys:
            assert REGISTRY.has(k), f"{k} missing"

    def test_registry_total_at_least_34(self):
        # Wave1 6 + Wave2a 2 + Wave2b 8 + Wave3 10 + Wave4 8 = 34
        assert len(REGISTRY.list_keys()) >= 34


class TestWave4SideEffectClass:
    def test_pure_nodes(self):
        for cls in (ScheduledTriggerExecutor, FilterExecutor,
                     TransformExecutor, SplitExecutor, JoinExecutor,
                     LogExecutor):
            assert cls.side_effect_class == SideEffectClass.PURE, cls.__name__

    def test_chat_external(self):
        assert SendChatMessageExecutor.side_effect_class == SideEffectClass.EXTERNAL

    def test_webhook_read_only(self):
        assert ReadWebhookExecutor.side_effect_class == SideEffectClass.READ_ONLY


# ─── scheduled_trigger ───────────────────────────────────────────


class TestScheduledTrigger:
    @pytest.mark.asyncio
    async def test_no_config_ok(self):
        result = await ScheduledTriggerExecutor().execute(_ctx(), {})
        assert result.status == "completed"
        assert result.output_data["trigger_source"] == "schedule"
        assert result.output_data["timezone"] == "UTC"
        # triggered_at parseable as ISO
        datetime.fromisoformat(result.output_data["triggered_at"])

    @pytest.mark.asyncio
    async def test_cron_must_be_string(self):
        with pytest.raises(NodeExecutorError):
            await ScheduledTriggerExecutor().execute(_ctx(), {"cron": 12345})

    @pytest.mark.asyncio
    async def test_passes_through_metadata(self):
        result = await ScheduledTriggerExecutor().execute(_ctx(), {
            "cron": "0 9 * * 1-5",
            "schedule_id": "contract-renewal-daily",
            "timezone": "Asia/Ho_Chi_Minh",
        })
        assert result.output_data["cron"] == "0 9 * * 1-5"
        assert result.output_data["schedule_id"] == "contract-renewal-daily"
        assert result.output_data["timezone"] == "Asia/Ho_Chi_Minh"


# ─── filter ──────────────────────────────────────────────────────


class TestFilter:
    @pytest.mark.asyncio
    async def test_empty_rows_passthrough(self):
        result = await FilterExecutor().execute(_ctx(), {
            "rows": [],
            "condition": {"left": 1, "op": "==", "right": 1},
        })
        assert result.output_data["rows"] == []
        assert result.output_data["total"] == 0

    @pytest.mark.asyncio
    async def test_missing_condition_raises(self):
        with pytest.raises(NodeExecutorError):
            await FilterExecutor().execute(_ctx(), {"rows": [{}]})

    @pytest.mark.asyncio
    async def test_predicate_on_row_column(self):
        rows = [
            {"name": "A", "value": 100},
            {"name": "B", "value": 50},
            {"name": "C", "value": 200},
        ]
        result = await FilterExecutor().execute(_ctx(), {
            "rows": rows,
            "condition": {"left": "$._row.value", "op": ">=", "right": 100},
        })
        assert len(result.output_data["rows"]) == 2
        assert result.output_data["dropped"] == 1

    @pytest.mark.asyncio
    async def test_negate(self):
        rows = [{"x": 1}, {"x": 2}, {"x": 3}]
        result = await FilterExecutor().execute(_ctx(), {
            "rows": rows,
            "condition": {"left": "$._row.x", "op": "==", "right": 2},
            "negate": True,
        })
        # Keeps everything EXCEPT x==2
        assert len(result.output_data["rows"]) == 2

    @pytest.mark.asyncio
    async def test_limit_truncates(self):
        rows = [{"v": i} for i in range(100)]
        result = await FilterExecutor().execute(_ctx(), {
            "rows": rows,
            "condition": {"left": "$._row.v", "op": ">=", "right": 0},
            "limit": 5,
        })
        assert len(result.output_data["rows"]) == 5

    @pytest.mark.asyncio
    async def test_compound_and(self):
        rows = [
            {"x": 5, "y": "yes"},
            {"x": 10, "y": "yes"},
            {"x": 10, "y": "no"},
        ]
        result = await FilterExecutor().execute(_ctx(), {
            "rows": rows,
            "condition": {"and": [
                {"left": "$._row.x", "op": ">=", "right": 10},
                {"left": "$._row.y", "op": "==", "right": "yes"},
            ]},
        })
        assert len(result.output_data["rows"]) == 1


# ─── transform ───────────────────────────────────────────────────


class TestTransform:
    @pytest.mark.asyncio
    async def test_rename_columns(self):
        rows = [{"old_name": "Acme", "value": 100}]
        result = await TransformExecutor().execute(_ctx(), {
            "rows": rows,
            "output_columns": [
                {"name": "company", "from": "old_name"},
                {"name": "amount", "from": "value"},
            ],
        })
        assert result.output_data["rows"] == [{"company": "Acme", "amount": 100}]

    @pytest.mark.asyncio
    async def test_literal_constant(self):
        result = await TransformExecutor().execute(_ctx(), {
            "rows": [{"a": 1}],
            "output_columns": [
                {"name": "a", "from": "a"},
                {"name": "currency", "literal": "VND"},
            ],
        })
        assert result.output_data["rows"][0]["currency"] == "VND"

    @pytest.mark.asyncio
    async def test_map_value(self):
        result = await TransformExecutor().execute(_ctx(), {
            "rows": [{"status": "PAID"}, {"status": "PENDING"}, {"status": "PAID"}],
            "output_columns": [
                {"name": "is_paid", "from": "status",
                  "map": {"PAID": True, "*": False}},
            ],
        })
        flags = [r["is_paid"] for r in result.output_data["rows"]]
        assert flags == [True, False, True]

    @pytest.mark.asyncio
    async def test_fn_upper(self):
        result = await TransformExecutor().execute(_ctx(), {
            "rows": [{"name": "an"}],
            "output_columns": [{"name": "name_upper", "from": "name", "fn": "upper"}],
        })
        assert result.output_data["rows"][0]["name_upper"] == "AN"

    @pytest.mark.asyncio
    async def test_fn_mul_arg(self):
        result = await TransformExecutor().execute(_ctx(), {
            "rows": [{"qty": 5}],
            "output_columns": [{"name": "qty_doubled", "from": "qty", "fn": "mul", "arg": 2}],
        })
        assert result.output_data["rows"][0]["qty_doubled"] == 10

    @pytest.mark.asyncio
    async def test_missing_name_raises(self):
        with pytest.raises(NodeExecutorError):
            await TransformExecutor().execute(_ctx(), {
                "rows": [{"x": 1}],
                "output_columns": [{"from": "x"}],
            })


# ─── split ───────────────────────────────────────────────────────


class TestSplit:
    @pytest.mark.asyncio
    async def test_half_mode(self):
        result = await SplitExecutor().execute(_ctx(), {
            "rows": list(range(10)), "mode": "half",
        })
        assert result.output_data["first_count"] == 5
        assert result.output_data["second_count"] == 5

    @pytest.mark.asyncio
    async def test_fraction(self):
        result = await SplitExecutor().execute(_ctx(), {
            "rows": list(range(10)), "mode": "fraction", "fraction": 0.7,
        })
        assert result.output_data["first_count"] == 7
        assert result.output_data["second_count"] == 3

    @pytest.mark.asyncio
    async def test_predicate(self):
        rows = [{"high_value": True, "id": i % 2 == 0} for i in range(6)]
        # Cleaner: mark half explicitly
        rows = [
            {"score": 10}, {"score": 80}, {"score": 30},
            {"score": 90}, {"score": 50}, {"score": 95},
        ]
        result = await SplitExecutor().execute(_ctx(), {
            "rows": rows,
            "mode": "predicate",
            "condition": {"left": "$._row.score", "op": ">=", "right": 80},
        })
        # 3 high-score (80,90,95) → first; 3 low → second
        assert result.output_data["first_count"] == 3
        assert result.output_data["second_count"] == 3

    @pytest.mark.asyncio
    async def test_fraction_out_of_range(self):
        with pytest.raises(NodeExecutorError):
            await SplitExecutor().execute(_ctx(), {
                "rows": [1, 2], "mode": "fraction", "fraction": 1.5,
            })

    @pytest.mark.asyncio
    async def test_half_with_seed_deterministic(self):
        rows = list(range(10))
        r1 = await SplitExecutor().execute(_ctx(), {"rows": rows, "mode": "half", "seed": 42})
        r2 = await SplitExecutor().execute(_ctx(), {"rows": rows, "mode": "half", "seed": 42})
        assert r1.output_data["first"] == r2.output_data["first"]


# ─── join ────────────────────────────────────────────────────────


class TestJoin:
    @pytest.mark.asyncio
    async def test_inner_join(self):
        left = [
            {"invoice_id": "I1", "amount": 100},
            {"invoice_id": "I2", "amount": 200},
            {"invoice_id": "I3", "amount": 300},
        ]
        right = [
            {"invoice_id": "I1", "vendor": "Acme"},
            {"invoice_id": "I3", "vendor": "Beta"},
        ]
        result = await JoinExecutor().execute(_ctx(), {
            "left_rows": left, "right_rows": right,
            "left_key": "invoice_id",
        })
        # Inner join — I2 dropped (no match)
        assert result.output_data["joined_count"] == 2
        joined = result.output_data["rows"]
        assert all("vendor" in r for r in joined)

    @pytest.mark.asyncio
    async def test_left_join_preserves_unmatched(self):
        left = [{"k": 1}, {"k": 2}]
        right = [{"k": 1, "extra": "X"}]
        result = await JoinExecutor().execute(_ctx(), {
            "left_rows": left, "right_rows": right,
            "left_key": "k", "mode": "left",
        })
        # k=2 preserved even without match
        assert result.output_data["joined_count"] == 2

    @pytest.mark.asyncio
    async def test_prefix_avoids_collision(self):
        left = [{"id": 1, "name": "L"}]
        right = [{"id": 1, "name": "R"}]
        result = await JoinExecutor().execute(_ctx(), {
            "left_rows": left, "right_rows": right,
            "left_key": "id", "prefix_right": "r_",
        })
        # right's 'name' should be 'r_name'
        merged = result.output_data["rows"][0]
        assert merged["name"] == "L"
        assert merged["r_name"] == "R"

    @pytest.mark.asyncio
    async def test_missing_left_key_raises(self):
        with pytest.raises(NodeExecutorError):
            await JoinExecutor().execute(_ctx(), {
                "left_rows": [], "right_rows": [],
            })


# ─── log ─────────────────────────────────────────────────────────


class TestLog:
    @pytest.mark.asyncio
    async def test_basic_log(self):
        result = await LogExecutor().execute(_ctx(), {
            "event": "workflow.audit.invoice_processed",
            "level": "info",
            "payload": {"invoice_id": "INV-001"},
        })
        assert result.output_data["logged"] is True
        assert result.output_data["level"] == "info"

    @pytest.mark.asyncio
    async def test_invalid_level_raises(self):
        with pytest.raises(NodeExecutorError):
            await LogExecutor().execute(_ctx(), {
                "event": "x", "level": "panic",
            })

    @pytest.mark.asyncio
    async def test_empty_event_raises(self):
        with pytest.raises(NodeExecutorError):
            await LogExecutor().execute(_ctx(), {"event": ""})

    @pytest.mark.asyncio
    async def test_dict_payload_serialised(self):
        result = await LogExecutor().execute(_ctx(), {
            "event": "x",
            "payload": {"nested": {"k": "v"}},
        })
        assert result.status == "completed"


# ─── send_chat_message ───────────────────────────────────────────


class TestSendChatMessage:
    @pytest.mark.asyncio
    async def test_invalid_channel_raises(self):
        with pytest.raises(NodeExecutorError):
            await SendChatMessageExecutor().execute(_ctx(), {
                "channel": "irc", "target": "x", "message": "y",
            })

    @pytest.mark.asyncio
    async def test_missing_target_raises(self):
        with pytest.raises(NodeExecutorError):
            await SendChatMessageExecutor().execute(_ctx(), {
                "channel": "slack", "message": "x",
            })

    @pytest.mark.asyncio
    async def test_oversize_message_raises(self):
        with pytest.raises(NodeExecutorError):
            await SendChatMessageExecutor().execute(_ctx(), {
                "channel": "slack", "target": "#x",
                "message": "y" * 5000,
            })

    @pytest.mark.asyncio
    async def test_enqueues_new(self, monkeypatch):
        from uuid import uuid4 as _u

        class _Row(dict):
            def __getitem__(self, k):
                return super().__getitem__(k)

        class _Conn:
            async def fetchrow(self, sql, *args):
                # First call: check existing → return None (not found).
                # Second call: insert → return outbox_id.
                if "SELECT outbox_id" in sql:
                    return None
                return _Row(outbox_id=_u())

        class _CM:
            async def __aenter__(self): return _Conn()
            async def __aexit__(self, *a): return False

        import ai_orchestrator.shared.db as _db
        monkeypatch.setattr(_db, "acquire_for_tenant", lambda _: _CM())

        result = await SendChatMessageExecutor().execute(_ctx(), {
            "channel": "slack", "target": "#sales-alerts",
            "message": "New high-value lead!",
        })
        assert result.output_data["dedup_hit"] is False
        assert result.output_data["channel"] == "slack"

    @pytest.mark.asyncio
    async def test_dedup_hit(self, monkeypatch):
        from uuid import uuid4 as _u
        existing_id = _u()

        class _Row(dict):
            def __getitem__(self, k):
                return super().__getitem__(k)

        class _Conn:
            async def fetchrow(self, sql, *args):
                # Always returns the existing row
                return _Row(outbox_id=existing_id)

        class _CM:
            async def __aenter__(self): return _Conn()
            async def __aexit__(self, *a): return False

        import ai_orchestrator.shared.db as _db
        monkeypatch.setattr(_db, "acquire_for_tenant", lambda _: _CM())

        result = await SendChatMessageExecutor().execute(_ctx(), {
            "channel": "telegram", "target": "@an",
            "message": "ping",
        })
        assert result.output_data["dedup_hit"] is True


# ─── read_webhook ────────────────────────────────────────────────


class TestReadWebhook:
    @pytest.mark.asyncio
    async def test_missing_queue_key_raises(self):
        with pytest.raises(NodeExecutorError):
            await ReadWebhookExecutor().execute(_ctx(), {})

    @pytest.mark.asyncio
    async def test_no_pending_returns_found_false(self, monkeypatch):
        class _Conn:
            async def fetchrow(self, *a, **k):
                return None
            async def execute(self, *a, **k):
                return "OK"
            def transaction(self):
                return _Tx()

        class _Tx:
            async def __aenter__(self): return self
            async def __aexit__(self, *a): return False

        class _CM:
            async def __aenter__(self): return _Conn()
            async def __aexit__(self, *a): return False

        import ai_orchestrator.shared.db as _db
        monkeypatch.setattr(_db, "acquire_for_tenant", lambda _: _CM())

        result = await ReadWebhookExecutor().execute(_ctx(), {
            "queue_key": "stripe_events",
        })
        assert result.output_data["found"] is False
        assert result.output_data["webhook_id"] is None
