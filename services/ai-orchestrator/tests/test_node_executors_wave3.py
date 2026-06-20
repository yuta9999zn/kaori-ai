"""
Unit tests for wave 3 (commit 6) executors:
  publish_insight / publish_alert / create_task / display_dashboard /
  save_to_database / call_api / trigger_workflow / generate_report /
  validate / read_email

Mock strategy: monkey-patch shared.db.acquire_for_tenant with a fake
context manager exposing a fake connection. validate is pure (no mocks).
call_api uses httpx — patch httpx.AsyncClient.
"""
from __future__ import annotations

import pytest
from datetime import datetime, timezone
from uuid import uuid4

from workflow_runtime.node_executor import (
    NodeContext,
    NodeExecutorError,
    REGISTRY,
)
from workflow_runtime.executors.output import (
    CreateTaskExecutor,
    DisplayDashboardExecutor,
    PublishAlertExecutor,
    PublishInsightExecutor,
    SAVE_TABLE_WHITELIST,
    SaveToDatabaseExecutor,
)
from workflow_runtime.executors.action import (
    CallApiExecutor,
    GenerateReportExecutor,
    TriggerWorkflowExecutor,
    _allowed_hosts,
)
from workflow_runtime.executors.validate_exec import ValidateExecutor
from workflow_runtime.executors.data import ReadEmailExecutor
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


class _FakeRow(dict):
    def __getitem__(self, key):
        return super().__getitem__(key)


def _fake_db(monkeypatch, *, fetchrow_return=None, execute_return="INSERT 0 1"):
    """Patch shared.db.acquire_for_tenant with a controllable fake.
    Returns a 'spy' dict tracking calls."""
    spy = {"fetchrow_calls": [], "execute_calls": []}

    class _Conn:
        async def fetchrow(self, sql, *args):
            spy["fetchrow_calls"].append((sql, args))
            return fetchrow_return
        async def execute(self, sql, *args):
            spy["execute_calls"].append((sql, args))
            return execute_return
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
    return spy


# ─── Registry / coverage ──────────────────────────────────────────


class TestWave3Registry:
    def test_all_wave3_executors_registered(self):
        keys = (
            "publish_insight", "publish_alert", "create_task",
            "display_dashboard", "save_to_database",
            "call_api", "trigger_workflow", "generate_report",
            "validate", "read_email",
        )
        for k in keys:
            assert REGISTRY.has(k), f"{k} missing from registry"

    def test_registry_total_at_least_26(self):
        # 6 wave1 + 2 wave2a + 8 wave2b + 10 wave3 = 26 minimum.
        # Subsequent waves can add more.
        assert len(REGISTRY.list_keys()) >= 26


class TestWave3SideEffectClasses:
    def test_classes(self):
        assert PublishInsightExecutor.side_effect_class == SideEffectClass.WRITE_NON_IDEMPOTENT
        assert PublishAlertExecutor.side_effect_class == SideEffectClass.WRITE_NON_IDEMPOTENT
        assert CreateTaskExecutor.side_effect_class == SideEffectClass.WRITE_IDEMPOTENT
        assert DisplayDashboardExecutor.side_effect_class == SideEffectClass.WRITE_IDEMPOTENT
        assert SaveToDatabaseExecutor.side_effect_class == SideEffectClass.WRITE_IDEMPOTENT
        assert CallApiExecutor.side_effect_class == SideEffectClass.EXTERNAL
        assert TriggerWorkflowExecutor.side_effect_class == SideEffectClass.WRITE_NON_IDEMPOTENT
        assert GenerateReportExecutor.side_effect_class == SideEffectClass.WRITE_IDEMPOTENT
        assert ValidateExecutor.side_effect_class == SideEffectClass.PURE
        assert ReadEmailExecutor.side_effect_class == SideEffectClass.READ_ONLY


# ─── publish_insight ──────────────────────────────────────────────


