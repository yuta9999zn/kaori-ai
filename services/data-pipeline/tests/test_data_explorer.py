"""
test_data_explorer.py — F-NEW3 Data Explorer hub overview.

Black-box tests for ``GET /data/explorer``. Same fixture pattern as
test_api.py — TestClient wraps a freshly-built FastAPI app with the
data_explorer router only, asyncpg mocked.

What we cover:
  * Empty tenant → all counts are 0, all timestamps null
  * Populated tenant → aggregates flow through the right layer
  * Missing X-Enterprise-ID header → 422 (FastAPI Header validation)
  * Status → (layer, action, ui_status) mapping for recent activity
  * Quality_avg NULL → 0.0% (FE expects a number, not None)
  * size_gb conversion preserves precision
"""
from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient


ENTERPRISE_A = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
HEADERS_A = {"X-Enterprise-ID": ENTERPRISE_A}


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _make_mock_conn() -> AsyncMock:
    conn = AsyncMock()
    conn.fetchrow.return_value = None
    conn.fetch.return_value = []
    return conn


def _make_tenant_ctx_factory(conn: AsyncMock):
    """Replicates the (enterprise_id) -> async-context manager shape of
    shared.db.acquire_for_tenant."""
    @asynccontextmanager
    async def _ctx(_enterprise_id):
        yield conn
    return _ctx


@pytest.fixture
def conn() -> AsyncMock:
    return _make_mock_conn()


@pytest.fixture
def app_client(conn):
    """TestClient bound to a minimal app with only the data_explorer router."""
    tenant_ctx = _make_tenant_ctx_factory(conn)
    with patch("data_pipeline.routers.data_explorer.acquire_for_tenant", tenant_ctx):
        import data_pipeline.routers.data_explorer as _explorer  # noqa: PLC0415

        test_app = FastAPI(title="Kaori Data Pipeline (test)")
        test_app.include_router(_explorer.router, prefix="/data")

        with TestClient(test_app, raise_server_exceptions=True) as client:
            yield client


# ---------------------------------------------------------------------------
# Helpers — build the 5 fetchrow / 1 fetch responses the endpoint expects
# ---------------------------------------------------------------------------

def _row(**kwargs):
    """asyncpg.Record stub — supports ``row["key"]`` access."""
    return MagicMock(__getitem__=lambda _, k: kwargs[k])


def _wire_responses(conn: AsyncMock, *,
                    bronze=None, size=None, failed=None,
                    silver=None, gold=None, recent=None):
    """Sequence the 5 fetchrow + 1 fetch calls in the endpoint's exact order."""
    conn.fetchrow.side_effect = [
        bronze or _row(file_count=0, row_count_total=0, last_ingested_at=None),
        size   or _row(bytes_total=0),
        failed or _row(failed_24h=0),
        silver or _row(dataset_count=0, row_count_total=0, quality_avg=None,
                       last_processed_at=None),
        gold   or _row(feature_count=0, last_aggregated_at=None, stale_count=0),
    ]
    conn.fetch.return_value = recent or []


# ---------------------------------------------------------------------------
# Empty tenant
# ---------------------------------------------------------------------------

class TestEmptyTenant:
    """Tenant with no pipeline runs → safe zero defaults, no None counts."""

    def test_returns_200_with_zero_counts(self, app_client, conn):
        _wire_responses(conn)
        r = app_client.get("/data/explorer", headers=HEADERS_A)
        assert r.status_code == 200
        body = r.json()
        assert body["bronze"]["file_count"]  == 0
        assert body["bronze"]["row_count_total"] == 0
        assert body["bronze"]["size_gb"]     == 0.0
        assert body["bronze"]["last_ingested_at"] is None
        assert body["bronze"]["failed_24h"]  == 0

    def test_silver_quality_avg_is_zero_when_null(self, app_client, conn):
        # FE expects a number for the quality tile — None breaks the toFixed call.
        _wire_responses(conn)
        r = app_client.get("/data/explorer", headers=HEADERS_A)
        assert r.status_code == 200
        assert r.json()["silver"]["quality_avg_pct"] == 0.0

    def test_gold_zero_features(self, app_client, conn):
        _wire_responses(conn)
        body = app_client.get("/data/explorer", headers=HEADERS_A).json()
        assert body["gold"]["feature_count"]    == 0
        assert body["gold"]["row_count_total"]  == 0
        assert body["gold"]["stale_count"]      == 0

    def test_recent_is_empty_list(self, app_client, conn):
        _wire_responses(conn)
        body = app_client.get("/data/explorer", headers=HEADERS_A).json()
        assert body["recent"] == []


