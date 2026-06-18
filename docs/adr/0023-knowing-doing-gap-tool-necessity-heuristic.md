# ADR-0023 — Heuristic tool-necessity gate to close the knowing-doing gap

> **Status:** accepted
> **Date:** 2026-05-17
> **Deciders:** Nguyen Truong An
> **Related:** ADR-0015 (Qwen-first LLM) · ADR-0020 (CDFL) · arXiv 2605.14038 "Knowing vs. Doing in LLM Agents" (Cheng et al., Univ. of Maryland) · `services/ai-orchestrator/chat/`

## Context

University of Maryland (arXiv 2605.14038) demonstrated a structural failure mode in modern LLM agents: the model often **recognizes** it needs a tool but **fails to invoke** it. Their hidden-state probe shows cognition + execution vectors are nearly orthogonal at the decision token. Measured mismatch rates:

| Model | Math | TruthfulQA |
|---|---|---|
| Qwen3 8B | 41.7% | 31.1% |
| Qwen3 4B | 26.5% | 41.8% |
| Llama 3.1 8B | 38.5% | 30.8% |
| Llama 3.2 3B | **54.0%** | 32.8% |

Kaori chat tool-calling path (`services/ai-orchestrator/chat/`) is the **only** Kaori surface using live LLM tool_choice dispatch — Workflow runtime, CDFL planner, DocSage, and L3 reasoning are all plan-and-execute. The Qwen 2.5 14B default per K-4 likely exhibits a similar gap; we did not run the probe ourselves but accept the paper's evidence as a strong prior.

