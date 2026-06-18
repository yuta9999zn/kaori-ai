# ADR-0015 — Qwen-first LLM with pluggable vendor adapters

> **Status:** accepted
> **Date:** 2026-05-08
> **Deciders:** Nguyen Truong An
> **Related:** ADR-0004 (LLM Gateway service) · `docs/strategic/SAD_SKELETON_V2.md` Phần 17 + Phần 53 · K-3 / K-4 / K-5 · `docs/BACKLOG_V4.md` P1-S5 · P15-S9

## Context

Hai signal trái chiều:

1. **SAD master Phần 53 (ADR-006)** mặc định nói "vendor LLM (Anthropic / OpenAI) > self-hosted Phase 1-2" — lý do: chất lượng output, tránh GPU ops cho 1 dev.
2. **Anh chủ động thiết kế `llm-gateway` đã pluggable** — adapter pattern Anthropic + OpenAI + Ollama đã có; output_schema validation + tool calling chạy. Anh muốn **giữ Qwen 14B làm default** cho khách Vietnam (privacy + cost + latency local), và để vendor adapter làm tùy chọn opt-in qua consent.

Trade-off thực tế:
- **Quality:** vendor (Claude Sonnet 4.6 / GPT-4o) hơn Qwen 14B trên reasoning task khoảng 15-25 điểm benchmark. Nhưng pilot Olist + insight panel của em đang chạy Qwen, output dùng được — gap không phải dealbreaker Phase 1.
- **Cost:** Qwen self-host laptop pilot = $0/inference. Vendor batch ~ vài cent/insight × N tenants × M insights/ngày = phình theo MAU.
- **Privacy:** Qwen local = data không ra ngoài. Vendor = phải PII redaction (K-5) + DPA. Khách enterprise VN nhiều người prefer in-country.
- **Operational:** vendor có ưu thế khi peak load (no GPU constraint); Qwen local cần monitor VRAM + queue.
- **Architecture đã sẵn:** llm-gateway adapter pattern đã viết — không phải build mới gì.

## Decision

Chúng ta giữ **Qwen 2.5 14B local làm default cho mọi tenant**, **vendor adapter (Anthropic / OpenAI / Cohere / ...) là tùy chọn opt-in qua consent flag**, và `llm-gateway` tiếp tục là **vendor-agnostic adapter layer**:

1. **Default routing per task (no vendor consent):**
   - `task=insight/summarize/reasoning/coding/SQL/chat.*/embedding` → **Qwen 2.5 14B local** (chat) hoặc **BGE-M3 local** (embedding).
   - Mọi insight Phase 1 mặc định chạy Qwen.
2. **Vendor opt-in routing (tenant.consent_external=True + per-call flag):**
   - Khi tenant settings bật `consent_external` (giữ K-4) **VÀ** request đặt cờ `prefer_external=True` (per-task opt-in để tránh "luôn external" sau khi consent một lần) → router thử vendor primary, fallback Qwen on vendor error.
   - Nếu tenant `data_residency_strict=true` (flag mới Phase 1) → router **bỏ qua** mọi vendor, ép Qwen ngay cả khi `consent_external=True` cho tenant level. Nói cách khác: data residency override consent.
3. **Pluggable adapter contract (`llm-gateway` đã có):**
   - Adapter interface: `complete(messages, tools, output_schema, ...) → CompletionResponse`.
   - Phase 1 ship adapters: `OllamaAdapter` (Qwen + BGE-M3, default), `AnthropicAdapter` (Claude Sonnet 4.6), `OpenAIAdapter` (GPT-4o).
   - Phase 2 thêm: `CohereAdapter`, `GoogleVertexAdapter` khi customer yêu cầu.
   - Mỗi adapter có circuit breaker per provider + per-tenant token budget (NOV-CST-009 cost tracking).
