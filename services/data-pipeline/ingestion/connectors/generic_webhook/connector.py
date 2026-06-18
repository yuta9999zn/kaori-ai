"""
Generic webhook event-log connector — PM-EVT-008 (P2-S13).

The escape hatch when none of the 7 first-party connectors (Postgres
CDC / Excel / Zalo / Gmail-Outlook / Calendar / Slack-Teams / SharePoint)
fits. Tenants register a webhook URL + a mapping config that says
"my payload's `data.userEmail` is the actor; `data.event_name` is the
event_type; case grouping is `data.orderId`".

Two modes (decided per-tenant):

  * **push mode (default):** tenant POSTs to our webhook URL; we
    map + publish per request. Lowest latency but requires tenant to
    instrument their app or webhook from their existing iPaaS.

  * **pull mode (future):** we long-poll a tenant-supplied REST
    endpoint that returns a list of events since a cursor. Not in this
    commit — needs a poll scheduler + auth strategy registry.

We're strict about mapping shapes:
  * `actor_path`, `event_type_path`, `occurred_at_path` are required
  * `case_id_path` is optional
  * `event_id_path` is optional — if missing we hash the payload
  * extra keys you want preserved go under `payload_keys` (allowlist)

K-5: tenant defines `pii_redact_paths` (list of JSONPaths) — we run
the existing shared/pii redactor over those values before publish.
The connector doesn't know what fields are sensitive in YOUR payload;
the mapping makes you declare them.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, AsyncIterator, Optional
from uuid import UUID

from ...base import Connector, NormalizedEvent


@dataclass(frozen=True)
class WebhookMapping:
    """Per-tenant mapping from raw webhook JSON → NormalizedEvent.

    JSONPath is the simplified dotted form (no `$`, no filters, no
    wildcards) — `data.user.email` reaches `payload['data']['user']['email']`.
    Phase 2 may add full jsonpath-ng if tenants need complex queries.
    """
    actor_path:        str
    event_type_path:   str
    occurred_at_path:  str
    case_id_path:      Optional[str] = None
    event_id_path:     Optional[str] = None
    payload_keys:      tuple[str, ...] = field(default_factory=tuple)
    pii_redact_paths:  tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class GenericWebhookEvent:
    """Wire shape for the in-memory queue mode used in tests + the bg
    worker (push mode bypasses this — endpoint calls map_payload directly)."""
    raw_payload:  dict[str, Any]
    received_at:  datetime


def _dotted_get(d: dict, path: str) -> Any:
    """`data.user.email` → d['data']['user']['email']. Returns None on
    any missing key (doesn't raise)."""
    cur: Any = d
    for part in path.split("."):
        if not isinstance(cur, dict):
            return None
        cur = cur.get(part)
        if cur is None:
            return None
    return cur


def _dotted_set(d: dict, path: str, value: Any) -> None:
    parts = path.split(".")
    cur = d
    for p in parts[:-1]:
        cur = cur.setdefault(p, {})
        if not isinstance(cur, dict):
            return
    cur[parts[-1]] = value


def map_payload(
    raw: dict, mapping: WebhookMapping, *, tenant_id: UUID, source: str,
) -> NormalizedEvent:
    """Pure mapper. Tests import + drive this directly."""
    actor = _dotted_get(raw, mapping.actor_path)
    event_type = _dotted_get(raw, mapping.event_type_path)
    occurred_at_raw = _dotted_get(raw, mapping.occurred_at_path)

    if actor is None or event_type is None or occurred_at_raw is None:
        raise ValueError(
            f"webhook mapping incomplete: actor={actor!r}, "
            f"event_type={event_type!r}, occurred_at={occurred_at_raw!r} "
            f"(raw keys: {list(raw.keys())[:10]})"
        )

    # Parse occurred_at — accept ISO string or unix epoch seconds.
    if isinstance(occurred_at_raw, (int, float)):
        occurred_at = datetime.fromtimestamp(float(occurred_at_raw))
    else:
        try:
            occurred_at = datetime.fromisoformat(str(occurred_at_raw).replace("Z", "+00:00"))
        except ValueError as e:
            raise ValueError(f"occurred_at must be ISO 8601 or epoch; got {occurred_at_raw!r}") from e

    # event_id: tenant-supplied or sha256 of full payload (deterministic).
    if mapping.event_id_path:
        event_id_raw = _dotted_get(raw, mapping.event_id_path)
        if event_id_raw is None:
            raise ValueError(
                f"event_id_path={mapping.event_id_path!r} returned None"
            )
        event_id = str(event_id_raw)
    else:
        event_id = hashlib.sha256(
            json.dumps(raw, sort_keys=True, ensure_ascii=False).encode("utf-8")
        ).hexdigest()[:32]

    # PII redaction on declared paths (K-5).
    if mapping.pii_redact_paths:
        # Walk a deep copy so we don't mutate caller's raw.
        raw = json.loads(json.dumps(raw, ensure_ascii=False))
        for path in mapping.pii_redact_paths:
            val = _dotted_get(raw, path)
            if isinstance(val, str) and val:
                _dotted_set(raw, path, "[redacted]")

    # Build payload allowlist.
    payload: dict[str, Any] = {}
    for k in mapping.payload_keys:
        v = _dotted_get(raw, k)
        if v is not None:
            payload[k] = v
    # Always include the raw event_type for debugging (NOT under
    # payload_keys allowlist so we don't double-include).
    payload["_raw_event_type"] = str(event_type)

    case_id = None
    if mapping.case_id_path:
        cid = _dotted_get(raw, mapping.case_id_path)
        if cid is not None:
            case_id = str(cid)

    return NormalizedEvent(
        tenant_id=tenant_id,
        event_id=f"webhook:{source}:{event_id}",
        source="generic_webhook",
        event_type=f"webhook.{event_type}",
        occurred_at=occurred_at,
        actor=hashlib.sha256(str(actor).strip().lower().encode("utf-8")).hexdigest(),
        case_id=case_id,
        payload=payload,
    )


class GenericWebhookConnector(Connector):
    """Webhook connector. Push-mode primarily — the FastAPI endpoint
    calls map_payload directly. extract_events is a no-op generator
    so the abstract base is satisfied."""

    source = "generic_webhook"

    def __init__(self, *, tenant_id: UUID, config: dict[str, Any]) -> None:
        super().__init__(tenant_id=tenant_id, config=config)
        webhook_label = str(self.config.get("webhook_label", "")).strip()
        if not webhook_label:
            raise ValueError(
                "generic_webhook connector requires config['webhook_label'] "
                "(tenant-supplied id, e.g. 'crm-events' or 'stripe-prod' — "
                "used as event_id prefix + Prometheus label)"
            )
        mapping_dict = self.config.get("mapping")
        if not isinstance(mapping_dict, dict):
            raise ValueError(
                "generic_webhook connector requires config['mapping'] "
                "(dict matching WebhookMapping shape)"
            )
        try:
            self.mapping = WebhookMapping(
                actor_path=mapping_dict["actor_path"],
                event_type_path=mapping_dict["event_type_path"],
                occurred_at_path=mapping_dict["occurred_at_path"],
                case_id_path=mapping_dict.get("case_id_path"),
                event_id_path=mapping_dict.get("event_id_path"),
                payload_keys=tuple(mapping_dict.get("payload_keys") or ()),
                pii_redact_paths=tuple(mapping_dict.get("pii_redact_paths") or ()),
            )
        except KeyError as e:
            raise ValueError(
                f"generic_webhook mapping missing required key: {e}"
            ) from e

        self.webhook_label = webhook_label

    def map_one(self, raw: dict) -> NormalizedEvent:
        """Push-mode entrypoint — the endpoint receives a raw POST body
        and calls this to turn it into a NormalizedEvent ready for
        publish."""
        return map_payload(
            raw, self.mapping,
            tenant_id=self.tenant_id, source=self.webhook_label,
        )

    async def extract_events(
        self, *, since: Optional[datetime] = None, until: Optional[datetime] = None,
    ) -> AsyncIterator[NormalizedEvent]:
        """Push-mode is the supported mode today; the bg-pull queue
        lands when we ship the cursor scheduler. This generator yields
        nothing so the Connector ABC is satisfied."""
        return
        yield  # pragma: no cover
