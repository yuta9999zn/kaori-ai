"""End-to-end Build Week demo chain — P15-S11 Tuần 6.

Exercises the full happy-path flow that the 8/7 presentation walks
through:

    POST /process-mining/mine          (Phúc Long event fixture)
        ↓ direct_follows JSON
    POST /cdfl/plan-next-action        (current state = browse-equivalent)
        ↓ top-K ranked actions
    POST /workflow/from-cdfl-plan      (telegram intervention channel)
        ↓ valid Temporal YAML
    POST /rag/answer?ranking=cdfl_ig   (Tableau book corpus, 3 queries)

Each step's invariants are asserted. The test is intentionally a SINGLE
function so a regression at any point fails the whole chain — anh wants
to know "did the demo flow still work after my last change?" without
parsing 5 separate test outputs.

All inputs are in-memory fixtures (no DB, no external service, no LLM
calls). Tableau book tree fixture is loaded from the committed JSON if
present; otherwise that step is skipped with an explanatory message
(skipif on fixture presence).
"""
from __future__ import annotations

import asyncio
from pathlib import Path

import pytest
import yaml
from fastapi import FastAPI
from fastapi.testclient import TestClient

from ai_orchestrator.tests.fixtures.demo_phuc_long import (
    PHUC_LONG_TENANT_ID,
    build_phuc_long_payload,
)
from ai_orchestrator.workflow_runtime.yaml_schema import validate_workflow_yaml


HEADERS = {"X-Enterprise-Id": PHUC_LONG_TENANT_ID}

_TABLEAU_BOOK_SHA = "0572777beef3ea9a93de3b5ffea5759890263d92693b24e08bf62fc386cb9167"
_TABLEAU_FIXTURE = (
    Path(__file__).resolve().parent / "fixtures" / "pageindex_trees" /
    f"{_TABLEAU_BOOK_SHA}.json"
)


@pytest.fixture
def app():
    """Compose all 4 routers under one app for the E2E walk."""
    import ai_orchestrator.routers.process_mining as pm
    import ai_orchestrator.routers.cdfl as cdfl_router
    import ai_orchestrator.routers.workflow_from_cdfl as wf
    import ai_orchestrator.routers.rag as rag_module

    rag_module._ROUTER_SINGLETON = None  # type: ignore[attr-defined]
    rag_module._RERANKER_SINGLETON = None  # type: ignore[attr-defined]
    rag_module._TREE_BUILDER_SINGLETON = None  # type: ignore[attr-defined]

    test_app = FastAPI()
    test_app.include_router(pm.router)
    test_app.include_router(cdfl_router.router)
    test_app.include_router(wf.router)
    test_app.include_router(rag_module.router)
    return test_app


@pytest.fixture
def client(app):
    with TestClient(app, raise_server_exceptions=True) as c:
        yield c