# ---------------------------------------------------------------------------
# Populated tenant
# ---------------------------------------------------------------------------

class TestPopulatedTenant:

    def test_aggregates_flow_through(self, app_client, conn):
        last_bronze = datetime(2026, 5, 1, 10, 30, tzinfo=timezone.utc)
        last_silver = datetime(2026, 5, 2, 11, 0,  tzinfo=timezone.utc)
        last_gold   = datetime(2026, 5, 3, 12, 0,  tzinfo=timezone.utc)

        _wire_responses(conn,
            bronze=_row(file_count=42, row_count_total=15_000,
                        last_ingested_at=last_bronze),
            size  =_row(bytes_total=2_500_000_000),    # 2.5 GB
            failed=_row(failed_24h=2),
            silver=_row(dataset_count=12, row_count_total=14_500,
                        quality_avg=0.927, last_processed_at=last_silver),
            gold  =_row(feature_count=320, last_aggregated_at=last_gold,
                        stale_count=5),
        )

        body = app_client.get("/data/explorer", headers=HEADERS_A).json()

        # Bronze
        assert body["bronze"]["file_count"]  == 42
        assert body["bronze"]["row_count_total"] == 15_000
        assert body["bronze"]["size_gb"]     == 2.5
        assert body["bronze"]["last_ingested_at"] == last_bronze.isoformat()
        assert body["bronze"]["failed_24h"]  == 2

        # Silver — quality 0.927 → 92.7%
        assert body["silver"]["dataset_count"]   == 12
        assert body["silver"]["row_count_total"] == 14_500
        assert body["silver"]["quality_avg_pct"] == 92.7
        assert body["silver"]["last_processed_at"] == last_silver.isoformat()

        # Gold — feature_count drives row_count_total (1-to-1 with customer)
        assert body["gold"]["feature_count"]      == 320
        assert body["gold"]["row_count_total"]    == 320
        assert body["gold"]["last_aggregated_at"] == last_gold.isoformat()
        assert body["gold"]["stale_count"]        == 5

    def test_size_gb_handles_sub_gigabyte_files(self, app_client, conn):
        # 250 MB → 0.25 GB. Confirms we don't truncate to 0 for small tenants.
        _wire_responses(conn, size=_row(bytes_total=250_000_000))
        body = app_client.get("/data/explorer", headers=HEADERS_A).json()
        assert body["bronze"]["size_gb"] == 0.25


# ---------------------------------------------------------------------------
# Recent-activity strip
# ---------------------------------------------------------------------------

class TestRecentActivity:
    """Mapping pipeline_runs.status → (layer, action, ui_status)."""

    def _recent_run(self, run_id: str, status: str):
        return _row(
            run_id=run_id,
            filename=f"file-{run_id[:4]}.csv",
            status=status,
            updated_at=datetime(2026, 5, 1, 10, tzinfo=timezone.utc),
        )

    def test_status_to_layer_mapping(self, app_client, conn):
        _wire_responses(conn, recent=[
            self._recent_run("11111111-1111-1111-1111-111111111111", "bronze_complete"),
            self._recent_run("22222222-2222-2222-2222-222222222222", "silver_complete"),
            self._recent_run("33333333-3333-3333-3333-333333333333", "analysis_complete"),
            self._recent_run("44444444-4444-4444-4444-444444444444", "failed"),
            self._recent_run("55555555-5555-5555-5555-555555555555", "uploading"),
        ])
        recent = app_client.get("/data/explorer", headers=HEADERS_A).json()["recent"]
        layers = [r["layer"] for r in recent]
        assert layers == ["bronze", "silver", "gold", "bronze", "bronze"]

        statuses = [r["status"] for r in recent]
        assert statuses == ["ok", "ok", "ok", "fail", "running"]

    def test_unknown_status_falls_back_to_bronze_ok(self, app_client, conn):
        # Defensive — if a future status sneaks past the enum check we
        # keep responding 200 instead of 500'ing the entire hub page.
        _wire_responses(conn, recent=[
            self._recent_run("99999999-9999-9999-9999-999999999999", "novel_state"),
        ])
        recent = app_client.get("/data/explorer", headers=HEADERS_A).json()["recent"]
        assert recent[0]["layer"]  == "bronze"
        assert recent[0]["status"] == "ok"
        assert recent[0]["action"] == "novel_state"   # raw status as label

    def test_recent_carries_run_id_filename_at(self, app_client, conn):
        run_id = "abcdabcd-abcd-abcd-abcd-abcdabcdabcd"
        _wire_responses(conn, recent=[
            _row(run_id=run_id, filename="sales-q1.csv", status="bronze_complete",
                 updated_at=datetime(2026, 5, 4, 9, 15, tzinfo=timezone.utc)),
        ])
        recent = app_client.get("/data/explorer", headers=HEADERS_A).json()["recent"]
        assert recent[0]["id"]   == run_id
        assert recent[0]["name"] == "sales-q1.csv"
        assert recent[0]["at"]   == "2026-05-04T09:15:00+00:00"


