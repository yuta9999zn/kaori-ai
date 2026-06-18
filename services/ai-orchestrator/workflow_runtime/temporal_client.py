"""
Temporal client wrapper — single connection per process, async-first.

Phase 1.5 P15-S9 D3 — first real wiring of the workflow_runtime contract
surface to a Temporal server. The wrapper is intentionally thin:

  * connect() returns a cached temporalio.client.Client.
  * start_workflow() prefixes workflow_id with `t-{tenant_id}-` per the
    operational note in infrastructure/temporal/README.md (K-1 + ADR-0013
    spirit applied to Temporal IDs — every running workflow is greppable
    by tenant in the UI).
  * Configuration comes entirely from env (no hard-coded host) so the
    same code runs against docker-compose dev (localhost:7233) and
    production K8s (temporal-frontend.temporal.svc.cluster.local:7233).

Why the temporalio import is conditional
=========================================
The package (and its grpc/protobuf transitive deps) is heavy. CI lanes
that only run unit tests for ``side_effect`` / ``yaml_schema`` /
``idempotency`` should not need it installed. The connect path imports
the SDK lazily; module import always succeeds, so callers like
ai_orchestrator.main can `from .temporal_client import ...` without
forcing the dependency on every consumer.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Optional
from uuid import UUID

import structlog

if TYPE_CHECKING:  # pragma: no cover — type-only import
    from temporalio.client import Client, WorkflowHandle

log = structlog.get_logger()


# ---------------------------------------------------------------------------
# Config — read once per process, override via env. The defaults match
# the docker-compose dev cluster (auto-setup image with `kaori` namespace
# registered by the bootstrap container).
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class TemporalConfig:
    """Connection + namespace config for the workflow worker.

    Single dataclass so tests can construct synthetic configs without
    monkeypatching env, and main.py lifespan can hand the config to both
    the client wrapper and the worker entrypoint.
    """

    address: str
    namespace: str
    task_queue: str
    enable_worker: bool

    @classmethod
    def from_env(cls) -> "TemporalConfig":
        """Build a config from the standard env contract.

        TEMPORAL_ADDRESS    default localhost:7233 (docker-compose)
        TEMPORAL_NAMESPACE  default 'kaori' (registered by bootstrap)
        TEMPORAL_TASK_QUEUE default 'kaori-default'
        TEMPORAL_ENABLE_WORKER  default 'false' — Phase 1.5 rollout
                                opt-in until the cluster is verified
                                stable, then flip the default.
        """
        return cls(
            address=os.getenv("TEMPORAL_ADDRESS", "localhost:7233"),
            namespace=os.getenv("TEMPORAL_NAMESPACE", "kaori"),
            task_queue=os.getenv("TEMPORAL_TASK_QUEUE", "kaori-default"),
            enable_worker=_truthy(os.getenv("TEMPORAL_ENABLE_WORKER", "false")),
        )


def _truthy(s: str) -> bool:
    """Match the env-var conventions used elsewhere (kaori_vault profile,
    EXTERNAL_AI_ENABLED) — accept '1', 'true', 'yes' (case-insensitive).
    Anything else is false. Centralised here so worker enable/disable
    obeys the same rules as every other feature flag."""
    return s.strip().lower() in {"1", "true", "yes", "on"}


# ---------------------------------------------------------------------------
# Process-global client — Temporal SDK opens a long-lived gRPC channel;
# multiple connections per process is wasteful + makes shutdown noisy.
# ---------------------------------------------------------------------------


_client: "Client | None" = None


async def connect(config: Optional[TemporalConfig] = None) -> "Client":
    """Connect (or return the cached client). Idempotent.

    The first caller wins — subsequent calls receive the same Client even
    if they pass a different config. That mirrors how `init_db_pool()`
    behaves elsewhere; tests that need isolation should call
    :func:`reset_client` first.
    """
    global _client
    if _client is not None:
        return _client

    from temporalio.client import Client  # lazy import (see module docstring)

    cfg = config or TemporalConfig.from_env()
    log.info(
        "temporal.client.connecting",
        address=cfg.address,
        namespace=cfg.namespace,
    )
    _client = await Client.connect(cfg.address, namespace=cfg.namespace)
    log.info(
        "temporal.client.connected",
        address=cfg.address,
        namespace=cfg.namespace,
    )
    return _client


def reset_client() -> None:
    """Drop the cached client. Used by tests + by lifespan shutdown.

    Doesn't try to gracefully close — Temporal SDK clients have no
    explicit close method (the underlying channel cleans itself up on
    GC). Resetting the reference is enough to trigger that.
    """
    global _client
    _client = None


# ---------------------------------------------------------------------------
# Workflow ID conventions — applied at start-time so the UI + tctl can
# filter by tenant without parsing workflow input. Matches the convention
# documented in infrastructure/temporal/README.md.
# ---------------------------------------------------------------------------


def workflow_id_for(tenant_id: str | UUID, run_id: str | UUID) -> str:
    """Build the canonical Temporal workflow ID `t-{tenant}-{run}`.

    Both pieces are stringified verbatim. The function rejects empty
    inputs so a malformed payload can't sneak a workflow into the cluster
    with id 't--' (which is technically valid but unfilterable).
    """
    t = str(tenant_id).strip()
    r = str(run_id).strip()
    if not t or not r:
        raise ValueError(
            "workflow_id_for requires non-empty tenant_id and run_id "
            f"(got tenant={tenant_id!r}, run={run_id!r})"
        )
    return f"t-{t}-{r}"


async def start_workflow(
    workflow: Any,
    *args: Any,
    tenant_id: str | UUID,
    run_id: str | UUID,
    config: Optional[TemporalConfig] = None,
    **kwargs: Any,
) -> "WorkflowHandle":
    """Start a workflow with the canonical id + the configured task queue.

    Thin pass-through to ``Client.start_workflow``; the only opinions
    are the id derivation (``workflow_id_for``) and the task_queue
    default (from config). Callers can still override task_queue via
    kwargs if a workflow needs a dedicated queue (rare — most live on
    `kaori-default`).
    """
    cfg = config or TemporalConfig.from_env()
    client = await connect(cfg)

    kwargs.setdefault("task_queue", cfg.task_queue)
    kwargs.setdefault("id", workflow_id_for(tenant_id, run_id))

    log.info(
        "temporal.workflow.start",
        workflow_id=kwargs["id"],
        task_queue=kwargs["task_queue"],
        tenant_id=str(tenant_id),
    )
    return await client.start_workflow(workflow, *args, **kwargs)