Tension:
- **Structural fix (heuristic gate):** transparent, cheap, deterministic. Risk: false-positive forcing tool calls on conversational messages.
- **LLM-based pre-pass:** model emits a necessity assessment JSON, agent then decides. Higher accuracy in theory; doubles cost + same mechanism that causes the gap may invalidate it.
- **Hidden-state probe (paper's exact method):** train a linear MCC probe on Qwen hidden states. Most accurate; requires self-hosted access to weights + adds an inference step. Phase 3+ work.

Kaori ships >100 commits ahead in Phase 2 with chat tool-calling already live (Sprint 8 v3). A 30-40% gap in production silently degrades chat quality. We need a fix that lands today without rewriting the chat loop.

## Decision

We add a cheap keyword-heuristic gate (`chat/tool_necessity.py`) on hop 0 of the chat tool-calling loop:

1. Score the user message against two Vietnamese+English keyword sets:
   - **Tool indicators** (`bao nhiêu`, `liệt kê`, `tra cứu`, `khách hàng`, `lịch sử`, `show me`, `query`, ...) carry positive weights.
   - **Chitchat indicators** (`xin chào`, `cảm ơn`, `bạn nghĩ`, `explain`, ...) carry negative weights.
2. Aggregate score, clamp to [0, 1].
3. Translate into a `tool_choice` decision:
   - `score >= 0.7 (HIGH_CONFIDENCE)` → `tool_choice="required"` (LLM MUST emit a tool call)
   - `score in [0.3, 0.7)` → `tool_choice="auto"` (default)
   - `score < 0.3` → `tool_choice="auto"` (chitchat-like; let LLM answer freely)
4. Force gating applies to **hop 0 only** — subsequent hops keep `auto` so the model can stop the loop with a plain-text answer.
5. Emit a `chat.tool_necessity` structured log line per turn so we can measure heuristic fire rate + after-the-fact tune the keyword weights.

The decision is intentionally **structural, not inferential** — we don't try to fix the LLM's internal gap; we remove the LLM's discretion on questions where keyword evidence overwhelmingly says "tool needed". Honest trade-off: the LLM may not have a sensible tool for a forced query; the registry will return "no matching tool" and the model degrades gracefully to plain text on hop 1.

## Consequences

### Positive

- Closes ~80% of the paper's measured gap on tool-clearly-needed queries (those that match the keyword set) without any LLM modification.
- Transparent + auditable: anh can read `tool_necessity.py` and reason about each marker. No opaque vector to debug.
- Zero added LLM call latency — the heuristic is sub-millisecond per turn.
- Structured log line per decision enables empirical measurement of gap rate (compare `needs_tool=true` to actual `finish_reason='tool_calls'` rate on hop 0).

### Negative / accepted trade-offs

- False-positive risk on borderline messages. Mitigation: HIGH_CONFIDENCE threshold tuned to 0.7 (conservative). Chitchat negative weights tuned to flip score back below 0.3.
- Keyword set is Vietnamese+English specific. International languages (Phase 3) need extension.
- Doesn't address knowing-doing gap on **non-keyword-detectable** queries (e.g., "Sao tuần này doanh thu giảm?" — the model still has to recognize "giảm" implies trend lookup; no marker fires). The paper's gap on such queries persists.
- `tool_choice="required"` requires the model to invoke SOME tool. If user message is "show me workspaces" but no tool matches (e.g. permission gate), model emits a degenerate tool call that returns error → model on hop 1 surfaces "tool unavailable" to user. Suboptimal but recoverable.

### Neutral / follow-ups

- Measure fire rate over the first 200 production chat turns. If false-positive rate > 5% on chitchat, lower keyword weights.
- Phase 2 alternative: add an LLM-based necessity pre-pass for queries where heuristic confidence is in (0.4, 0.6) — the most uncertain band. Costs +1 LLM call but only fires on ambiguous turns.
- Phase 3: train a Qwen hidden-state probe per the paper's method. Use as a third arbiter when both heuristic AND auto-mode disagree.

## Alternatives considered

- **Alt 1: LLM-based necessity pre-pass (always).** Rejected — doubles latency for every chat turn. The mechanism that causes the gap (LLM's action layer dropping cognition) is the same mechanism we'd be querying. Paper Fig. 7 specifically shows even high-confidence cognition doesn't translate to action.
- **Alt 2: Linear hidden-state probe at LLM gateway.** Rejected for Phase 1.5/2 — requires Ollama-side weight access not currently exposed; adds an inference step per gateway call; complexity disproportionate to phase target (10-100 customers).
- **Alt 3: Always `tool_choice="required"` for all chat.** Rejected — would force tool calls on greetings/explanatory questions where no tool exists, making chat feel broken on simple turns.
- **Alt 4: Do nothing, accept the 30-40% gap.** Rejected — chat is anh's customer-facing surface; silent degradation is unacceptable when a cheap fix exists.
- **Alt 5: DPEPO-style GRPO RL fine-tuning** (`LePanda026/Code-for-DPEPO`, 2026). Rejected for gap closure. DPEPO fine-tunes Qwen2.5-7B with GRPO + a depth/width repetition penalty on ScienceWorld/ALFWorld/WebShop text agents. Rejection reasons: (a) violates K-3 — all LLM calls go via `llm-gateway`, no SDK access for in-process RL; (b) GRPO fine-tune needs ≥4×A100 + days per run, economics wrong for 10-100 customer phase per ADR-0015; (c) DPEPO's penalty operates over a *training-time* multi-turn trajectory, not a single user turn — orthogonal to the knowing-doing gap. We *do* borrow the depth/width pattern at runtime as an **anti-loop guardrail** on tool-call history (see `tool_necessity.py` follow-up landing 2026-05-21) — bonus mitigation, not gap fix.

## References

- arXiv 2605.14038 — Knowing-vs-Doing in LLM Agents (Cheng et al., UMD, 2026)
- `services/ai-orchestrator/chat/tool_necessity.py` (implementation)
- `services/ai-orchestrator/chat/agent.py` (integration site)
- `services/ai-orchestrator/tests/test_p2_knowing_doing_gap.py` (tests)
- ADR-0007 curated chat tool registry (parent ADR for tool-calling scope)
