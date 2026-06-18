"""
P15-S11 — HTTP-surface tests for customers/vendors/contracts routers.

Mocks acquire_for_tenant; no Postgres required. Focused on:
  - List endpoint forwards filters as SQL params.
  - Detail endpoint returns 404 when missing.
  - Detail endpoint bundles contracts under the parent.
"""
from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import date, datetime, timezone
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient


ENTERPRISE   = "11111111-1111-1111-1111-111111111111"
USER         = "22222222-2222-2222-2222-222222222222"
CUSTOMER_ID  = "33333333-3333-3333-3333-333333333333"
VENDOR_ID    = "44444444-4444-4444-4444-444444444444"
CONTRACT_C   = "55555555-5555-5555-5555-555555555555"
CONTRACT_V   = "66666666-6666-6666-6666-666666666666"

HEADERS = {"X-Enterprise-ID": ENTERPRISE, "X-User-ID": USER}


def _row(**kwargs) -> MagicMock:
    r = MagicMock()
    r.__getitem__ = lambda _s, k: kwargs[k]
    r.get = lambda k, default=None: kwargs.get(k, default)
    r.keys = lambda: list(kwargs.keys())
    r.__iter__ = lambda _s: iter(kwargs.keys())
    return r


def _make_conn() -> AsyncMock:
    conn = AsyncMock()
    conn.fetch.return_value = []
    conn.fetchrow.return_value = None
    return conn


def _tenant_ctx(conn):
    @asynccontextmanager
    async def _fake(_eid):
        yield conn
    return _fake


@pytest.fixture
def conn():
    return _make_conn()


@pytest.fixture
def app_client(conn):
    with patch("ai_orchestrator.routers.customers_vendors.acquire_for_tenant",
               _tenant_ctx(conn)):
        import ai_orchestrator.routers.customers_vendors as cv
        from ai_orchestrator.shared.errors import register_problem_handlers
        test_app = FastAPI()
        test_app.include_router(cv.router)
        register_problem_handlers(test_app)
        with TestClient(test_app, raise_server_exceptions=True) as c:
            yield c


def _customer_row(**overrides):
    base = {
        "customer_id":              UUID(CUSTOMER_ID),
        "code":                     "KH-TEST-001",
        "customer_name":            "Test Customer",
        "contact_person":           "Anh Test",
        "phone":                    "0900000000",
        "email":                    "test@example.com",
        "tax_code":                 "0123456789",
        "address":                  "Hà Nội",
        "city":                     "Hà Nội",
        "customer_type":            "enterprise",
        "industry":                 "Bán lẻ",
        "years_in_business":        10,
        "employees_count":          500,
        "annual_revenue_vnd":       Decimal("5000000000"),
        "credit_rating":            "AA",
        "titles_awards":            None,
        "certifications":           None,
        "experience_summary":       "Test summary",
        "relationship_tier":        "gold",
        "first_contact_date":       date(2024, 1, 15),
        "assigned_account_manager": "sales1@kaori.local",
        "note":                     None,
        "status":                   "active",
        "created_at":               datetime(2024, 1, 15, tzinfo=timezone.utc),
    }
    base.update(overrides)
    return _row(**base)


def _vendor_row(**overrides):
    base = {
        "vendor_id":            UUID(VENDOR_ID),
        "code":                 "NCC-TEST-001",
        "vendor_name":          "Test Vendor",
        "contact_person":       "Mr Vendor",
        "phone":                "0911111111",
        "email":                "vendor@example.com",
        "tax_code":             "0987654321",
        "address":              "TP.HCM",
        "city":                 "TP.HCM",
        "country":              "VN",
        "vendor_type":          "supplier",
        "services_offered":     "Tư vấn",
        "industries_served":    "Bán lẻ",
        "years_in_business":    8,
        "employees_count":      200,
        "annual_revenue_vnd":   Decimal("1000000000"),
        "credit_rating":        "A",
        "certifications":       None,
        "titles_awards":        None,
        "experience_summary":   "Test vendor summary",
        "reliability_tier":     "gold",
        "first_contract_date":  date(2023, 6, 1),
        "managed_by":           "proc1@kaori.local",
        "note":                 None,
        "status":               "active",
        "created_at":           datetime(2023, 6, 1, tzinfo=timezone.utc),
    }
    base.update(overrides)
    return _row(**base)


def _customer_contract_row(**overrides):
    base = {
        "contract_id":           UUID(CONTRACT_C),
        "customer_id":           UUID(CUSTOMER_ID),
        "customer_code":         "KH-TEST-001",
        "customer_name":         "Test Customer",
        "contract_no":           "CT-TEST-001",
        "contract_type":         "license_enterprise",
        "description":           "Gói thử",
        "signed_at":             date(2024, 4, 1),
        "start_at":              date(2024, 4, 10),
        "end_at":                date(2025, 4, 9),
        "value_vnd":             Decimal("60000000"),
        "currency":              "VND",
        "payment_terms_days":    30,
        "payment_schedule":      "monthly",
        "status":                "active",
        "signed_by_customer":    "Anh Test",
        "customer_signer_title": "CIO",
        "signed_by_us":          "Hoàng Văn Em",
        "us_signer_title":       "COO",
        "attachment_uri":        None,
        "renewal_type":          "manual",
        "note":                  None,
        "created_at":            datetime(2024, 4, 1, tzinfo=timezone.utc),
    }
    base.update(overrides)
    return _row(**base)


