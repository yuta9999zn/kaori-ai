# -*- coding: utf-8 -*-
"""Set runner configs for 'Thu mua nong san tu HTX' v2 nodes — run inside
ai-orchestrator container AFTER bpmn/sync (node_ids change on every sync).

Usage: docker exec kaorisystem-ai-orchestrator-1 python /tmp/set_configs.py
"""
import json
import httpx

BASE = "http://localhost:8093"
ENT = "3d1c1a53-f924-41fa-a4ce-defade00e898"
UID = "4ebbb853-8aaf-4f0c-9e86-e5180337ee63"   # giamdoc@dongxanh.vn
WF = "d2f72d21-21af-4351-8c0a-995afe164c74"
HDR = {"X-Enterprise-ID": ENT, "X-User-ID": UID, "X-User-Role": "MANAGER"}

tree = httpx.get(f"{BASE}/workflows/{WF}/tree", headers=HDR, timeout=30).json()
ids = {n["bpmn_element_id"]: n["node_id"] for n in tree["nodes"] if n.get("bpmn_element_id")}
print("node map:", json.dumps(ids, indent=1))


def ref(elem, path=""):
    return f"$.{ids[elem]}{('.' + path) if path else ''}"


CONFIGS = {
    "Task_ReadForm": {"form_key": "don_chao_ban_htx", "latest_for_form": True},
    "Task_Validate": {
        "data": ref("Task_ReadForm", "payload"), "strict": True,
        "schema": {
            "type": "object",
            "required": ["ma_phieu", "htx_nong_ho", "items", "thanh_tien"],
            "properties": {
                "thanh_tien": {"type": "number", "exclusiveMinimum": 0},
                "items": {"type": "array", "minItems": 1},
                "htx_nong_ho": {"type": "string", "minLength": 3},
            },
        },
    },
    "Task_Extract": {
        "text": ref("Task_ReadForm", "payload"),
        "entity_types": ["mặt hàng", "khối lượng", "đơn giá", "chứng nhận"],
    },
    "Task_Rag": {
        "query": ("Đơn thu mua nông sản giá trị trên 50 triệu đồng cần ai phê duyệt "
                  "theo QĐ-01, và khi nhận hàng phải kiểm QA theo tiêu chuẩn nào?"),
        "top_k": 4,
    },
    "Task_Risk": {
        "subject": ref("Task_ReadForm", "payload"),
        "dimensions": ["chất lượng nguồn hàng", "độ tin cậy HTX",
                       "biến động giá", "rủi ro công nợ"],
        "score_range": [0, 100],
        "composite_method": "mean",
    },
    "GW_Value": {
        "condition": {"left": ref("Task_ReadForm", "payload.thanh_tien"),
                      "op": ">", "right": 50000000},
    },
    "Task_AutoLog": {
        "level": "info", "event": "thu_mua.auto_approve_duoi_nguong",
        "payload": {"ma_phieu": ref("Task_ReadForm", "payload.ma_phieu"),
                    "thanh_tien": ref("Task_ReadForm", "payload.thanh_tien")},
    },
    "Task_Approval": {
        "approver_role": "MANAGER", "sla_minutes": 240,
        "reason_prompt": ("Lô hàng vượt 50 triệu — theo QĐ-01 bắt buộc Giám đốc phê duyệt "
                          "(SLA 240 phút). Xem điểm rủi ro AI và trích dẫn KB ở các bước "
                          "trước khi quyết định."),
    },
    "Task_Contract": {
        "title": "Hợp đồng thu mua nông sản — HTX Đơn Dương (demo P5)",
        "contract_type": "thu_mua", "value_vnd": 82700000,
        "sign_mode": "threshold", "required_signatures": 1,
        "parties": [
            {"party_role": "Bên mua — Đồng Xanh", "internal_user_id": UID, "sign_order": 1},
            {"party_role": "Bên bán — HTX Đơn Dương", "external_name": "HTX Đơn Dương",
             "external_email": "htxdonduong@lamdong.coop.vn", "sign_order": 2},
        ],
    },
    "Task_CreateTask": {
        "task_key": "nhap-kho-{" + ref("Task_ReadForm", "payload.ma_phieu") + "}",
        "title": "Nhập kho + kiểm QA lô HTX Đơn Dương theo SOP-02",
        "description": ("Kiểm VietGAP, tỷ lệ hao hụt, nhiệt độ bảo quản theo SOP-02 "
                        "trước khi nhập kho."),
        "assignee_role": "OPERATOR", "priority": "high",
    },
    "Task_Narrative": {
        "template": ("Viết 3-4 câu tiếng Việt ghi lại LÝ DO quyết định thu mua: đơn "
                     "{ma_phieu} của {htx}, tổng giá trị {thanh_tien} VND, điểm rủi ro "
                     "tổng hợp {risk_composite}/100 (band {risk_band}). Nêu rõ căn cứ "
                     "QĐ-01 (trên 50 triệu do Giám đốc duyệt) và điều kiện kiểm QA theo SOP-02."),
        "variables": {
            "ma_phieu": ref("Task_ReadForm", "payload.ma_phieu"),
            "htx": ref("Task_ReadForm", "payload.htx_nong_ho"),
            "thanh_tien": ref("Task_ReadForm", "payload.thanh_tien"),
            "risk_composite": ref("Task_Risk", "composite"),
            "risk_band": ref("Task_Risk", "band"),
        },
        "max_tokens": 400,
    },
    "Task_Insight": {
        "title": "Quyết định thu mua lô HTX Đơn Dương đã được phê duyệt",
        "body": ref("Task_Narrative", "text"),
        "severity": "info",
        "tags": ["thu_mua", "htx", "p5_demo"],
        "source_data": {"workflow": "Thu mua nông sản từ HTX", "quy_dinh": "QĐ-01"},
    },
    "Task_Email": {
        "to": "htxdonduong@lamdong.coop.vn",
        "subject": "Đồng Xanh xác nhận thu mua — đơn chào bán đã được duyệt",
        "body": ("Kính gửi HTX Đơn Dương,\n\nĐơn chào bán của quý HTX đã được Giám đốc "
                 "Đồng Xanh phê duyệt. Hợp đồng thu mua sẽ được gửi ký điện tử. Lịch giao "
                 "hàng và kiểm QA thực hiện theo SOP-02.\n\nTrân trọng,\n"
                 "Phòng Thu mua — Thực phẩm Đồng Xanh"),
    },
}