class TestPublishInsight:
    @pytest.mark.asyncio
    async def test_missing_title_raises(self):
        with pytest.raises(NodeExecutorError):
            await PublishInsightExecutor().execute(_ctx(), {"body": "x"})

    @pytest.mark.asyncio
    async def test_invalid_severity_raises(self):
        with pytest.raises(NodeExecutorError):
            await PublishInsightExecutor().execute(_ctx(), {
                "title": "x", "body": "y", "severity": "panic",
            })

    @pytest.mark.asyncio
    async def test_confidence_out_of_range(self):
        with pytest.raises(NodeExecutorError):
            await PublishInsightExecutor().execute(_ctx(), {
                "title": "x", "body": "y", "confidence": 1.5,
            })

    @pytest.mark.asyncio
    async def test_successful_insert(self, monkeypatch):
        insight_id = uuid4()
        _fake_db(monkeypatch,
                  fetchrow_return=_FakeRow(insight_id=insight_id))
        result = await PublishInsightExecutor().execute(_ctx(), {
            "title":      "Doanh thu Q1 giảm",
            "body":       "Phân tích sâu...",
            "severity":   "critical",
            "confidence": 0.83,
            "tags":       ["revenue", "Q1"],
            "source_data": {"chart_url": "/chart/x"},
        })
        assert result.output_data["severity"] == "critical"
        assert result.output_data["insight_id"] == str(insight_id)

    @pytest.mark.asyncio
    async def test_body_dict_serialised(self, monkeypatch):
        _fake_db(monkeypatch, fetchrow_return=_FakeRow(insight_id=uuid4()))
        result = await PublishInsightExecutor().execute(_ctx(), {
            "title": "x",
            "body":  {"k": "v"},  # dict body — gets json.dumps'd
        })
        assert result.status == "completed"


# ─── publish_alert ────────────────────────────────────────────────


class TestPublishAlert:
    @pytest.mark.asyncio
    async def test_missing_code_raises(self):
        with pytest.raises(NodeExecutorError):
            await PublishAlertExecutor().execute(_ctx(), {"message": "x"})

    @pytest.mark.asyncio
    async def test_target_role_uppercased(self, monkeypatch):
        captured = {"args": None}

        class _Conn:
            async def fetchrow(self, sql, *args):
                captured["args"] = args
                return _FakeRow(alert_id=uuid4())

        class _CM:
            async def __aenter__(self): return _Conn()
            async def __aexit__(self, *a): return False

        import ai_orchestrator.shared.db as _db
        monkeypatch.setattr(_db, "acquire_for_tenant", lambda _: _CM())

        result = await PublishAlertExecutor().execute(_ctx(), {
            "code": "SLA_BREACH", "message": "Late!",
            "target_role": "manager",  # lowercase input
        })
        assert result.output_data["target_role"] == "MANAGER"
        assert captured["args"][6] == "MANAGER"


# ─── create_task ──────────────────────────────────────────────────


class TestCreateTask:
    @pytest.mark.asyncio
    async def test_task_key_required(self):
        with pytest.raises(NodeExecutorError):
            await CreateTaskExecutor().execute(_ctx(), {"title": "x"})

    @pytest.mark.asyncio
    async def test_invalid_assignee_uuid(self):
        with pytest.raises(NodeExecutorError):
            await CreateTaskExecutor().execute(_ctx(), {
                "task_key": "k1", "title": "x",
                "assignee_user_id": "not-a-uuid",
            })

    @pytest.mark.asyncio
    async def test_invalid_priority(self):
        with pytest.raises(NodeExecutorError):
            await CreateTaskExecutor().execute(_ctx(), {
                "task_key": "k1", "title": "x",
                "priority": "panic",
            })

    @pytest.mark.asyncio
    async def test_upsert_returns_status(self, monkeypatch):
        task_id = uuid4()
        _fake_db(monkeypatch,
                  fetchrow_return=_FakeRow(task_id=task_id, inserted=True))
        result = await CreateTaskExecutor().execute(_ctx(), {
            "task_key":      "approval-INV-001",
            "title":         "Duyệt hoá đơn INV-001",
            "assignee_role": "manager",
            "priority":      "high",
        })
        assert result.output_data["status"] == "created"
        assert result.output_data["task_id"] == str(task_id)


# ─── display_dashboard ────────────────────────────────────────────


