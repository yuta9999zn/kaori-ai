"""
P2-S15 — node_type_catalog (mig 068) + production templates (mig 069) +
agent studio builder palette.

Comprehensive test suite per anh's "chuẩn chỉ + hiệu năng + phi chức năng"
template (reference: tests/test_p2_s14_pm_algorithms.py). Layout:

  1. Mig 068 shape          — 45 rows, 6 categories, K-17 5-value enum
  2. Mig 069 shape          — 25 templates, industry_vertical, JSON wellformed
  3. /workflow-node-types  — list + category filter + ordering
  4. /workflow-templates    — industry filter (NEW for P2-S15)
  5. /shared/agents/.../palette  — buckets + filter + curation invariants
  6. Tenant isolation       — header required, never from body (K-12)
  7. Determinism            — repeated calls return identical structure
  8. Performance            — 45-row catalog + 25-template list bounded latency

Mig shape tests are file-level greps (no DB needed). Router tests mock
`acquire_for_tenant` per existing pattern (test_workflow_builder_router.py).
"""
from __future__ import annotations

import json
import re
import time
from contextlib import asynccontextmanager
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient


ENTERPRISE = "11111111-1111-1111-1111-111111111111"
HEADERS = {"X-Enterprise-ID": ENTERPRISE}

REPO_ROOT = Path(__file__).resolve().parents[3]
MIG_DIR = REPO_ROOT / "infrastructure" / "postgres" / "migrations"


# ═════════════════════════════════════════════════════════════════════
# Mock fixtures
# ═════════════════════════════════════════════════════════════════════


def _make_conn() -> AsyncMock:
    conn = AsyncMock()
    conn.fetch.return_value = []
    conn.fetchrow.return_value = None
    conn.fetchval.return_value = 45
    return conn


def _tenant_ctx(conn):
    @asynccontextmanager
    async def _fake(_enterprise_id):
        yield conn
    return _fake


def _catalog_row(node_type_key: str, category: str = "data_input",
                 side_effect_class: str = "read_only",
                 is_irreversible: bool = False,
                 requires_saga: bool = False,
                 cost_band: str = "low",
                 pricing_tier_required=None,
                 sort_order: int = 11,
                 description_vi: str = "test desc",
                 default_retry_policy=None,
                 config_schema_json=None,
                 ui_schema_json=None,
                 type_version: int = 1,
                 is_trigger: bool = False,
                 rate_limit_json=None,
                 compensating_action=None) -> dict:
    """Mock row resembling asyncpg.Record (supports __getitem__)."""
    data = {
        "node_type_key": node_type_key,
        "category": category,
        "side_effect_class": side_effect_class,
        "is_irreversible": is_irreversible,
        "requires_saga": requires_saga,
        "cost_band": cost_band,
        "pricing_tier_required": pricing_tier_required,
        "sort_order": sort_order,
        "description_vi": description_vi,
        "default_retry_policy": default_retry_policy or {
            "max_attempts": 3, "backoff_seconds": 1
        },
        "config_schema_json": config_schema_json or {"type": "object"},
        "ui_schema_json": ui_schema_json if ui_schema_json is not None else {},  # ADR-0034 B4
        "type_version": type_version,                                            # ADR-0034 B3
        "is_trigger": is_trigger,                                                # ADR-0035 B6
        "rate_limit_json": rate_limit_json,
        "compensating_action": compensating_action,
    }
    r = MagicMock()
    r.__getitem__ = lambda _self, k: data[k]
    r.get = lambda k, default=None: data.get(k, default)
    return r


def _template_row(**overrides) -> MagicMock:
    base = {
        "template_id": uuid4(),
        "display_name": "Campaign Launch",
        "display_name_vi": "Khởi chạy chiến dịch marketing",
        "description": "Test description",
        "department_type": "marketing",
        "category": "campaign",
        "industry_vertical": "general",
        "estimated_setup_minutes": 10,
        "workflow_definition": {"nodes": [{"client_id": "n1"}], "edges": []},
    }
    base.update(overrides)
    r = MagicMock()
    r.__getitem__ = lambda _self, k: base[k]
    r.get = lambda k, default=None: base.get(k, default)
    return r


def _make_app() -> FastAPI:
    """Build a minimal FastAPI app with only the routers under test."""
    from ai_orchestrator.routers import agents_studio_builder, workflow_builder
    app = FastAPI()
    app.include_router(workflow_builder.router)
    app.include_router(agents_studio_builder.router)
    return app


