"""
Tests for workflow_runtime.temporal_client — config, ID derivation,
client caching. No live Temporal needed; the connect() path is covered
by the worker-environment tests in test_analyze_pipeline_workflow.py.
"""
from __future__ import annotations

import os
from unittest.mock import patch
from uuid import UUID

import pytest

from ai_orchestrator.workflow_runtime.temporal_client import (
    TemporalConfig,
    reset_client,
    workflow_id_for,
)


# ---------------------------------------------------------------------------
# Config — env defaults + truthy parsing
# ---------------------------------------------------------------------------


def test_temporal_config_defaults_match_docker_compose_dev():
    """Defaults assume the docker-compose dev cluster — laptop dev must
    work without setting any env vars."""
    env = {k: v for k, v in os.environ.items()
           if not k.startswith("TEMPORAL_")}
    with patch.dict(os.environ, env, clear=True):
        cfg = TemporalConfig.from_env()
    assert cfg.address == "localhost:7233"
    assert cfg.namespace == "kaori"
    assert cfg.task_queue == "kaori-default"
    assert cfg.enable_worker is False  # opt-in Phase 1.5


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("true", True), ("True", True), ("TRUE", True),
        ("1", True), ("yes", True), ("YES", True), ("on", True),
        ("false", False), ("0", False), ("no", False),
        ("", False), ("maybe", False), ("2", False),
    ],
)
def test_temporal_enable_worker_truthy_values(raw, expected):
    """The worker must only enable on the documented truthy values.

    Anything else (typos, unset, '2') means disabled — matches how
    EXTERNAL_AI_ENABLED behaves so users have one mental model.
    """
    with patch.dict(os.environ, {"TEMPORAL_ENABLE_WORKER": raw}, clear=False):
        cfg = TemporalConfig.from_env()
    assert cfg.enable_worker is expected


# ---------------------------------------------------------------------------
# Workflow ID — canonical t-{tenant}-{run} prefix
# ---------------------------------------------------------------------------


def test_workflow_id_for_string_inputs():
    assert workflow_id_for("tenant-abc", "run-123") == "t-tenant-abc-run-123"


def test_workflow_id_for_uuid_inputs():
    """UUIDs must stringify the same way path builders do (kaori_vault
    tenant_path) — keeps the workflow_id greppable across services."""
    tenant = UUID("11111111-1111-1111-1111-111111111111")
    run = UUID("22222222-2222-2222-2222-222222222222")
    wid = workflow_id_for(tenant, run)
    assert wid == "t-11111111-1111-1111-1111-111111111111-22222222-2222-2222-2222-222222222222"


def test_workflow_id_for_rejects_empty():
    """Empty tenant or run = unfilterable workflow in the UI. Reject so
    a malformed payload can't sneak past."""
    with pytest.raises(ValueError, match="non-empty"):
        workflow_id_for("", "r1")
    with pytest.raises(ValueError, match="non-empty"):
        workflow_id_for("t1", "")
    with pytest.raises(ValueError, match="non-empty"):
        workflow_id_for("   ", "r1")  # whitespace-only treated as empty


def test_workflow_id_for_strips_whitespace():
    """Accidental leading/trailing whitespace from a request body must
    not produce a workflow_id with embedded spaces. Strip explicitly."""
    assert workflow_id_for("  tenant-x  ", "  run-y  ") == "t-tenant-x-run-y"


# ---------------------------------------------------------------------------
# Client caching — reset_client() is the test-isolation primitive
# ---------------------------------------------------------------------------


def test_reset_client_clears_module_cache():
    """Tests that need a fresh client must call reset_client() — confirm
    it actually resets the module-level cache."""
    import ai_orchestrator.workflow_runtime.temporal_client as mod
    mod._client = object()  # plant a sentinel
    reset_client()
    assert mod._client is None
