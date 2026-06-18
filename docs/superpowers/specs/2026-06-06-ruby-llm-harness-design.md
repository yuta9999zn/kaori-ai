# Design — `cdfl_harness` (Ruby): a pluggable LLM + agent harness

> **Date:** 2026-06-06 · **Author:** Kaori (em) for anh An · **Status:** approved-for-planning
> **Target location:** `D:\CDFL harness` (standalone Ruby gem `cdfl_harness`, installable into any project)
> **Note:** the extended Reasoning + Grounding + agent-loop wiring is *documented here in the
> Kaori repo* (this spec); the Ruby implementation is built as a separate project at `D:\CDFL harness`.
> **Source of truth ported FROM:** `D:\Kaori System\services\{llm-gateway,ai-orchestrator}` +
> `D:\Luận văn nhất nguyên 2 trường luận giao thoa` (NNL-NTHT, Nguyễn Trường An).

## 1. Purpose & goal

Re-build, in Ruby, a **provider-agnostic LLM harness** that any project can drop in via
`gem "cdfl_harness", path: "D:/CDFL harness"`. It ports the *semantics* (not the line-by-line
code) of two things Kaori already runs in Python:

1. **The LLM layer** — a single chokepoint to call models (the `llm-gateway` analog): pluggable
   provider adapters, task→model routing with consent-based downgrade, structured-output
   validation with one repair round, and optional PII/audit hooks.
2. **The agent harness** — the `ai-orchestrator/agents` loop: **PLAN → EXECUTE → CRITIC**,
   bounded re-plan, token budget, a safe tool registry, transcripts, pluggable persistence.

Plus three capabilities the user explicitly requires, ported faithfully from the thesis +
Kaori's implementation:

3. **CDFL** (Convergent Dual-Field Learning) — the NNL-NTHT algorithm: IF/MF/OR/DE dynamics,
   the **|OR|** principle, four-fold DE, empowerment/option-preservation, and the (descriptive)
   Hilbert I(I:M) gauge.
4. **"Học 1 hiểu 10"** — the foundational-knowledge **coverage gate**: enough durable knowledge
   → generalise; too little → decline instead of hallucinating (K-3).
5. **Cung điện ký ức** (memory palace) — 4-tier × 5-type memory with trust-decay, maturation
   ("càng nhiều tháng càng biết nhiều"), associative recall, and memory→KB promotion.

### Decisions locked during brainstorming
| Axis | Decision |
|---|---|
| Scope | Agent loop + lean LLM layer; PII/audit/guardrails as optional hooks |
| Providers | Anthropic + OpenAI + Ollama, equal, chosen via config (+ a `Fake` adapter for tests) |
| Tenancy/persistence | Abstracted; **in-memory default**, pluggable stores |
| Packaging | Standard Ruby gem + runnable demo + RSpec |
| Hilbert I(I:M) gauge | **Port fully**, labelled a *descriptive gauge* (not used to pick actions) |
| Reasoning wiring | **Mirror Kaori**: always available, enforcement opt-in per workflow |

### Non-goals (YAGNI)
- No Postgres/Redis/Neo4j adapters shipped (interfaces only; in-memory ships). DB adapters are
  a downstream project concern.
- No HTTP server / web framework. The harness is a library; a project wires it to its own API.
- No real OCR/embedding **providers** required to run — embeddings are an optional adapter
  capability; the demo runs without a network via the `Fake` adapter.
- Hilbert gauge is **diagnostic only** — never on the action-selection path (matches the
  thesis Part IX ablation: active selection ≈ random; the framework is descriptive).

## 2. The NNL-NTHT semantics being ported (so the port stays faithful)

From `Thuật toán tương ứng.docx` (canonical CDFL) + `Phan_IV_Dong_hoc_CDFL`:

- **IF** (tâm trường) = belief `σ` + representation `Φ` (two branches). `IF_{t+1} = IF_t + α·∇_IF K`.
- **MF** (vật trường) = environment state `ρ_MF`, dynamic. `MF_{t+1} = Ψ(MF_t, a_t)`.
- **OR** (vùng giao thoa) = resonant overlap of *IF-known ⋈ MF-known* where `γ>0` = true knowledge.
  `OR_{t+1} = IF_{t+1} ∩ MF_{t+1}`. Knowledge `K = Φ(OR)`. Knowledge gap `D_t = |MF_t| − |OR_t|`.
