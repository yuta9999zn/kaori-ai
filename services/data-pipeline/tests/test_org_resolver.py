"""
test_org_resolver.py — P15-S11 Tuần 8 Step 4.1.

Unit tests for services/data-pipeline/shared/org_resolver.py — the helper
that fills in dept/branch/source defaults for uploads when the caller
omits the X-Department-ID / X-Branch-ID / X-Source-ID headers.

These tests are pure asyncio + mock conn — no DB needed. They exercise:
  - default branch/dept/source lookup queries
  - cross-tenant guard (ValueError when supplied ID escapes enterprise)
  - mapping_template glob matching is case-insensitive
"""
import uuid
from typing import Any
from unittest.mock import AsyncMock

import pytest

from data_pipeline.shared.org_resolver import (
    assert_branch_in_enterprise,
    assert_department_in_enterprise,
    assert_source_in_department,
    match_mapping_template,
    resolve_default_branch,
    resolve_default_department,
    resolve_default_source,
    resolve_org_attribution,
)


ENTERPRISE_ID = uuid.UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
BRANCH_ID     = uuid.UUID("11111111-1111-1111-1111-111111111111")
DEPT_ID       = uuid.UUID("22222222-2222-2222-2222-222222222222")
SOURCE_ID     = uuid.UUID("33333333-3333-3333-3333-333333333333")
TEMPLATE_ID   = uuid.UUID("44444444-4444-4444-4444-444444444444")


def _row(**kwargs) -> dict:
    """Build a dict mimicking asyncpg.Record's key-access shape."""
    return dict(kwargs)


@pytest.fixture
def conn() -> AsyncMock:
    return AsyncMock()


# ───── default lookup tests ─────────────────────────────────────────────


@pytest.mark.asyncio
async def test_resolve_default_branch_returns_id(conn):
    conn.fetchrow.return_value = _row(branch_id=BRANCH_ID)
    out = await resolve_default_branch(conn, ENTERPRISE_ID)
    assert out == BRANCH_ID


@pytest.mark.asyncio
async def test_resolve_default_branch_returns_none_when_missing(conn):
    conn.fetchrow.return_value = None
    out = await resolve_default_branch(conn, ENTERPRISE_ID)
    assert out is None


@pytest.mark.asyncio
async def test_resolve_default_department_marketing(conn):
    conn.fetchrow.return_value = _row(department_id=DEPT_ID)
    out = await resolve_default_department(conn, ENTERPRISE_ID)
    assert out == DEPT_ID
    args = conn.fetchrow.call_args
    # SQL must filter by dept_type='marketing'
    assert "marketing" in args[0][0].lower() or "marketing" in str(args)


@pytest.mark.asyncio
async def test_resolve_default_department_falls_back_to_any_active(conn):
    """When the enterprise has no Marketing dept, the resolver must still
    return a department (oldest active) — not None. The SQL filters by
    status='active' (not exclusively dept_type='marketing') and only
    *prefers* marketing via ORDER BY."""
    conn.fetchrow.return_value = _row(department_id=DEPT_ID)
    out = await resolve_default_department(conn, ENTERPRISE_ID)
    assert out == DEPT_ID
    sql = conn.fetchrow.call_args[0][0]
    # marketing is a preference (ORDER BY), not a hard WHERE filter
    assert "ORDER BY (dept_type = 'marketing')" in sql
    assert "status        = 'active'" in sql or "status = 'active'" in sql


@pytest.mark.asyncio
async def test_resolve_default_department_none_when_no_dept(conn):
    """Returns None only when the enterprise has zero active departments."""
    conn.fetchrow.return_value = None
    assert await resolve_default_department(conn, ENTERPRISE_ID) is None


@pytest.mark.asyncio
async def test_resolve_default_source_manual_upload(conn):
    conn.fetchrow.return_value = _row(source_id=SOURCE_ID)
    out = await resolve_default_source(conn, ENTERPRISE_ID, DEPT_ID)
    assert out == SOURCE_ID
    args = conn.fetchrow.call_args
    assert "manual_upload" in args[0][0]


# ───── assertion helpers ────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_assert_department_in_enterprise_true(conn):
    conn.fetchrow.return_value = _row(exists=1)
    assert await assert_department_in_enterprise(conn, ENTERPRISE_ID, DEPT_ID) is True


@pytest.mark.asyncio
async def test_assert_department_in_enterprise_false(conn):
    conn.fetchrow.return_value = None
    assert await assert_department_in_enterprise(conn, ENTERPRISE_ID, DEPT_ID) is False


@pytest.mark.asyncio
async def test_assert_branch_in_enterprise_false(conn):
    conn.fetchrow.return_value = None
    assert await assert_branch_in_enterprise(conn, ENTERPRISE_ID, BRANCH_ID) is False


@pytest.mark.asyncio
async def test_assert_source_in_department_true(conn):
    conn.fetchrow.return_value = _row(exists=1)
    assert await assert_source_in_department(
        conn, ENTERPRISE_ID, DEPT_ID, SOURCE_ID
    ) is True


# ───── resolve_org_attribution ─────────────────────────────────────────


@pytest.mark.asyncio
async def test_resolve_org_attribution_all_defaults(conn):
    """When caller passes no IDs, defaults fill in for all three."""
    conn.fetchrow.side_effect = [
        _row(department_id=DEPT_ID),     # default dept lookup
        _row(branch_id=BRANCH_ID),       # default branch lookup
        _row(source_id=SOURCE_ID),       # default source lookup
    ]
    out = await resolve_org_attribution(conn, ENTERPRISE_ID)
    assert out["department_id"] == DEPT_ID
    assert out["branch_id"]     == BRANCH_ID
    assert out["source_id"]     == SOURCE_ID


