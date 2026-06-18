"""
Tests for the ingestion package contract surface.

P1-S3 task B — verifies the Connector ABC + 3 skeleton connectors
(postgres_cdc, excel_filesystem, zalo_metadata) instantiate cleanly,
expose the right ``source`` identifier, and raise NotImplementedError
on extract_events (so a Sprint P1-S7 implementer knows where to wire
the real logic).

Also covers the normalizer + pii stub helpers so the contract surface
doesn't drift silently before the real impl lands.
"""
from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID, uuid4

import pytest

from ingestion.base import Connector, NormalizedEvent
from ingestion.connectors.excel_filesystem import ExcelFilesystemConnector
from ingestion.connectors.postgres_cdc import PostgresCdcConnector
from ingestion.connectors.zalo_metadata import ZaloMetadataConnector
from ingestion.normalizer import build_event, derive_event_id
from ingestion import pii


TENANT = UUID("11111111-1111-1111-1111-111111111111")


# ---------------------------------------------------------------------------
# NormalizedEvent + Connector ABC
# ---------------------------------------------------------------------------


def test_normalized_event_is_immutable_dataclass():
    """frozen=True so accidental mutation in a downstream consumer is
    caught at the call site, not silently propagated through Kafka."""
    ev = NormalizedEvent(
        tenant_id=TENANT,
        event_id="postgres_cdc:abc",
        source="postgres_cdc",
        event_type="order.created",
        occurred_at=datetime(2026, 5, 8, tzinfo=timezone.utc),
    )
    with pytest.raises(Exception):  # FrozenInstanceError or AttributeError
        ev.event_type = "tampered"


def test_connector_subclass_must_declare_source():
    """A Connector subclass without source='' raises at construction
    time — fail loud at startup, not during the first event."""
    class NoSource(Connector):
        async def extract_events(self, **kw):
            raise NotImplementedError
            yield  # pragma: no cover

    with pytest.raises(ValueError, match="source"):
        NoSource(tenant_id=TENANT, config={})


@pytest.mark.asyncio
async def test_connector_default_lifecycle_hooks_are_noop():
    """connect/disconnect default to no-op so stateless connectors
    don't need to override them."""
    c = PostgresCdcConnector(tenant_id=TENANT, config={})
    await c.connect()      # must not raise
    await c.disconnect()   # must not raise


# ---------------------------------------------------------------------------
# Three Phase 1 v4 connectors — skeleton contract
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("cls,expected_source", [
    (PostgresCdcConnector,    "postgres_cdc"),
    (ExcelFilesystemConnector, "excel_filesystem"),
    (ZaloMetadataConnector,   "zalo_metadata"),
])
def test_connector_source_identifier_matches_folder_name(cls, expected_source):
    """The class-level ``source`` attribute must match the folder name
    so log lines + Kafka keys are greppable. Diverging would cause
    silent routing bugs in the consumer."""
    assert cls.source == expected_source


@pytest.mark.parametrize("cls", [
    PostgresCdcConnector,
    ExcelFilesystemConnector,
    ZaloMetadataConnector,
])
def test_connector_can_instantiate_with_minimal_config(cls):
    """Skeleton connectors should construct without external deps —
    actual connection happens in connect() / extract_events()."""
    c = cls(tenant_id=TENANT, config={})
    assert c.tenant_id == TENANT
    assert c.config == {}


@pytest.mark.asyncio
@pytest.mark.parametrize("cls", [
    PostgresCdcConnector,
    ZaloMetadataConnector,
])
async def test_connector_extract_raises_not_implemented_phase_1(cls):
    """Skeleton sentinel: extract_events MUST raise NotImplementedError
    until the connector ships its real impl. If a connector accidentally
    starts emitting events while still a stub, this test fails loudly.

    ExcelFilesystemConnector excluded — shipped real impl P15-S9 D4b;
    its tests live in test_excel_filesystem_connector.py.
    """
    c = cls(tenant_id=TENANT, config={})
    with pytest.raises(NotImplementedError):
        async for _ in c.extract_events():
            break  # pragma: no cover


# ---------------------------------------------------------------------------
# normalizer.derive_event_id + build_event
# ---------------------------------------------------------------------------


def test_derive_event_id_is_deterministic():
    """Same (source, raw_id) → same event_id. Required for Kafka
    consumer-side dedupe (idempotent retries don't double-write)."""
    a = derive_event_id("postgres_cdc", "row-42")
    b = derive_event_id("postgres_cdc", "row-42")
    assert a == b


def test_derive_event_id_is_source_prefixed():
    """Greppable in Loki — log lines carry event_id, ops can filter
    by source without joining to Kafka headers."""
    eid = derive_event_id("zalo_metadata", "thread-99")
    assert eid.startswith("zalo_metadata:")


def test_derive_event_id_differs_per_source_for_same_raw_id():
    """Postgres row id 42 ≠ Excel row id 42 — independent namespaces.
    derive_event_id must keep them apart."""
    pg = derive_event_id("postgres_cdc", "42")
    excel = derive_event_id("excel_filesystem", "42")
    assert pg != excel


def test_build_event_wraps_constructor_with_derived_id():
    ev = build_event(
        tenant_id=TENANT,
        source="postgres_cdc",
        raw_id="row-1",
        event_type="order.created",
        occurred_at=datetime(2026, 5, 8, tzinfo=timezone.utc),
        actor="agent_42",
        case_id="order-99",
    )
    assert ev.tenant_id == TENANT
    assert ev.event_id == derive_event_id("postgres_cdc", "row-1")
    assert ev.source == "postgres_cdc"
    assert ev.actor == "agent_42"
    assert ev.case_id == "order-99"


# ---------------------------------------------------------------------------
# pii stub — Phase 1 v4 returns input unchanged but contract is fixed.
# ---------------------------------------------------------------------------


def test_redact_pii_phase_1_returns_input_unchanged():
    """Stub behaviour: returns input untouched. Sprint P1-S7 ships
    actual VN-aware redaction. This test will need updating when impl
    lands — that's the signal P1-S7 work touched the contract."""
    text = "Anh Nguyễn email yuta@example.com phone 0901234567"
    assert pii.redact_pii(text) == text  # unchanged in stub


def test_redact_event_payload_returns_shallow_copy():
    """Stub returns a shallow copy — caller can rely on receiving a
    new dict (won't mutate caller's payload through the helper)."""
    payload = {"name": "Anh Nguyễn", "phone": "0901234567"}
    result = pii.redact_event_payload(payload)
    assert result == payload
    assert result is not payload  # different dict object


def test_detect_pii_keys_returns_empty_in_phase_1():
    """Stub returns []; real impl Sprint P1-S7 returns key list."""
    assert pii.detect_pii_keys({"name": "Anh", "phone": "0901234567"}) == []
