"""
PM-ALG-014 (P1-S7) — case_id inference for event logs.

Process Mining needs cases (think: one customer order, one support
ticket) to reconstruct sequences. Connectors that emit events with a
natural case_id (Postgres CDC capturing orders.id) get cases for free;
connectors that don't (Zalo messages keyed by thread_id) need
inference here.

Phase 1 v4 ships the simple grouping: events with the same explicit
``case_id`` field group together. Events missing a case_id get bucketed
by ``actor`` — a fallback that gives 80% of the value with 20% of the
code.

Phase 1.5+ adds:
  * Time-window splitting (gap > 24h → new case)
  * Cross-source correlation (Zalo thread + Postgres order)
  * ML-based clustering when natural keys aren't present
"""
from __future__ import annotations

from collections import defaultdict
from typing import Iterable

from .types import Event


def infer_cases(events: Iterable[Event]) -> dict[str, list[Event]]:
    """Group events into cases. Return {case_id: [events sorted by time]}.

    Strategy:
      1. If event.case_id is set, use it.
      2. Otherwise fall back to actor (so all of one user's events form
         a synthetic case keyed by actor).
      3. Events missing both case_id and actor go into a synthetic
         catch-all bucket 'unknown:<source>' so they're not silently
         dropped — Process Mining ops can spot the data quality issue.

    Each case's event list is sorted by occurred_at so downstream
    sequence reconstruction (Heuristic Miner) sees the right order.
    """
    cases: dict[str, list[Event]] = defaultdict(list)
    for ev in events:
        if ev.case_id:
            key = ev.case_id
        elif ev.actor:
            key = f"actor:{ev.actor}"
        else:
            key = f"unknown:{ev.source}"
        cases[key].append(ev)

    # Sort each case chronologically — Heuristic Miner reads adjacent
    # event_type pairs as direct-follow relations.
    for case_events in cases.values():
        case_events.sort(key=lambda e: e.occurred_at)

    return dict(cases)
