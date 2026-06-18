"""Smoke tests for Phúc Long demo fixture — P15-S11 Build Week."""
from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from ai_orchestrator.org_intel.process_mining import EventLog, HeuristicMiner

from .fixtures.demo_phuc_long import (
    PHUC_LONG_TENANT_ID,
    build_phuc_long_event_log,
    build_phuc_long_events,
    build_phuc_long_payload,
)


def test_fixture_is_deterministic():
    """Same seed → byte-equal events."""
    events_1 = build_phuc_long_events(num_customers=10, days=7, seed=42)
    events_2 = build_phuc_long_events(num_customers=10, days=7, seed=42)
    assert len(events_1) == len(events_2)
    for a, b in zip(events_1, events_2):
        assert a.event_id == b.event_id
        assert a.event_type == b.event_type
        assert a.case_id == b.case_id


def test_fixture_default_scale_produces_expected_event_volume():
    """200 customers × 60 days × avg ~4.5 events per case ≈ 54,000+ events."""
    log = build_phuc_long_event_log()
    # Minimum sanity: at least 50k events at full scale.
    assert len(log.events) > 50_000
    # Tenant tagged correctly.
    assert str(log.tenant_id) == PHUC_LONG_TENANT_ID


def test_fixture_event_types_match_8_variants():
    """All 8 expected event types appear in default fixture."""
    log = build_phuc_long_event_log(num_customers=50, days=10)
    types = {ev.event_type for ev in log.events}
    # 7 always-on types + refund (probabilistic).
    expected = {
        "view_menu",
        "add_cart",
        "choose_payment",
        "pay_card",
        "pay_cash",
        "complete",
        "abandon",
    }
    assert expected.issubset(types)
    # refund may or may not appear in small sample — check at full scale below.


def test_fixture_full_scale_includes_refund():
    """At default scale, 1% refund probability over ~9000 happy cases →
    expect ~90 refunds. Sanity: at least 1."""
    log = build_phuc_long_event_log()
    types = {ev.event_type for ev in log.events}
    assert "refund" in types


def test_heuristic_miner_produces_expected_top_edges():
    """Mining the fixture should surface happy-path edges as top frequency."""
    log = build_phuc_long_event_log(num_customers=100, days=30)
    miner = HeuristicMiner(min_frequency=1)
    mined = miner.mine(log)
    # Happy paths share these 3 edges — they should be the top counts.
    df = mined.direct_follows
    assert df[("view_menu", "add_cart")] > 0
    assert df[("add_cart", "choose_payment")] > df[("add_cart", "abandon")]
    assert df[("pay_card", "complete")] > 0


def test_payload_shape_matches_mine_endpoint(tmp_path):
    """build_phuc_long_payload output must be JSON-serialisable + accepted
    by /process-mining/mine. Smoke roundtrip with TestClient."""
    import json

    import ai_orchestrator.routers.process_mining as pm_module

    test_app = FastAPI()
    test_app.include_router(pm_module.router)
    client = TestClient(test_app)

    # Use small scale so test runs fast.
    payload = build_phuc_long_payload(num_customers=5, days=3, min_frequency=1)
    # Must be JSON-clean (datetimes serialised as ISO strings).
    json.dumps(payload)

    r = client.post(
        "/process-mining/mine",
        json=payload,
        headers={"X-Enterprise-Id": PHUC_LONG_TENANT_ID},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["case_count"] > 0
    assert "view_menu|add_cart" in body["direct_follows"]


def test_three_variants_present_at_full_scale():
    """Distribution should reflect 75/15/10 variant weights."""
    log = build_phuc_long_event_log()
    # Count case_ids by their last event_type.
    case_last_event: dict[str, str] = {}
    for ev in log.events:
        if ev.case_id:
            # Track last NON-refund event since refund is post-complete.
            if ev.event_type != "refund":
                case_last_event[ev.case_id] = ev.event_type
    completes = sum(1 for v in case_last_event.values() if v == "complete")
    abandons = sum(1 for v in case_last_event.values() if v == "abandon")
    total = completes + abandons
    # At full scale (200×60 = 12,000 cases) the distribution should be
    # close to 90% complete vs 10% abandon. Allow ±3%.
    complete_pct = completes / total
    assert 0.86 < complete_pct < 0.94, (
        f"happy paths {complete_pct:.2%} — expected ~90% (happy_card + happy_cash)"
    )
