"""ADR-0037 Tier-3 Phase 1 — Document Tree.

Covers the pure, risk-carrying logic without a DB:
  • the 7-state document status machine (allowed transitions, note rules)
  • build_document_tree (3-tier input/output/reference grouping, current version,
    loose ad-hoc docs)
  • the router mounts cleanly with its endpoints.
"""
from __future__ import annotations

from uuid import uuid4

from ai_orchestrator.workflow_runtime import doc_status as ds
from ai_orchestrator.routers.workflow_documents import build_document_tree


# ─────────────────── status machine ───────────────────
class TestDocStatusMachine:
    def test_upload_path(self):
        assert ds.can_transition(ds.CHO_NOP, ds.DA_NOP)
        assert not ds.can_transition(ds.CHO_NOP, ds.DA_DUYET)   # can't approve unsubmitted

    def test_review_decisions_from_submitted(self):
        for to in (ds.DANG_XEM_XET, ds.DA_DUYET, ds.TU_CHOI, ds.YEU_CAU_BO_SUNG):
            assert ds.can_transition(ds.DA_NOP, to)

    def test_reject_and_request_more_require_note(self):
        assert ds.requires_note(ds.TU_CHOI)
        assert ds.requires_note(ds.YEU_CAU_BO_SUNG)
        assert not ds.requires_note(ds.DA_DUYET)

    def test_review_decision_flag(self):
        assert ds.is_review_decision(ds.DA_DUYET)
        assert ds.is_review_decision(ds.TU_CHOI)
        assert not ds.is_review_decision(ds.DANG_XEM_XET)

    def test_reupload_after_rejection(self):
        # rejected / needs-more → re-upload a new version (back to da_nop)
        assert ds.can_transition(ds.TU_CHOI, ds.DA_NOP)
        assert ds.can_transition(ds.YEU_CAU_BO_SUNG, ds.DA_NOP)

    def test_approved_is_terminal(self):
        assert ds.is_terminal(ds.DA_DUYET)
        assert ds.allowed_targets(ds.DA_DUYET) == []

    def test_expired_can_be_replaced(self):
        assert ds.is_terminal(ds.HET_HAN)
        assert ds.can_transition(ds.HET_HAN, ds.DA_NOP)

    def test_every_state_has_a_label(self):
        assert all(s in ds.STATUS_LABEL for s in ds.ALL_STATES)


# ─────────────────── tree builder ───────────────────
def _node(nid, title="Bước", lane=None):
    return {"node_id": nid, "title_vi": title, "title": title, "lane_name": lane}


def _req(rid, nid, cls, name, order=0):
    return {"requirement_id": rid, "node_id": nid, "doc_class": cls,
            "name_vi": name, "description": None, "is_required": True, "sort_order": order}


def _doc(nid, rid, cls, status, version=1, is_current=True, filename="f.pdf"):
    return {"node_id": nid, "requirement_id": rid, "doc_class": cls,
            "status": status, "version": version, "is_current": is_current,
            "filename": filename, "attachment_id": str(uuid4())}


class TestBuildDocumentTree:
    def test_groups_by_three_classes(self):
        nid = str(uuid4())
        r_in, r_out, r_ref = str(uuid4()), str(uuid4()), str(uuid4())
        reqs = [
            _req(r_in, nid, "input", "Đơn yêu cầu"),
            _req(r_out, nid, "output", "Báo cáo thẩm định"),
            _req(r_ref, nid, "reference", "Quy trình nội bộ"),
        ]
        tree = build_document_tree([_node(nid)], reqs, [])
        step = tree[0]
        assert [r["name_vi"] for r in step["input"]] == ["Đơn yêu cầu"]
        assert [r["name_vi"] for r in step["output"]] == ["Báo cáo thẩm định"]
        assert [r["name_vi"] for r in step["reference"]] == ["Quy trình nội bộ"]
        assert step["doc_count"] == 3

    def test_unfulfilled_requirement_is_cho_nop(self):
        nid, rid = str(uuid4()), str(uuid4())
        tree = build_document_tree([_node(nid)], [_req(rid, nid, "input", "CMND")], [])
        assert tree[0]["input"][0]["status"] == ds.CHO_NOP
        assert tree[0]["input"][0]["document"] is None
        assert tree[0]["input"][0]["version_count"] == 0

    def test_picks_current_version_and_counts_chain(self):
        nid, rid = str(uuid4()), str(uuid4())
        docs = [
            _doc(nid, rid, "input", ds.TU_CHOI, version=1, is_current=False),
            _doc(nid, rid, "input", ds.DA_DUYET, version=2, is_current=True),
        ]
        tree = build_document_tree([_node(nid)], [_req(rid, nid, "input", "CMND")], docs)
        slot = tree[0]["input"][0]
        assert slot["status"] == ds.DA_DUYET           # the CURRENT version
        assert slot["document"]["version"] == 2
        assert slot["version_count"] == 2              # both versions counted

    def test_loose_adhoc_doc_surfaced(self):
        nid = str(uuid4())
        loose = _doc(nid, None, "output", ds.DA_NOP, filename="extra.pdf")
        tree = build_document_tree([_node(nid)], [], [loose])
        assert tree[0]["output"][0]["requirement_id"] is None
        assert tree[0]["output"][0]["name_vi"] == "extra.pdf"

    def test_sort_order_respected(self):
        nid = str(uuid4())
        reqs = [
            _req(str(uuid4()), nid, "input", "Thứ hai", order=2),
            _req(str(uuid4()), nid, "input", "Thứ nhất", order=1),
        ]
        tree = build_document_tree([_node(nid)], reqs, [])
        assert [r["name_vi"] for r in tree[0]["input"]] == ["Thứ nhất", "Thứ hai"]


# ─────────────────── router mount ───────────────────
def test_router_exposes_endpoints():
    from ai_orchestrator.routers.workflow_documents import router
    paths = {r.path for r in router.routes}
    assert "/workflows/{workflow_id}/document-tree" in paths
    assert "/workflow-documents/{attachment_id}/transition" in paths
    assert "/workflow-documents/{attachment_id}/download" in paths   # ADR-0037 Phase 0
    assert "/workflows/{workflow_id}/nodes/{node_id}/doc-requirements" in paths