# ═════════════════════════════════════════════════════════════════════
# 1. Mig 068 shape — 45 rows, 6 categories, K-17 enum
# ═════════════════════════════════════════════════════════════════════


class TestMig068Shape:

    @pytest.fixture(scope="class")
    def mig_text(self) -> str:
        path = MIG_DIR / "068_node_type_catalog.sql"
        return path.read_text(encoding="utf-8")

    def test_table_creation_present(self, mig_text: str):
        assert "CREATE TABLE IF NOT EXISTS node_type_catalog" in mig_text

    def test_k17_check_constraint_locked(self, mig_text: str):
        # K-17 invariant: side_effect_class ∈ 5 values
        assert "chk_nt_side_effect" in mig_text
        for cls in ("pure", "read_only", "write_idempotent",
                    "write_non_idempotent", "external"):
            assert f"'{cls}'" in mig_text, f"Missing K-17 class {cls}"

    def test_category_check_constraint_6_values(self, mig_text: str):
        assert "chk_nt_category" in mig_text
        for cat in ("data_input", "processing", "decision", "ai",
                    "action", "output"):
            assert f"'{cat}'" in mig_text, f"Missing category {cat}"

    def test_pricing_tier_check_4_values(self, mig_text: str):
        assert "chk_nt_pricing" in mig_text
        for tier in ("PILOT", "BASIC", "MID", "MAX"):
            assert f"'{tier}'" in mig_text

    def test_45_node_type_keys_seeded(self, mig_text: str):
        # 45 expected node_type_keys per WORKFLOW_SYSTEM §2.2-2.7
        expected = {
            # data_input (8)
            "read_table", "read_file_upload", "read_api", "read_webhook",
            "read_form_submission", "read_email", "read_calendar", "read_chat",
            # processing (10)
            "filter", "aggregate", "join", "transform", "validate", "enrich",
            "sort", "deduplicate", "split", "merge",
            # decision (5)
            "if_else", "switch", "wait_for_condition", "scheduled_trigger",
            "approval_gate",
            # ai (8)
            "call_insight_engine", "call_recommendation_engine",
            "call_risk_detection", "call_forecasting", "generate_narrative",
            "classify_text", "extract_entities", "rag_query",
            # action (8)
            "send_email", "send_sms", "send_chat_message", "create_task",
            "call_api", "trigger_workflow", "export_file", "generate_report",
            # output (6)
            "save_to_database", "update_record", "publish_alert",
            "publish_insight", "display_dashboard", "log",
        }
        assert len(expected) == 45
        for key in expected:
            assert f"'{key}'" in mig_text, f"Mig 068 missing seed for {key}"

    def test_irreversible_action_nodes_flagged(self, mig_text: str):
        # send_email + send_sms + send_chat_message MUST have is_irreversible=TRUE
        # The 3 must appear with TRUE somewhere after their key
        irreversible_keys = ("send_email", "send_sms", "send_chat_message")
        for k in irreversible_keys:
            # Find the row block + assert TRUE marker exists in proximity
            idx = mig_text.find(f"'{k}'")
            assert idx >= 0
            block = mig_text[idx:idx + 800]
            assert "TRUE" in block, f"{k} must be marked irreversible"

    def test_index_present(self, mig_text: str):
        assert "idx_node_type_catalog_category" in mig_text


# ═════════════════════════════════════════════════════════════════════
# 2. Mig 069 shape — 25 templates, industry_vertical, JSON wellformed
# ═════════════════════════════════════════════════════════════════════


