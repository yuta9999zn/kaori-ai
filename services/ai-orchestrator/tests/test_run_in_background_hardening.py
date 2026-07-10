"""
Tests for run_in_background orphan hardening.

Incident 2026-07-10 (run d3d2e493): a uvicorn worker died while a
BackgroundTasks-launched run awaited an LLM node. asyncio.CancelledError
is a BaseException on py3.11, so the old ``except Exception`` neither
logged nor released the run — the workflow_runs row froze at
status='running' forever with no error_summary.

Contract pinned here: any exit of the background coroutine that is not a
clean return must best-effort mark the run failed. Cancellation re-raises
(cooperative cancellation must propagate); crashes stay swallowed
(spawn-and-forget — a failed run must never crash the parent process).
"""
from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest

from ai_orchestrator.workflow_runtime import runner as runner_mod


@pytest.mark.asyncio
async def test_cancelled_background_run_marks_run_failed_and_reraises():
    run_id, eid = uuid4(), uuid4()
    with patch.object(runner_mod.WorkflowRunner, "run",
                      AsyncMock(side_effect=asyncio.CancelledError())), \
         patch.object(runner_mod.WorkflowRunner, "_update_run_status",
                      AsyncMock()) as upd:
        with pytest.raises(asyncio.CancelledError):
            await runner_mod.run_in_background(
                run_id=run_id, enterprise_id=eid,
            )

    upd.assert_awaited_once()
    args, kwargs = upd.await_args
    assert args[0] == run_id
    assert args[1] == eid
    assert kwargs["status"] == "failed"
    assert kwargs["ended"] is True
    assert "cancel" in kwargs["error_summary"].lower()


@pytest.mark.asyncio
async def test_crashed_background_run_marks_run_failed_without_reraise():
    run_id, eid = uuid4(), uuid4()
    with patch.object(runner_mod.WorkflowRunner, "run",
                      AsyncMock(side_effect=RuntimeError("boom-42"))), \
         patch.object(runner_mod.WorkflowRunner, "_update_run_status",
                      AsyncMock()) as upd:
        # Spawn-and-forget: the crash must NOT propagate.
        await runner_mod.run_in_background(run_id=run_id, enterprise_id=eid)

    upd.assert_awaited_once()
    _, kwargs = upd.await_args
    assert kwargs["status"] == "failed"
    assert kwargs["ended"] is True
    assert "boom-42" in kwargs["error_summary"]


@pytest.mark.asyncio
async def test_cancellation_reraises_even_when_mark_failed_itself_fails():
    """During shutdown the DB pool may already be closing — the
    best-effort mark must never mask the CancelledError."""
    run_id, eid = uuid4(), uuid4()
    with patch.object(runner_mod.WorkflowRunner, "run",
                      AsyncMock(side_effect=asyncio.CancelledError())), \
         patch.object(runner_mod.WorkflowRunner, "_update_run_status",
                      AsyncMock(side_effect=RuntimeError("pool closed"))):
        with pytest.raises(asyncio.CancelledError):
            await runner_mod.run_in_background(
                run_id=run_id, enterprise_id=eid,
            )


@pytest.mark.asyncio
async def test_clean_run_does_not_touch_run_status_from_wrapper():
    """A successful run() already wrote its own terminal status — the
    wrapper must not second-guess it."""
    run_id, eid = uuid4(), uuid4()
    with patch.object(runner_mod.WorkflowRunner, "run",
                      AsyncMock(return_value={"status": "completed"})), \
         patch.object(runner_mod.WorkflowRunner, "_update_run_status",
                      AsyncMock()) as upd:
        await runner_mod.run_in_background(run_id=run_id, enterprise_id=eid)

    upd.assert_not_awaited()