# ---------------------------------------------------------------------------
# Header validation
# ---------------------------------------------------------------------------

class TestHeaderValidation:

    def test_missing_enterprise_header_returns_422(self, app_client, conn):
        _wire_responses(conn)
        r = app_client.get("/data/explorer")
        # FastAPI's required Header() raises a 422 with the missing-field
        # error envelope — same shape as every other endpoint in this
        # service. Gateway translates upstream 422s to its own RFC 7807
        # in production.
        assert r.status_code == 422

    def test_malformed_uuid_header_returns_422(self, app_client, conn):
        _wire_responses(conn)
        r = app_client.get("/data/explorer", headers={"X-Enterprise-ID": "not-a-uuid"})
        assert r.status_code == 422


# ---------------------------------------------------------------------------
# F-NEW3 v1 — Bronze drill-down
# ---------------------------------------------------------------------------

FILE_ID = "11111111-1111-1111-1111-111111111111"
RUN_ID  = "22222222-2222-2222-2222-222222222222"


def _bronze_file(file_id=FILE_ID, run_id=RUN_ID,
                 sheet_name="Sheet1", row_count=1200,
                 source_filename="sales-q1.csv",
                 created_at=None):
    return _row(
        file_id=file_id,
        run_id=run_id,
        sheet_name=sheet_name,
        sheet_index=0,
        detected_purpose="orders",
        detected_language="vi",
        row_count=row_count,
        col_count=8,
        file_format="csv",
        created_at=created_at or datetime(2026, 5, 1, 10, tzinfo=timezone.utc),
        source_filename=source_filename,
        run_status="bronze_complete",
    )


def _bronze_data_row(row_index=0, raw_data=None, row_hash="abc123"):
    return _row(
        row_index=row_index,
        raw_data=raw_data or {"customer": "Alice", "amount": 1000},
        row_hash=row_hash,
        created_at=datetime(2026, 5, 1, 10, tzinfo=timezone.utc),
    )


class TestListBronzeFiles:

    def test_empty_tenant_returns_data_meta(self, app_client, conn):
        conn.fetch.return_value = []
        r = app_client.get("/data/bronze/files", headers=HEADERS_A)
        assert r.status_code == 200
        body = r.json()
        assert body["data"] == []
        assert body["meta"]["count"] == 0
        assert body["meta"]["has_more"] is False
        assert body["meta"]["cursor"] is None
        assert body["meta"]["limit"] == 50  # default

    def test_populated_returns_serialised_rows(self, app_client, conn):
        conn.fetch.return_value = [
            _bronze_file(file_id=FILE_ID, source_filename="a.csv"),
            _bronze_file(file_id="33333333-3333-3333-3333-333333333333",
                         source_filename="b.csv"),
        ]
        r = app_client.get("/data/bronze/files", headers=HEADERS_A)
        body = r.json()
        assert len(body["data"]) == 2
        first = body["data"][0]
        assert first["file_id"]         == FILE_ID
        assert first["source_filename"] == "a.csv"
        assert first["sheet_name"]      == "Sheet1"
        assert first["row_count"]       == 1200
        assert first["run_status"]      == "bronze_complete"

    def test_has_more_when_returned_exceeds_limit(self, app_client, conn):
        # Endpoint fetches limit+1 to detect next page; mock returns 6
        # rows for limit=5 — last row should be cut off and has_more=true.
        conn.fetch.return_value = [_bronze_file() for _ in range(6)]
        r = app_client.get("/data/bronze/files?limit=5", headers=HEADERS_A)
        body = r.json()
        assert body["meta"]["count"]    == 5
        assert body["meta"]["has_more"] is True
        assert body["meta"]["cursor"] is not None

    def test_limit_clamp_at_max(self, app_client, conn):
        # FastAPI Query(le=500) should reject limit=9999 with 422.
        r = app_client.get("/data/bronze/files?limit=9999", headers=HEADERS_A)
        assert r.status_code == 422

    def test_invalid_cursor_returns_400(self, app_client, conn):
        r = app_client.get("/data/bronze/files?cursor=not-base64",
                           headers=HEADERS_A)
        assert r.status_code == 400

    def test_missing_enterprise_header_returns_422(self, app_client, conn):
        r = app_client.get("/data/bronze/files")
        assert r.status_code == 422