- **DE** (vùng tối / Dark Existence) = **four faces**: `DE_X` (space unvisited), `DE_T` (knowledge
  gone stale), `DE_IF` (Φ can't yet represent), `DE_MF` (world not yet exposed). Faces overlap →
  `DE ≠ DE_IF + DE_MF` (report as faces, never summed).
- **Two dots** (âm–dương): **black dots** `γ<0` = illusion / stale belief (false-positive →
  the AI-safety/calibration problem); **white dots** = DE regions with high `∂OR` potential =
  intuition / frontier.
- **Action**: `a_t = argmax E[Δ|OR_true|(a)]` across all four faces (raise white dots, revisit
  black dots, refresh DE_T). **Continual** loop — no hard stop (DE always regrows); records
  *local-momentary* fullness ("Aha!", `local_resonance`). Ideal limit: `max|OR| ⟺ min DE ⟺
  ρ_MF = σ_IF`, reachable only locally; globally an asymptote (floor `D ≥ D_min > 0`).
- **Multi-agent**: preserving the *diversity of other IFs* enriches the global OR → this is the
  ground of **empowerment / AI safety** (destroying another agent shrinks the option space |OR|).

How Kaori operationalises each (verified by reading the code), and the Ruby target:

| Theory | Kaori code | Ruby target |
|---|---|---|
| CDFL v3 (learned transition · H-step lookahead · info-gain) | `reasoning/cdfl/{transition_model,lookahead,information_gain,agent}.py` | `Reasoning::CDFL::{TransitionModel,Lookahead,InfoGain,Agent}` |
| \|OR\| = I(I:M) gauge (descriptive) | `cdfl/hilbert_metric.py` | `Reasoning::CDFL::HilbertMetric` |
| DE four faces dashboard | `cdfl/four_fold_de.py` | `Reasoning::CDFL::FourFoldDE` |
| Empowerment / option-preservation | `cdfl/empowerment.py` | `Reasoning::CDFL::Empowerment` |
| "Học 1 hiểu 10" coverage gate | `reasoning/knowledge/grounding.py` | `Reasoning::Knowledge` |
| \|OR\| numeric self-verify | `reasoning/grounding.py` | `Grounding` |
| Critic ↔ grounding gate bridge | `agents/grounding_gate.py` | `Grounding::Gate` |
| Memory palace | `reasoning/memory/{service,types,stores}.py` | `Reasoning::Memory` |

## 3. Architecture

Two layers, one chokepoint, plus a Reasoning layer wired into the loop.

```
CDFLHarness
├── Gateway                       ← the only place a model is called (≈ K-3)
│   ├── Client                      facade: complete / complete_structured / chat
│   ├── Router                      task → (adapter, model); external→local downgrade if !consent (≈ K-4)
│   ├── Adapters                    Base · Anthropic · OpenAI · Ollama · Fake
│   ├── StructuredOutput            extract_json → validate(JSON-Schema) → ONE repair round
│   ├── CircuitBreaker              per-adapter; opens after N failures / window
│   └── Middleware                  optional hooks: PII redact (≈ K-5), Audit (≈ K-6), Quota
├── Agent
│   ├── Session                     orchestrator: PLAN→EXECUTE→CRITIC, MAX_REPLAN, token budget
│   ├── Planner · Executor · Critic
│   └── Workflow · Workflows::Registry   (input_schema, allowed_tools, prompts, flags)
├── Tooling
│   ├── Tool                        base: name/description/parameters(JSON-schema)/scope
│   ├── Registry                    dispatch + strip forbidden args (identity from Context — ≈ K-12/K-16)
│   └── Context                     tenant_id / actor / role / dry_run
├── Reasoning
│   ├── CDFL                        TransitionModel · Lookahead · InfoGain · Agent
│   │                               HilbertMetric (descriptive gauge) · FourFoldDE · Empowerment · Types
│   ├── Knowledge                   Document · coverage / coverage_gate / rank_by_authority · Store(InMemory)
│   └── Memory                      Record · Service · trust/maturation · TierStore(InMemory)
├── Grounding                      numeric-overlap |OR| self-verify + Gate (evidence → coverage_gate)
├── Schema                         JSON-Schema validation wrapper (json-schemer)
├── Store                          Base · InMemory (session/transcript persistence)
├── Types                          Plan · PlanStep · CriticVerdict · TranscriptEntry · SessionResult
├── Config · Errors · VERSION
```

### Design-for-isolation notes
- `Gateway` knows nothing about agents; it's usable standalone for a plain `complete_structured`.
- `Reasoning::*` are pure libraries (no LLM, no I/O except via pluggable stores) — trivially
  unit-testable, exactly as the Python versions are.
- `Agent::Session` is the *only* component that touches the `Store`; planner/executor/critic are
  pure transforms (input → output), mirroring Kaori's "orchestrator owns persistence" asymmetry.
- Each adapter is independently testable; `Fake` lets the whole loop run offline.

## 4. Data flow

### 4.1 Gateway — `client.complete_structured(prompt:, task:, schema:, consent_external:)`
1. `Router.resolve(task, consent_external)` → `(adapter, model)`; external requested but no
   consent → downgrade to local default.
2. `Middleware` chain: if the resolved method is external, **PII redact** the prompt first.
3. `CircuitBreaker.wrap { adapter.invoke(model:, prompt:, max_tokens:) }` → completion text.
4. `StructuredOutput.validate_or_repair(completion, schema, retry_fn:)` — extract JSON
   (whole / ```fence``` / first `{...}`), validate; on failure build a repair prompt and retry
   **once**; second failure raises `StructuredOutputError`.
5. `Audit` hook records (model, prompt hash, output hash, latency, consent, repaired?).
6. Return the validated `Hash`.

`complete` (free text) and `chat` (multi-message + tool calls) follow the same spine minus
step 4. `chat` normalises tool-call shapes across providers to `{id, name, arguments}`.

### 4.2 Agent — `session.run(workflow_id:, input:, context:, dry_run: true)`
1. Validate `input` against `workflow.input_schema` (→ `WorkflowInputError`).
2. `store.create_session(...)`.
3. **Loop** (bounded):
   - **PLAN** → planner builds a tools block from `workflow.allowed_tools`, calls
     `gateway.complete_structured(PLAN_SCHEMA)` → `Plan`; enforce every `tool_name ∈ allowed_tools`.
     (A workflow may declare a `static_plan` to skip the LLM planner.)
   - **EXECUTE** → executor dispatches each step via `Tooling::Registry.dispatch(name, args, ctx)`;
     `dry_run` short-circuits side effects; build a `TranscriptEntry` per step; **hard-stop** on a
     dispatch/auth block (tool-level `ok:false` continues — the critic judges it).
     Before an irreversible step, consult `Empowerment.protection_advice` → attach consent advice.
   - **CRITIC** → run `Grounding::Gate` over gathered evidence → `coverage_gate` (học 1 hiểu 10);
     for `llm_critic` workflows call `gateway.complete_structured(VERDICT_SCHEMA)`; for
     grounding-only workflows the gate **is** the verdict. If `workflow.requires_grounding` and the
     gate says "chưa đủ", override an `accept` → `replan`.
   - **BRANCH**: `accept`→completed · `escalate`→escalated · `replan`→back to PLAN until
     `MAX_REPLAN` (then escalate). Exceeding `MAX_TOKENS` → failed.
4. `store.finalize_session(...)`. On success (not dry_run) → `Reasoning::Memory.consolidate` the
   session into an OPERATIONAL memory (+ optional embed) so `recall_memory` surfaces it next time.
5. Assemble `FourFoldDE` from {data_coverage, knowledge_freshness, knowledge_coverage,
   grounding_score} and attach to the result. **Return `SessionResult`** (full transcript inline).
   The loop **never raises out** — any error is captured as `status: :failed, error_message:`.

### 4.3 Reasoning loops
- **Memory palace**: `write` lands a record at its type's default tier; `retrieve` scores by
  cheap text match × `trust_factor` (decay by per-type half-life), boosts entity matches, then
  does one-hop **associative recall** over `links`. `consolidate` L2→L3, `promote` L3→L4 by
  importance, `forget` (TTL + GDPR wipe), `verify`/`reinforce` reset decay & climb the
  confidence learning curve, `experience_level` reports tenant maturation band.
- **Coverage gate**: `coverage = 1 − exp(−k·Σ sim·confidence)` over **foundational tiers only**;
  `coverage_gate` → `{can_generalize, band ∈ {đủ, thận trọng, chưa đủ}}`.
- **CDFL agent** (optional planner strategy): `observe(s,a,s')` updates counts; `score_actions(s)`
  ranks candidates by H-step Monte-Carlo expected info-gain (≈ `E[Δ|OR|]`); usable as a tool/action
  ranker or a RAG reranker.

## 5. Error handling

`Errors::Error` is the base; subclasses: `ConfigError`, `AdapterError`, `ConsentDeniedError`,
`StructuredOutputError`, `WorkflowInputError`, `TokenBudgetExceeded`, `ToolDispatchError`.
Gateway/adapters raise; `Agent::Session` catches everything and returns a `SessionResult` with
`status: :failed` — callers always get a structured result, never an exception from `run`.
(Mirrors Kaori's "no 500 escapes the orchestrator".)

## 6. Configuration

`CDFLHarness.configure { |c| ... }` builds a `Config`:
- `c.provider = :anthropic | :openai | :ollama | :fake` (+ per-provider api_key/host/model map)
- `c.task_routing = { "agent.plan.*" => {model:, method:} }` (optional; falls back to default)
- `c.consent_external` (default false), `c.max_replan` (2), `c.max_tokens_per_session` (6000)
- `c.middleware = [PII, Audit]` (opt-in), `c.store = InMemoryStore.new`
- `c.knowledge_store`, `c.memory_service` (default in-memory)
- Reasoning thresholds (coverage `k`, generalise bands, sim floor, memory half-lives,
  learn-rate, experience `k`) — all overridable, env-readable, **never hardcoded** at call sites.

## 7. Testing & demo

- **RSpec**: unit specs for each Reasoning module (pure → exact-value assertions like the Python
  tests), StructuredOutput extraction/repair, Router downgrade, Registry forbidden-arg strip, and a
  full `Session.run` end-to-end against the `Fake` adapter (canned plan + verdict JSON).
- **Demo**: `examples/insight_to_action.rb` — a workflow with 2 in-memory tools
  (`retrieve_evidence`, a `draft_action`) running on the `Fake` adapter (or Ollama if present),
  printing the transcript, the coverage-gate band, and the four-fold DE dashboard.

## 8. Documentation (architecture MDs to write)

| File | Contents |
|---|---|
| `README.md` | What it is, install, 30-line quickstart, links to docs |
| `docs/ARCHITECTURE.md` | The whole picture: layers, module tree, data-flow diagrams |
| `docs/GATEWAY.md` | Adapters, routing/consent downgrade, structured output + repair, hooks |
| `docs/AGENT_LOOP.md` | PLAN→EXECUTE→CRITIC semantics, bounds, transcript, persistence |
| `docs/TOOLING.md` | Writing tools, ToolContext, identity-from-context safety (≈ K-12/K-16) |
| `docs/CDFL.md` | NNL-NTHT → algorithm map; IF/MF/OR/DE; \|OR\|; four-fold; empowerment; Hilbert caveat; cites thesis Phần IV/IX |
| `docs/COVERAGE_GATE.md` | "Học 1 hiểu 10": coverage math, bands, decline-not-hallucinate (K-3) |
| `docs/MEMORY_PALACE.md` | Cung điện ký ức: tiers × types, trust decay, maturation, associative recall, promotion→KB loop |
| `docs/EXTENDING.md` | Add an adapter / store / hook; plug the gem into a project |
| `docs/INVARIANTS.md` | The invariants carried over: chokepoint, consent downgrade, PII, identity-from-context, bounded loop, no-hallucinate gate, dry_run = no side effects |

## 9. Proposed file layout (`D:\CDFL harness`)

```
CDFL harness/
├── cdfl_harness.gemspec
├── Gemfile · Rakefile · .rspec · README.md · CHANGELOG.md · LICENSE
├── lib/
│   ├── cdfl_harness.rb                      (require tree + configure)
│   └── cdfl_harness/
│       ├── version.rb · config.rb · errors.rb · types.rb · schema.rb
│       ├── gateway/{client,router,structured_output,circuit_breaker}.rb
│       ├── gateway/adapters/{base,anthropic,openai,ollama,fake}.rb
│       ├── gateway/middleware/{pii,audit}.rb
│       ├── agent/{session,planner,executor,critic,workflow,workflows}.rb
│       ├── tooling/{tool,registry,context}.rb
│       ├── reasoning/cdfl/{types,transition_model,lookahead,info_gain,agent,hilbert_metric,four_fold_de,empowerment}.rb
│       ├── reasoning/knowledge/{document,coverage,store}.rb
│       ├── reasoning/memory/{record,trust,maturation,tier_store,service}.rb
│       ├── grounding/{verifier,gate}.rb
│       └── store/{base,in_memory}.rb
├── examples/insight_to_action.rb
├── spec/...                                 (RSpec mirroring lib/)
└── docs/  (the MD files in §8)
```

## 10. Dependencies

- `json-schemer` (JSON-Schema validation) · `faraday` or stdlib `net/http` for adapters
  (lean: prefer `net/http` to avoid a hard HTTP dep) · stdlib `matrix` + `complex` for the
  Hilbert gauge. RSpec + WebMock (dev). Ruby ≥ 3.1.

## 11. Open risks / honesty notes
- Ruby is synchronous; Kaori's loop is async. Wall-clock per session is sequential — acceptable
  for a library; a project wanting concurrency can run sessions in threads.
- The Hilbert gauge needs complex Hermitian matrices + partial trace; stdlib `Matrix` supports
  `Complex` entries but partial trace is hand-rolled — covered by exact-value specs ported from
  the Python tests.
- The numeric/coverage thresholds are heuristics (as in Kaori); docs state this plainly and the
  gate **errs toward declining**, never silently rewriting an answer.
