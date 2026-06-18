"""
EU AI Act Art 50 (K-24) — AI-generated disclosure on InferResponse.

Import root matches the existing llm-gateway test convention
(``from llm_gateway.X import ...``; conftest.py mirrors the Docker
package layout so ``llm_gateway`` resolves to services/llm-gateway/).

Two layers:
  * Unit  — build_disclosure() is a pure, total builder.
  * Gateway — POST /v1/infer surfaces the disclosure on the response,
              mirroring the test_router.py TestClient harness.
"""
from unittest.mock import patch
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from llm_gateway.models import AiDisclosure, build_disclosure


# ─── Unit — pure builder ─────────────────────────────────────────────

def test_build_disclosure_internal():
    d = build_disclosure("qwen2.5:14b", "internal")
    assert isinstance(d, AiDisclosure)
    assert d.generated_by_ai is True
    assert d.model == "qwen2.5:14b"
    assert d.method == "internal"
    assert d.notice_vi and d.notice_en


def test_build_disclosure_external_reflects_method():
    d = build_disclosure("claude-sonnet-4-6", "external")
    assert d.method == "external"
    assert d.model == "claude-sonnet-4-6"
    assert d.generated_by_ai is True


# ─── Gateway — /v1/infer surfaces the disclosure ─────────────────────
# Mirrors test_router.py: router mounted in a bare app, every
# collaborator patched so no real LLM / DB runs.

from llm_gateway.errors import register_problem_handlers  # noqa: E402
from llm_gateway.router import router as v1_router  # noqa: E402


@pytest.fixture
def client():
    app = FastAPI()
    register_problem_handlers(app)
    app.include_router(v1_router)
    return TestClient(app)


def _payload(**overrides):
    base = {
        "task": "schema_mapping",
        "prompt": "Map columns",
        "enterprise_id": str(uuid4()),
        "consent_external": False,
        "max_tokens": 200,
    }
    base.update(overrides)
    return base


def test_infer_response_carries_disclosure(client):
    from unittest.mock import AsyncMock
    model_used = "qwen2.5:14b"
    patches = [
        patch("llm_gateway.router.get_pool", return_value=object()),
        patch("llm_gateway.router.routing.resolve_model",
              AsyncMock(return_value=(model_used, "internal"))),
        patch("llm_gateway.router.providers.invoke",
              AsyncMock(return_value=("an AI answer", model_used))),
        patch("llm_gateway.router.providers.invoke_chat",
              AsyncMock(return_value=("an AI answer", model_used, None, "stop"))),
        patch("llm_gateway.router.audit.log_decision", AsyncMock(return_value=None)),
        patch("llm_gateway.router.ai_governance.record_ai_call",
              AsyncMock(return_value=None)),
        patch("llm_gateway.router.tenant_quotas.check_and_consume",
              AsyncMock(return_value=None)),
    ]
    for p in patches:
        p.start()
    try:
        resp = client.post("/v1/infer", json=_payload())
    finally:
        for p in reversed(patches):
            p.stop()

    assert resp.status_code == 200
    body = resp.json()
    assert body["disclosure"]["generated_by_ai"] is True
    assert body["disclosure"]["model"] == model_used
    assert body["disclosure"]["method"] == "internal"
    assert body["disclosure"]["notice_vi"]
    assert body["disclosure"]["notice_en"]
