"""Deterministic workflow-advisor detectors (ADR-0040).

PURE functions over a `profile` dict (built by profile.py). No DB, no LLM —
the advisor never hallucinates a finding; rules find, Qwen only narrates.
Each detector returns a list of finding dicts (schema.finding).

profile shape (see profile.build_profile):
    {
      "workflow_id": str, "name": str, "state": str,
      "nodes": [{node_id, node_type, catalog_key, title, has_action,
                 is_terminal, decision_config, outgoing_count, expected_edges}],
      "edges": [{source, target, is_default, label}],
      "doc_requirements": [{node_id, name_vi, is_required, has_current}],
      "runtime": None | {
          "run_count": int,
          "per_node": {node_id: {visits, failures, avg_ms}},
      },
    }
"""
from __future__ import annotations

import os

from .schema import finding

# Env-tunable thresholds — no hardcode (tenet: thresholds env-configurable).
_MIN_RUNS_FOR_DEAD = int(os.getenv("KAORI_ADVISOR_MIN_RUNS_FOR_DEAD", "3"))
_BOTTLENECK_MS = int(os.getenv("KAORI_ADVISOR_BOTTLENECK_MS", "30000"))
_FAILURE_RATE = float(os.getenv("KAORI_ADVISOR_FAILURE_RATE", "0.3"))


def _title(node: dict) -> str:
    return node.get("title") or node.get("node_id", "")[:8]


# ─── Static detectors (work even with zero runs) ─────────────────────────

def detect_incomplete(profile: dict) -> list[dict]:
    """A step on the canvas with no action/executor bound — can't do anything."""
    out = []
    for n in profile["nodes"]:
        if n.get("is_terminal"):
            continue
        if not n.get("has_action"):
            out.append(finding(
                category="incomplete", severity="high", step_id=n["node_id"],
                title=f"Bước chưa gán hành động: {_title(n)}",
                detail="Bước này nằm trên quy trình nhưng chưa gán hành động Kaori "
                       "(executor) — khi chạy sẽ không làm gì.",
                suggestion="Gán một hành động cho bước, hoặc xoá nếu thừa. "
                           "Kiểm tra cả nút 'Thêm bước' có bị gắn nhầm nhánh.",
            ))
    return out


def detect_branch_errors(profile: dict) -> list[dict]:
    """Decision / switch / parallel node missing outgoing branches (dangling)."""
    out = []
    for n in profile["nodes"]:
        expected = n.get("expected_edges")
        if expected is None:
            continue  # not a branching node
        actual = n.get("outgoing_count", 0)
        if actual < expected:
            out.append(finding(
                category="branch_error", severity="high", step_id=n["node_id"],
                title=f"Nhánh rẽ thiếu lối ra: {_title(n)}",
                detail=f"Bước rẽ nhánh cần ≥{expected} nhánh ra nhưng chỉ có "
                       f"{actual} — một số hồ sơ sẽ không có đường đi.",
                suggestion="Bổ sung nhánh còn thiếu (vd nhánh Sai / default) "
                           "và kiểm tra điều kiện rẽ.",
            ))
    return out


def detect_compliance(profile: dict) -> list[dict]:
    """Approval gate with no approver bound (chain/role) — pauses with nobody."""
    out = []
    for n in profile["nodes"]:
        if not n.get("is_approval_gate"):
            continue
        if not n.get("has_approver"):
            out.append(finding(
                category="compliance", severity="high", step_id=n["node_id"],
                title=f"Cổng duyệt rỗng quyền: {_title(n)}",
                detail="Cổng phê duyệt chưa gắn chuỗi duyệt hoặc vai trò người "
                       "duyệt — khi chạy sẽ dừng vô hạn vì không ai duyệt.",
                suggestion="Gắn chuỗi duyệt (Duyệt & Phân quyền) hoặc chọn vai "
                           "trò người duyệt cho cổng này.",
            ))
    return out


def detect_missing_doc(profile: dict) -> list[dict]:
    """A required document requirement that has no submitted current file."""
    out = []
    for req in profile.get("doc_requirements", []):
        if req.get("is_required") and not req.get("has_current"):
            out.append(finding(
                category="missing_doc", severity="medium", step_id=req.get("node_id"),
                title=f"Thiếu tài liệu bắt buộc: {req.get('name_vi', '')}",
                detail="Bước này khai báo tài liệu bắt buộc nhưng chưa có file "
                       "nào được nộp (cây tài liệu).",
                suggestion="Nộp tài liệu cho bước (nút 'Nộp file' trong cây tài liệu).",
                confidence=0.85,
            ))
    return out