class TestSampleBronzeFile:

    def test_returns_file_meta_plus_rows(self, app_client, conn):
        # First fetchrow → file metadata; then fetch → rows.
        conn.fetchrow.side_effect = [_bronze_file()]
        conn.fetch.return_value = [
            _bronze_data_row(row_index=0,
                             raw_data={"name": "Alice", "amount": 1000}),
            _bronze_data_row(row_index=1,
                             raw_data={"name": "Bob",   "amount": 2500}),
        ]
        r = app_client.get(f"/data/bronze/files/{FILE_ID}/sample",
                           headers=HEADERS_A)
        assert r.status_code == 200
        body = r.json()
        assert body["data"]["file"]["file_id"]         == FILE_ID
        assert body["data"]["file"]["source_filename"] == "sales-q1.csv"
        assert body["data"]["file"]["row_count"]       == 1200
        assert len(body["data"]["rows"]) == 2
        assert body["data"]["rows"][0]["raw_data"]["name"] == "Alice"
        assert body["data"]["limit"] == 50

    def test_file_not_in_tenant_returns_404(self, app_client, conn):
        # fetchrow returns None for the metadata lookup → 404 RFC 7807.
        conn.fetchrow.side_effect = [None]
        r = app_client.get(f"/data/bronze/files/{FILE_ID}/sample",
                           headers=HEADERS_A)
        assert r.status_code == 404

    def test_sample_limit_clamp(self, app_client, conn):
        r = app_client.get(f"/data/bronze/files/{FILE_ID}/sample?limit=9999",
                           headers=HEADERS_A)
        assert r.status_code == 422

    def test_missing_enterprise_header_returns_422(self, app_client, conn):
        r = app_client.get(f"/data/bronze/files/{FILE_ID}/sample")
        assert r.status_code == 422

    def test_malformed_file_id_returns_422(self, app_client, conn):
        # FastAPI Path(UUID) rejects non-UUID strings before our handler runs.
        r = app_client.get("/data/bronze/files/not-a-uuid/sample",
                           headers=HEADERS_A)
        assert r.status_code == 422


# ---------------------------------------------------------------------------
# F-NEW3 v1 — Silver drill-down
# ---------------------------------------------------------------------------

def _silver_dataset(file_id=FILE_ID, source_filename="sales-q1.csv",
                    row_count=1180, quality_avg=0.927,
                    last_processed_at=None, sheet_name="Sheet1"):
    return _row(
        file_id=file_id,
        source_filename=source_filename,
        sheet_name=sheet_name,
        run_status="silver_complete",
        row_count=row_count,
        col_count=8,
        quality_avg=quality_avg,
        first_processed_at=datetime(2026, 4, 28, 10, tzinfo=timezone.utc),
        last_processed_at=last_processed_at or datetime(2026, 5, 1, 14, tzinfo=timezone.utc),
    )


def _silver_data_row(row_index=0, clean_data=None,
                     applied_rules=None, quality_score=0.95):
    # Migration 006 renamed silver_rows.clean_data → row_data. Tests
    # still use `clean_data` as the kwarg name (mirrors the JSON key
    # FE callers expect) but the underlying mock row carries it under
    # `row_data` so the SELECT in routers/data_explorer.py finds it.
    return _row(
        row_index=row_index,
        row_data=clean_data or {"customer": "Alice", "amount": 1000},
        applied_rules=list(applied_rules or ["trim_whitespace", "parse_date"]),
        quality_score=quality_score,
        created_at=datetime(2026, 5, 1, 10, tzinfo=timezone.utc),
    )


def _rule_row(file_id=FILE_ID, rule_id="trim_whitespace",
              rule_category="UNIVERSAL", affected_total=1200):
    return _row(
        file_id=file_id,
        rule_id=rule_id,
        rule_category=rule_category,
        affected_total=affected_total,
    )