def _vendor_contract_row(**overrides):
    base = {
        "contract_id":         UUID(CONTRACT_V),
        "vendor_id":           UUID(VENDOR_ID),
        "vendor_code":         "NCC-TEST-001",
        "vendor_name":         "Test Vendor",
        "contract_no":         "VC-TEST-001",
        "contract_type":       "consulting",
        "description":         "Test SOW",
        "signed_at":           date(2024, 5, 1),
        "start_at":            date(2024, 5, 5),
        "end_at":              date(2025, 5, 4),
        "value_vnd":           Decimal("100000000"),
        "currency":            "VND",
        "payment_terms_days":  45,
        "payment_schedule":    "milestone",
        "status":              "active",
        "signed_by_vendor":    "Mr Vendor",
        "vendor_signer_title": "Director",
        "signed_by_us":        "Hoàng Văn Em",
        "us_signer_title":     "COO",
        "attachment_uri":      None,
        "renewal_type":        "manual",
        "note":                None,
        "created_at":          datetime(2024, 5, 1, tzinfo=timezone.utc),
    }
    base.update(overrides)
    return _row(**base)


# ─── Customers ──────────────────────────────────────────────────────


class TestCustomers:

    def test_list_returns_rows(self, app_client, conn):
        conn.fetch.return_value = [_customer_row(), _customer_row(code="KH-TEST-002")]
        resp = app_client.get("/customers", headers=HEADERS)
        assert resp.status_code == 200
        body = resp.json()
        assert len(body) == 2
        assert body[0]["customer_id"] == CUSTOMER_ID

    def test_list_forwards_filters(self, app_client, conn):
        conn.fetch.return_value = []
        resp = app_client.get(
            "/customers?status=active&customer_type=enterprise&relationship_tier=gold",
            headers=HEADERS,
        )
        assert resp.status_code == 200
        args = conn.fetch.call_args.args
        assert "active"     in args
        assert "enterprise" in args
        assert "gold"       in args

    def test_detail_404_when_missing(self, app_client, conn):
        conn.fetchrow.return_value = None
        resp = app_client.get(f"/customers/{CUSTOMER_ID}", headers=HEADERS)
        assert resp.status_code == 404

    def test_detail_bundles_contracts(self, app_client, conn):
        conn.fetchrow.return_value = _customer_row()
        conn.fetch.return_value    = [_customer_contract_row()]
        resp = app_client.get(f"/customers/{CUSTOMER_ID}", headers=HEADERS)
        assert resp.status_code == 200
        body = resp.json()
        assert body["customer"]["code"] == "KH-TEST-001"
        assert len(body["contracts"]) == 1
        assert body["contracts"][0]["contract_no"] == "CT-TEST-001"
        assert body["contracts"][0]["customer_code"] == "KH-TEST-001"


# ─── Vendors ────────────────────────────────────────────────────────


class TestVendors:

    def test_list_returns_rows(self, app_client, conn):
        conn.fetch.return_value = [_vendor_row()]
        resp = app_client.get("/vendors", headers=HEADERS)
        assert resp.status_code == 200
        assert resp.json()[0]["vendor_id"] == VENDOR_ID

    def test_list_forwards_filters(self, app_client, conn):
        conn.fetch.return_value = []
        resp = app_client.get(
            "/vendors?vendor_type=supplier&reliability_tier=gold",
            headers=HEADERS,
        )
        assert resp.status_code == 200
        args = conn.fetch.call_args.args
        assert "supplier" in args
        assert "gold"     in args

    def test_detail_bundles_contracts(self, app_client, conn):
        conn.fetchrow.return_value = _vendor_row()
        conn.fetch.return_value    = [_vendor_contract_row()]
        resp = app_client.get(f"/vendors/{VENDOR_ID}", headers=HEADERS)
        assert resp.status_code == 200
        body = resp.json()
        assert body["vendor"]["code"] == "NCC-TEST-001"
        assert len(body["contracts"]) == 1
        assert body["contracts"][0]["vendor_code"] == "NCC-TEST-001"


# ─── Contracts ──────────────────────────────────────────────────────


class TestContractsList:

    def test_customer_contracts_filter_by_customer(self, app_client, conn):
        conn.fetch.return_value = [_customer_contract_row()]
        resp = app_client.get(
            f"/customer-contracts?customer_id={CUSTOMER_ID}",
            headers=HEADERS,
        )
        assert resp.status_code == 200
        args = conn.fetch.call_args.args
        # customer_id is parsed as UUID by FastAPI; assert by str roundtrip.
        assert UUID(CUSTOMER_ID) in args

    def test_vendor_contracts_filter_by_status(self, app_client, conn):
        conn.fetch.return_value = []
        resp = app_client.get(
            "/vendor-contracts?status=expired",
            headers=HEADERS,
        )
        assert resp.status_code == 200
        args = conn.fetch.call_args.args
        assert "expired" in args