class TestMig069Shape:

    @pytest.fixture(scope="class")
    def mig_text(self) -> str:
        path = MIG_DIR / "069_production_templates_seed.sql"
        return path.read_text(encoding="utf-8")

    def test_industry_vertical_column_added(self, mig_text: str):
        assert "ADD COLUMN IF NOT EXISTS industry_vertical" in mig_text

    def test_industry_check_constraint(self, mig_text: str):
        assert "chk_industry_vertical" in mig_text
        for v in ("general", "retail", "manufacturing", "fintech",
                  "logistics", "healthcare", "fmcg", "saas"):
            assert f"'{v}'" in mig_text

    def test_industry_index_partial(self, mig_text: str):
        assert "idx_workflow_templates_industry" in mig_text
        assert "WHERE is_active = TRUE" in mig_text

    def test_exactly_25_template_inserts(self, mig_text: str):
        # Count `INSERT INTO workflow_templates` occurrences
        count = mig_text.count("INSERT INTO workflow_templates")
        assert count == 25, f"Expected 25 templates, got {count}"

    def test_5_department_types_covered(self, mig_text: str):
        # marketing/sales/customer_service/warehouse/finance — 5 each
        for dept in ("marketing", "sales", "customer_service",
                     "warehouse", "finance"):
            count = len(re.findall(rf"'{dept}', '", mig_text))
            assert count == 5, f"{dept} should appear 5x as dept tag (got {count})"

    def test_each_template_has_jsonb_payload(self, mig_text: str):
        # Every template line ends with `'::jsonb`
        count = mig_text.count("'::jsonb,")
        assert count == 25

    def test_workflow_definition_json_valid(self, mig_text: str):
        # Extract every JSON between `'{"nodes":` and `}'::jsonb` and parse
        pattern = re.compile(r"'(\{\"nodes\":.*?\})'::jsonb", re.DOTALL)
        matches = pattern.findall(mig_text)
        assert len(matches) == 25
        for blob in matches:
            # SQL escaped single quotes back to JSON
            data = json.loads(blob.replace("''", "'"))
            assert "nodes" in data and "edges" in data
            assert len(data["nodes"]) == 5, "Each template = 5 cards"
            assert len(data["edges"]) == 4, "5 cards = 4 sequential edges"
            # Each node must declare node_type_catalog_key (FK to mig 068)
            for n in data["nodes"]:
                assert "node_type_catalog_key" in n
                assert n["node_type_catalog_key"]  # non-empty


# ═════════════════════════════════════════════════════════════════════
# 3. GET /workflow-node-types — list + category filter + ordering
# ═════════════════════════════════════════════════════════════════════