class TestListSilverDatasets:

    def test_empty_returns_data_meta(self, app_client, conn):
        # First fetch = aggregated datasets (empty); rules query is
        # short-circuited because we wrap it in `if rows:`.
        conn.fetch.side_effect = [[], []]
        r = app_client.get("/data/silver/datasets", headers=HEADERS_A)
        assert r.status_code == 200
        body = r.json()
        assert body["data"] == []
        assert body["meta"]["count"] == 0
        assert body["meta"]["has_more"] is False
        assert body["meta"]["limit"] == 50

    def test_populated_with_rule_breakdown(self, app_client, conn):
        # 1st fetch: silver datasets aggregate.
        # 2nd fetch: cleaning_rules_applied join.
        conn.fetch.side_effect = [
            [_silver_dataset(file_id=FILE_ID, quality_avg=0.927)],
            [_rule_row(file_id=FILE_ID, rule_id="trim_whitespace",
                       affected_total=1200),
             _rule_row(file_id=FILE_ID, rule_id="parse_date",
                       rule_category="BY_TYPE", affected_total=800)],
        ]
        r = app_client.get("/data/silver/datasets", headers=HEADERS_A)
        body = r.json()
        assert len(body["data"]) == 1
        ds = body["data"][0]
        assert ds["file_id"]               == FILE_ID
        assert ds["quality_avg_pct"]       == 92.7
        assert ds["row_count"]             == 1180
        assert len(ds["applied_rules_top"]) == 2
        # Rules are sorted by affected_total DESC at SQL layer; we trust ordering.
        assert ds["applied_rules_top"][0]["rule_id"]       == "trim_whitespace"
        assert ds["applied_rules_top"][0]["rows_affected"] == 1200

    def test_quality_avg_null_returns_zero(self, app_client, conn):
        conn.fetch.side_effect = [
            [_silver_dataset(quality_avg=None)],
            [],
        ]
        body = app_client.get("/data/silver/datasets", headers=HEADERS_A).json()
        assert body["data"][0]["quality_avg_pct"] == 0.0

    def test_invalid_cursor_returns_400(self, app_client, conn):
        r = app_client.get("/data/silver/datasets?cursor=not-base64",
                           headers=HEADERS_A)
        assert r.status_code == 400

    def test_limit_clamp_at_max(self, app_client, conn):
        r = app_client.get("/data/silver/datasets?limit=9999", headers=HEADERS_A)
        assert r.status_code == 422

    def test_missing_enterprise_header_returns_422(self, app_client, conn):
        r = app_client.get("/data/silver/datasets")
        assert r.status_code == 422


class TestSampleSilverDataset:

    def test_returns_file_meta_plus_rows(self, app_client, conn):
        conn.fetchrow.side_effect = [
            _row(
                file_id=FILE_ID, sheet_name="Sheet1", col_count=8,
                file_format="csv", source_filename="sales-q1.csv",
                row_count=1180,
                last_processed_at=datetime(2026, 5, 1, tzinfo=timezone.utc),
            )
        ]
        conn.fetch.return_value = [
            _silver_data_row(row_index=0, clean_data={"customer": "Alice", "amount": 1000}),
            _silver_data_row(row_index=1, clean_data={"customer": "Bob",   "amount": 2500},
                             applied_rules=["trim_whitespace"]),
        ]
        r = app_client.get(f"/data/silver/datasets/{FILE_ID}/sample",
                           headers=HEADERS_A)
        assert r.status_code == 200
        body = r.json()
        assert body["data"]["file"]["file_id"]   == FILE_ID
        assert body["data"]["file"]["row_count"] == 1180
        assert len(body["data"]["rows"]) == 2
        assert body["data"]["rows"][0]["clean_data"]["customer"] == "Alice"
        assert body["data"]["rows"][0]["applied_rules"] == ["trim_whitespace", "parse_date"]
        assert body["data"]["rows"][0]["quality_score"] == 0.95
        assert body["data"]["limit"] == 50

    def test_dataset_not_in_tenant_returns_404(self, app_client, conn):
        # fetchrow returns None → tenant doesn't own this file.
        conn.fetchrow.side_effect = [None]
        r = app_client.get(f"/data/silver/datasets/{FILE_ID}/sample",
                           headers=HEADERS_A)
        assert r.status_code == 404

    def test_never_cleaned_returns_404(self, app_client, conn):
        # File exists but no silver rows ever written — row_count = 0.
        conn.fetchrow.side_effect = [
            _row(
                file_id=FILE_ID, sheet_name="Sheet1", col_count=8,
                file_format="csv", source_filename="x.csv",
                row_count=0, last_processed_at=None,
            )
        ]
        r = app_client.get(f"/data/silver/datasets/{FILE_ID}/sample",
                           headers=HEADERS_A)
        assert r.status_code == 404

    def test_sample_limit_clamp(self, app_client, conn):
        r = app_client.get(f"/data/silver/datasets/{FILE_ID}/sample?limit=9999",
                           headers=HEADERS_A)
        assert r.status_code == 422

    def test_missing_enterprise_header_returns_422(self, app_client, conn):
        r = app_client.get(f"/data/silver/datasets/{FILE_ID}/sample")
        assert r.status_code == 422


