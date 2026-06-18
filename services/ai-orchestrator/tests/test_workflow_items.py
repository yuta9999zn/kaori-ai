"""Tests for ADR-0034 workflow item envelope (workflow_runtime/items.py):
backward-compatible coercion + lineage-preserving map/fan-out/aggregate.
"""
from ai_orchestrator.workflow_runtime.items import (
    aggregate,
    as_items,
    fan_out,
    is_items,
    map_items,
    to_output_data,
    wrap_dict,
)


# ── coercion / back-compat bridge ────────────────────────────────────────────

def test_wrap_dict_makes_one_item():
    items = wrap_dict({"a": 1})
    assert items == [{"json": {"a": 1}, "binary": None, "pairedItem": None}]


def test_wrap_dict_none_is_empty_json_item():
    assert wrap_dict(None) == [{"json": {}, "binary": None, "pairedItem": None}]


def test_as_items_dict_is_single_item():
    assert as_items({"x": 9}) == [{"json": {"x": 9}, "binary": None, "pairedItem": None}]


def test_as_items_none_is_empty():
    assert as_items(None) == []


def test_as_items_list_of_plain_dicts():
    out = as_items([{"a": 1}, {"a": 2}])
    assert len(out) == 2 and out[0]["json"] == {"a": 1} and out[1]["json"] == {"a": 2}


def test_as_items_already_items_normalises():
    src = [{"json": {"a": 1}, "pairedItem": {"item": 0, "input": 0}}]
    out = as_items(src)
    assert out[0]["json"] == {"a": 1}
    assert out[0]["pairedItem"] == {"item": 0, "input": 0}
    assert out[0]["binary"] is None        # filled in


def test_is_items_discriminates():
    assert is_items([{"json": {}}]) is True
    assert is_items([{"a": 1}]) is False
    assert is_items({"a": 1}) is False


def test_to_output_data_back_compat_first_json():
    assert to_output_data(wrap_dict({"a": 1})) == {"a": 1}
    assert to_output_data([]) == {}


# ── map_items: per-item transform + lineage + Tenet 13 ───────────────────────

def test_map_items_transforms_and_keeps_lineage():
    items = as_items([{"n": 1}, {"n": 2}])
    out = map_items(items, lambda j: {"n2": j["n"] * 2})
    assert [o["json"] for o in out] == [{"n2": 2}, {"n2": 4}]
    assert out[0]["pairedItem"] == {"item": 0, "input": 0}
    assert out[1]["pairedItem"] == {"item": 1, "input": 0}


def test_map_items_per_item_failure_does_not_abort():
    items = as_items([{"n": 1}, {"bad": True}, {"n": 3}])

    def fn(j):
        return {"n2": j["n"] * 2}        # KeyError on the middle item

    out = map_items(items, fn)
    assert len(out) == 3                  # nothing aborted
    assert out[0]["json"] == {"n2": 2}
    assert "error" in out[1] and out[1]["json"] == {"bad": True}   # degraded, preserved
    assert out[2]["json"] == {"n2": 6}


# ── fan_out (1→N) + aggregate (N→1) ──────────────────────────────────────────

def test_fan_out_expands_and_traces_source():
    items = as_items([{"order": "A", "lines": 2}, {"order": "B", "lines": 1}])
    out = fan_out(items, lambda j: [{"order": j["order"], "line": i} for i in range(j["lines"])])
    assert len(out) == 3
    assert out[0]["pairedItem"]["item"] == 0 and out[1]["pairedItem"]["item"] == 0
    assert out[2]["pairedItem"]["item"] == 1          # traces back to source B


def test_fan_out_per_source_failure_degrades():
    items = as_items([{"ok": 1}, {"ok": 2}])

    def expand(j):
        if j["ok"] == 2:
            raise ValueError("boom")
        return [{"v": j["ok"]}]

    out = fan_out(items, expand)
    assert out[0]["json"] == {"v": 1}
    assert "error" in out[1]                          # second source degraded, not aborted


def test_aggregate_collapses_to_one_item():
    items = as_items([{"amt": 10}, {"amt": 5}, {"amt": 7}])
    out = aggregate(items, lambda jsons: {"total": sum(j["amt"] for j in jsons)})
    assert out == [{"json": {"total": 22}, "binary": None, "pairedItem": None}]


# ── binary field handling + defensive coercion (review follow-ups) ───────────

def test_map_items_preserves_binary():
    items = as_items([{"json": {"n": 1}, "binary": {"file": "b64"}}])
    out = map_items(items, lambda j: {"n2": j["n"]})
    assert out[0]["binary"] == {"file": "b64"}        # binary carried through transform


def test_fan_out_new_items_have_no_binary():
    items = as_items([{"json": {"k": 1}, "binary": {"f": "x"}}])
    out = fan_out(items, lambda j: [{"v": 1}])
    assert out[0]["binary"] is None                   # fresh records, source binary not duplicated


def test_norm_item_tolerates_non_dict_json():
    out = as_items([{"json": "oops"}])                # stray string json must not throw
    assert out[0]["json"] == {"value": "oops"}
    assert as_items([{"json": None}])[0]["json"] == {}


# ── ADR-0034 PR2: NodeContext.prior_items contract + runner rebuild semantics ─

def test_node_context_prior_items_default_empty():
    from uuid import uuid4
    from ai_orchestrator.workflow_runtime.node_executor import NodeContext
    ctx = NodeContext(enterprise_id=uuid4(), workspace_id=None, workflow_id=uuid4(),
                      run_id=uuid4(), node_id=uuid4(), user_id=None, input_data={})
    assert ctx.prior_items == {}              # additive default — legacy executors unaffected


def test_runner_rebuild_from_persisted_dicts_is_lossless():
    # Mirrors the runner init: persisted single-dict outputs → one-item envelopes,
    # and project back losslessly for today's single-dict executors.
    prior_completed = {"n1": {"rows": 3}, "n2": {"ok": True}}
    rebuilt = {nid: as_items(od) for nid, od in prior_completed.items()}
    assert rebuilt["n1"] == [{"json": {"rows": 3}, "binary": None, "pairedItem": None}]
    assert to_output_data(rebuilt["n1"]) == {"rows": 3}
    assert to_output_data(rebuilt["n2"]) == {"ok": True}
