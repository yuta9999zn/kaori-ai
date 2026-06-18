# UAT — Phase 2 Sprint 2.1 Close-out

> **Created:** 2026-05-04
> **Goal:** Smoke-test 3 features ship gần nhất trong Sprint 2.1 close-out (F-033 PR B advanced, F-035 surface, F-041 explainability) trước khi tag release v1.2-phase2-sprint-2-1.
> **Mode:** Dev mode browser walkthrough (MSW intercept). Mode B (real BE) chỉ cần khi anh muốn chạm vào DB CHECK constraints + Kafka events.
> **Time budget:** ~20-30 phút.
>
> **Per-feature deep-dive UAT** (chi tiết hơn — pre-flight DB query + Kafka inspect + RFC 7807 paths):
> `F-033-multi-tier.md` · `F-035-cohort.md` · `F-041-explainability.md` · `HAPPY_PATH_SWEEP.md` §3.0 / §3.05 / §3.07.
> File này là round-2 sweep ngắn cho close-out — không thay thế chúng.

---

## 0. Pre-flight

Dev mode (MSW intercept):

```powershell
cd "D:\Kaori System\frontend"
npm run dev   # Next on :3000, MSW intercepts /api/v1/*
```

Login mock: `test@demo.com / password123` (MANAGER role — đủ cho mọi advanced + approve flow).

Full stack (chỉ cần cho SCN-2.E + SCN-3.D K-rule probes):

```powershell
docker compose up postgres redis kafka zookeeper ollama -d
docker exec kaori-ollama-1 ollama pull qwen2.5:14b   # hoặc 7b cho 16GB laptop
docker compose up -d
cd frontend; npm run dev
```

---

## 1. F-033 PR B Advanced tier + approval (~10 phút)

### 1.A — Tenant CHƯA opt-in → approval flow

| # | Action | Expected |
|---|--------|----------|
| 1.A.1 | Vào `/p2/analysis` | Hub render: 3 tier cards (basic + intermediate + advanced), không còn "PR B" badge trên Advanced |
| 1.A.2 | Click "Mở tier Nâng cao" → `/p2/analysis/advanced` | Form: cross-workspaces (1 item current workspace, MANAGER) + sources picker (silver/gold) + framework toggle + question + consent checkbox (đã tick) |
| 1.A.3 | Pick 2 sources + chọn SWOT + nhập "Khách hàng VIP nào sắp churn?" → bấm Dispatch | Redirect `/p2/analysis/runs/{id}` |
| 1.A.4 | Detail page render | Banner vàng "Đang chờ MANAGER duyệt" với button "Duyệt + dispatch"; status `queued`; polling DỪNG (không hammer BE) |
| 1.A.5 | Bấm "Duyệt + dispatch" | Banner biến mất, polling resume; status pollback `queued → running → done` ~3s (MSW) |
| 1.A.6 | Result render | SWOT 4-quadrant với weight bars + summary; `approved_at` timestamp hiển thị |

### 1.B — Tenant ĐÃ opt-in → direct dispatch (MSW dev)

| # | Action | Expected |
|---|--------|----------|
| 1.B.1 | Mở DevTools console, set `__kaoriMockTenantConsent=true` | flag flip cho MSW |
| 1.B.2 | Lặp lại 1.A.2 → 1.A.3 với run mới | Detail page render với status `queued` (KHÔNG `awaiting_approval`); auto-dispatch ngay |
| 1.B.3 | Sau ~3s | status `done`, không cần manual approve |

### 1.C — Validation + role gate

| # | Action | Expected |
|---|--------|----------|
| 1.C.1 | Form Advanced: bỏ tick consent checkbox → Dispatch | Button enable check disable hoặc 400 RFC 7807 — `consent_external=true (K-4)` |
| 1.C.2 | Form Advanced: chỉ pick 1 source | Dispatch button disable (FE require ≥2) |
| 1.C.3 | DevTools: set `__kaoriMockRole="VIEWER"` rồi bấm Approve trên 1A.5 | 403 RFC 7807 — `Only MANAGER can approve advanced runs` |
| 1.C.4 | Approve 2 lần liên tiếp (re-bấm sau khi đã success) | Lần 2 → 404 — `Run not found or already actioned` (idempotency) |

---

## 2. F-035 Cohort Retention (~5 phút)

### 2.A — Picker surface

| # | Action | Expected |
|---|--------|----------|
| 2.A.1 | Vào `/p2/analysis/basic` | Pipeline picker + template list 5 items (summary_stats, rfm_churn, **Cohort Retention**, anomaly, time_series) |
| 2.A.2 | Tick CHỈ "Cohort Retention" | Run button enable |
| 2.A.3 | Bấm Run → redirect `/p2/analysis/runs/{id}` | Status `queued → running → done` ~3s |

