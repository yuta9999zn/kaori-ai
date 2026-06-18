# PROJECT STATUS — 2026-05-20

> **Mục đích:** Source-of-truth duy nhất cho trạng thái thật của dự án Kaori AI tại ngày 2026-05-20.
> Đặt ở root `D:\Tài liệu dự án\` để bất kỳ ai mở thư mục cũng thấy ngay sự lệch giữa **tài liệu BA**, **GitHub remote**, và **code local (zip / working tree)**.
> File này được tạo sau khi rà soát toàn bộ Folder 01–04 + Excel v4.1 + code repo `D:\Kaori System\` ngày 2026-05-20.

---

## 0. Tóm tắt 30 giây

| Trục | Trạng thái thật | Trạng thái tài liệu đang ghi | Hành động |
|---|---|---|---|
| **Code local** | Phase 2.7 (governance lineage / quotas / policy / DLQ console / AI audit đã wire vào producer) — CLAUDE.md 3.8.1 | BA docs (FRD/SRS/CR) coi GAP-01/02/03 ASSESSING, chưa biết Phase 2.5/2.6/2.7 đã ship | Update sang **PARTIAL IMPLEMENTED** + thêm AS-IS mục mới |
| **GitHub remote** | baseline cũ — CLAUDE.md 3.0.0 ngày 2026-05-08 (Phase A docs reset) | — | Khi quota CI reset (June) push branch `feat/p15-s9-d1` (~221 commit ahead `main`) |
| **CI** | PR #179 đỏ vì quota GitHub Actions 3000 phút/tháng hết, anh không $40 overage | Tài liệu nhiều chỗ ghi "tests pass" như production-ready | Phải đọc là **"local pytest claimed pass, CI pending quota reset"** |
| **Excel v4.1** | 266 feature ghi Phase 1.5 nhưng sprint P3-S25; 1.143 feature trống Owner; Delivery Readiness chỉ template | — | CR-0004/0005 vẫn SUBMITTED, **chưa đóng** |
| **Secret** | `.env` thật nằm trong zip: Telegram token, JWT priv/pub key, DB pw, SMTP, Zalo, API key | — | **Nếu zip từng gửi ra ngoài → rotate toàn bộ ngay**; tuyệt đối không kèm `.env` khi push branch lên GitHub |

---

## 1. Bản đồ 3 nguồn lệch

### 1.1 Code local (`D:\Kaori System\` — zip working tree)

Đây là nơi đi xa nhất. CLAUDE.md đầu file ghi:

```
Version: 3.8.1 | Updated: 2026-05-20
Phase 2.7 wiring: 4 of 4 producer-side wiring commits
  - record_ai_call on llm-gateway dispatch
  - tenant quota gate on /v1/infer + /workflows/run
  - policy override at approval_gate
  - lineage emit on bronze→silver + output sinks