class TestDisplayDashboard:
    @pytest.mark.asyncio
    async def test_missing_keys_raises(self):
        with pytest.raises(NodeExecutorError):
            await DisplayDashboardExecutor().execute(_ctx(), {})

    @pytest.mark.asyncio
    async def test_payload_must_be_dict(self):
        with pytest.raises(NodeExecutorError):
            await DisplayDashboardExecutor().execute(_ctx(), {
                "dashboard_key": "d", "tile_key": "t",
                "payload": "not a dict",
            })

    @pytest.mark.asyncio
    async def test_upsert_success(self, monkeypatch):
        _fake_db(monkeypatch,
                  fetchrow_return=_FakeRow(tile_id=uuid4(), inserted=False))
        result = await DisplayDashboardExecutor().execute(_ctx(), {
            "dashboard_key": "sales_director",
            "tile_key":      "pipeline_value",
            "payload":       {"total": 12_500_000_000},
        })
        assert result.output_data["status"] == "updated"


# ─── save_to_database ────────────────────────────────────────────


class TestSaveToDatabase:
    @pytest.mark.asyncio
    async def test_unknown_table_raises(self):
        with pytest.raises(NodeExecutorError):
            await SaveToDatabaseExecutor().execute(_ctx(), {
                "table": "silver_transactions",  # not in save whitelist
                "values": {"x": 1},
            })

    @pytest.mark.asyncio
    async def test_unknown_column_raises(self):
        with pytest.raises(NodeExecutorError):
            await SaveToDatabaseExecutor().execute(_ctx(), {
                "table":  "workflow_alerts",
                "values": {"password": "leak"},  # not in allowed cols
            })

    @pytest.mark.asyncio
    async def test_dict_value_auto_jsonified(self, monkeypatch):
        spy = _fake_db(monkeypatch,
                        fetchrow_return=_FakeRow(alert_id=uuid4()))
        await SaveToDatabaseExecutor().execute(_ctx(), {
            "table": "workflow_alerts",
            "values": {
                "code":    "X",
                "message": "msg",
                "payload": {"nested": "value"},
            },
        })
        # Last fetchrow's args should have dict converted to JSON string
        args = spy["fetchrow_calls"][0][1]
        assert any(isinstance(a, str) and '"nested"' in a for a in args)


# ─── validate (pure compute) ─────────────────────────────────────


class TestValidate:
    @pytest.mark.asyncio
    async def test_type_match_pass(self):
        result = await ValidateExecutor().execute(_ctx(), {
            "data":   {"age": 25, "name": "An"},
            "schema": {
                "type": "object",
                "required": ["age", "name"],
                "properties": {
                    "age":  {"type": "integer", "minimum": 0},
                    "name": {"type": "string", "minLength": 1},
                },
            },
        })
        assert result.output_data["valid"] is True
        assert result.output_data["errors"] == []

    @pytest.mark.asyncio
    async def test_missing_required(self):
        result = await ValidateExecutor().execute(_ctx(), {
            "data":   {"age": 25},
            "schema": {
                "type": "object",
                "required": ["age", "name"],
                "properties": {"name": {"type": "string"}},
            },
        })
        assert result.output_data["valid"] is False
        assert any("name" in e for e in result.output_data["errors"])

    @pytest.mark.asyncio
    async def test_numeric_out_of_range(self):
        result = await ValidateExecutor().execute(_ctx(), {
            "data":   75,
            "schema": {"type": "number", "minimum": 0, "maximum": 50},
        })
        assert result.output_data["valid"] is False

    @pytest.mark.asyncio
    async def test_enum_match(self):
        result = await ValidateExecutor().execute(_ctx(), {
            "data":   "VND",
            "schema": {"type": "string", "enum": ["USD", "VND", "EUR"]},
        })
        assert result.output_data["valid"] is True

    @pytest.mark.asyncio
    async def test_pattern_check(self):
        result = await ValidateExecutor().execute(_ctx(), {
            "data":   "abc123",
            "schema": {"type": "string", "pattern": r"^[a-z]+\d+$"},
        })
        assert result.output_data["valid"] is True

    @pytest.mark.asyncio
    async def test_strict_false_demotes_errors(self):
        result = await ValidateExecutor().execute(_ctx(), {
            "data":   "wrong",
            "schema": {"type": "integer"},
            "strict": False,
        })
        assert result.output_data["valid"] is True
        assert len(result.output_data["warnings"]) >= 1

    @pytest.mark.asyncio
    async def test_array_min_items(self):
        result = await ValidateExecutor().execute(_ctx(), {
            "data":   [1, 2],
            "schema": {"type": "array", "minItems": 3},
        })
        assert result.output_data["valid"] is False

    @pytest.mark.asyncio
    async def test_nested_object_property(self):
        result = await ValidateExecutor().execute(_ctx(), {
            "data": {"user": {"age": -5}},
            "schema": {
                "type": "object",
                "properties": {
                    "user": {
                        "type": "object",
                        "properties": {"age": {"type": "integer", "minimum": 0}},
                    },
                },
            },
        })
        assert result.output_data["valid"] is False
        assert any("user.age" in e for e in result.output_data["errors"])


