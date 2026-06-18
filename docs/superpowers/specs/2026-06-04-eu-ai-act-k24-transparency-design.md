# EU AI Act Layer 3 — K-24 Transparency Disclosure (slice 2) — Design

> **Status:** design, pending approval → writing-plans
> **Date:** 2026-06-04
> **Part of:** EU AI Act Layer 3 (runtime enforcement), ADR-0041. Slice 2 of 4 (K-23 done PR #348, K-22 done PR #347).
> **Branch:** `feat/eu-ai-act-k24-transparency`, off `main` (independent — no Layer 2/K-23 dependency).

## Goal

Every generative AI output to an end-user carries a **machine-readable AI disclosure** (EU AI Act Art 50: people must be informed they are interacting with / receiving content from an AI), and the chatbot **self-identifies as AI**. Achieved at the single chokepoint all LLM calls pass through (K-3: llm-gateway) plus an explicit chat signal.

## Decisions (confirmed with anh, 2026-06-04)

1. **Attach point:** a `disclosure` field on llm-gateway `InferResponse` (the chokepoint). Universal coverage in one place — every downstream consumer (insight, decision, chat, workflow AI nodes) receives it.
2. **Chatbot self-identification:** `chat/agent.py` emits an SSE `disclosure` event at stream start (machine-readable; FE renders an "Đây là AI" badge). Not a system-prompt line (not machine-readable, LLM may ignore it).
3. **Not a GuardrailEngine rule:** a disclosure is metadata to attach, not a pass/fail check → it's a response field, not a guardrail rule.
4. **Out of scope (YAGNI):** OCR/embed responses (vectors / extracted text, not generative user-facing content); FE badge rendering (contract only); per-tenant notice customization; ai-orchestrator per-endpoint envelopes (they get it transitively via the field).

## Architecture

### `AiDisclosure` model (llm-gateway `models.py`)
```
class AiDisclosure(BaseModel):
    generated_by_ai: bool = True
    model:           str          # the concrete model_used
    method:          str          # 'internal' | 'external'
    notice_vi:       str          # human-readable VN notice
    notice_en:       str          # human-readable EN notice
```
A small pure builder `build_disclosure(model_used: str, method: str) -> AiDisclosure` (testable without I/O) produces it with the standard notices.

### `InferResponse.disclosure`
Add `disclosure: AiDisclosure` to `InferResponse` (models.py:180). Populate it at the single construction site (router.py:484) from `model_used` + `method`. Always present — there is no path where an AI completion leaves the gateway without it. (Tool-call returns also carry it — there is one `InferResponse(...)` construction in `infer`; verify no second construction site needs it.)

### Chat SSE disclosure event (`chat/agent.py`)
The chat agent (`run_agent`, SSE generator) `yield`s an `SSEEvent(type="disclosure", ...)` ONCE at the start of the stream, before the first `message`/tool event, carrying the disclosure payload (generated_by_ai + a notice). Shape matches the existing `SSEEvent` dataclass (confirm its fields in the plan; if it only has `type` + `text`, carry a JSON string or extend it minimally with an optional `data` field). The FE shows the AI badge on receipt.

## Data flow
LLM call → providers.invoke → completion → `InferResponse(..., disclosure=build_disclosure(model_used, method))` → caller (insight/decision/workflow node/chat agent). For chat specifically, the agent ALSO emits a `disclosure` SSE event up front so the human sees the AI badge immediately, independent of the per-completion field.

## Error handling
None special — `disclosure` is always-present metadata. `build_disclosure` is pure and total (never raises; unknown method still yields a valid disclosure with method passed through).

## Testing
- **Unit (pure):** `build_disclosure('qwen2.5:14b', 'internal')` → generated_by_ai True, model + method set, both notices non-empty; `'external'` method reflected.
- **Gateway:** `POST /v1/infer` response includes `disclosure` with `generated_by_ai=True` and `model == model_used`; present on both the plain-completion and tool-call return paths.
- **Chat:** `run_agent` yields exactly one `disclosure` SSE event, before the `message` event, on a normal turn.
- Regression: existing llm-gateway + chat tests still pass (the new field is additive with a default builder; existing assertions on InferResponse fields unaffected).

## Drift artefacts
- OpenAPI regen (`scripts/dump_openapi.py` — InferResponse schema gains `disclosure`). NOTE: llm-gateway isn't one of the two FastAPI services dumped by that script (pipeline + orchestrator) — confirm whether the gateway spec is dumped elsewhere; if the gateway has no committed OpenAPI artefact, none to refresh.
- No DB migration → no schema_snapshot change.
- No new gateway route → no RouteConfig change.
- FE types: if the FE consumes a generated InferResponse / chat-event type, add the `disclosure` shape; otherwise document the contract for the FE badge.

## Invariants
K-3 (disclosure attached at the gateway chokepoint — the K-3 enforcement point), K-20 (model identity surfaced in the disclosure). No K-1/K-12/K-14/K-21 surface here (no new tenant-scoped DB, no new error path).

## File structure (anticipated — finalised in plan)
- `services/llm-gateway/models.py` — `AiDisclosure` + `InferResponse.disclosure`
- `services/llm-gateway/disclosure.py` (or a function in models.py) — pure `build_disclosure(...)`
- `services/llm-gateway/router.py` — populate `disclosure` at the InferResponse return
- `services/llm-gateway/tests/...` — unit + gateway tests
- `services/ai-orchestrator/chat/agent.py` — emit the `disclosure` SSE event
- `services/ai-orchestrator/tests/...` — chat disclosure test
- drift: OpenAPI / FE types as applicable

## Open risk
The chat `SSEEvent` shape may only carry `type` + `text`; carrying structured disclosure data may need a minimal optional field on the dataclass (additive). The plan reads `SSEEvent` first and chooses the least-invasive carrier.
