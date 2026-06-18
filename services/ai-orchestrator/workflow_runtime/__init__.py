"""
Workflow Runtime — L4 of the Kaori stack (Workflow System v2.0).

Phase 1 v4 P1-S6 ships the contract surface for Temporal-based workflow
orchestration:
  * 5 side-effect class taxonomy (REL-001 / K-17)
  * Workflow YAML schema + validator (REL-002)
  * Idempotency key derivation (REL-004)
  * idempotency_records DB lookup (REL-005, migration 041)

Real Temporal worker process + saga orchestrator + DLQ admin UI ship
Phase 1.5+ when the FPT Cloud K8s cluster lands (per ADR-0011 +
ADR-0010 — Phase 1 keeps modular monolith).

Phase 2 P2-S19 extracts this whole package into ``services/workflow-engine/``
with a gRPC API (skeleton already exists at services/workflow-engine/).

See:
  * docs/strategic/WORKFLOW_SYSTEM.md PART V (Workflow Engine Architecture)
  * docs/adr/0011-temporal-for-workflow-orchestration.md
  * docs/adr/0014-at-least-once-plus-idempotency.md
"""

from .side_effect import SideEffectClass, validate_side_effect_class
from .idempotency import derive_idempotency_key

__all__ = [
    "SideEffectClass",
    "validate_side_effect_class",
    "derive_idempotency_key",
]
