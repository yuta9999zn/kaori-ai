"""ADR-0034 — the n8n-style item envelope for workflow nodes.

Uniform node I/O: an *array of items*, each ``{json, binary?, pairedItem?}``.
Carries record-level lineage (``pairedItem`` = which input item produced this
output item) so fan-out / aggregate steps stay traceable (K-6), complementing
``shared/lineage``.

Adopted **additively** (ADR-0034): legacy executors that return a plain
``output_data: dict`` are wrapped as a one-item envelope, so nothing breaks —
``wrap_dict`` / ``as_items`` do the coercion, ``to_output_data`` projects back to
the single-dict shape `prior_outputs` still exposes. New nodes opt into multi-
item by returning ``Items`` and using ``map_items`` / ``fan_out`` / ``aggregate``.

This module is pure (no DB, no engine) — the contract + helpers the runner
integration (PR2) and item-aware executors build on.
"""
from __future__ import annotations

from typing import Any, Callable, Optional

# An Item is a dict with keys json (dict), binary (dict|None), pairedItem
# ({"item": int, "input": int}|None). Items is a list of them.
Item = dict
Items = list


def _paired(in_index: int, input_port: int = 0) -> dict:
    return {"item": in_index, "input": input_port}


def _norm_item(x: Any, idx: int) -> Item:
    """Normalise one element into the canonical item shape. A dict carrying a
    ``json`` key is already an item; any other dict is treated as the json body."""
    if isinstance(x, dict) and "json" in x:
        j = x.get("json")
        # Defensive: n8n json is always an object, but tolerate a non-dict
        # ``json`` (e.g. a stray string) instead of throwing on dict(j).
        json_body = dict(j) if isinstance(j, dict) else ({} if j is None else {"value": j})
        return {"json": json_body,
                "binary": x.get("binary"),
                "pairedItem": x.get("pairedItem")}
    return {"json": dict(x) if isinstance(x, dict) else {"value": x},
            "binary": None, "pairedItem": None}


def wrap_dict(output_data: Optional[dict]) -> Items:
    """Legacy single-dict output → degenerate one-item envelope (the back-compat
    bridge: an executor returning a plain dict still flows as Items)."""
    return [{"json": dict(output_data or {}), "binary": None, "pairedItem": None}]


def is_items(value: Any) -> bool:
    """True when ``value`` is already an Items list (list of item-shaped dicts)."""
    return (isinstance(value, list)
            and all(isinstance(el, dict) and "json" in el for el in value))


def as_items(value: Any) -> Items:
    """Coerce an executor's return into Items. ``None`` → []; a plain dict →
    one item (the common/legacy case); a list → one item per element."""
    if value is None:
        return []
    if isinstance(value, dict):
        return wrap_dict(value)
    if isinstance(value, list):
        return [_norm_item(el, i) for i, el in enumerate(value)]
    return [{"json": {"value": value}, "binary": None, "pairedItem": None}]


def to_output_data(items: Items) -> dict:
    """Back-compat projection for ``prior_outputs[node_id]`` (single dict): the
    first item's ``json``. Full multi-item data lives in the new ``prior_items``
    view, so item-aware downstream nodes see everything."""
    return dict(items[0]["json"]) if items else {}


def map_items(items: Items, fn: Callable[[dict], dict]) -> Items:
    """Per-item transform, preserving lineage (out item i ← in item i). A
    per-item failure is captured on that item (``error`` key, json preserved) and
    does NOT abort the batch — Engineering Tenet 13 (per-item failure ≠ abort)."""
    out: Items = []
    for i, it in enumerate(items):
        entry: Item = {"binary": it.get("binary"), "pairedItem": _paired(i)}
        try:
            entry["json"] = dict(fn(it["json"]) or {})
        except Exception as exc:  # noqa: BLE001 — degrade this item, keep the rest
            entry["json"] = dict(it["json"])
            entry["error"] = str(exc)[:300]
        out.append(entry)
    return out


def fan_out(items: Items, expand_fn: Callable[[dict], list[dict]]) -> Items:
    """1→N: each source item yields ≥0 output items; each output records the
    source item index in ``pairedItem`` so the expansion stays traceable."""
    out: Items = []
    for i, it in enumerate(items):
        try:
            produced = expand_fn(it["json"]) or []
        except Exception as exc:  # noqa: BLE001 — degrade this source item
            out.append({"json": dict(it["json"]), "binary": it.get("binary"),
                        "pairedItem": _paired(i), "error": str(exc)[:300]})
            continue
        for nj in produced:
            out.append({"json": dict(nj), "binary": None, "pairedItem": _paired(i)})
    return out


def aggregate(items: Items, agg_fn: Callable[[list[dict]], dict]) -> Items:
    """N→1: collapse all items' json into a single output item. ``pairedItem`` is
    omitted (the output derives from many inputs, not one)."""
    payload = agg_fn([it["json"] for it in items])
    return [{"json": dict(payload or {}), "binary": None, "pairedItem": None}]
