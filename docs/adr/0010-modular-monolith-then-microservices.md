# ADR-0010 — Modular monolith Phase 1, selective microservices Phase 2+

> **Status:** accepted
> **Date:** 2026-05-08
> **Deciders:** Nguyen Truong An
> **Related:** ADR-0001 (single-repo monolith) · `docs/strategic/SAD_SKELETON_V2.md` Phần 48 (ADR-001 trong SAD master) · `docs/BACKLOG_V4.md` Phase 1 / Phase 2 sprint plan

## Context

Feature Tree v4.0 chia roadmap 24 tháng thành 4 phase. Phase 1 (M1-M4, 8 sprint) ship MVP với core capabilities cho 10-15 khách đầu tiên. Phase 2 (M7-M12, 12 sprint) là "Differentiation" — đòi hỏi extract Workflow Engine và Process Mining thành microservices, service mesh, gRPC contracts (P2-S19/S20).

Hai luồng kéo:

1. **Phase 1 cần ship nhanh và refactor rẻ.** Một dev + một AI assistant không thể vận hành 6+ deploy pipeline, 6+ DB connection pool, 6+ helm chart. Internal mocking giữa service tốn cognitive overhead.
2. **Phase 2 cần scale + isolate failure domain.** Process Mining chạy tốn CPU (sequence mining algorithms); Temporal worker cần persistent connection pool tới Temporal cluster; cả hai sẽ throttle nếu nhồi chung pod với reasoning service.

ADR-0001 đã chốt single-repo. Câu hỏi mới: trong repo đó, các "service" Phase 1 chạy như **modular monolith** (1 process, internal calls) hay như **separate processes** (HTTP/gRPC giữa services)?

Thực tế hiện tại: 6 service đã chạy tách process (api-gateway/auth/data-pipeline/ai-orchestrator/llm-gateway/notification) qua docker-compose. Đây không phải monolith thuần — gọi là "process-per-service monolith" thì đúng hơn. Phần `services/ai-orchestrator/` đang gánh 3 layer (L3 Reasoning + L4 Workflow + L4.5 Org Intel) — chính nó là phần cần modularize trước.

## Decision

Phase 1 + 1.5 chúng ta giữ **6 process-level service** hiện tại nhưng **modularize INTERNAL** trong từng service:

- `services/data-pipeline/` → `ingestion/` · `data_plane/` · `quality/` (Pipeline Unified 12-stage logical split, không tách process).
- `services/ai-orchestrator/` → `reasoning/` · `workflow_runtime/` · `org_intel/{process_mining, adoption, economics}/` — vẫn 1 process, 1 deploy, nhưng internal API rõ ràng (mỗi module có `__init__.py` export contract, không cross-import private).
- `services/{process-mining, adoption-intel, economics, workflow-engine}/` skeleton folder + service.yaml CHƯA chạy — placeholder cho Phase 2 extract.

Phase 2 Sprint P2-S19 + P2-S20 mới extract `workflow-engine` và `process-mining` thành standalone process + service mesh (Istio/Linkerd). Khi extract, internal API của module hiện hữu trở thành contract gRPC/HTTP.

Phase 3 mới full microservices (extract reasoning + adoption + economics).

## Consequences

### Positive

- Anh code Phase 1 không phải maintain 4 service mới (process-mining, adoption-intel, economics, workflow-engine) — chỉ thêm folder con trong ai-orchestrator. Build/test/deploy time không phình.
- Internal API rõ ràng từ đầu → khi extract Phase 2, không phải refactor toàn bộ; chỉ thay `from .reasoning import ...` thành `httpx.post(...)`.
- 1 codepath debugging trong Phase 1 (Sentry traces 1 service); Phase 2 mới chấp nhận distributed tracing complexity.
- Pilot Olist trên `main` không bị regression — vẫn 6 process, vẫn docker-compose.

### Negative / accepted trade-offs

- Một service (`ai-orchestrator`) phình to (~3 layer) → memory footprint cao hơn microservices riêng. Chấp nhận đến Phase 1.5 sprint 9 (eval lại).
- Không scale process-mining riêng — nếu mining session chạy vào giờ cao điểm, có thể đè reasoning latency. Mitigation: Phase 1 cap 1 mining session đồng thời / tenant; Phase 2 extract.
- Internal modules có thể bị "cross-import lén" nếu dev vội → cần lint rule (`flake8-banned-imports`) hoặc code review gate.

### Neutral / follow-ups

- Trigger extract sớm hơn Phase 2: nếu `ai-orchestrator` peak memory > 4 GB, OR p95 latency tăng > 30% so với Phase 1 baseline.
- Khi extract: Phase 2 ADR mới ghi rõ contract gRPC + retry policy + circuit breaker per service.

## Alternatives considered

- **Full microservices Phase 1 (8+ service mới ngay).** Rejected — anh là dev solo, scope Phase 1 đã 514 features, không đủ headroom cho 8 deploy pipeline.
- **Pure monolith 1 process Phase 1.** Rejected — 6 process hiện tại đã chạy ổn, gộp lại = phá pilot Olist + trộn Java/Python = phức tạp hơn.
- **Modulith với strict module boundaries dùng Python `__init__.py` + `__all__`.** Đã chọn — đúng level tradeoff cho 1 dev.

## References

- `docs/strategic/SAD_SKELETON_V2.md` PART XIV Roadmap (Phase 1 → Phase 3 evolution path)
- `docs/strategic/WORKFLOW_SYSTEM.md` Phần 0.2 "Why Workflow System v2.0"
- ADR-0001 (single repo)

## Update 2026-05-18 — Phase 2 extraction deferred

Anh decided to defer P2-S19 (Workflow Engine extraction) and P2-S20 (Process Mining + service mesh) to **Phase 3** alongside multi-region deployment (P3-S26+). Rationale:

- Phase 2 target = 100 customers. Modular monolith (`ai-orchestrator`) provides sufficient throughput at this scale; no acceptance-criteria forces extraction.
- The Phase B-2 internal restructure (commits `783a9ac` → `5b7c153`, Phase 1 sprints) already established clean module boundaries inside `services/ai-orchestrator/{reasoning,workflow_runtime,org_intel}/` — Phase 3 extraction becomes a file move, not a logic rewrite.
- Service mesh (Istio/Linkerd) + chaos engineering (REL-025) only pay off when there ARE distributed services to coordinate + break. Investing in them at 100-customer monolith scale = premature.
- K8s FPT Cloud cluster provisioning (originally P15-S9 Task K) is also deferred — extracting services without the K8s host platform doubles the deployment-complexity surface area.

The original "trigger criteria" in this ADR (peak memory > 4 GB, p95 +30%) still applies and stays the early-warning signal for moving the trigger forward inside Phase 3.
