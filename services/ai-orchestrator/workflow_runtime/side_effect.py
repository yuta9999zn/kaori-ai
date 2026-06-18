"""
REL-001 (P1-S6) — 5 side-effect class taxonomy.

Every workflow node MUST declare one of these classes (K-17 invariant).
The Action Runtime branches on the class to choose the right
reliability strategy:

    pure                 → no side effects, retry freely, no dedup needed
                          examples: parse JSON, compute mean
    read_only            → SELECT/GET, retry freely + cache safely
                          examples: read gold_features (with RLS scope),
                          GET /api/health
    write_idempotent     → UPSERT by natural key, set field to absolute
                          value. Same key → same result. Retry-safe.
                          examples: UPSERT keyed by natural key (workflow
                          status, tenant settings)
    write_non_idempotent → INSERT autoincrement, increment counter,
                          append to log. Need idempotency_records dedup
                          + distributed lock to prevent duplicate effect.
                          examples: append-only audit row, Kafka produce
                          without msg_key
    external             → 3rd-party API with side effect (send email,
                          charge card, post Zalo message). Need
                          provider-side dedup key when supported,
                          saga compensation otherwise.
                          examples: SendGrid email, Stripe charge,
                          Zalo OA message

The validation lives here (not just in YAML schema) because the same
classes appear in:
  * Workflow YAML — at definition time
  * idempotency_records.side_effect_class column — at runtime
  * audit log — for forensics

A single Python enum keeps the names canonical across all three layers.

See:
  * docs/strategic/WORKFLOW_SYSTEM.md Phần 2.1 (5 side-effect classes)
  * docs/adr/0014-at-least-once-plus-idempotency.md
"""
from __future__ import annotations

from enum import Enum


class SideEffectClass(str, Enum):
    """K-17 invariant — workflow node side-effect taxonomy.

    Inheriting from str so JSON-serialisation gives the bare string
    'pure' / 'read_only' / etc. (matches what idempotency_records
    column expects + what YAML schema enforces).
    """

    PURE = "pure"
    READ_ONLY = "read_only"
    WRITE_IDEMPOTENT = "write_idempotent"
    WRITE_NON_IDEMPOTENT = "write_non_idempotent"
    EXTERNAL = "external"

    @classmethod
    def all_values(cls) -> set[str]:
        """All accepted string values — for YAML schema enum constraint."""
        return {member.value for member in cls}


def validate_side_effect_class(value: str | None) -> SideEffectClass:
    """Coerce a string from YAML/JSON into the canonical enum.

    Raises :class:`ValueError` (with K-17 reference in the message) when
    the value is missing or not in the taxonomy. Caller (YAML validator,
    Action Runtime, audit writer) decides whether to convert that into
    HTTP 422 / workflow rejection / fallback path.
    """
    if value is None or not isinstance(value, str) or not value.strip():
        raise ValueError(
            "K-17: every workflow node must declare a side_effect_class — got null/empty. "
            "Choose from: " + ", ".join(sorted(SideEffectClass.all_values()))
        )
    try:
        return SideEffectClass(value.strip())
    except ValueError:
        raise ValueError(
            f"K-17: side_effect_class={value!r} not in taxonomy. "
            "Choose from: " + ", ".join(sorted(SideEffectClass.all_values()))
        )


def needs_idempotency_dedup(klass: SideEffectClass) -> bool:
    """REL-003 helper — does this class need an idempotency_records lookup?

    pure / read_only never write side effects → no dedup needed (retry
    is free). write_idempotent dedups via the natural key the operation
    already uses (same UPSERT twice = same row state). write_non_idempotent
    + external need explicit dedup via idempotency_records before the
    side effect fires.
    """
    return klass in {SideEffectClass.WRITE_NON_IDEMPOTENT, SideEffectClass.EXTERNAL}


def needs_distributed_lock(klass: SideEffectClass) -> bool:
    """REL-006 helper — does this class need a distributed lock around
    the idempotency_records check + side effect?

    Only write_non_idempotent — two concurrent retries on the same node
    must serialise so the dedup row insert wins exactly once. external
    relies on the provider-side dedup key (REL-007) so no lock here.
    """
    return klass == SideEffectClass.WRITE_NON_IDEMPOTENT


def needs_compensation(klass: SideEffectClass) -> bool:
    """REL-011/012 helper — does this class require a compensation
    action declaration in workflow YAML?

    external is the canonical case: send-email can't be undone, but it
    can be followed by a 'send-correction-email' compensation. Saga
    orchestrator (REL-013, P1.5+) reads this list when a downstream
    step fails after this one succeeded.
    """
    return klass == SideEffectClass.EXTERNAL