def test_demo_chain_mine_to_plan_to_yaml_to_rag(client):
    """Full Build Week demo flow under one assert chain."""

    # ── Step 1: mine workflow from Phúc Long fixture ──
    # Use small subset for test speed — full 200×60 takes ~1s; 20×7 is plenty
    # to surface direct-follow edges for the happy paths.
    payload = build_phuc_long_payload(num_customers=20, days=7, min_frequency=1)
    r_mine = client.post(
        "/process-mining/mine",
        json=payload,
        headers=HEADERS,
    )
    assert r_mine.status_code == 200, r_mine.text
    mined = r_mine.json()
    assert mined["case_count"] > 100  # 20 cust × 7 day = 140 cases
    assert "view_menu|add_cart" in mined["direct_follows"]
    assert "add_cart|choose_payment" in mined["direct_follows"]

    # ── Step 2: ask CDFL planner what to do from "browse"-equivalent ──
    # Customer is at `add_cart` — Plan recommends next action.
    plan_body = {
        "direct_follows": mined["direct_follows"],
        "current_state": "add_cart",
        "top_k": 3,
        "seed": 42,
    }
    r_plan = client.post(
        "/cdfl/plan-next-action",
        json=plan_body,
        headers=HEADERS,
    )
    assert r_plan.status_code == 200, r_plan.text
    plan = r_plan.json()
    assert plan["current_state"] == "add_cart"
    assert len(plan["top_actions"]) >= 1
    assert "NNL-NTHT" in plan["theory_position"] or "CDFL" in plan["theory_position"]
    # CDFL exploration semantics (faithful to luận văn): the well-trodden
    # successors of `add_cart` (`choose_payment` count≈126, `abandon` count≈14)
    # have LOW uncertainty after pre-seeding from direct_follows. Top-K
    # therefore favours actions UNobserved from `add_cart` — agent
    # prioritises "khám phá vùng chưa biết". This IS the demo narrative.
    top_action_names = {a["action"] for a in plan["top_actions"]}
    # Top-1 should have visit_proxy=0 (never observed from add_cart).
    assert plan["top_actions"][0]["visit_proxy"] == 0, (
        f"top action {plan['top_actions'][0]['action']!r} should have "
        f"visit_proxy=0 (CDFL prefers unexplored); got "
        f"{plan['top_actions'][0]['visit_proxy']}"
    )
    # Happy-path successors (choose_payment + abandon) are explored →
    # they should NOT be in top-K for K=3 in this small action space.
    explored_successors = {"choose_payment", "abandon"}
    assert not (top_action_names & explored_successors), (
        f"explored successors {top_action_names & explored_successors} "
        f"should be ranked LOW by CDFL, not in top-{plan_body['top_k']}"
    )

    # ── Step 3: emit a Temporal workflow YAML from the plan ──
    emit_body = {
        "current_state": plan["current_state"],
        "top_actions": plan["top_actions"],
        "intervention_channel": "telegram",
        "workflow_name_suffix": "phuc_long_demo",
    }
    r_emit = client.post(
        "/workflow/from-cdfl-plan",
        json=emit_body,
        headers=HEADERS,
    )
    assert r_emit.status_code == 200, r_emit.text
    emit = r_emit.json()
    assert emit["k17_check"] == "passed"
    assert "phuc_long_demo" in emit["workflow_id"]

    # YAML round-trip + revalidate via the production schema validator
    # (so the demo asset is the same YAML operators upload manually).
    doc = yaml.safe_load(emit["yaml"])
    assert doc == emit["yaml_parsed"]
    validate_workflow_yaml(doc)

    # Telegram channel → 4 nodes incl. external notify with compensation.
    assert len(doc["nodes"]) == 4
    notify = next(n for n in doc["nodes"] if n["node_id"] == "notify_customer")
    assert notify["side_effect_class"] == "external"
    assert "compensation" in notify

    # ── Step 4: RAG demo — 3 queries with cdfl_ig ranking ──
    # Stub tree (default for /rag/answer cdfl_ig path) has 2 leaves —
    # second query should pick the OTHER leaf after first observed.
    pages_seen = []
    for i, query_text in enumerate([
        "What is dashboard design about?",
        "How to handle color contrast?",
        "Best practice for storytelling?",
    ]):
        r_rag = client.post(
            "/rag/answer?ranking=cdfl_ig",
            json={"query_text": query_text},
            headers=HEADERS,
        )
        assert r_rag.status_code == 200, r_rag.text
        body = r_rag.json()
        assert body["engine_name"] == "pageindex"
        assert len(body["citations"]) == 1
        pages_seen.append(body["citations"][0]["page_range"])

    # Across 3 queries the CDFL agent should have visited BOTH stub leaves
    # (it's a 2-leaf tree). If we see only 1 distinct page across all 3,
    # the IG signal isn't kicking in.
    distinct_pages = set(pages_seen)
    assert len(distinct_pages) >= 2, (
        f"CDFL IG re-ranking should explore both leaves, "
        f"got pages={pages_seen}"
    )


@pytest.mark.skipif(
    not _TABLEAU_FIXTURE.exists(),
    reason="Tableau book fixture not present — run scripts/pageindex_offline_build.py",
)
def test_demo_rag_with_real_tableau_book_fixture(client, monkeypatch):
    """Bonus E2E using the REAL committed Tableau book tree (228 nodes,
    24 chapters). Verifies cdfl_ig works on production-shaped data.

    Swaps the singleton tree builder for FixturePageIndexTreeBuilder
    pointed at the committed JSON, then runs 3 queries and asserts at
    least 3 distinct chapter citations emerge across the session.
    """
    import ai_orchestrator.routers.rag as rag_module
    from reasoning.rag.pageindex import FixturePageIndexTreeBuilder

    # Override the default Stub builder with a Fixture one that targets
    # the Tableau book. Patch the cached singleton.
    fixture_dir = _TABLEAU_FIXTURE.parent
    rag_module._TREE_BUILDER_SINGLETON = None  # type: ignore[attr-defined]

    class _ForceFixtureBuilder(FixturePageIndexTreeBuilder):
        """Force every build() call to load the Tableau fixture, regardless
        of the doc_sha256 the engine passes in."""

        async def build(self, *, tenant_id, doc_sha256, doc_text, doc_kind, meta=None):
            return await super().build(
                tenant_id=tenant_id,
                doc_sha256=_TABLEAU_BOOK_SHA,
                doc_text=doc_text,
                doc_kind=doc_kind,
                meta=meta,
            )

    rag_module._TREE_BUILDER_SINGLETON = _ForceFixtureBuilder(fixture_dir)

    pages_seen = []
    for i in range(5):
        r = client.post(
            "/rag/answer?ranking=cdfl_ig",
            json={"query_text": f"What is chapter {i} about?"},
            headers=HEADERS,
        )
        assert r.status_code == 200, r.text
        body = r.json()
        page = body["citations"][0]["page_range"]
        pages_seen.append(page)

    distinct_pages = set(pages_seen)
    assert len(distinct_pages) >= 3, (
        f"Across 5 queries on a 228-leaf tree, CDFL agent should explore "
        f"≥3 distinct chapters; got {pages_seen}"
    )
