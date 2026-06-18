"""Build the workflow `profile` the detectors consume (ADR-0040).

Does the DB I/O (RLS-scoped connection passed in by the router); detectors
stay pure. Static structure from workflow_nodes/edges + doc requirements;
runtime aggregates from workflow_events (mig 094) over this workflow's runs.
"""
from __future__ import annotations

import json
from typing import Optional
from uuid import UUID

# A 'step' with no executor key is incomplete; structural nodes act by nature.
_STRUCTURAL_ACTION_TYPES = {
    "decision_if_else", "decision_switch", "parallel_split", "parallel_join",
    "loop_foreach", "loop_end", "approval_gate",
}
_TERMINAL_TYPES = {"start", "end", "start_event", "end_event", "trigger"}
_BRANCHING = {"decision_if_else", "decision_switch", "parallel_split"}


def _loads(raw) -> dict:
    if isinstance(raw, str):
        try:
            return json.loads(raw) or {}
        except (ValueError, TypeError):
            return {}
    return raw or {}


def _expected_edges(node_type: str, dc: dict) -> Optional[int]:
    if node_type == "decision_switch":
        return max(len(dc.get("cases") or []) + 1, 2)
    if node_type in ("decision_if_else", "parallel_split"):
        return 2
    return None


async def build_profile(conn, workflow_id: UUID, *, with_runtime: bool = True) -> dict:
    wf = await conn.fetchrow(
        "SELECT workflow_id, name, state FROM workflows WHERE workflow_id = $1",
        workflow_id,
    )
    if wf is None:
        return {}

    node_rows = await conn.fetch(
        """SELECT node_id, node_type, node_type_catalog_key, title, title_vi,
                  decision_config, category
           FROM workflow_nodes WHERE workflow_id = $1""",
        workflow_id,
    )
    edge_rows = await conn.fetch(
        """SELECT source_node_id, target_node_id, is_default, label
           FROM workflow_edges WHERE workflow_id = $1""",
        workflow_id,
    )

    # outgoing distinct-target counts per source
    out_counts: dict[str, int] = {}
    for e in edge_rows:
        s = str(e["source_node_id"])
        out_counts.setdefault(s, set()).add(str(e["target_node_id"]))  # type: ignore
    out_counts = {k: len(v) for k, v in out_counts.items()}  # type: ignore

    nodes = []
    for r in node_rows:
        nid = str(r["node_id"])
        nt = r["node_type"]
        catalog = r["node_type_catalog_key"]
        dc = _loads(r["decision_config"])
        is_gate = catalog == "approval_gate" or nt == "approval_gate"
        has_approver = bool(dc.get("approval_chain_id")) or bool(
            (dc.get("approver_role") or "").strip()
            if isinstance(dc.get("approver_role"), str) else dc.get("approver_role"))
        has_action = bool(catalog) or nt in _STRUCTURAL_ACTION_TYPES
        nodes.append({
            "node_id": nid,
            "node_type": nt,
            "catalog_key": catalog,
            "title": r["title_vi"] or r["title"],
            "decision_config": dc,
            "is_terminal": nt in _TERMINAL_TYPES or (r["category"] == "event"),
            "has_action": has_action,
            "is_approval_gate": is_gate,
            "has_approver": bool(has_approver),
            "outgoing_count": out_counts.get(nid, 0),
            "expected_edges": _expected_edges(nt, dc),
        })

    edges = [{
        "source": str(e["source_node_id"]),
        "target": str(e["target_node_id"]),
        "is_default": e["is_default"],
        "label": e["label"],
    } for e in edge_rows]

    # Doc requirements + whether a current file has been submitted (mig 119/120).
    doc_rows = await conn.fetch(
        """SELECT r.requirement_id, r.node_id, r.name_vi, r.is_required,
                  EXISTS (SELECT 1 FROM workflow_step_documents d
                          WHERE d.requirement_id = r.requirement_id
                            AND d.is_current = TRUE) AS has_current
           FROM workflow_step_document_requirements r
           WHERE r.workflow_id = $1""",
        workflow_id,
    )
    doc_requirements = [{
        "node_id": str(d["node_id"]),
        "name_vi": d["name_vi"],
        "is_required": d["is_required"],
        "has_current": d["has_current"],
    } for d in doc_rows]

    profile = {
        "workflow_id": str(wf["workflow_id"]),
        "name": wf["name"],
        "state": wf["state"],
        "nodes": nodes,
        "edges": edges,
        "doc_requirements": doc_requirements,
        "runtime": None,
    }

    if with_runtime:
        profile["runtime"] = await _build_runtime(conn, workflow_id)
    return profile


async def _build_runtime(conn, workflow_id: UUID) -> Optional[dict]:
    """Aggregate workflow_events across this workflow's runs into per-node stats."""
    run_rows = await conn.fetch(
        "SELECT run_id FROM workflow_runs WHERE workflow_id = $1", workflow_id,
    )
    run_ids = [r["run_id"] for r in run_rows]
    if not run_ids:
        return None

    ev_rows = await conn.fetch(
        """SELECT run_id, node_id, event_type, occurred_at
           FROM workflow_events
           WHERE run_id = ANY($1::uuid[])
             AND node_id IS NOT NULL
             AND event_type IN ('node_started', 'node_completed', 'node_failed')
           ORDER BY run_id, sequence_no""",
        run_ids,
    )

    per: dict[str, dict] = {}
    # pair started→completed per (run_id, node_id) in sequence order for duration
    pending: dict[tuple, object] = {}
    for e in ev_rows:
        nid = str(e["node_id"])
        st = per.setdefault(nid, {"visits": 0, "failures": 0, "_dur_ms": [], })
        et = e["event_type"]
        if et == "node_started":
            st["visits"] += 1
            pending[(str(e["run_id"]), nid)] = e["occurred_at"]
        elif et == "node_failed":
            st["failures"] += 1
        elif et == "node_completed":
            started = pending.pop((str(e["run_id"]), nid), None)
            if started is not None and e["occurred_at"] is not None:
                st["_dur_ms"].append((e["occurred_at"] - started).total_seconds() * 1000.0)

    for nid, st in per.items():
        durs = st.pop("_dur_ms")
        st["avg_ms"] = (sum(durs) / len(durs)) if durs else 0.0

    return {"run_count": len(run_ids), "per_node": per}