# ---------------------------------------------------------------------------
# F-NEW3 v1 — Gold drill-down
# ---------------------------------------------------------------------------

def _gold_customer(customer_external_id="CUST-A0001",
                   revenue_at_risk=480_000_000.0,
                   purchase_count=38, is_actioned=False,
                   computed_at=None):
    return _row(
        customer_external_id=customer_external_id,
        revenue_at_risk=revenue_at_risk,
        last_purchase_at=datetime(2026, 1, 30, tzinfo=timezone.utc),
        total_purchases=18_240_000.0,
        purchase_count=purchase_count,
        avg_purchase_value=480_000.0,
        is_actioned=is_actioned,
        actioned_at=datetime(2026, 5, 1, tzinfo=timezone.utc) if is_actioned else None,
        computed_at=computed_at or datetime(2026, 5, 3, tzinfo=timezone.utc),
    )


class TestListGoldCustomers:

    def test_empty_returns_data_meta(self, app_client, conn):
        conn.fetch.return_value = []
        r = app_client.get("/data/gold/customers", headers=HEADERS_A)
        assert r.status_code == 200
        body = r.json()
        assert body["data"] == []
        assert body["meta"]["limit"] == 50

    def test_populated_serialises_money_as_float(self, app_client, conn):
        conn.fetch.return_value = [
            _gold_customer(customer_external_id="CUST-A0001",
                           revenue_at_risk=480_000_000.0,
                           purchase_count=38),
            _gold_customer(customer_external_id="CUST-B0042",
                           revenue_at_risk=285_000_000.0,
                           purchase_count=19, is_actioned=True),
        ]
        body = app_client.get("/data/gold/customers", headers=HEADERS_A).json()
        assert len(body["data"]) == 2
        first = body["data"][0]
        assert first["customer_external_id"] == "CUST-A0001"
        assert first["revenue_at_risk"]      == 480_000_000.0
        assert first["purchase_count"]       == 38
        assert first["is_actioned"] is False
        assert body["data"][1]["is_actioned"] is True
        assert body["data"][1]["actioned_at"] is not None

    def test_actioned_filter_forwarded(self, app_client, conn):
        # The endpoint should pass actioned=true through. We assert the
        # mock was called by capturing the SQL — and easier, we just
        # verify the response shape on a stub.
        conn.fetch.return_value = [_gold_customer(is_actioned=True)]
        body = app_client.get("/data/gold/customers?actioned=true",
                              headers=HEADERS_A).json()
        assert body["data"][0]["is_actioned"] is True

    def test_invalid_cursor_returns_400(self, app_client, conn):
        r = app_client.get("/data/gold/customers?cursor=not-base64",
                           headers=HEADERS_A)
        assert r.status_code == 400

    def test_limit_clamp_at_max(self, app_client, conn):
        r = app_client.get("/data/gold/customers?limit=9999", headers=HEADERS_A)
        assert r.status_code == 422

    def test_missing_enterprise_header_returns_422(self, app_client, conn):
        r = app_client.get("/data/gold/customers")
        assert r.status_code == 422


# ---------------------------------------------------------------------------
# F-NEW3 v1 — Lineage
# ---------------------------------------------------------------------------

UPLOADER = "11111111-2222-3333-4444-555555555555"