# ─── call_api ────────────────────────────────────────────────────


class TestCallApi:
    @pytest.mark.asyncio
    async def test_missing_url_raises(self):
        with pytest.raises(NodeExecutorError):
            await CallApiExecutor().execute(_ctx(), {})

    @pytest.mark.asyncio
    async def test_invalid_method_raises(self):
        with pytest.raises(NodeExecutorError):
            await CallApiExecutor().execute(_ctx(), {
                "url": "http://llm-gateway/x", "method": "PATCH",
            })

    @pytest.mark.asyncio
    async def test_disallowed_host_raises(self):
        with pytest.raises(NodeExecutorError, match="whitelist"):
            await CallApiExecutor().execute(_ctx(), {
                "url": "https://evil.example.com/api", "method": "POST",
            })

    @pytest.mark.asyncio
    async def test_timeout_out_of_range(self):
        with pytest.raises(NodeExecutorError):
            await CallApiExecutor().execute(_ctx(), {
                "url": "http://llm-gateway/x", "timeout_s": 9999,
            })

    @pytest.mark.asyncio
    async def test_successful_call_and_dedup(self, monkeypatch):
        # Clear the cache between tests
        CallApiExecutor._DEDUP_CACHE.clear()

        class _Resp:
            status_code = 200
            text = "OK"
            def json(self): return {"ok": True}

        class _Client:
            def __init__(self, *a, **k): pass
            async def __aenter__(self): return self
            async def __aexit__(self, *a): return False
            async def request(self, *a, **k): return _Resp()
            async def get(self, *a, **k): return _Resp()
            async def delete(self, *a, **k): return _Resp()

        import workflow_runtime.executors.action as _action
        monkeypatch.setattr(_action.httpx, "AsyncClient", _Client)

        ctx = _ctx()
        # First call: live, dedup_hit=False
        result1 = await CallApiExecutor().execute(ctx, {
            "url": "http://llm-gateway/health", "method": "GET",
        })
        assert result1.output_data["dedup_hit"] is False
        # Second identical call same ctx: dedup_hit=True
        result2 = await CallApiExecutor().execute(ctx, {
            "url": "http://llm-gateway/health", "method": "GET",
        })
        assert result2.output_data["dedup_hit"] is True

    def test_allowed_hosts_env_override(self, monkeypatch):
        monkeypatch.setenv("WORKFLOW_CALL_API_ALLOWED_HOSTS", "foo.com,bar.com")
        hosts = _allowed_hosts()
        assert "foo.com" in hosts
        assert "bar.com" in hosts


# ─── SSRF guard (fix 1: tighter default · fix 2: IP denylist) ─────


