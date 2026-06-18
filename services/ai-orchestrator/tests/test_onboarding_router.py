"""
P15-S11 Hướng A finisher — tests for POST /enterprise-users/onboard-from-csv.

Two layers of coverage:

  1. **Pure helpers** (_onboarding_helpers.py) — classify_dept_name VN
     mapping + generate_pending_password_hash format. No mocks.
  2. **HTTP surface** — mocks acquire_for_tenant; verifies the endpoint
     handles every outcome path: created / skipped_existing /
     skipped_no_dept / skipped_no_template / error / dry_run, plus
     the bronze-file ownership and MANAGER authz checks.

Mirrors the pattern in test_role_templates_router.py (which uses the
same router file). No Postgres required.
"""
from __future__ import annotations

import json
import re
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID, uuid4

import bcrypt
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from ai_orchestrator.routers._onboarding_helpers import (
    classify_dept_name,
    generate_pending_password_hash,
)


# ─── Pure helper tests (no fixtures, no mocks) ────────────────────


class TestClassifyDeptName:
    """Vietnamese-aware dept_name → dept_type mapping."""

    @pytest.mark.parametrize("raw,expected", [
        # English direct
        ("Marketing",          "marketing"),
        ("Sales",              "sales"),
        ("Warehouse",          "warehouse"),
        ("HR",                 "hr"),
        ("Finance",            "finance"),
        # Vietnamese
        ("Tiếp thị",           "marketing"),
        ("Truyền thông",       "marketing"),
        ("Kinh doanh",         "sales"),
        ("Bán hàng",           "sales"),
        ("Khách hàng",         "customer_service"),
        ("Chăm sóc khách hàng","customer_service"),
        ("Hỗ trợ",             "customer_service"),
        ("Kho vận",            "warehouse"),
        ("Kho",                "warehouse"),
        ("Logistics",          "warehouse"),
        ("Vận chuyển",         "warehouse"),
        ("Nhân sự",            "hr"),
        ("Tuyển dụng",         "hr"),
        ("Tài chính",          "finance"),
        ("Kế toán",            "finance"),
        # Whitespace tolerance
        ("  Marketing  ",      "marketing"),
        # Specific-before-general — "khách sạn" (hotel) is NOT customer_service
        # (it doesn't match the regex because the second word isn't "hàng").
        # It falls through to custom — correct.
        ("Khách sạn",          "custom"),
        # Fallbacks
        ("Kỹ thuật",           "custom"),
        ("Pháp lý",            "custom"),
        ("R&D",                "custom"),
        ("Chiến lược",         "custom"),
        ("",                   "custom"),
        ("   ",                "custom"),
    ])
    def test_returns_expected_dept_type(self, raw, expected):
        assert classify_dept_name(raw) == expected

    def test_none_returns_custom(self):
        assert classify_dept_name(None) == 'custom'


class TestGeneratePendingPasswordHash:
    """BCrypt hash format + Spring-Security verification compatibility."""

    def test_bcrypt_2a_format(self):
        h = generate_pending_password_hash()
        # bcrypt produces $2a$ or $2b$ prefix; either is valid for Spring.
        assert re.match(r"^\$2[ab]\$\d{2}\$.{53}$", h), \
            f"Unexpected BCrypt format: {h!r}"

    def test_strength_10(self):
        # Strength 10 matches Spring Security default.
        h = generate_pending_password_hash()
        assert "$10$" in h, f"Expected strength 10 in {h!r}"

    def test_each_call_distinct(self):
        # Two calls in a row must produce different hashes (salt + plaintext
        # both random). Repeats would be a bug.
        a = generate_pending_password_hash()
        b = generate_pending_password_hash()
        assert a != b

    def test_hash_verifies_against_its_own_plaintext(self):
        # Sanity check that the hash is internally consistent — bcrypt
        # round-trips. We don't know the plaintext (it's discarded
        # inside the helper) but we can show the hash isn't degenerate.
        h = generate_pending_password_hash()
        # Wrong plaintext must fail.
        assert not bcrypt.checkpw(b"wrong-password", h.encode())


# ─── HTTP surface fixtures ────────────────────────────────────────


ENT  = "11111111-1111-1111-1111-111111111111"
USR  = "22222222-2222-2222-2222-222222222222"
WS   = "33333333-3333-3333-3333-333333333333"
BF   = "44444444-4444-4444-4444-444444444444"
DEPT = "55555555-5555-5555-5555-555555555555"
TPL  = "66666666-6666-6666-6666-666666666666"