@pytest.mark.asyncio
async def test_resolve_org_attribution_all_explicit(conn):
    """When caller supplies all three IDs, only the cross-tenant guards
    query the DB — no default lookups."""
    # 3 guard queries: dept-exists, branch-exists, source-in-dept
    conn.fetchrow.side_effect = [
        _row(exists=1),   # dept guard
        _row(exists=1),   # branch guard
        _row(exists=1),   # source guard
    ]
    out = await resolve_org_attribution(
        conn,
        ENTERPRISE_ID,
        branch_id=BRANCH_ID,
        department_id=DEPT_ID,
        source_id=SOURCE_ID,
    )
    assert out["department_id"] == DEPT_ID
    assert out["branch_id"]     == BRANCH_ID
    assert out["source_id"]     == SOURCE_ID


@pytest.mark.asyncio
async def test_resolve_org_attribution_cross_tenant_dept_rejected(conn):
    """Supplied X-Department-ID that doesn't belong to enterprise → ValueError."""
    conn.fetchrow.return_value = None  # dept guard returns NULL = not in tenant
    with pytest.raises(ValueError, match="X-Department-ID"):
        await resolve_org_attribution(
            conn, ENTERPRISE_ID, department_id=DEPT_ID
        )


@pytest.mark.asyncio
async def test_resolve_org_attribution_cross_tenant_branch_rejected(conn):
    """Supplied X-Branch-ID that doesn't belong to enterprise → ValueError.

    Sequencing — dept resolves to default first, THEN branch guard fires.
    """
    conn.fetchrow.side_effect = [
        _row(department_id=DEPT_ID),  # default dept lookup OK
        None,                          # branch guard FAILS
    ]
    with pytest.raises(ValueError, match="X-Branch-ID"):
        await resolve_org_attribution(
            conn, ENTERPRISE_ID, branch_id=BRANCH_ID
        )


@pytest.mark.asyncio
async def test_resolve_org_attribution_no_active_department_errors(conn):
    """Enterprise with ZERO active departments → caller gets a clear
    ValueError telling them to create a department. (A missing *Marketing*
    dept no longer errors — resolve_default_department falls back to the
    oldest active dept; the error only fires when there is no dept at all.)"""
    conn.fetchrow.return_value = None
    with pytest.raises(ValueError, match="no active department"):
        await resolve_org_attribution(conn, ENTERPRISE_ID)


# ───── match_mapping_template ───────────────────────────────────────────


@pytest.mark.asyncio
async def test_match_mapping_template_case_insensitive_glob(conn):
    """Filename `Customers_2026_Q1.CSV` matches pattern `customers_*.csv`."""
    conn.fetch.return_value = [
        {
            "template_id":     TEMPLATE_ID,
            "name":            "Customers",
            "file_pattern":    "customers_*.csv",
            "file_kind":       "csv",
            "column_mapping":  {"columns": []},
            "domain":          "retail",
            "confirmed_count": 5,
            "last_used_at":    None,
        }
    ]
    out = await match_mapping_template(
        conn, ENTERPRISE_ID, SOURCE_ID, "Customers_2026_Q1.CSV"
    )
    assert out is not None
    assert out["template_id"] == TEMPLATE_ID


@pytest.mark.asyncio
async def test_match_mapping_template_no_match(conn):
    """No template matches → None (and FE skips pre-fill)."""
    conn.fetch.return_value = [
        {
            "template_id":     TEMPLATE_ID,
            "name":            "Customers",
            "file_pattern":    "customers_*.csv",
            "file_kind":       "csv",
            "column_mapping":  {"columns": []},
            "domain":          "retail",
            "confirmed_count": 5,
            "last_used_at":    None,
        }
    ]
    out = await match_mapping_template(
        conn, ENTERPRISE_ID, SOURCE_ID, "totally_unrelated.xlsx"
    )
    assert out is None


@pytest.mark.asyncio
async def test_match_mapping_template_no_active_templates(conn):
    """Source has no templates at all → None."""
    conn.fetch.return_value = []
    out = await match_mapping_template(
        conn, ENTERPRISE_ID, SOURCE_ID, "anything.csv"
    )
    assert out is None


@pytest.mark.asyncio
async def test_match_mapping_template_picks_highest_confirmed_count(conn):
    """Multiple matches → first row wins (already ordered by confirmed_count DESC)."""
    conn.fetch.return_value = [
        {
            "template_id":     TEMPLATE_ID,
            "name":            "Customers v2",
            "file_pattern":    "*.csv",
            "file_kind":       "csv",
            "column_mapping":  {"columns": ["v2"]},
            "domain":          "retail",
            "confirmed_count": 100,
            "last_used_at":    None,
        },
        {
            "template_id":     uuid.uuid4(),
            "name":            "Customers v1 (legacy)",
            "file_pattern":    "*.csv",
            "file_kind":       "csv",
            "column_mapping":  {"columns": ["v1"]},
            "domain":          "retail",
            "confirmed_count": 1,
            "last_used_at":    None,
        },
    ]
    out = await match_mapping_template(
        conn, ENTERPRISE_ID, SOURCE_ID, "customers_2026.csv"
    )
    assert out is not None
    assert out["confirmed_count"] == 100
    assert out["name"] == "Customers v2"