4. **K-3 / K-4 / K-5 giữ nguyên ý nghĩa cũ** (không đảo):
   - K-3: mọi inference qua `llm-gateway`, không SDK trực tiếp.
   - K-4: external chỉ khi `consent_external=True`; Qwen default.
   - K-5: PII redaction trước external (Vietnamese-aware Phase 1.5 từ `PM-PII-010`).
5. **K-20 (LLM version pinning) áp dụng cho cả Qwen lẫn vendor** — workflow YAML ghi rõ `model: qwen2.5-14b-instruct-q4_K_M` `version: "2025-09-15"` hoặc `model: claude-sonnet-4-6` `version: "2026-01-01"`. Không upgrade ngầm.
6. **Drift detection** (P15-S9 P1-LLM-005) chạy trên cả Qwen (re-run baseline khi Ollama upgrade) và vendor (re-run khi Anthropic/OpenAI release).
7. **Output validation (`output_schema` Issue #3)** chạy đồng đều cho mọi adapter.

## Consequences

### Positive

- Khách phổ thông Vietnam mặc định privacy + cost-controlled.
- Anh không phải vận hành GPU cluster Phase 1 — Ollama trên FPT Cloud GPU instance khi cần scale.
- Khách enterprise muốn quality cao (consent + budget) chỉ cần bật flag → vendor activate.
- Adapter pluggable đã có → thêm provider mới Phase 2 chi phí thấp.
- Ít risk regression: pilot Olist đã chạy Qwen-first, Phase 1 v4 không đổi behaviour.

### Negative / accepted trade-offs

- Quality khách "free tier" (no consent) thấp hơn vendor — phải educate trong onboarding (Playbook 90-day Phần 7 AI Quality Framework).
- Qwen self-host cần monitor VRAM, queue, model load time. Phase 1 1 GPU instance chạy được 10-15 khách; Phase 2 cần GPU pool autoscale.
- Vendor adapter ít được test ở Phase 1 vì default routing không qua nó — risk silent bug khi khách bật consent. Mitigation: contract test riêng adapter mỗi sprint.
- LLM version pinning áp dụng cho Qwen có nghĩa: khi anh upgrade Ollama image, nếu workflow YAML chốt `qwen2.5-14b@v2025-09-15` thì image mới phải vẫn pull được model cũ. Cần Ollama Modelfile registry.

### Neutral / follow-ups

- Phase 1.5 evaluate: bật vendor adapter cho task `coding/SQL` mặc định không (vì Qwen yếu hơn rõ rệt task này)? Sẽ cần `prefer_external_for_task` map.
- Phase 2 đánh giá fine-tune Qwen với VN business data — khi MAU > 5K → break-even self-fine-tune.
- Phase 2 thêm hybrid LLM routing (P3-S32 cost-based routing).
- Data residency strict flag UI Phase 1: anh có thể không UI ngay; chỉ cần DB column + admin set thủ công cho khách regulated.

## Alternatives considered

- **Vendor-first default (SAD ADR-006 master).** Rejected: anh chốt giữ Qwen-first. Pilot đã chạy Qwen, không có lý do flip default Phase 1. Quality gap không phải dealbreaker.
- **Vendor-only, không Qwen.** Rejected: mất segment data residency; phụ thuộc 100% vendor outage.
- **Self-host Llama 3 fine-tune Phase 1.** Rejected: 1 dev không đủ thời gian + GPU cost.
- **Qwen-only, không adapter vendor.** Rejected: anh đã build adapter rồi → vứt là phí; khách enterprise cần upgrade path.

## References

- ADR-0004 (LLM Gateway service)
- `docs/strategic/SAD_SKELETON_V2.md` Phần 17 (LLM Integration Patterns)
- `docs/strategic/REASONING_LAYER.md` PART IV (RAG)
- CLAUDE.md §8 LLM Routing Logic + K-3/K-4/K-5/K-20
- Memory `project_pilot_deployment.md` (Qwen 7B default cho pilot 16GB laptop)
- Memory `project_v4_phase_a_landed.md` (Phase A docs landed 2026-05-08)
