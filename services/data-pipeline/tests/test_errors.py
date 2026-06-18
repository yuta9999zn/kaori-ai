"""
Tests for the K-14 RFC 7807 error envelope.

Builds a tiny FastAPI app in-process, registers the same handlers
production code does, and asserts wire-format compliance for the
three error paths (HTTPException, validation, unhandled).
"""
import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from pydantic import BaseModel

from data_pipeline.shared.errors import PROBLEM_JSON, register_problem_handlers


def _make_app() -> FastAPI:
    app = FastAPI()
    register_problem_handlers(app)

    class Body(BaseModel):
        n: int

    @app.get("/boom-string")
    def _boom_string():
        raise HTTPException(status_code=404, detail="thing not found")

    @app.get("/boom-default-title")
    def _boom_default():
        # detail omitted → handler must fall back to status-derived title.
        raise HTTPException(status_code=403)

    @app.post("/echo")
    def _echo(body: Body):
        return {"ok": body.n}

    @app.get("/crash")
    def _crash():
        raise RuntimeError("oh no")

    return app


def _assert_problem(resp, *, status: int, instance: str):
    assert resp.status_code == status
    assert resp.headers["content-type"].startswith(PROBLEM_JSON)
    body = resp.json()
    assert body["type"] == "about:blank"
    assert body["status"] == status
    assert body["instance"] == instance
    assert "title" in body
    return body


def test_http_exception_with_string_detail_uses_detail_as_title():
    client = TestClient(_make_app())
    body = _assert_problem(client.get("/boom-string"), status=404, instance="/boom-string")
    assert body["title"] == "thing not found"
    # detail field omitted when title == detail (avoid duplicating the same string).
    assert "detail" not in body


def test_http_exception_without_detail_falls_back_to_status_title():
    client = TestClient(_make_app())
    body = _assert_problem(client.get("/boom-default-title"), status=403, instance="/boom-default-title")
    assert body["title"] == "Forbidden"


def test_validation_error_returns_422_problem():
    client = TestClient(_make_app())
    body = _assert_problem(client.post("/echo", json={"n": "not a number"}), status=422, instance="/echo")
    assert body["title"] == "Validation Error"
    assert "detail" in body  # surfacing the pydantic errors list as a string


def test_unhandled_exception_returns_500_problem_without_leaking_internals():
    client = TestClient(_make_app(), raise_server_exceptions=False)
    body = _assert_problem(client.get("/crash"), status=500, instance="/crash")
    assert body["title"] == "Internal Server Error"
    # No leaking of "oh no" / RuntimeError / stack trace into the wire body.
    assert "detail" not in body
    assert "oh no" not in str(body)
    assert "RuntimeError" not in str(body)


def test_response_media_type_is_application_problem_json():
    client = TestClient(_make_app())
    resp = client.get("/boom-string")
    assert resp.headers["content-type"].split(";")[0].strip() == "application/problem+json"