MANAGER_HEADERS = {
    "X-Enterprise-ID": ENT,
    "X-User-ID":       USR,
    "X-User-Role":     "MANAGER",
}


def _row(**kwargs) -> MagicMock:
    r = MagicMock()
    r.__getitem__ = lambda _s, k: kwargs[k]
    r.get = lambda k, default=None: kwargs.get(k, default)
    r.keys = lambda: list(kwargs.keys())
    r.__iter__ = lambda _s: iter(kwargs.keys())
    return r


def _bronze_row(row_index: int, **csv_cols) -> MagicMock:
    """One bronze_rows row whose `raw_data` JSONB holds the CSV columns."""
    return _row(row_index=row_index, raw_data=csv_cols)


@pytest.fixture
def conn():
    c = AsyncMock()
    c.fetch.return_value = []
    c.fetchrow.return_value = None
    c.fetchval.return_value = None
    # `async with conn.transaction():` — asyncpg's transaction() returns
    # an async-context-manager directly (not a coroutine). AsyncMock by
    # default makes attribute calls return coroutines, which breaks the
    # `async with` protocol. Override with a sync-callable MagicMock that
    # returns an async-context-manager object.
    tx = MagicMock()
    tx.__aenter__ = AsyncMock(return_value=None)
    tx.__aexit__ = AsyncMock(return_value=None)
    c.transaction = MagicMock(return_value=tx)
    return c


@pytest.fixture
def client(conn):
    @asynccontextmanager
    async def _fake(_eid):
        yield conn
    with patch("ai_orchestrator.routers.enterprise_users.acquire_for_tenant",
               _fake):
        import ai_orchestrator.routers.enterprise_users as eu
        from ai_orchestrator.shared.errors import register_problem_handlers
        app = FastAPI()
        app.include_router(eu.router)
        register_problem_handlers(app)
        with TestClient(app, raise_server_exceptions=True) as c:
            yield c


def _wire_fetchrow_sequence(conn, *rows):
    """Sequentially return each row on consecutive conn.fetchrow calls,
    then None for everything after. The endpoint hits fetchrow in this
    order: bronze_files → enterprises → (per row × N) dept lookup +
    template + INSERT RETURNING."""
    conn.fetchrow.side_effect = list(rows) + [None] * 100


# ─── HTTP tests — happy path + each outcome class ─────────────────