TITLES_VI = {
    "Start_1": "Nhận đơn chào bán",
    "Task_ReadForm": "Đọc đơn chào bán từ HTX",
    "Task_Validate": "Kiểm tra dữ liệu đơn",
    "Task_Extract": "Bóc tách lô hàng (AI)",
    "Task_Rag": "Đối chiếu QĐ-01 + SOP kiểm QA (KB)",
    "Task_Risk": "Chấm điểm rủi ro lô hàng (AI)",
    "GW_Value": "Giá trị > 50 triệu?",
    "Task_AutoLog": "Dưới ngưỡng — ghi nhận tự duyệt",
    "Task_Approval": "Giám đốc phê duyệt (QĐ-01)",
    "Task_Contract": "Lập hợp đồng thu mua (e-sign)",
    "Task_CreateTask": "Lệnh nhập kho + kiểm QA (SOP-02)",
    "Task_Narrative": "Ghi lý do quyết định (AI)",
    "Task_Insight": "Đăng quyết định lên feed",
    "Task_Email": "Thông báo HTX",
    "End_1": "Hoàn tất",
}

failed = []
for elem, node_id in ids.items():
    body = {"title_vi": TITLES_VI.get(elem)}
    if elem in CONFIGS:
        body["config"] = CONFIGS[elem]
    r = httpx.put(f"{BASE}/workflows/{WF}/nodes/{node_id}", headers=HDR,
                  json=body, timeout=30)
    ok = r.status_code == 200
    print(f"{elem:16s} -> {r.status_code}")
    if not ok:
        failed.append((elem, r.text[:300]))

if failed:
    print("FAILED:", json.dumps(failed, ensure_ascii=False, indent=1))
    raise SystemExit(1)
print(f"OK — {len(CONFIGS)} configs + {len(ids)} titles set")