class TestSsrfGuard:
    def test_default_allowlist_excludes_localhost(self, monkeypatch):
        # Fix 1: loopback names must NOT be reachable by default — they let a
        # workflow author hit any local port (Ollama :11434, Vault :8200, ...).
        monkeypatch.delenv("WORKFLOW_CALL_API_ALLOWED_HOSTS", raising=False)
        hosts = _allowed_hosts()
        assert "localhost" not in hosts
        assert "127.0.0.1" not in hosts

    def test_default_allowlist_keeps_internal_services(self, monkeypatch):
        # Internal service-to-service calls the runner legitimately makes.
        monkeypatch.delenv("WORKFLOW_CALL_API_ALLOWED_HOSTS", raising=False)
        hosts = _allowed_hosts()
        assert "llm-gateway" in hosts
        assert "notification-service" in hosts

    def test_is_blocked_ip_loopback_linklocal_metadata(self):
        from workflow_runtime.executors.action import _is_blocked_ip
        for ip in ("127.0.0.1", "127.0.0.5", "169.254.169.254",
                   "0.0.0.0", "::1", "fe80::1"):
            assert _is_blocked_ip(ip) is True, ip

    def test_is_blocked_ip_allows_public_and_private(self):
        # Private ranges (172.16/12, 10/8, 192.168/16) stay ALLOWED — internal
        # services resolve to Docker-bridge private IPs; blocking them would
        # break legitimate service-to-service calls.
        from workflow_runtime.executors.action import _is_blocked_ip
        for ip in ("8.8.8.8", "172.17.0.2", "10.0.0.5", "192.168.1.1"):
            assert _is_blocked_ip(ip) is False, ip

    @pytest.mark.asyncio
    async def test_allowlisted_host_resolving_to_metadata_blocked(self, monkeypatch):
        # Fix 2: even an operator-allowlisted hostname is rejected if it
        # resolves to a metadata/loopback IP (DNS-rebinding / TOCTOU defense).
        import workflow_runtime.executors.action as _action
        monkeypatch.setenv("WORKFLOW_CALL_API_ALLOWED_HOSTS", "partner.example.com")
        monkeypatch.setattr(_action, "_resolve_host_ips",
                            lambda host: ["169.254.169.254"])
        with pytest.raises(NodeExecutorError, match="SSRF"):
            await CallApiExecutor().execute(_ctx(), {
                "url": "https://partner.example.com/x", "method": "GET",
            })

    @pytest.mark.asyncio
    async def test_allowlisted_host_resolving_to_loopback_blocked(self, monkeypatch):
        import workflow_runtime.executors.action as _action
        monkeypatch.setenv("WORKFLOW_CALL_API_ALLOWED_HOSTS", "partner.example.com")
        monkeypatch.setattr(_action, "_resolve_host_ips",
                            lambda host: ["127.0.0.1"])
        with pytest.raises(NodeExecutorError, match="SSRF"):
            await CallApiExecutor().execute(_ctx(), {
                "url": "https://partner.example.com/x", "method": "GET",
            })

    @pytest.mark.asyncio
    async def test_external_host_requires_https(self, monkeypatch):
        # Fix 3: external-class hosts must use TLS — plaintext http is refused.
        import workflow_runtime.executors.action as _action
        monkeypatch.setenv("WORKFLOW_CALL_API_EXTERNAL_HOSTS", "partner.example.com")
        monkeypatch.setattr(_action, "_resolve_host_ips", lambda host: ["93.184.216.34"])
        with pytest.raises(NodeExecutorError, match="https"):
            await CallApiExecutor().execute(_ctx(), {
                "url": "http://partner.example.com/x", "method": "GET",
            })

    @pytest.mark.asyncio
    async def test_external_host_requires_port_443(self, monkeypatch):
        import workflow_runtime.executors.action as _action
        monkeypatch.setenv("WORKFLOW_CALL_API_EXTERNAL_HOSTS", "partner.example.com")
        monkeypatch.setattr(_action, "_resolve_host_ips", lambda host: ["93.184.216.34"])
        with pytest.raises(NodeExecutorError, match="443"):
            await CallApiExecutor().execute(_ctx(), {
                "url": "https://partner.example.com:8443/x", "method": "GET",
            })

    @pytest.mark.asyncio
    async def test_external_host_https_443_allowed(self, monkeypatch):
        import workflow_runtime.executors.action as _action
        CallApiExecutor._DEDUP_CACHE.clear()
        monkeypatch.setenv("WORKFLOW_CALL_API_EXTERNAL_HOSTS", "partner.example.com")
        monkeypatch.setattr(_action, "_resolve_host_ips", lambda host: ["93.184.216.34"])

        class _Resp:
            status_code = 200
            text = "OK"
            def json(self): return {"ok": True}

        class _Client:
            def __init__(self, *a, **k): pass
            async def __aenter__(self): return self
            async def __aexit__(self, *a): return False
            async def get(self, *a, **k): return _Resp()

        monkeypatch.setattr(_action.httpx, "AsyncClient", _Client)
        result = await CallApiExecutor().execute(_ctx(), {
            "url": "https://partner.example.com/v1/refund", "method": "GET",
        })
        assert result.output_data["status_code"] == 200

    @pytest.mark.asyncio
    async def test_internal_host_allows_plain_http(self, monkeypatch):
        # Internal-class hosts keep http + non-443 ports (service-to-service).
        import workflow_runtime.executors.action as _action
        CallApiExecutor._DEDUP_CACHE.clear()
        monkeypatch.setattr(_action, "_resolve_host_ips", lambda host: ["172.17.0.4"])

        class _Resp:
            status_code = 200
            text = "OK"
            def json(self): return {"ok": True}

        class _Client:
            def __init__(self, *a, **k): pass
            async def __aenter__(self): return self
            async def __aexit__(self, *a): return False
            async def get(self, *a, **k): return _Resp()

        monkeypatch.setattr(_action.httpx, "AsyncClient", _Client)
        result = await CallApiExecutor().execute(_ctx(), {
            "url": "http://llm-gateway:8095/health", "method": "GET",
        })
        assert result.output_data["status_code"] == 200

    @pytest.mark.asyncio
    async def test_unresolvable_host_allowed_through_to_http(self, monkeypatch):
        # If resolution yields nothing (e.g. CI sandbox), the allowlist already
        # vouched for the host — proceed; httpx will fail on its own if dead.
        import workflow_runtime.executors.action as _action
        CallApiExecutor._DEDUP_CACHE.clear()
        monkeypatch.setattr(_action, "_resolve_host_ips", lambda host: [])

        class _Resp:
            status_code = 200
            text = "OK"
            def json(self): return {"ok": True}

        class _Client:
            def __init__(self, *a, **k): pass
            async def __aenter__(self): return self
            async def __aexit__(self, *a): return False
            async def get(self, *a, **k): return _Resp()

        monkeypatch.setattr(_action.httpx, "AsyncClient", _Client)
        result = await CallApiExecutor().execute(_ctx(), {
            "url": "http://llm-gateway/health", "method": "GET",
        })
        assert result.output_data["status_code"] == 200