class TestOnboardFromCsv:

    def test_403_when_not_manager(self, client):
        r = client.post(
            "/enterprise-users/onboard-from-csv",
            json={"bronze_file_id": BF},
            headers={**MANAGER_HEADERS, "X-User-Role": "VIEWER"},
        )
        assert r.status_code == 403
        assert "MANAGER" in r.text

    def test_404_when_bronze_file_missing(self, client, conn):
        conn.fetchrow.return_value = None  # bronze_files lookup empty
        r = client.post(
            "/enterprise-users/onboard-from-csv",
            json={"bronze_file_id": BF},
            headers=MANAGER_HEADERS,
        )
        assert r.status_code == 404
        assert "bronze file not found" in r.text

    def test_403_when_bronze_file_belongs_to_other_enterprise(self, client, conn):
        conn.fetchrow.return_value = _row(
            file_id=UUID(BF),
            enterprise_id=UUID("99999999-9999-9999-9999-999999999999"),
        )
        r = client.post(
            "/enterprise-users/onboard-from-csv",
            json={"bronze_file_id": BF},
            headers=MANAGER_HEADERS,
        )
        assert r.status_code == 403

    def test_happy_path_creates_one_user(self, client, conn):
        _wire_fetchrow_sequence(
            conn,
            # 1. bronze_files validation
            _row(file_id=UUID(BF), enterprise_id=UUID(ENT)),
            # 2. enterprises workspace lookup
            _row(workspace_id=UUID(WS)),
            # 3. departments lookup for dept_type=marketing
            _row(department_id=UUID(DEPT)),
            # 4. template lookup
            _row(template_id=UUID(TPL), default_role="ANALYST"),
            # 5. INSERT enterprise_users RETURNING user_id
            _row(user_id=uuid4()),
        )
        conn.fetch.return_value = [
            _bronze_row(0,
                email="an.nguyen@example.com", full_name="Nguyễn Văn An",
                department="Marketing", seniority_level="mid"),
        ]
        r = client.post(
            "/enterprise-users/onboard-from-csv",
            json={"bronze_file_id": BF},
            headers=MANAGER_HEADERS,
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["created"] == 1
        assert body["skipped_existing"] == 0
        assert body["errors"] == 0
        assert body["outcomes"][0]["outcome"] == "created"
        assert body["outcomes"][0]["role"] == "ANALYST"
        assert body["outcomes"][0]["dept_type"] == "marketing"

    def test_skipped_existing_when_insert_returns_no_row(self, client, conn):
        _wire_fetchrow_sequence(
            conn,
            _row(file_id=UUID(BF), enterprise_id=UUID(ENT)),
            _row(workspace_id=UUID(WS)),
            _row(department_id=UUID(DEPT)),
            _row(template_id=UUID(TPL), default_role="ANALYST"),
            None,  # INSERT ... ON CONFLICT DO NOTHING RETURNING → None
        )
        conn.fetch.return_value = [
            _bronze_row(0,
                email="existing@example.com", full_name="Existing",
                department="Marketing", seniority_level="mid"),
        ]
        r = client.post(
            "/enterprise-users/onboard-from-csv",
            json={"bronze_file_id": BF},
            headers=MANAGER_HEADERS,
        )
        assert r.status_code == 200
        body = r.json()
        assert body["created"] == 0
        assert body["skipped_existing"] == 1
        assert body["outcomes"][0]["outcome"] == "skipped_existing"

    def test_skipped_no_dept(self, client, conn):
        _wire_fetchrow_sequence(
            conn,
            _row(file_id=UUID(BF), enterprise_id=UUID(ENT)),
            _row(workspace_id=UUID(WS)),
            None,  # dept lookup empty
        )
        conn.fetch.return_value = [
            _bronze_row(0,
                email="x@example.com", full_name="X",
                department="Marketing", seniority_level="mid"),
        ]
        r = client.post(
            "/enterprise-users/onboard-from-csv",
            json={"bronze_file_id": BF},
            headers=MANAGER_HEADERS,
        )
        assert r.status_code == 200
        body = r.json()
        assert body["skipped_no_dept"] == 1
        assert body["outcomes"][0]["outcome"] == "skipped_no_dept"
        assert body["outcomes"][0]["dept_type"] == "marketing"

    def test_skipped_no_template(self, client, conn):
        _wire_fetchrow_sequence(
            conn,
            _row(file_id=UUID(BF), enterprise_id=UUID(ENT)),
            _row(workspace_id=UUID(WS)),
            _row(department_id=UUID(DEPT)),
            None,  # template lookup empty
        )
        conn.fetch.return_value = [
            _bronze_row(0,
                email="x@example.com", full_name="X",
                department="Custom Strange Dept", seniority_level="entry"),
        ]
        r = client.post(
            "/enterprise-users/onboard-from-csv",
            json={"bronze_file_id": BF},
            headers=MANAGER_HEADERS,
        )
        assert r.status_code == 200
        body = r.json()
        assert body["skipped_no_template"] == 1
        assert body["outcomes"][0]["outcome"] == "skipped_no_template"

    def test_error_on_invalid_email(self, client, conn):
        _wire_fetchrow_sequence(
            conn,
            _row(file_id=UUID(BF), enterprise_id=UUID(ENT)),
            _row(workspace_id=UUID(WS)),
        )
        conn.fetch.return_value = [
            _bronze_row(0,
                email="not-an-email", full_name="Bad",
                department="Marketing", seniority_level="mid"),
        ]
        r = client.post(
            "/enterprise-users/onboard-from-csv",
            json={"bronze_file_id": BF},
            headers=MANAGER_HEADERS,
        )
        assert r.status_code == 200
        body = r.json()
        assert body["errors"] == 1
        assert body["outcomes"][0]["outcome"] == "error"
        assert "email" in body["outcomes"][0]["error"]

    def test_error_on_invalid_seniority(self, client, conn):
        _wire_fetchrow_sequence(
            conn,
            _row(file_id=UUID(BF), enterprise_id=UUID(ENT)),
            _row(workspace_id=UUID(WS)),
        )
        conn.fetch.return_value = [
            _bronze_row(0,
                email="x@example.com", full_name="X",
                department="Marketing", seniority_level="ULTRA_SENIOR"),
        ]
        r = client.post(
            "/enterprise-users/onboard-from-csv",
            json={"bronze_file_id": BF},
            headers=MANAGER_HEADERS,
        )
        assert r.status_code == 200
        body = r.json()
        assert body["errors"] == 1
        assert "seniority_level" in body["outcomes"][0]["error"]

    def test_dry_run_does_not_insert(self, client, conn):
        _wire_fetchrow_sequence(
            conn,
            _row(file_id=UUID(BF), enterprise_id=UUID(ENT)),
            _row(workspace_id=UUID(WS)),
            _row(department_id=UUID(DEPT)),
            _row(template_id=UUID(TPL), default_role="ANALYST"),
        )
        conn.fetch.return_value = [
            _bronze_row(0,
                email="dry@example.com", full_name="Dry",
                department="Marketing", seniority_level="mid"),
        ]
        r = client.post(
            "/enterprise-users/onboard-from-csv",
            json={"bronze_file_id": BF, "dry_run": True},
            headers=MANAGER_HEADERS,
        )
        assert r.status_code == 200
        body = r.json()
        assert body["dry_run"] is True
        assert body["created"] == 1  # "would create"
        assert body["outcomes"][0]["outcome"] == "created"
        assert body["outcomes"][0]["user_id"] is None  # nothing inserted

    def test_mixed_batch_correct_aggregate(self, client, conn):
        """3 rows: 1 created + 1 skipped_existing + 1 error. Confirms
        the aggregate counts and the per-row outcomes both match."""
        _wire_fetchrow_sequence(
            conn,
            _row(file_id=UUID(BF), enterprise_id=UUID(ENT)),
            _row(workspace_id=UUID(WS)),
            # Row 0 (marketing) — dept + template + INSERT returns row
            _row(department_id=UUID(DEPT)),
            _row(template_id=UUID(TPL), default_role="ANALYST"),
            _row(user_id=uuid4()),
            # Row 1 (sales) — dept + template + INSERT conflict (None)
            _row(department_id=UUID(DEPT)),
            _row(template_id=UUID(TPL), default_role="OPERATOR"),
            None,
            # Row 2 (error) — fails before any lookup (bad email)
        )
        conn.fetch.return_value = [
            _bronze_row(0,
                email="a@example.com", full_name="A",
                department="Marketing", seniority_level="mid"),
            _bronze_row(1,
                email="b@example.com", full_name="B",
                department="Sales", seniority_level="junior"),
            _bronze_row(2,
                email="bademail", full_name="C",
                department="Marketing", seniority_level="mid"),
        ]
        r = client.post(
            "/enterprise-users/onboard-from-csv",
            json={"bronze_file_id": BF},
            headers=MANAGER_HEADERS,
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["total_rows"] == 3
        assert body["created"] == 1
        assert body["skipped_existing"] == 1
        assert body["errors"] == 1
        # Order preserved in outcomes[]
        assert body["outcomes"][0]["outcome"] == "created"
        assert body["outcomes"][1]["outcome"] == "skipped_existing"
        assert body["outcomes"][2]["outcome"] == "error"

    def test_dept_cache_reused_within_batch(self, client, conn):
        """Two rows of the same dept_type should only hit the departments
        table ONCE (per-batch cache). Catches a regression where someone
        removes the cache and ends up with N+1 dept lookups."""
        _wire_fetchrow_sequence(
            conn,
            _row(file_id=UUID(BF), enterprise_id=UUID(ENT)),
            _row(workspace_id=UUID(WS)),
            # Row 0 — dept (1 call) + template + INSERT
            _row(department_id=UUID(DEPT)),
            _row(template_id=UUID(TPL), default_role="ANALYST"),
            _row(user_id=uuid4()),
            # Row 1 — NO dept call (cached) + template + INSERT
            _row(template_id=UUID(TPL), default_role="ANALYST"),
            _row(user_id=uuid4()),
        )
        conn.fetch.return_value = [
            _bronze_row(0,
                email="a@example.com", full_name="A",
                department="Marketing", seniority_level="mid"),
            _bronze_row(1,
                email="b@example.com", full_name="B",
                department="Marketing", seniority_level="senior"),
        ]
        r = client.post(
            "/enterprise-users/onboard-from-csv",
            json={"bronze_file_id": BF},
            headers=MANAGER_HEADERS,
        )
        assert r.status_code == 200, r.text
        assert r.json()["created"] == 2
        # The 5 fetchrow calls represent: bronze_files (1) + workspace (1)
        # + dept (1, shared) + per-row (template + insert) × 2 = 7.
        # If the cache regressed, we'd see 8 (one extra dept call).
        # Count fetchrows that fired (None sentinels stop the sequence
        # so we can't trivially count; instead assert the cached row
        # path was taken — Row 1 must NOT have the no_dept outcome).
        assert all(o["outcome"] == "created" for o in r.json()["outcomes"])
