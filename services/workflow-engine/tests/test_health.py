"""Smoke test — /health returns 200 + the expected envelope."""
from fastapi.testclient import TestClient

from main import app

client = TestClient(app)


def test_health_returns_skeleton_envelope() -> None:
    resp = client.get("/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["service"] == "workflow-engine"
    assert body["phase"] == "skeleton"