# ─── trigger_workflow ────────────────────────────────────────────


class TestTriggerWorkflow:
    @pytest.mark.asyncio
    async def test_missing_target_raises(self):
        with pytest.raises(NodeExecutorError):
            await TriggerWorkflowExecutor().execute(_ctx(), {})

    @pytest.mark.asyncio
    async def test_invalid_target_uuid(self):
        with pytest.raises(NodeExecutorError):
            await TriggerWorkflowExecutor().execute(_ctx(), {
                "target_workflow_id": "not-a-uuid",
            })

    @pytest.mark.asyncio
    async def test_target_not_in_tenant(self, monkeypatch):
        _fake_db(monkeypatch, fetchrow_return=None)
        with pytest.raises(NodeExecutorError, match="not found"):
            await TriggerWorkflowExecutor().execute(_ctx(), {
                "target_workflow_id": str(uuid4()),
            })


# ─── generate_report ─────────────────────────────────────────────


class TestGenerateReport:
    @pytest.mark.asyncio
    async def test_missing_template_raises(self):
        with pytest.raises(NodeExecutorError):
            await GenerateReportExecutor().execute(_ctx(), {})

    @pytest.mark.asyncio
    async def test_missing_title_raises(self):
        with pytest.raises(NodeExecutorError):
            await GenerateReportExecutor().execute(_ctx(), {
                "report_template_id": "monthly_pdf",
            })

    @pytest.mark.asyncio
    async def test_invalid_recipients_filtered(self, monkeypatch):
        spy = _fake_db(monkeypatch,
                        fetchrow_return=_FakeRow(task_id=uuid4(), inserted=True))
        result = await GenerateReportExecutor().execute(_ctx(), {
            "report_template_id": "x",
            "report_title":       "y",
            "recipient_emails":   ["valid@ok.vn", "not-email", "second@x.com"],
        })
        # The 'not-email' gets filtered; metadata should record 2 recipients
        assert result.output_data["recipient_count"] == 2


# ─── read_email ──────────────────────────────────────────────────


class TestReadEmail:
    @pytest.mark.asyncio
    async def test_missing_queue_key_raises(self):
        with pytest.raises(NodeExecutorError):
            await ReadEmailExecutor().execute(_ctx(), {})

    @pytest.mark.asyncio
    async def test_no_pending_returns_found_false(self, monkeypatch):
        _fake_db(monkeypatch, fetchrow_return=None)
        result = await ReadEmailExecutor().execute(_ctx(), {
            "queue_key": "ap_invoices",
        })
        assert result.output_data["found"] is False
        assert result.output_data["email_id"] is None
