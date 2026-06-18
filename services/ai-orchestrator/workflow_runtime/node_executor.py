"""
Node executor registry — closes the gap raised in workflow-gap audit
2026-05-19 where 45 node_type_catalog entries existed but only 14 Temporal
activities mapped to them, leaving 25 mig 069 templates as seed-only.

Architecture
============
Three layers:

  NodeExecutor (ABC)   — contract every executor implements
  NodeExecutorRegistry — singleton mapping node_type_key → NodeExecutor
  NodeContext          — runtime context passed to each executor

A workflow run iterates nodes in topo-sort order, looks up the
executor by node.node_type_catalog_key, and calls
``await executor.execute(context, config)``. The registry is the
single bottleneck — adding a new node type means writing one executor
class and registering it. No Temporal coupling: the registry is
in-process callable so the same executors run from the in-process
runner (Phase 1) or from a Temporal activity wrapper (Phase 2+).

K-rules
-------
K-17: every executor declares ``side_effect_class`` matching the
catalog row. Caller (runner) records the value into
workflow_run_nodes.side_effect_class for post-mortem.

K-13: external + write_non_idempotent classes accept ``idempotency_key``
from context — they short-circuit on duplicate keys via Redis 24h TTL.

K-3: AI executors NEVER call vendor SDK directly. They route through
llm-gateway like every other LLM dispatcher.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Optional
from uuid import UUID

import structlog

from .side_effect import SideEffectClass

log = structlog.get_logger()


@dataclass
class NodeContext:
    """Runtime context handed to every executor.

    ``prior_outputs`` is the accumulated map of completed nodes'
    output_data, keyed by node_id (str). Executors that need branching
    based on upstream values read it here.

    ``prior_items`` (ADR-0034) is the same map in the item-envelope shape
    ``{node_id → Items}`` (see workflow_runtime/items.py). It runs ALONGSIDE
    ``prior_outputs`` (additive, never replaces it): a legacy executor keeps
    reading ``prior_outputs`` dicts; an item-aware executor reads ``prior_items``
    to see all of an upstream node's items + walk ``pairedItem`` lineage. Default
    empty so executors that don't pass it (e.g. utility per-row sub-contexts)
    are unaffected.
    """
    enterprise_id:    UUID
    workspace_id:     Optional[UUID]
    workflow_id:      UUID
    run_id:           UUID
    node_id:          UUID
    user_id:          Optional[UUID]
    input_data:       dict[str, Any]
    prior_outputs:    dict[str, dict[str, Any]] = field(default_factory=dict)
    prior_items:      dict[str, list] = field(default_factory=dict)
    # ADR-0035 B5 — typed side connections feeding THIS node, keyed by port_type
    # ({'ai_tool': [node_id, ...], 'ai_memory': [...], 'ai_model': [...]}).
    # An agent executor reads this to find its tools/memory/model. Default {} —
    # 'main' (flow) edges are NOT here, they drive ordering instead.
    connections:      dict[str, list] = field(default_factory=dict)
    idempotency_key:  Optional[str] = None


@dataclass(frozen=True)
class NodeResult:
    """Result returned by an executor.

    status: 'completed' on success; 'awaiting_approval' for approval_gate
    pause; 'failed' on error. The runner reads this to decide whether to
    proceed to the next node, persist a pause state, or terminate the run.
    """
    status:        str
    output_data:   dict[str, Any]
    error_message: Optional[str] = None


class NodeExecutorError(Exception):
    """Raised by an executor when input config is invalid or pre-flight
    fails. Runner catches and records failure status."""


class NodeExecutor(ABC):
    """Contract every node executor implements.

    Subclasses declare:
      * ``node_type_key`` (matches mig 068 catalog entry).
      * ``side_effect_class`` (K-17 — matches catalog).
      * ``type_version`` (ADR-0034 B3 / K-20 — bump when behaviour/contract
        changes so old workflows pin to the version they were built on).
        Defaults to 1; existing executors need not set it.
      * ``async execute(ctx, config)`` — runs the node.
    """
    node_type_key:     str
    side_effect_class: SideEffectClass
    type_version:      int = 1

    @abstractmethod
    async def execute(
        self,
        ctx:    NodeContext,
        config: dict[str, Any],
    ) -> NodeResult:
        """Run the node. ``config`` is the workflow_nodes.config_json
        for this instance — the catalog's config_schema_json validates
        the shape before the runner gets here."""


class NodeExecutorRegistry:
    """Singleton registry. Caller registers executors at module import
    time; runner looks them up at workflow run."""

    def __init__(self) -> None:
        self._by_key: dict[str, NodeExecutor] = {}
        # ADR-0034 B3 — parallel (key, version) index for version-aware lookup.
        # Kept ALONGSIDE _by_key so has()/get()/list_keys()/coverage_report stay
        # exactly as before (key-only); only get_versioned consults it.
        self._by_key_version: dict[tuple[str, int], NodeExecutor] = {}

    def register(self, executor: NodeExecutor) -> None:
        key = executor.node_type_key
        if key in self._by_key:
            log.warning("node_executor.duplicate_register",
                        node_type_key=key,
                        existing=type(self._by_key[key]).__name__,
                        new=type(executor).__name__)
        self._by_key[key] = executor
        self._by_key_version[(key, getattr(executor, "type_version", 1))] = executor

    def get(self, node_type_key: str) -> NodeExecutor:
        try:
            return self._by_key[node_type_key]
        except KeyError as e:
            raise NodeExecutorError(
                f"No executor registered for node_type_key={node_type_key!r}. "
                f"Registered: {sorted(self._by_key.keys())}"
            ) from e

    def get_versioned(self, node_type_key: str, type_version: int = 1) -> NodeExecutor:
        """Look up by (key, version); fall back to the key's registered executor
        when that exact version isn't present (the common case until a real v2
        executor ships). Lets a workflow pin a node-type version (K-20) without
        breaking when only v1 exists."""
        exact = self._by_key_version.get((node_type_key, type_version))
        if exact is not None:
            return exact
        return self.get(node_type_key)

    def has(self, node_type_key: str) -> bool:
        return node_type_key in self._by_key

    def list_keys(self) -> list[str]:
        return sorted(self._by_key.keys())

    def coverage_report(self, catalog_keys: list[str]) -> dict[str, list[str]]:
        """Diff catalog vs registry. Returns {'registered', 'missing'}."""
        registered = [k for k in catalog_keys if k in self._by_key]
        missing = [k for k in catalog_keys if k not in self._by_key]
        return {"registered": registered, "missing": missing}


# Module-level singleton — import this and call .register() at module load.
REGISTRY = NodeExecutorRegistry()
