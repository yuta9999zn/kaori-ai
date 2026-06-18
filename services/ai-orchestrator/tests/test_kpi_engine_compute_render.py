"""Tests for kpi_engine.compute.render_formula + _to_async_params.

These are pure-function tests that don't need a DB — they verify the
defensive validation layer that protects against bad seed data in
kpi_definitions.
"""
from __future__ import annotations

import pytest

from reasoning.kpi_engine.compute import (
    _ALLOWED_PLACEHOLDERS,
    _to_async_params,
    render_formula,
)


def test_render_substitutes_view():
    sql = "SELECT 1 FROM {{view}} WHERE x = 1"
    out = render_formula(sql, target_view="gold.customer_360_marketing")
    assert out == "SELECT 1 FROM gold.customer_360_marketing WHERE x = 1"


def test_render_handles_whitespace_in_brace():
    sql = "SELECT 1 FROM {{ view }} LIMIT 1"
    out = render_formula(sql, target_view="gold.customer_360_marketing")
    assert "{{ view }}" not in out
    assert "gold.customer_360_marketing" in out


def test_render_rejects_unknown_placeholder():
    sql = "SELECT 1 FROM {{view}} WHERE id = {{evil_param}}"
    with pytest.raises(ValueError, match="unknown placeholders"):
        render_formula(sql, target_view="gold.test")


def test_render_rejects_view_outside_allowlist():
    """target_view that doesn't match gold.* or silver.* is rejected
    even if syntactically valid SQL — defends against schema spoofing
    via a bad seed row."""
    sql = "SELECT 1 FROM {{view}}"
    with pytest.raises(ValueError, match="not allowed"):
        render_formula(sql, target_view="public.evil_table")


def test_render_rejects_view_with_quotes():
    sql = "SELECT 1 FROM {{view}}"
    with pytest.raises(ValueError, match="not allowed"):
        render_formula(sql, target_view='gold.x"; DROP TABLE users--')


def test_render_allows_silver_view():
    sql = "SELECT 1 FROM {{view}}"
    out = render_formula(sql, target_view="silver.customers")
    assert "silver.customers" in out


def test_to_async_params_single_placeholder():
    sql = "SELECT * FROM x WHERE id = {{enterprise_id}}"
    final, params = _to_async_params(sql, {"enterprise_id": "uuid-1"})
    assert final == "SELECT * FROM x WHERE id = $1"
    assert params == ["uuid-1"]


def test_to_async_params_repeated_placeholder():
    """Same placeholder appearing twice should map to ONE $N, not two."""
    sql = "SELECT * FROM x WHERE a = {{enterprise_id}} OR b = {{enterprise_id}}"
    final, params = _to_async_params(sql, {"enterprise_id": "uuid-1"})
    assert final == "SELECT * FROM x WHERE a = $1 OR b = $1"
    assert params == ["uuid-1"]


def test_to_async_params_multiple_placeholders_keep_order():
    sql = "SELECT * FROM {{view}} WHERE e = {{enterprise_id}} AND d = {{department_id}}"
    rendered = render_formula(sql, target_view="gold.x")
    final, params = _to_async_params(
        rendered,
        {"enterprise_id": "ent-uuid", "department_id": "dept-uuid"},
    )
    assert "$1" in final and "$2" in final
    # enterprise_id appears first → $1; department_id → $2.
    assert final.index("$1") < final.index("$2")
    assert params == ["ent-uuid", "dept-uuid"]


def test_to_async_params_period_dates_pass_through():
    from datetime import date

    sql = "SELECT 1 WHERE t BETWEEN {{period_start}} AND {{period_end}}"
    final, params = _to_async_params(sql, {
        "period_start": date(2026, 1, 1),
        "period_end": date(2026, 1, 31),
    })
    assert params[0] == date(2026, 1, 1)
    assert params[1] == date(2026, 1, 31)


def test_allowed_placeholders_set_is_stable():
    """Locks the API: any new placeholder addition must be deliberate
    + reflected in kpi_definitions seed data."""
    assert _ALLOWED_PLACEHOLDERS == {
        "enterprise_id",
        "department_id",
        "branch_id",
        "period_start",
        "period_end",
        "view",
    }