class TestNodeTypesEndpoint:

    def test_basic_list_returns_all(self):
        from ai_orchestrator.routers import workflow_builder

        conn = _make_conn()
        # Simulate 3 rows of varying categories
        rows = [
            _catalog_row("read_table", "data_input", "read_only", sort_order=11),
            _catalog_row("filter", "processing", "pure", sort_order=21),
            _catalog_row("send_email", "action", "external",
                         is_irreversible=True, sort_order=51),
        ]
        conn.fetch.return_value = rows
        with patch.object(workflow_builder, "acquire_for_tenant", _tenant_ctx(conn)):
            app = _make_app()
            client = TestClient(app)
            r = client.get("/workflow-node-types", headers=HEADERS)
        assert r.status_code == 200, r.text
        data = r.json()
        assert len(data) == 3
        # Ordering enforced by SQL (sort_order ASC) — first row is data_input
        assert data[0]["node_type_key"] == "read_table"
        assert data[0]["category"] == "data_input"
        # K-17 field is plain string
        assert data[0]["side_effect_class"] == "read_only"

    def test_ui_schema_json_returned_for_builder(self):
        # ADR-0034 B4 — builder gets ui_schema_json (render hints) alongside the
        # validation schema; rows without hints default to {}.
        from ai_orchestrator.routers import workflow_builder

        conn = _make_conn()
        conn.fetch.return_value = [
            _catalog_row("send_email", "action", "external", sort_order=51,
                         ui_schema_json={"to": {"label_vi": "Người nhận", "widget": "email"}}),
            _catalog_row("filter", "processing", "pure", sort_order=21),  # no hints
        ]
        with patch.object(workflow_builder, "acquire_for_tenant", _tenant_ctx(conn)):
            client = TestClient(_make_app())
            r = client.get("/workflow-node-types", headers=HEADERS)
        assert r.status_code == 200, r.text
        data = r.json()
        assert data[0]["ui_schema_json"]["to"]["label_vi"] == "Người nhận"
        assert data[1]["ui_schema_json"] == {}              # default when no hints
        assert "config_schema_json" in data[0]              # validation source still there

    def test_type_version_returned_defaults_one(self):
        # ADR-0034 B3 — builder/audit sees the node-type version.
        from ai_orchestrator.routers import workflow_builder

        conn = _make_conn()
        conn.fetch.return_value = [
            _catalog_row("read_table", "data_input", "read_only"),            # default 1
            _catalog_row("generate_narrative", "ai", "external", type_version=2),
        ]
        with patch.object(workflow_builder, "acquire_for_tenant", _tenant_ctx(conn)):
            client = TestClient(_make_app())
            r = client.get("/workflow-node-types", headers=HEADERS)
        assert r.status_code == 200, r.text
        data = r.json()
        assert data[0]["type_version"] == 1
        assert data[1]["type_version"] == 2

    def test_is_trigger_returned(self):
        # ADR-0035 B6 — builder sees which node types are triggers (entry points).
        from ai_orchestrator.routers import workflow_builder

        conn = _make_conn()
        conn.fetch.return_value = [
            _catalog_row("scheduled_trigger", "decision", "read_only", is_trigger=True),
            _catalog_row("filter", "processing", "pure"),
        ]
        with patch.object(workflow_builder, "acquire_for_tenant", _tenant_ctx(conn)):
            client = TestClient(_make_app())
            r = client.get("/workflow-node-types", headers=HEADERS)
        assert r.status_code == 200, r.text
        data = r.json()
        assert data[0]["is_trigger"] is True
        assert data[1]["is_trigger"] is False

    def test_category_filter_passes_through_sql(self):
        from ai_orchestrator.routers import workflow_builder

        conn = _make_conn()
        conn.fetch.return_value = [
            _catalog_row("if_else", "decision", "pure", sort_order=31)
        ]
        with patch.object(workflow_builder, "acquire_for_tenant", _tenant_ctx(conn)):
            app = _make_app()
            client = TestClient(app)
            r = client.get("/workflow-node-types?category=decision",
                           headers=HEADERS)
        assert r.status_code == 200
        # Verify SQL was called with the filter parameter
        called_sql = conn.fetch.await_args.args[0]
        assert "WHERE category =" in called_sql

    def test_category_filter_rejects_invalid_value(self):
        from ai_orchestrator.routers import workflow_builder

        conn = _make_conn()
        with patch.object(workflow_builder, "acquire_for_tenant", _tenant_ctx(conn)):
            app = _make_app()
            client = TestClient(app)
            r = client.get("/workflow-node-types?category=bogus",
                           headers=HEADERS)
        # FastAPI Query regex validation → 422
        assert r.status_code == 422

    def test_pricing_tier_field_passes_through(self):
        from ai_orchestrator.routers import workflow_builder

        conn = _make_conn()
        conn.fetch.return_value = [
            _catalog_row("call_insight_engine", "ai", "read_only",
                         cost_band="high", pricing_tier_required="BASIC",
                         rate_limit_json={"PILOT": 0, "BASIC": 100},
                         sort_order=41)
        ]
        with patch.object(workflow_builder, "acquire_for_tenant", _tenant_ctx(conn)):
            app = _make_app()
            client = TestClient(app)
            r = client.get("/workflow-node-types", headers=HEADERS)
        data = r.json()
        assert data[0]["pricing_tier_required"] == "BASIC"
        assert data[0]["rate_limit_json"] == {"PILOT": 0, "BASIC": 100}


# ═════════════════════════════════════════════════════════════════════
# 4. GET /workflow-templates ?industry= — P2-S15 filter (NEW)
# ═════════════════════════════════════════════════════════════════════


class TestWorkflowTemplatesIndustryFilter:

    def test_industry_filter_in_sql(self):
        from ai_orchestrator.routers import workflow_builder

        conn = _make_conn()
        conn.fetch.return_value = [_template_row(industry_vertical="saas")]
        with patch.object(workflow_builder, "acquire_for_tenant", _tenant_ctx(conn)):
            app = _make_app()
            client = TestClient(app)
            r = client.get("/workflow-templates?industry=saas", headers=HEADERS)
        assert r.status_code == 200
        called_sql = conn.fetch.await_args.args[0]
        assert "industry_vertical =" in called_sql

    def test_industry_filter_rejects_invalid(self):
        from ai_orchestrator.routers import workflow_builder

        conn = _make_conn()
        with patch.object(workflow_builder, "acquire_for_tenant", _tenant_ctx(conn)):
            app = _make_app()
            client = TestClient(app)
            r = client.get("/workflow-templates?industry=alien", headers=HEADERS)
        assert r.status_code == 422

    def test_template_out_includes_industry(self):
        from ai_orchestrator.routers import workflow_builder

        conn = _make_conn()
        conn.fetch.return_value = [_template_row(industry_vertical="retail")]
        with patch.object(workflow_builder, "acquire_for_tenant", _tenant_ctx(conn)):
            app = _make_app()
            client = TestClient(app)
            r = client.get("/workflow-templates", headers=HEADERS)
        data = r.json()
        assert data[0]["industry_vertical"] == "retail"

    def test_both_filters_compose(self):
        """dept + industry both in WHERE — SQL must AND them."""
        from ai_orchestrator.routers import workflow_builder

        conn = _make_conn()
        conn.fetch.return_value = []
        with patch.object(workflow_builder, "acquire_for_tenant", _tenant_ctx(conn)):
            app = _make_app()
            client = TestClient(app)
            r = client.get(
                "/workflow-templates?department_type=marketing&industry=saas",
                headers=HEADERS,
            )
        assert r.status_code == 200
        called_sql = conn.fetch.await_args.args[0]
        assert "department_type =" in called_sql
        assert "industry_vertical =" in called_sql


