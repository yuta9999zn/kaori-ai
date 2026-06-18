# ADR-0028 — OpenTelemetry Forward Sync Phase 3 (1.28 / 0.49b2 holster)

| | |
|---|---|
| **Status**   | Accepted |
| **Date**     | 2026-05-23 |
| **Phase**    | Phase 3 (Year 2) — holster Phase 1-2 |
| **Anh ref**  | Session 2026-05-22 EOD sequence Item 4 |
| **Related**  | ADR-0027 (Spring Boot 4.x + Java 25 Phase 3 holster), K-19 (OTel mandatory + tenant_id span attribute), CLAUDE.md §2 (Tech Stack PINNED), PR #202 (OTel 1.28 + Spring 3.2.5 lock fix), memory `feedback_dependabot_piecemeal_bumps.md` |

## Context

Trạng thái 2026-05-23, OTel pin trên 4 Python service + 2 Java service:

| Service | OTel core | OTel instrumentation | Bind |
|---|---|---|---|
| data-pipeline | 1.28.2 | 0.49b2 (fastapi/asyncpg/aiokafka/httpx) | requirements.txt |
| llm-gateway | 1.28.2 | 0.49b2 (fastapi/asyncpg/httpx) | requirements.txt |
| notification-service | 1.28.2 | 0.49b2 (fastapi/asyncpg/httpx) | requirements.txt |
| ai-orchestrator | 1.28.2 | 0.49b2 (fastapi/asyncpg/aiokafka/httpx) | requirements.txt |
| api-gateway | implicit ~1.32 qua Micrometer 1.2.x | qua `micrometer-tracing-bridge-otel` | Spring Boot 3.2.5 BOM |
| auth-service | implicit ~1.32 qua Micrometer 1.2.x | qua `micrometer-tracing-bridge-otel` | Spring Boot 3.2.5 BOM |

Versions hiện tại (2024-10 GA) đã ~1 năm cũ tại 2026-05-23. OTel ecosystem releases:

- **OTel 1.30** (2025-02): log API redesign, semantic conventions overhaul (`http.method` → `http.request.method`); breaking change cho exporter custom code
- **OTel 1.32** (2025-06): Span Links semantic refinement; auto-detected runtime instrumentation cho asyncio events
- **OTel instrumentation 0.50b** (2025-02): Python 3.9+ required (we'll stay 3.11+ qua Phase 1-2 per ADR Python holster, OK)
- **OTel instrumentation 0.51b** (2025-04): asyncpg context propagation fix; aiokafka instrumentation regression (0.50b1 broke header injection — fixed 0.51b2)
- **OTel SDK 1.40** (2025-10): synced với Spring Boot 4.0 BOM (Micrometer Tracing 2.0)

Hai pull đối nghịch:

- **Pull toward upgrade**: K-19 mandate enterprise-grade trace search; OTel 1.32+ có semantic conventions HTTP/database stable cho production grade; Spring AI 1.0 GA (Spring Boot 4) chỉ instrument đúng với OTel 1.40+; Dependabot tuần nào cũng fire major bump PR phải reject thủ công.
- **Pull toward hold**: PR #202 vừa fix ổn 2026-05-22 (memory `feedback_dependabot_piecemeal_bumps.md`); 2350+ tests trên ai-orchestrator đang xanh với matrix 1.28/0.49b2; semantic convention rename 1.30 break dashboard Grafana + Prometheus rule + Loki LogQL hiện đang dùng `http.method`, `db.statement` (Phase 1-2 K-19 spec); aiokafka instrumentation regression đã verified trong dev → không thể bump 0.49b2 → 0.50b mà không pin >0.51b2; Java OTel implicit qua Spring Boot BOM nên cannot bump độc lập với ADR-0027 (Spring Boot 4 Phase 3).

## Decision

**Hold OTel 1.28.2 / instrumentation 0.49b2 trên Python + implicit Spring Boot 3.2.5 BOM trên Java qua hết Phase 2. Phase 3 mới forward-sync, coordinated với ADR-0027 Spring Boot 4 cutover.**

### Phase 1-2 (now → 2026-06-30, Phase 2 close)

- **Python services**: pin `opentelemetry-api==1.28.2`, `opentelemetry-sdk==1.28.2`, `opentelemetry-exporter-otlp-proto-http==1.28.2`, tất cả `opentelemetry-instrumentation-*==0.49b2`. Không patch nội bộ.
- **Java services**: Spring Boot 3.2.5 BOM define version (Micrometer Tracing 1.2.x → OTel ~1.32) — không override. Khi ADR-0027 hold giữ SB 3.2.5, side OTel tự động hold.
- **Cấm bump**: Dependabot ignore `opentelemetry-*` semver-major + semver-minor cho cả 4 Python service. Thêm vào `.github/dependabot.yml` Phase 1-2 ignore block. Pip semver semantics → ignore range `>=1.29` cho `opentelemetry-*` và `>=0.50` cho instrumentation. (Lưu ý: instrumentation dùng pre-release `bN` suffix, cần `update-types: ["version-update:semver-major", "version-update:semver-minor"]`.)
- **Cấm**: thêm OTel instrumentation **mới** trong Phase 1-2 (vd `opentelemetry-instrumentation-redis`, `-celery`, `-sqlalchemy`) trừ khi pin 0.49b2 — tránh accidental skew khi adapter chỉ ship version 0.51b+.
- **Test gate**: span attribute `tenant_id` (K-19) verified qua existing CI test `test_tenant_span_attribute.py` (ai-orchestrator). Nếu rơi đỏ trong bất kỳ Dependabot PR nào → close PR, không investigate piecemeal.

### Phase 3 — coordinated forward-sync sprint (sau ADR-0027 step 2)

Thứ tự bắt buộc (gắn vào sprint Phase 3 base-image/Spring Boot cutover):

1. **Bump Java OTel = qua bump Spring Boot 3.2.5 → 4.0.x** (ADR-0027 step 2). Micrometer Tracing 1.2 → 2.0 carry OTel 1.32 → 1.40 implicit. Không override.
2. **Bump Python OTel** trên 4 service cùng commit (1 PR atomic):
   - `opentelemetry-api/sdk/exporter-otlp-proto-http`: `1.28.2` → `1.40.x` (LTS line cho Phase 3)
   - `opentelemetry-instrumentation-*`: `0.49b2` → `0.51b2` (skip 0.50b — aiokafka regression)
3. **Audit semantic convention rename** trong Grafana dashboard + Prometheus rule + Loki LogQL: `http.method` → `http.request.method`, `http.url` → `url.full`, `db.statement` → `db.query.text`. Provide alias query trong Promtail/Vector relabel layer **trước** PR ship để không gãy alert.
4. **Re-verify K-19**: `tenant_id` span attribute propagation test pass; cross-tenant search Grafana xanh.
5. **Re-verify aiokafka instrumentation**: header injection test pass (regression cũ 0.50b1).
6. **Update CLAUDE.md §2**: chuyển từ "Phase 1-2 lock OTel 1.28/0.49b2" → "Phase 3 OTel 1.40/0.51b2 (ADR-0028 cutover)".

Coordinated với ADR-0027 nhưng **không cùng PR** — ship trước SB4 bump 1 PR riêng để giảm scope rủi ro, sau khi ADR-0027 step 2 CI green ≥48h.

### Forbid (cả Phase 1-2 lẫn Phase 3)

- Bump Python OTel core mà không bump instrumentation cùng commit (version skew → exporter mismatch error).
- Bump 1 instrumentation lẻ (vd `-asyncpg` 0.49b2 → 0.51b2 trong khi `-fastapi` còn 0.49b2) — context propagation chain gãy ở boundary.
- Add new OTel instrumentation Phase 1-2 với version ngoài 0.49b2 pin range.
- Override OTel version trong Java pom mà không bump Spring Boot BOM cùng commit (BOM constraint conflict).

## Consequences

### Positive

- **Stable trace surface qua Phase 2 close**: 2350 tests + Grafana dashboard + Prometheus rule + Loki LogQL không phải audit lại khi semantic conventions còn `http.method`/`db.statement`.
- **Single coordinated cutover Phase 3**: Java OTel bump tự động theo Spring Boot 4.x; Python OTel bump 1 PR atomic. Tổng scope 2 PR ≤ 1 sprint.
- **Loại Dependabot noise**: ignore rule cụ thể, không phải close PR thủ công tuần nào cũng có (precedent đã rõ trong memory).
- **K-19 invariant preserved**: tenant_id propagation đã verified với 1.28/0.49b2 — không rủi ro Phase 1-2.

### Negative / accepted trade-offs

- **OTel lag ~7 tháng** so với upstream LTS (1.28 → 1.40). Mất features: log API redesign (1.30), runtime asyncio instrumentation auto (1.32), Span Links semantic refinement.
- **Semantic conventions cũ** (`http.method`, `db.statement`) — không tương thích với industry-standard new convention; vendor/SaaS observability tool (Datadog, Honeycomb) đã chuyển sang new convention → tích hợp Phase 2 khó hơn.
- **Spring AI 1.0 GA hoãn**: ADR-0027 đã defer Spring Boot 4 → Phase 3, OTel Java cũng follow. Phase 2 không thể thử Spring AI features mới.

### Neutral / follow-ups

- **Trigger reconsider sớm**: CVE critical trong OTel 1.28 stream không patch được → bump khẩn 1.29.x (patch within minor OK).
- **Trigger reconsider sớm**: aiokafka 0.49b2 regression mới phát hiện → có thể patch 0.49b3 nếu upstream ship; chấp nhận patch-level bump trong Phase 2.
- **Phase 3 prep**: viết runbook `docs/runbooks/otel-1.40-cutover.md` với semantic convention rename alias mapping. Phải có **trước** khi ship PR cutover, không freestyle.
- **Update `.github/dependabot.yml`**: PR follow-up sẽ bundle ignore rules cho cả ADR-0027 (spring-boot) + ADR-0028 (opentelemetry-*) + ADR Python (đã làm 2026-05-22 PR #209).
- **Update CLAUDE.md §2**: ghi rõ "OTel 1.28/0.49b2 pinned Phase 1-2 per ADR-0028; bump 1.40/0.51b2 Phase 3" để future agent đọc context.

## Alternatives considered

- **Alt 1 — Bump Python OTel 1.28 → 1.30 now (drop instrumentation bump)**. Lý do: 1.30 fix log API + semantic conventions HTTP. Nhược: semantic convention rename break Grafana dashboard + Prometheus rules ngay lập tức trong Phase 2; instrumentation 0.49b2 không tương thích forward với OTel 1.30 API → exporter crash. Quyết định: không — bump tách rời từng layer không khả thi cho OTel.
- **Alt 2 — Bump cả OTel core + instrumentation lên 0.51b2 now**. Atomicity OK nhưng semantic convention rename vẫn break dashboard mid-Phase 2; aiokafka regression đã fix nhưng cần Grafana/Prometheus relabel layer trước → too much side work mid-sprint. Quyết định: không — Phase 3 đủ thời gian audit.
- **Alt 3 — Bump Java OTel độc lập với Spring Boot (override version trong pom)**. Override OTel exporter version trong api-gateway pom có thể làm — nhưng Micrometer Tracing 1.2 (đến qua SB 3.2.5 BOM) binding OTel 1.32 API; force 1.40 sẽ binary-incompatible. Quyết định: không — Java OTel coupling với Spring Boot BOM là cứng.
- **Alt 4 — Forward-sync Python OTel Phase 2, hold Java OTel tới Phase 3**. Tốt cho Python side independence nhưng dashboard/alert ecosystem gãy vì Python service emit new convention attribute mà Java service vẫn emit cũ → cross-service trace search inconsistent (vi phạm K-19 spirit). Quyết định: không — full ecosystem sync hơn split-brain.

## References

- CLAUDE.md §2 (Tech Stack PINNED) + K-19 (OTel mandatory + tenant_id span attribute)
- ADR-0027 — Spring Boot 4 + Java 25 Phase 3 holster (sibling ADR, gắn coordinated cutover)
- ADR-0013 — RLS multi-tenancy formalize v4 (mandate tenant_id traceable cross-service → K-19)
- PR #202 (merged 2026-05-22) — OTel 1.28.2 + 0.49b2 lock fix
- PR #209 (open 2026-05-22) — Dependabot Python major bump ignore (precedent)
- Memory `feedback_dependabot_piecemeal_bumps.md` — anh's "lock + ignore + coordinate" precedent
- OpenTelemetry semantic conventions HTTP migration guide: https://opentelemetry.io/docs/specs/semconv/http/migration-guide/ (verify before Phase 3 cutover)
- OTel instrumentation 0.50b → 0.51b2 aiokafka changelog (verify upstream before Phase 3)

---

**Editing note** — ADRs append-only. Phase 3 cutover sẽ ship ADR-0028a (runbook companion) hoặc ADR-0029 (post-cutover lessons) tùy outcome. Khi bump ship, set Status → "superseded by ADR-XXXX" và link tới ADR mới ghi version pinned mới.