Phase 2.7 shape → production-wired
```

Tóm tắt cái đã thực sự ship (BE), gom theo phase:

| Phase | Đã ship trong code local | Nguồn truy ngược |
|---|---|---|
| Phase 1 v4 (M1-M4) | 8/8 sprint P1-S1..S8 ✅ tag `v4.0-phase1-complete` | `docs/archive/PHASE1_V4_CLOSEOUT.md` |
| Phase 1.5 (M5-M6) | 4/4 sprint P15-S9..S12 ✅ | CLAUDE.md §14 + `docs/sprint/` |
| Phase 2 (M7-M12) | P2-S13/S14/S15/S16/S18/S21/S25 ✅; S17 mobile **không scope BA**; S19/S20 microservices **defer Phase 3** | CLAUDE.md §14 |
| Phase 2.5 (MinerU pattern + AI node catalog) | 10/10 BE ✅ (FE bbox UI đợi FE restructure) | CLAUDE.md §14 row P2.5 |
| Phase 2.6 (orchestration hardening) | 9/12 ship; 3 infra-gated defer (CDC, ClickHouse cutover, streaming) | `docs/sprint/PHASE_2_6_DEFER_QUEUE.md` |
| Phase 2.7 (governance + observability + producer wiring) | 5/5 + 4/4 wiring ship | CLAUDE.md §14 row P2.7 |
| Workflow Execution Closeout (catalog 45/45) | 45/45 executor ✅, 25/25 mig 069 template LIVE | CLAUDE.md §14 row "Workflow Execution Closeout" |

### 1.2 GitHub remote

- Branch `main` HEAD ngày 2026-05-08 commit `5d36fea` (sau Phase A docs reset).
- Branch `feat/p15-s9-d1` đã push tới HEAD trùng zip nhưng PR #179 chưa merge vì CI đỏ.
- CLAUDE.md trên main **không phải 3.8.1**, là phiên bản 3.0.0 v4 reset.

⇒ **Người outside truy cập GitHub repo sẽ thấy một dự án cũ hơn 12 ngày + ~221 commit so với thực tế.**

### 1.3 Tài liệu BA (`D:\Tài liệu dự án\`)

Hiện trạng theo từng file (chi tiết §3):

| File | Tình trạng so với code |
|---|---|
| `1.1`/`1.2`/`1.3`/`1.4` BRD/MRD/Vision/Business Case | Chiến lược ổn, không cần update Phase 2.x |
| `2.1` URD | Stale — không có US cho governance/lineage/quota/policy mới |
| `2.2` FRD | **Stale** — backlog GAP coi GAP-01/02/03 "đề xuất Phase 2"; thực tế đã PARTIAL |
| `2.3` PRD | OK ở cấp pricing, stale ở feature list |
| `3.1` SRS | **Stale** — UC-TB-01/02 coi TO-BE, thực tế đã PARTIAL trên code |
| `3.2` NFRS | Còn dùng được; AC P99 / latency / scale chưa đo CI |
| `3.3` Wireframe | **Chưa viết** — có `docs/specs/UI_SCREENS_INVENTORY.md` 70 screens trong code repo |
| `3.4` API Contract | **Chưa viết** — có `docs/API_CATALOG_V4.md` + `docs/api-specs/*.openapi.json` |
| `3.5` Data Dictionary | **Chưa viết** — có `docs/specs/MEDALLION_CONTRACT.md` + 99 mig SQL |
| `3.6` UAT | **Chưa viết** — có thư mục `docs/uat/` + screen UAT files |
| `4.1` RACI | Ổn |
| `4.2` CR Register | **Stale** — CR-0001/0002/0003 vẫn ASSESSING; thực tế đã PARTIAL |
| `90_Day_Delivery_Process_v4.md` | OK |
| `Kaori_AI_Feature_Tree_v4_1.xlsx` | **Stale** — 266 lệch phase, 1.143 Owner trống, Delivery Readiness chưa fill |

---

## 2. Rủi ro P0 — xử ngay

### 2.1 Secret leak trong zip

Lúc rà soát phát hiện `.env` trong zip chứa:
- Telegram bot token (P1-S8)
- JWT RS256 private key + public key
- Database password
- SMTP credentials (notification-service)
- Zalo OA token
- API keys vendor LLM (Anthropic / OpenAI) nếu có

**Hành động:** nếu zip này đã từng gửi qua bất kỳ kênh nào (email / Drive / chat / Github gist) thì coi như **rò rỉ** và:
1. Revoke Telegram bot token → tạo mới qua BotFather.
2. Rotate JWT keypair → re-issue qua Vault path `platform/auth/jwt`.
3. Reset DB password (Postgres user `kaori`).
4. Reset SMTP password.
5. Re-create Zalo OA secret.
6. Rotate Anthropic / OpenAI API key qua dashboard vendor.

**Phòng ngừa khi push GitHub:**
```
.gitignore phải đảm bảo có:
  .env
  .env.*
  !.env.example
  .claude/
  node_modules/
  .next/
  target/
  *.zip
```

### 2.2 GitHub vs local lệch ~221 commit + 12 ngày

- Quy ước hiện tại: **code local zip = source of truth**, GitHub là baseline cũ.
- Khi quota CI reset (đầu June 2026) tiến hành:
  1. Branch protection cho `main` (yêu cầu CI xanh trước merge — đã đúng).
  2. Push `feat/p15-s9-d1` lên remote (đã push trước đó, CI red).
  3. CI re-run, xử fail còn lại nếu có.
  4. Squash hoặc keep-history vào `main` qua PR #179 review.
  5. Tag `v2.7-governance-wired` sau merge.

### 2.3 CI status không tự confirm "production-ready"

Trong CLAUDE.md có nhiều dòng kiểu "ai-orch 2128 → 2355 (+227 tests, 0 failing)". **Đây là local pytest output, chưa qua CI matrix** (Linux + Windows + Python 3.11/3.12 + integration container + DB live + Vault). Đọc đúng là:

> **"Local tests claimed pass, CI pending GitHub Actions quota reset (June 2026)."**

Không được kết luận production-ready cho đến khi:
- CI matrix xanh trên `feat/p15-s9-d1`.
- Smoke E2E browser test pass (đặc biệt SSO Google + workflow runner + lineage walk).
- Manual UAT round phòng pilot.

### 2.4 Excel v4.1 issues

| Issue | Hiện trạng | CR liên kết |
|---|---|---|
| 266 feature ghi Phase 1.5 nhưng sprint P3-S25 | Vẫn lệch | CR-0004 SUBMITTED |
| 1.143 feature trống Owner | Vẫn trống | CR-0005 SUBMITTED |
| Delivery Readiness chỉ template | Vẫn template | Cần phiên CR Review Board kế |

Nếu coi Excel là tracker delivery → **chưa đủ tin cậy**. Đề xuất tạm dùng `BACKLOG_V4.md` trong code repo làm canonical source cho status; Excel chỉ làm portfolio overview cho stakeholder.

---

## 3. Lệch giữa BA và code (P1)

### 3.1 GAP-02 Workflow Card Document Library — đã PARTIAL, BA ghi ASSESSING

Tài liệu BA (`4.2` CR-0002 + `2.2` FRD §3.GAP-02 + `3.1` SRS UC-TB-02) coi đây là TO-BE Phase 2.

**Code thực tế đã có:**
- Mig 053 `workflows / workflow_nodes / workflow_edges / workflow_step_documents / workflow_templates` (commit `ef42989` 2026-05-15).
- Mig 054 18 templates auto-generated; mig 068 catalog 45 node types; mig 069 25 production templates.
- Mig 072 `workflow_editors / workflow_comments / workflow_locks` (commit `ff8fd22`).
- Step folder CRUD: 13 endpoint workflow + step_documents (CRUD `/p2/workflows`, `/p2/workflows/{id}/steps/{sid}/folders/...`, `/p2/workflows/{id}/steps/{sid}/documents`).
- Tree viewer FE route `/p2/workflows`.
- Upload pipeline nhận `X-Workflow-Step-ID` header → ghi `workflow_step_documents` row.
- Comment + lock + editor presence multi-user (commit `ff8fd22`).
- Import/Export workflow as YAML (commit `e438482`).

**Còn thiếu để đóng GAP-02:**
- UAT browser end-to-end "tạo workflow → thêm step → đính folder → upload tài liệu → assign reviewer" round 2.
- Wire FE Drag-drop builder full polish (FE đang paused theo §2 CLAUDE.md).
- Permission matrix tài liệu per node × role (Phase 2 RBAC, US-F4 trong URD).
- Spec final + UI mockup `3.3 Wireframe`.

⇒ **Đề nghị đổi CR-0002 status: ASSESSING → PARTIAL IMPLEMENTED.**

### 3.2 GAP-03 Document Intelligence Pipeline — đã PARTIAL nhiều, BA ghi ASSESSING

Tài liệu BA coi đây CRITICAL TO-BE Phase 2–3.

**Code thực tế đã có (Phase 2.5 + P15-S11 DocSage):**
- Document type detector (magic-byte aware) + spoof guard (commit `7dfa2b1`).
- DocSage extract end-to-end D1→D6 (commits `7a47b17`..`c6e47c5`):
  - Stage 2B LLM fallback (schema detection).
  - PDF: pdfplumber + table extractor + bbox.
  - DOCX: docx2python wrap.
  - Image: OCR Qwen2.5-VL local adapter via `/v1/ocr` (K-4 schema-pinned, không consent_external).
- Block taxonomy + header/footer strip (Pattern 1+2 commit `25e82be`).
- Multi-column reading order Pattern 4 (commit `be6867a`).
- 9 AI node ship: classify_document / extract_structured_data / summarise_document / sentiment_analysis / dedup_records / compare_to_template / call_insight_engine / generate_narrative / rag_query.
- Embedding BGE-M3 endpoint `/v1/embed` + pgvector HNSW (mig 067 VECTOR(1024)).
- RAG endpoint `/rag/answer` (D6) với 4 engines (gồm trace_recall T-Cube).
- Bronze→Silver lineage edge emit (commit `31af408`, mig 097).
- Confidence threshold + human-review fallback shape (ingestor `unsupported_today` escape hatch).
- compare_to_template = RAG contract diff (commit `0ce5115`, mig 087).

**Còn thiếu để đóng GAP-03:**
- Production pipeline 1-vertical chuyên sâu (hợp đồng / hoá đơn) — hiện đang generic.
- Vector store cluster ngoài Postgres pgvector (Qdrant fallback cho data residency strict — defer Phase 3).
- FE bbox highlight UI (đợi FE restructure).
- UAT browser end-to-end với khách thật.
- Compliance: retention policy + right-to-delete tài liệu chưa wire endpoint.
- ENT MID + ENT MAX plan-gating chưa wire.

⇒ **Đề nghị đổi CR-0003 status: ASSESSING → PARTIAL IMPLEMENTED (Phase 2-3 tiếp tục).**

### 3.3 GAP-01 Org Hierarchy Modeler — PARTIAL nhỏ

**Code thực tế đã có:**
- Mig 055 `corporate_groups / business_divisions / enterprises ALTER 3 FKs` + mig 056 Vingroup demo (commit `e0da8a8`).
- Mig 057 `workflow_cross_links` workspace-scoped + view `v_workflow_cross_links_enriched`.
- Router corporate_tree (10 endpoint) + cross-link CRUD (3 endpoint).
- Recursive parent_id self-FK pattern.

**Còn thiếu nhiều:**
- FE drag-drop org tree builder (Tuần 9, defer FE restructure).
- ABAC subject attribute mở rộng (Phase 2 PDP).
- Rollup KPI/NOV/Adoption từ leaf → root (Vingroup-class) chỉ ở model + view, chưa wire compute path.
- Feature flag per tenant để bật.
- ≥1 khách tập đoàn pilot cam kết.

⇒ **Status: ASSESSING → PARTIAL (model + API có, UX + rollup compute còn thiếu).**

### 3.4 Frontend status — "paused" không còn đúng tuyệt đối

CLAUDE.md §2 ghi `Frontend: ⏸ TẠM DỪNG`. Thực tế:
- Repo có nhiều page P1 (`/platform/*`) + P2 (`/p2/*`) + UAT screens.
- SSO Google live end-to-end browser-tested với account `nguyentruongan25051997@gmail.com` (commit `6c92b69`).
- Visual workflow builder page tồn tại.
- FE TypeScript types regenerated từ OpenAPI (pipeline.d.ts 1386 lines, orchestrator.d.ts 3877 lines).

⇒ Trạng thái đúng: **"FE scaffold + nhiều page exist + SSO + login + workflow builder + corporate tree page đã có; restructure paused trước khi build mới; build/typecheck/browser QA per-screen pending."**

---

## 4. Tài liệu BA còn thiếu (P1) → consolidator pointer

README ghi 3.3/3.4/3.5/3.6 là Batch sau. Code repo đã có docs tương đương — chưa hợp nhất vào BA officially.

| BA file đang thiếu | Doc tương đương trong code repo | Hành động đề xuất |
|---|---|---|
| `3.3_Wireframes_and_Screen_Spec.md` | `docs/specs/UI_SCREENS_INVENTORY.md` (70 screens × 6 portal) + `docs/specs/MESSAGE_DEFINITIONS.md` + `docs/specs/VALIDATION_RULES.md` | Tạo stub 3.3 với pointer-list + đánh dấu file nào canonical |
| `3.4_API_Contract.md` | `docs/API_CATALOG_V4.md` (169 endpoint) + `docs/api-specs/*.openapi.json` snapshots | Tạo stub 3.4 reference + ghi quy ước cập nhật |
| `3.5_Data_Dictionary_and_Event_Schema.md` | `docs/specs/MEDALLION_CONTRACT.md` + 99 mig SQL `infrastructure/postgres/migrations/` + Kafka topic table CLAUDE.md §7 + Redis Streams convention | Tạo stub 3.5 reference + table conventions |
| `3.6_UAT_Test_Cases_and_Acceptance_Criteria.md` | `docs/uat/` per-feature scripts + screen UAT files | Tạo stub 3.6 với checklist + index |

**Phải tránh:** copy-paste lại doc trong code repo vào BA folder — sẽ drift ngay vì code repo cập nhật theo commit, BA folder hiếm khi cập nhật. Pointer là đủ, kèm policy "khi nào hợp nhất chính thức".

---

## 5. Infra / production còn mở (P2)

Bảng defer-queue Phase 1.5 + Phase 2.6 + Phase 2.7. Không phải blocker để đóng pilot 10–15 khách, nhưng phải có khi đi 100 khách Phase 2.

| Hạng mục | Trạng thái | Trigger để mở khoá |
|---|---|---|
| K8s FPT Cloud provision | Defer | Runbook `docs/runbooks/k8s-fpt-cloud-provision.md` đã ship; cần hợp đồng FPT FKE |
| Temporal worker live cutover | Defer (`TEMPORAL_ENABLE_WORKER=true` flag default OFF) | Worker code ready từ P1-S6; bật khi K8s sẵn |
| ClickHouse Silver tier cutover | Defer | Helm chart `infrastructure/clickhouse/` sẵn; chưa provision cluster |
| Postgres CDC Debezium → ClickHouse | Defer | Mig 048+; design plan ở `PHASE_2_6_DEFER_QUEUE.md` |
| Streaming pipeline (Flink/ksqlDB) | Defer Phase 2.6 P2.4 | Watermarking design ở defer-queue |
| Microservice extraction (process-mining / adoption-intel / economics / workflow-engine) | Defer Phase 3 (ADR-0010 updated) | Modular monolith đủ tốt cho 100 khách |
| PageIndex PyPI activation | Defer (upstream-wrap ready commit `6c8d803`) | Wire khi cần tree-of-content theo content (vs heading) |
| Java VaultClient (D2) | Defer Phase 2 | Java service hiện đọc env; Vault HA đã ship cho Python services |
| Postgres CDC real (D4a) | Defer Phase 2 | Polling adapter dùng tạm |
| Zalo metadata real (D4c) | Defer Phase 2 | Stub adapter dùng tạm |
| Dual-write cutover (D8) | Defer Phase 2 | Bronze + Silver async write strategy |

---

## 6. Việc nên làm tiếp (action list)

### Trong tuần này (anh + em)

1. **Tạo + ký file PROJECT_STATUS này** làm baseline → commit vào `D:\Tài liệu dự án\`.
2. **Update 4.2_Change_Request_Register.md**: CR-0001 ASSESSING → PARTIAL · CR-0002 ASSESSING → PARTIAL IMPLEMENTED · CR-0003 ASSESSING → PARTIAL IMPLEMENTED.
3. **Update 2.2_FRD.md** + **3.1_SRS.md** đồng bộ status PARTIAL + bổ sung FR mới Phase 2.7.
4. **Update README.md** bảng Batch — đánh dấu Batch 2/3 đang **pointer-consolidated** chứ chưa native BA.
5. **Tạo stub 3.3 / 3.4 / 3.5 / 3.6 pointer file** trong `D:\Tài liệu dự án\` — mỗi file là 1 trang reference list về docs code-repo có sẵn.

### Khi quota CI reset (June 2026)

6. Push `feat/p15-s9-d1` clean snapshot (không kèm `.env`, `.claude/`, `node_modules/`, `.next/`, `target/`).
7. CI re-run + xử fail còn lại.
8. PR #179 review + merge.
9. Tag `v2.7-governance-wired`.
10. Update `D:\Tài liệu dự án\PROJECT_STATUS_2026-05-20.md` → mới (đặt tên theo ngày).

### Sau pilot 1 khách tập đoàn cam kết

11. Mở CR-0001 GAP-01 sang APPROVED → close hoàn toàn (Phase 2 sprint dedicated).
12. UAT round 2 + 3.6 UAT file canonical version.

### Nếu zip đã rò rỉ ra ngoài

13. Rotate toàn bộ secret §2.1 ngay.

---

## 7. Phụ lục — refs nhanh

- CLAUDE.md (code local): `D:\Kaori System\CLAUDE.md` v3.8.1 (2026-05-20).
- Sprint progress: `docs/BACKLOG_V4.md` + CLAUDE.md §14.
- ADRs: `docs/adr/` (ADR-0001 → ADR-0025).
- Defer-queues: `docs/sprint/PHASE_2_6_DEFER_QUEUE.md`.
- Runbooks: `docs/runbooks/` (sso-microsoft-setup / k8s-fpt-cloud-provision / dev-to-prod-data-cutover / workflow-execution-enable / pageindex-upstream-activation).
- Excel: `D:\Tài liệu dự án\Kaori_AI_Feature_Tree_v4_1.xlsx` — Issues sheet ghi ISS-001 + ISS-004.

---

*— Hết PROJECT STATUS 2026-05-20 —*