# ═════════════════════════════════════════════════════════════════════
# 5. /shared/agents/studio/builder/palette — buckets + curation
# ═════════════════════════════════════════════════════════════════════


class TestPaletteEndpoint:

    def test_palette_returns_grouped_buckets(self):
        from ai_orchestrator.routers import agents_studio_builder

        conn = _make_conn()
        conn.fetch.return_value = [
            _catalog_row("read_chat", "data_input", "read_only", sort_order=18),
            _catalog_row("call_insight_engine", "ai", "read_only",
                         pricing_tier_required="BASIC", sort_order=41),
            _catalog_row("if_else", "decision", "pure", sort_order=31),
            _catalog_row("send_chat_message", "action", "external",
                         is_irreversible=True, requires_saga=True, sort_order=53),
            _catalog_row("publish_insight", "output", "write_idempotent",
                         requires_saga=True, sort_order=64),
        ]
        conn.fetchval.return_value = 45
        with patch.object(agents_studio_builder, "acquire_for_tenant",
                          _tenant_ctx(conn)):
            app = _make_app()
            client = TestClient(app)
            r = client.get("/shared/agents/studio/builder/palette",
                           headers=HEADERS)
        assert r.status_code == 200, r.text
        body = r.json()
        # 5 buckets in response (intake / reasoning / decision / action / output)
        assert set(body["buckets"].keys()) == {
            "intake", "reasoning", "decision", "action", "output"
        }
        assert body["catalog_total"] == 45
        assert body["total_nodes"] == 5
        # Each PaletteNode carries its bucket label
        intake_nodes = body["buckets"]["intake"]
        assert intake_nodes[0]["bucket"] == "intake"
        assert intake_nodes[0]["category"] == "data_input"  # original mig 068 cat preserved

    def test_palette_bucket_filter(self):
        from ai_orchestrator.routers import agents_studio_builder

        conn = _make_conn()
        conn.fetch.return_value = [
            _catalog_row("call_insight_engine", "ai", "read_only", sort_order=41)
        ]
        with patch.object(agents_studio_builder, "acquire_for_tenant",
                          _tenant_ctx(conn)):
            app = _make_app()
            client = TestClient(app)
            r = client.get(
                "/shared/agents/studio/builder/palette?bucket=reasoning",
                headers=HEADERS,
            )
        assert r.status_code == 200
        body = r.json()
        # Only reasoning bucket present when filter applied
        assert list(body["buckets"].keys()) == ["reasoning"]

    def test_palette_bucket_filter_rejects_invalid(self):
        from ai_orchestrator.routers import agents_studio_builder

        conn = _make_conn()
        with patch.object(agents_studio_builder, "acquire_for_tenant",
                          _tenant_ctx(conn)):
            app = _make_app()
            client = TestClient(app)
            r = client.get(
                "/shared/agents/studio/builder/palette?bucket=foo",
                headers=HEADERS,
            )
        assert r.status_code == 422

    def test_palette_curation_drops_some_catalog_nodes(self):
        """Palette is curated subset — some 45-catalog nodes are excluded
        (e.g. read_form_submission for poll-style flows). Verify total
        bucketed keys < 45."""
        from ai_orchestrator.routers.agents_studio_builder import AGENT_PALETTE_BUCKETS

        total = sum(len(keys) for keys in AGENT_PALETTE_BUCKETS.values())
        assert total < 45, "Palette must be curated subset, not full catalog"
        assert total >= 20, "Palette too small — agent flows need enough nodes"

    def test_palette_curation_no_duplicate_keys(self):
        """A node_type_key must not appear in two buckets — else bucket_map
        collision in the router."""
        from ai_orchestrator.routers.agents_studio_builder import AGENT_PALETTE_BUCKETS

        seen: set[str] = set()
        for bucket, keys in AGENT_PALETTE_BUCKETS.items():
            for k in keys:
                assert k not in seen, f"Duplicate {k} in {bucket}"
                seen.add(k)