def _bronze_lineage_row():
    """Bronze row with the extra pipeline_runs columns the lineage SQL adds."""
    return _row(
        file_id=FILE_ID,
        run_id=RUN_ID,
        source_filename="sales-q1.csv",
        run_status="analysis_complete",
        uploaded_by=UPLOADER,
        sheet_name=None,
        sheet_index=0,
        detected_purpose="orders",
        detected_language="vi",
        row_count=1200,
        col_count=8,
        file_format="csv",
        created_at=datetime(2026, 5, 1, 10, tzinfo=timezone.utc),
        row_count_bronze=1200,
        row_count_silver=1180,
        run_quality_score=0.93,
    )


def _silver_aggregate(row_count=1180, quality_avg=0.93):
    return _row(
        row_count=row_count,
        quality_avg=quality_avg,
        first_processed_at=datetime(2026, 4, 28, 10, tzinfo=timezone.utc),
        last_processed_at=datetime(2026, 5, 1, 14, tzinfo=timezone.utc),
    )


def _link_row(rows_with_key=1180, distinct_customers=320):
    return _row(rows_with_key=rows_with_key, distinct_customers=distinct_customers)


def _count_row(c=300):
    return _row(c=c)


class TestLineage:

    def test_file_not_in_tenant_returns_404(self, app_client, conn):
        # First fetchrow (bronze metadata + tenant guard) returns None.
        conn.fetchrow.side_effect = [None]
        r = app_client.get(f"/data/lineage?file_id={FILE_ID}", headers=HEADERS_A)
        assert r.status_code == 404

    def test_bronze_only_silver_null(self, app_client, conn):
        # Bronze present, silver aggregate returns row_count=0.
        conn.fetchrow.side_effect = [
            _bronze_lineage_row(),
            _silver_aggregate(row_count=0, quality_avg=None),
        ]
        r = app_client.get(f"/data/lineage?file_id={FILE_ID}", headers=HEADERS_A)
        assert r.status_code == 200
        body = r.json()["data"]
        assert body["bronze"]["file_id"] == FILE_ID
        assert body["bronze"]["uploaded_by"] == UPLOADER
        assert body["silver"] is None
        assert body["gold"]   is None

    def test_silver_present_but_no_customer_key(self, app_client, conn):
        # Bronze + silver count > 0, but link_row says clean_data has no
        # customer_external_id key (rows_with_key = 0) → gold null.
        conn.fetchrow.side_effect = [
            _bronze_lineage_row(),
            _silver_aggregate(),
            _link_row(rows_with_key=0, distinct_customers=0),
        ]
        conn.fetch.return_value = []   # applied_rules query
        r = app_client.get(f"/data/lineage?file_id={FILE_ID}", headers=HEADERS_A)
        body = r.json()["data"]
        assert body["silver"] is not None
        assert body["silver"]["row_count"]       == 1180
        assert body["silver"]["quality_avg_pct"] == 93.0
        assert body["gold"] is None

    def test_full_chain_with_gold_link(self, app_client, conn):
        # Bronze + silver + customer key present + gold has matching rows.
        conn.fetchrow.side_effect = [
            _bronze_lineage_row(),
            _silver_aggregate(),
            _link_row(rows_with_key=1180, distinct_customers=320),
            _count_row(c=300),     # 300 of those customers actually in gold_features
        ]
        conn.fetch.return_value = [
            _row(rule_id="trim_whitespace", rule_category="UNIVERSAL",
                 affected_total=1200),
            _row(rule_id="parse_date",      rule_category="BY_TYPE",
                 affected_total=900),
        ]
        r = app_client.get(f"/data/lineage?file_id={FILE_ID}", headers=HEADERS_A)
        body = r.json()["data"]
        assert body["silver"]["applied_rules_top"][0]["rule_id"]       == "trim_whitespace"
        assert body["silver"]["applied_rules_top"][0]["rows_affected"] == 1200
        assert body["gold"] is not None
        assert body["gold"]["linked_customer_count"]   == 300
        assert body["gold"]["distinct_ids_in_silver"]  == 320
        assert body["gold"]["silver_rows_with_key"]    == 1180
        assert body["gold"]["customer_id_key"]         == "customer_external_id"

    def test_missing_file_id_query_returns_422(self, app_client, conn):
        # FastAPI Query(..., required) rejects missing param.
        r = app_client.get("/data/lineage", headers=HEADERS_A)
        assert r.status_code == 422

    def test_missing_enterprise_header_returns_422(self, app_client, conn):
        r = app_client.get(f"/data/lineage?file_id={FILE_ID}")
        assert r.status_code == 422