def detect_redundant(profile: dict) -> list[dict]:
    """Two directly-connected nodes with the same action — likely duplicated."""
    out = []
    by_id = {n["node_id"]: n for n in profile["nodes"]}
    seen = set()
    for e in profile["edges"]:
        src, tgt = by_id.get(e["source"]), by_id.get(e["target"])
        if not src or not tgt:
            continue
        key = src.get("catalog_key")
        if key and key == tgt.get("catalog_key") and (e["source"], e["target"]) not in seen:
            seen.add((e["source"], e["target"]))
            out.append(finding(
                category="redundant", severity="low", step_id=tgt["node_id"],
                title=f"Bước trùng hành động: {_title(src)} → {_title(tgt)}",
                detail="Hai bước liền nhau dùng cùng một hành động — có thể gộp.",
                suggestion="Xem xét gộp hai bước hoặc đổi hành động bước sau.",
                confidence=0.6,
            ))
    return out


# ─── Runtime detectors (need workflow_events history) ────────────────────

def detect_dead_branch(profile: dict) -> list[dict]:
    rt = profile.get("runtime")
    if not rt or rt["run_count"] < _MIN_RUNS_FOR_DEAD:
        return []
    out = []
    per = rt["per_node"]
    for n in profile["nodes"]:
        if n.get("is_terminal"):
            continue
        stats = per.get(n["node_id"])
        if stats is None or stats.get("visits", 0) == 0:
            out.append(finding(
                category="dead_branch", severity="medium", step_id=n["node_id"],
                title=f"Nhánh không bao giờ chạy tới: {_title(n)}",
                detail=f"Qua {rt['run_count']} lần chạy, bước này chưa từng được "
                       "thực thi — có thể điều kiện rẽ sai hoặc bước thừa.",
                suggestion="Kiểm tra điều kiện nhánh dẫn tới bước, hoặc xoá nếu thừa.",
                confidence=0.75,
            ))
    return out


def detect_no_action_on_path(profile: dict) -> list[dict]:
    rt = profile.get("runtime")
    if not rt:
        return []
    out = []
    per = rt["per_node"]
    for n in profile["nodes"]:
        if n.get("is_terminal") or n.get("has_action"):
            continue
        stats = per.get(n["node_id"])
        if stats and stats.get("visits", 0) > 0:
            out.append(finding(
                category="no_action_on_path", severity="high", step_id=n["node_id"],
                title=f"Bước chạy nhưng rỗng hành động: {_title(n)}",
                detail="Bước này NẰM TRÊN đường thực thi thật nhưng chưa gán hành "
                       "động — hồ sơ đi qua mà không có gì xảy ra.",
                suggestion="Gán hành động cho bước, hoặc nối lại nhánh cho đúng.",
            ))
    return out


def detect_bottleneck(profile: dict) -> list[dict]:
    rt = profile.get("runtime")
    if not rt:
        return []
    out = []
    by_id = {n["node_id"]: n for n in profile["nodes"]}
    for node_id, s in rt["per_node"].items():
        visits = s.get("visits", 0)
        if visits == 0:
            continue
        avg_ms = s.get("avg_ms") or 0
        fail_rate = (s.get("failures", 0) / visits) if visits else 0
        title = _title(by_id.get(node_id, {"node_id": node_id}))
        if fail_rate >= _FAILURE_RATE:
            out.append(finding(
                category="bottleneck", severity="medium", step_id=node_id,
                title=f"Bước hay lỗi: {title}",
                detail=f"Tỉ lệ lỗi {fail_rate:.0%} qua {visits} lần chạy.",
                suggestion="Xem log lỗi của bước; cân nhắc retry/validate đầu vào.",
                confidence=0.8,
            ))
        elif avg_ms >= _BOTTLENECK_MS:
            out.append(finding(
                category="bottleneck", severity="low", step_id=node_id,
                title=f"Bước chậm: {title}",
                detail=f"Thời gian trung bình {avg_ms/1000:.1f}s qua {visits} lần chạy.",
                suggestion="Kiểm tra bước có gọi LLM/IO nặng; cân nhắc tối ưu/chạy nền.",
                confidence=0.7,
            ))
    return out


_STATIC = (detect_incomplete, detect_branch_errors, detect_compliance,
           detect_missing_doc, detect_redundant)
_RUNTIME = (detect_dead_branch, detect_no_action_on_path, detect_bottleneck)


def run_all(profile: dict) -> list[dict]:
    """Run every applicable detector; runtime ones no-op without history."""
    out: list[dict] = []
    for d in _STATIC:
        out.extend(d(profile))
    for d in _RUNTIME:
        out.extend(d(profile))
    return out