# ═════════════════════════════════════════════════════════════════════
# 6. Tenant isolation — header required (K-1 / K-12)
# ═════════════════════════════════════════════════════════════════════


class TestTenantIsolation:

    def test_node_types_requires_enterprise_header(self):
        app = _make_app()
        client = TestClient(app)
        r = client.get("/workflow-node-types")  # no header
        assert r.status_code == 422  # FastAPI missing required Header

    def test_palette_requires_enterprise_header(self):
        app = _make_app()
        client = TestClient(app)
        r = client.get("/shared/agents/studio/builder/palette")
        assert r.status_code == 422

    def test_workflow_templates_industry_requires_enterprise_header(self):
        app = _make_app()
        client = TestClient(app)
        r = client.get("/workflow-templates?industry=saas")
        assert r.status_code == 422

    def test_enterprise_header_must_be_uuid(self):
        app = _make_app()
        client = TestClient(app)
        r = client.get("/workflow-node-types",
                       headers={"X-Enterprise-ID": "not-a-uuid"})
        assert r.status_code == 422


# ═════════════════════════════════════════════════════════════════════
# 7. Determinism — same query → same response shape
# ═════════════════════════════════════════════════════════════════════


class TestDeterminism:

    def test_node_types_endpoint_is_stable_across_calls(self):
        """Two identical GETs return identical bodies (no nondeterminism
        in serialization, ordering, or hash-based dicts)."""
        from ai_orchestrator.routers import workflow_builder

        rows = [
            _catalog_row("read_table", "data_input", "read_only", sort_order=11),
            _catalog_row("filter", "processing", "pure", sort_order=21),
        ]
        conn = _make_conn()
        conn.fetch.return_value = rows
        with patch.object(workflow_builder, "acquire_for_tenant",
                          _tenant_ctx(conn)):
            app = _make_app()
            client = TestClient(app)
            r1 = client.get("/workflow-node-types", headers=HEADERS)
            r2 = client.get("/workflow-node-types", headers=HEADERS)
        assert r1.json() == r2.json()

    def test_palette_bucket_keys_are_ordered_consistently(self):
        from ai_orchestrator.routers.agents_studio_builder import AGENT_PALETTE_BUCKETS

        # Python 3.7+ dicts preserve insertion order — verify our constant
        # iterates in the documented bucket sequence
        ordered = list(AGENT_PALETTE_BUCKETS.keys())
        assert ordered == ["intake", "reasoning", "decision", "action", "output"]


# ═════════════════════════════════════════════════════════════════════
# 8. Performance — bounded latency for catalog endpoints
# ═════════════════════════════════════════════════════════════════════


class TestPerformance:

    def test_node_types_full_45_under_500ms(self):
        """45-row fetch + serialize must complete within 500ms on a mocked
        DB. This is the hot path FE builder calls on every open."""
        from ai_orchestrator.routers import workflow_builder

        # Build 45 synthetic rows
        rows = [
            _catalog_row(f"node_{i}", "data_input", "read_only",
                         sort_order=i)
            for i in range(45)
        ]
        conn = _make_conn()
        conn.fetch.return_value = rows
        with patch.object(workflow_builder, "acquire_for_tenant",
                          _tenant_ctx(conn)):
            app = _make_app()
            client = TestClient(app)
            t0 = time.perf_counter()
            for _ in range(10):  # avg over 10 calls to absorb cold start
                r = client.get("/workflow-node-types", headers=HEADERS)
                assert r.status_code == 200
            elapsed = (time.perf_counter() - t0) / 10
        assert elapsed < 0.5, f"Endpoint too slow: {elapsed:.3f}s per call"

    def test_palette_curation_lookup_is_O1(self):
        """Bucket map construction must be linear in palette size, not
        quadratic. 28 nodes × 5 buckets should not iterate > 200 times."""
        from ai_orchestrator.routers.agents_studio_builder import AGENT_PALETTE_BUCKETS

        op_count = 0
        bucket_map: dict[str, str] = {}
        for b, keys in AGENT_PALETTE_BUCKETS.items():
            for k in keys:
                op_count += 1
                bucket_map[k] = b
        assert op_count <= 60, f"Bucket map build too many ops: {op_count}"
        assert len(bucket_map) == op_count, "Duplicate keys would shrink dict"
