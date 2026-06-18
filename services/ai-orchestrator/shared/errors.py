"""
RFC 7807 ``application/problem+json`` error envelope (K-14).

Wraps every error response in:

    {
        "type":     "about:blank",
        "title":    "...",
        "status":   <int>,
        "detail":   "...",
        "instance": "/the/request/path"
    }

with ``Content-Type: application/problem+json``. Three handlers cover
the FastAPI default failure paths:

  HTTPException            — anything raise()d via fastapi.HTTPException
                             or starlette.exceptions.HTTPException.
  RequestValidationError   — Pydantic body/query/path validation.
  Exception (catch-all)    — unhandled errors. Logs the traceback so
                             the response can stay generic without
                             leaking internals.

Register in main.py via:

    from .shared.errors import register_problem_handlers
    register_problem_handlers(app)

Endpoints don't need to change. Existing ``raise HTTPException(...)``
calls automatically come out in RFC 7807 shape.
"""
from __future__ import annotations

import structlog
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from .error_codes import default_code_for, VALIDATION_GENERIC

log = structlog.get_logger()

PROBLEM_JSON = "application/problem+json"


def _problem(
    *,
    status: int,
    title: str,
    detail: str | None = None,
    instance: str | None = None,
    type_: str = "about:blank",
    code: str | None = None,
) -> dict:
    """Build an RFC 7807 envelope. ``code`` is the canonical machine-readable
    key (``DOMAIN.NAME`` from ``error_codes.py``) — falls back to a status-
    derived default when the caller doesn't pass one, so every error
    response surfaces a non-null ``code`` to the FE."""
    body: dict = {
        "type":   type_,
        "title":  title,
        "status": status,
        "code":   code or default_code_for(status),
    }
    if detail is not None:
        body["detail"] = detail
    if instance is not None:
        body["instance"] = instance
    return body


async def _http_exception_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    detail = exc.detail if isinstance(exc.detail, str) else None
    title = (
        detail
        if detail and exc.status_code < 500
        else _default_title(exc.status_code)
    )
    return JSONResponse(
        status_code=exc.status_code,
        media_type=PROBLEM_JSON,
        content=_problem(
            status=exc.status_code,
            title=title,
            detail=detail if detail and title != detail else None,
            instance=request.url.path,
        ),
    )


async def _validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    return JSONResponse(
        status_code=422,
        media_type=PROBLEM_JSON,
        content=_problem(
            status=422,
            title="Validation Error",
            detail=str(exc.errors()),
            instance=request.url.path,
            code=VALIDATION_GENERIC,
        ),
    )


async def _unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    # Log the traceback once on the server so the wire response can stay
    # generic. Operators see `unhandled_exception` in structured logs;
    # API clients only see the title.
    log.exception("unhandled_exception", path=request.url.path, error=str(exc))
    return JSONResponse(
        status_code=500,
        media_type=PROBLEM_JSON,
        content=_problem(
            status=500,
            title="Internal Server Error",
            instance=request.url.path,
        ),
    )


def _default_title(status: int) -> str:
    return {
        400: "Bad Request",
        401: "Unauthorized",
        403: "Forbidden",
        404: "Not Found",
        405: "Method Not Allowed",
        409: "Conflict",
        422: "Unprocessable Entity",
        429: "Too Many Requests",
        500: "Internal Server Error",
        502: "Bad Gateway",
        503: "Service Unavailable",
        504: "Gateway Timeout",
    }.get(status, "Error")


def register_problem_handlers(app: FastAPI) -> None:
    """Attach the three RFC 7807 handlers to a FastAPI app."""
    app.add_exception_handler(StarletteHTTPException, _http_exception_handler)
    app.add_exception_handler(RequestValidationError, _validation_exception_handler)
    app.add_exception_handler(Exception, _unhandled_exception_handler)
