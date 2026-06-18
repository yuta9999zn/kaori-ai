"""
Demo company fixture — "Cà phê Phúc Long" for Build Week 8/7.

Generates a deterministic event log emulating a coffee chain SME:
- 200 customers × 60 days × 3 process variants
- 8 event types: view_menu, add_cart, choose_payment, pay_card, pay_cash,
  complete, abandon, refund
- ~2500+ events total → enough scale for CDFL advantage (>900 states niche
  per REPORT_V8.md; here states = event_type so the count argument is
  about case volume rather than state space, but the demo's KPI is
  visible direct-follow density).

Why 3 variants:
  1. Happy path (75% of cases):   view_menu → add_cart → choose_payment →
                                   pay_card → complete
  2. Cash variant (15%):           view_menu → add_cart → choose_payment →
                                   pay_cash → complete
  3. Abandon (10%):                view_menu → add_cart → abandon

Refund is rare (1% of completed cases retroactively trigger refund) so
it appears as a low-frequency edge in mined output — useful demo for
the "rare event highlighting" narrative.

All randomness is seeded so the fixture is byte-for-byte reproducible.
Caller uses `build_phuc_long_event_log()` to get an `EventLog`; or
`build_phuc_long_payload()` to get the JSON shape POSTed to
`/process-mining/mine`.
"""
from __future__ import annotations

import random
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID

from ai_orchestrator.org_intel.process_mining import Event, EventLog


_TENANT_ID = UUID("11111111-1111-1111-1111-111111111111")
_START = datetime(2026, 1, 1, 8, 0, 0, tzinfo=timezone.utc)
_SEED = 42

# Variant weights: must sum to 1.0
_VARIANTS = {
    "happy_card": 0.75,
    "happy_cash": 0.15,
    "abandon": 0.10,
}

_VARIANT_PATHS = {
    "happy_card": [
        "view_menu",
        "add_cart",
        "choose_payment",
        "pay_card",
        "complete",
    ],
    "happy_cash": [
        "view_menu",
        "add_cart",
        "choose_payment",
        "pay_cash",
        "complete",
    ],
    "abandon": [
        "view_menu",
        "add_cart",
        "abandon",
    ],
}

# Per-step elapsed seconds — mean + jitter (uniform ±20%).
_STEP_DURATION_SECONDS = {
    "view_menu→add_cart": 45,
    "add_cart→choose_payment": 30,
    "add_cart→abandon": 120,
    "choose_payment→pay_card": 25,
    "choose_payment→pay_cash": 35,
    "pay_card→complete": 15,
    "pay_cash→complete": 20,
}

# Refund probability AFTER complete event (1%).
_REFUND_PROBABILITY = 0.01
_REFUND_DELAY_HOURS = 6


def _pick_variant(rng: random.Random) -> str:
    r = rng.random()
    cumulative = 0.0
    for name, weight in _VARIANTS.items():
        cumulative += weight
        if r <= cumulative:
            return name
    return "happy_card"  # fallback (rounding)


def _jittered_seconds(mean: int, rng: random.Random) -> int:
    """Mean ± 20% uniform jitter."""
    delta = mean * 0.2
    return int(mean + rng.uniform(-delta, delta))


def build_phuc_long_events(
    *,
    num_customers: int = 200,
    days: int = 60,
    seed: int = _SEED,
) -> list[Event]:
    """Generate the full event log. Returns list ready to wrap in EventLog.

    Each customer fires 1 case per day (random offset within working hours
    8:00-22:00). Process variant per case is independent random pick.
    """
    rng = random.Random(seed)
    events: list[Event] = []
    event_seq = 0

    for customer_idx in range(num_customers):
        for day in range(days):
            day_start = _START + timedelta(days=day)
            # Random start hour 8:00-22:00 (14h window)
            hour_offset_seconds = int(rng.uniform(0, 14 * 3600))
            case_start = day_start + timedelta(seconds=hour_offset_seconds)
            case_id = f"cust{customer_idx:03d}-day{day:02d}"

            variant = _pick_variant(rng)
            path = _VARIANT_PATHS[variant]

            current_time = case_start
            for i, event_type in enumerate(path):
                event_seq += 1
                events.append(
                    Event(
                        tenant_id=_TENANT_ID,
                        event_id=f"e{event_seq:06d}",
                        source="phuc_long_pos",
                        event_type=event_type,
                        occurred_at=current_time,
                        actor=f"customer_{customer_idx:03d}",
                        case_id=case_id,
                    )
                )
                # Compute next step's offset
                if i < len(path) - 1:
                    edge_key = f"{event_type}→{path[i + 1]}"
                    mean = _STEP_DURATION_SECONDS.get(edge_key, 60)
                    current_time = current_time + timedelta(
                        seconds=_jittered_seconds(mean, rng)
                    )

            # Refund branch — only after a complete in happy_card / happy_cash.
            if variant in ("happy_card", "happy_cash"):
                if rng.random() < _REFUND_PROBABILITY:
                    event_seq += 1
                    refund_time = current_time + timedelta(hours=_REFUND_DELAY_HOURS)
                    events.append(
                        Event(
                            tenant_id=_TENANT_ID,
                            event_id=f"e{event_seq:06d}",
                            source="phuc_long_pos",
                            event_type="refund",
                            occurred_at=refund_time,
                            actor=f"customer_{customer_idx:03d}",
                            case_id=case_id,
                        )
                    )

    return events


def build_phuc_long_event_log(
    *,
    num_customers: int = 200,
    days: int = 60,
    seed: int = _SEED,
) -> EventLog:
    """EventLog-wrapped version for direct use with HeuristicMiner."""
    events = build_phuc_long_events(num_customers=num_customers, days=days, seed=seed)
    return EventLog(
        tenant_id=_TENANT_ID,
        events=tuple(events),
        window_start=_START,
        window_end=_START + timedelta(days=days),
    )


def build_phuc_long_payload(
    *,
    num_customers: int = 200,
    days: int = 60,
    seed: int = _SEED,
    min_frequency: int = 1,
) -> dict[str, Any]:
    """JSON-shaped payload for POSTing to /process-mining/mine.

    Caller adds `X-Enterprise-Id` header pointing at `tenant_id`.
    """
    events = build_phuc_long_events(num_customers=num_customers, days=days, seed=seed)
    return {
        "events": [
            {
                "event_id": ev.event_id,
                "source": ev.source,
                "event_type": ev.event_type,
                "occurred_at": ev.occurred_at.isoformat(),
                "actor": ev.actor,
                "case_id": ev.case_id,
            }
            for ev in events
        ],
        "min_frequency": min_frequency,
    }


# Demo defaults — full scale, deterministic.
PHUC_LONG_TENANT_ID = str(_TENANT_ID)