### 2.B — Heatmap render

| # | Action | Expected |
|---|--------|----------|
| 2.B.1 | Detail page sau run done | Section "Tổng quan" có 2 blocks: heatmap + stats card |
| 2.B.2 | Heatmap | Rows = cohort tháng (2026-01..04), cols = M0/M1/M2/M3; gradient đỏ→xanh; period 0 = 100% (đỉnh xanh) |
| 2.B.3 | Stats card | "Cohorts analysed" = 4, "Avg month1 retention" = 0.69 |
| 2.B.4 | Narrative | "M1 retention trung bình ~69%; cohort tháng 4 mạnh nhất (74%)..." |

---

## 3. F-041 Explainability (~5 phút)

### 3.A — Section render + lazy generate

| # | Action | Expected |
|---|--------|----------|
| 3.A.1 | Vào `/p2/decisions` → click bất kỳ row → `/p2/decisions/{id}` | Detail render với các section: Header → Lý do → **Vì sao Kaori quyết định thế?** (mới) → Lựa chọn thay thế → Override → Audit |
| 3.A.2 | Section "Vì sao Kaori quyết định thế?" | Disclaimer + button "Tạo giải thích" |
| 3.A.3 | Click "Tạo giải thích" | Spinner ~1.2s (MSW); render top-3 yếu tố + narrative + confidence footer |
| 3.A.4 | Top-3 yếu tố | Mỗi row: direction icon (TrendingUp/Down/Minus) + factor_name + weight % + horizontal bar + evidence quote |
| 3.A.5 | Bấm "Tạo lại" | Re-spin + render lại (cùng response trong MSW; thật BE có thể khác do LLM temperature) |

### 3.B — Edge cases

| # | Action | Expected |
|---|--------|----------|
| 3.B.1 | URL `/p2/decisions/miss-12345` rồi click "Tạo giải thích" | 404 RFC 7807 banner — `Decision not found` |
| 3.B.2 | URL `/p2/decisions/fail-12345` rồi click "Tạo giải thích" | 502 RFC 7807 banner — `LLM gave up...`; button stay available cho retry |

---

## 4. Cross-cutting probes (~5 phút, optional)

| # | Probe | Expected |
|---|---|---|
| 4.1 | DB CHECK: `INSERT INTO analysis_runs (tier, consent_external, ...) VALUES ('advanced', false, ...);` | Postgres reject — `analysis_runs_advanced_consent_check` violation (K-4) |
| 4.2 | DB CHECK: `INSERT INTO analysis_runs (tier, framework, ...) VALUES ('intermediate', NULL, ...);` | Reject — `analysis_runs_intermediate_framework_check` (K-10) |
| 4.3 | Kafka UI `localhost:8085` → topic `kaori.analysis.tier.started` sau 1 advanced run | 1 message với `tier=advanced, scope=cross, framework=swot` |
| 4.4 | `kaori.analysis.tier.completed` sau khi run done | 1 message với `status=done` |
| 4.5 | Audit chain: sau 1 advanced run + 1 explain | `decision_audit_log` có 3 rows mới: `analysis.advanced.approved` (manual) + `analysis.advanced` (llm_provider=external) + `explainability.explain` |
| 4.6 | Cross-tenant: login enterprise B, `GET /api/v1/analysis/runs/{A's id}` | 404 RLS — không leak existence |
| 4.7 | Quota: `GET /api/v1/analysis/quota/external-ai` sau advanced run | `external_calls_used` tăng theo số advanced run dispatch (count `decision_audit_log` `llm_provider != qwen-internal`) |

---

## 5. Sign-off checklist

Mark từng mục khi pass:

- [ ] **F-033 PR B** — 1.A (approval flow) + 1.B (direct dispatch) + 1.C (validation + role gate) đều pass
- [ ] **F-035** — 2.A picker visible + 2.B heatmap render đẹp
- [ ] **F-041** — 3.A happy path + 3.B edge cases (404 + 502) ổn
- [ ] **Cross-cutting** — ít nhất 4.1 (DB CHECK) + 4.6 (RLS) pass nếu chạy full stack
- [ ] **`tsc --noEmit`** clean (em đã verify)
- [ ] **ai-orchestrator pytest** 381/381 (em đã verify)

Anh check xong → tag `v1.2-phase2-sprint-2-1` rồi báo em đi tiếp Sprint 2.5/2.6.

---

*Phase 2 Sprint 2.1+2.2 close-out — 10/36 functions ship. Next stop: pilot deployment seed (synthetic data) hoặc Sprint 2.5 KG/AutoDB/BlastRadius wow-factor.*
