# -*- coding: utf-8 -*-
"""Seed demo data: form submission (don chao ban HTX) + K-22 risk register.

Usage: docker exec kaorisystem-ai-orchestrator-1 python /tmp/seed.py
Re-runnable: each call creates a NEW submission (latest_for_form picks newest).
Risk register: skipped if already registered for this workflow.
"""
import json
import httpx

BASE = "http://localhost:8093"
ENT = "3d1c1a53-f924-41fa-a4ce-defade00e898"
UID = "4ebbb853-8aaf-4f0c-9e86-e5180337ee63"
WF = "d2f72d21-21af-4351-8c0a-995afe164c74"
HDR = {"X-Enterprise-ID": ENT, "X-User-ID": UID, "X-User-Role": "MANAGER"}

submission = {
    "form_key": "don_chao_ban_htx",
    "source_channel": "api",
    "payload": {
        "ma_phieu": "TM-520",
        "ngay_giao_du_kien": "2026-07-12",
        "htx_nong_ho": "HTX Đơn Dương",
        "dat_vietgap": "Có",
        "items": [
            {"mat_hang": "Rau cải ngọt", "san_luong_kg": 2000, "gia_mua": 12000, "thanh_tien": 24000000},
            {"mat_hang": "Xà lách",      "san_luong_kg": 1500, "gia_mua": 14000, "thanh_tien": 21000000},
            {"mat_hang": "Bắp cải",      "san_luong_kg": 3000, "gia_mua": 6500,  "thanh_tien": 19500000},
            {"mat_hang": "Hành lá",      "san_luong_kg": 1400, "gia_mua": 13000, "thanh_tien": 18200000},
        ],
        "thanh_tien": 82700000,
        "ghi_chu": ("Đơn mùa vụ tháng 7. Công nợ kỳ trước còn 12.000.000. "
                    "Giá xà lách thị trường đang biến động ±10%."),
    },
}

r = httpx.post(f"{BASE}/workflow-form-submissions", headers=HDR, json=submission, timeout=30)
print("form submission:", r.status_code, r.json().get("submission_id") if r.status_code == 201 else r.text[:400])

use = {
    "workflow_id": WF,
    "use_name": "Thu mua nông sản từ HTX — AI hỗ trợ thẩm định",
    "risk_tier": "limited",
    "rationale": ("AI chỉ chấm điểm rủi ro + trích dẫn KB hỗ trợ; quyết định cuối cùng "
                  "do Giám đốc (human-in-the-loop theo QĐ-01)."),
}
existing = httpx.get(f"{BASE}/compliance/ai-uses", headers=HDR, timeout=30)
already = False
if existing.status_code == 200:
    data = existing.json()
    rows = data if isinstance(data, list) else data.get("items") or data.get("data") or []
    already = any(str(u.get("workflow_id")) == WF for u in rows if isinstance(u, dict))
if already:
    print("risk register: already registered — skip")
else:
    r2 = httpx.post(f"{BASE}/compliance/ai-uses", headers=HDR, json=use, timeout=30)
    print("risk register:", r2.status_code, r2.text[:400] if r2.status_code != 201 else r2.json().get("public_ref"))
