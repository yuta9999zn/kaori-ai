# CDFL Integration — NNL-NTHT × Kaori

> **Version:** 1.0 | **Created:** 2026-05-15 | **Sprint:** P15-S11 (CDFL port, Tuần 1 Build Week prep)
> **Source theory:** `D:\Luận văn nhất nguyên 2 trường luận giao thoa\` (Nguyễn Trường An)
> **Source code (port reference):** `_cdfl_extract\v8\REPORT_V8.md` + `Thuật toán tương ứng.docx`
> **Kaori module:** `services/ai-orchestrator/reasoning/cdfl/`
> **Test count:** 37/37 pass (676 total ai-orchestrator suite)

---

## 1. Tại sao CDFL trong Kaori?

CDFL (Convergent Dual-Field Learning) là thuật toán **exploration** xuất phát từ luận văn NNL-NTHT của anh, được benchmark qua 8 phase. Khác với RL classic (tối đa hoá reward), CDFL tối đa hoá **|OR|** = vùng giao thoa giữa Internal Field (mô hình nội tại của agent) và Manifest Field (state thật của environment).

Triết lý: **agent học để hiểu environment, không phải để đạt goal**.

Đặc tính phù hợp với customer Kaori:
- **Bounded compute** — SME Việt thường có dataset hạn chế, không có infra GPU lớn → CDFL niche khớp.
- **Tabular** — Process Mining event_type là tabular tự nhiên (5-15 distinct event types per process).
- **Scaling advantage** — emergent ≥ 900 states (+11.5% → +15.8% ở 2500 states). Khi customer có vài nghìn customer × vài chục event_type → đúng niche.

---

## 2. Mapping 3 component → 3 chức năng Kaori

CDFL có 3 component validated qua ablation (REPORT_V8.md §1):

| Component | Ablation drop | Map vào Kaori function |
|---|---|---|
| **Learned transition model P(s'\|s,a)** | **−31.6pp** (CRITICAL) | **Process Mining** — direct-follow count đã có sẵn ở `HeuristicMiner`, em viết adapter `TransitionModel.from_direct_follows()` |
| **H-step Monte Carlo lookahead** | −1.8pp đơn lẻ, +4pp combined | **Workflow planner** — đề xuất top-K next-action sequence cho doanh nghiệp |
| **Information gain (novelty × uncertainty)** | <2pp đơn lẻ | **RAG re-ranking + insight prioritisation** — re-rank PageIndex candidates khi corpus lớn |

Module layout:

```
services/ai-orchestrator/reasoning/cdfl/
├── __init__.py            # public API: CDFLAgent, TransitionModel, IGScorer, LookaheadPlanner
├── types.py               # State, Action, Transition, ActionScore, RolloutResult
├── transition_model.py    # TransitionModel + from_direct_follows() adapter
├── information_gain.py    # IGScorer: novelty(s) + λ·uncertainty(s,a)
├── lookahead.py           # LookaheadPlanner H-step Monte Carlo
└── agent.py               # CDFLAgent (compat với CDFLv3 interface) + factory
```

Math (REPORT_V8.md §6):

    novelty(s)        = 1 / sqrt(N(s) + 1)
    uncertainty(s,a)  = 1 / sqrt(n(s,a) + 1)
    IG(s,a)           = novelty(s') + λ · uncertainty(s,a)
    π* = argmax_π E_τ[ Σ_{t=0..H} novelty(s_t) + λ · uncertainty(s_{t-1}, a_t) ]

---

## 3. Chức năng 1 — Process Mining → CDFL → Workflow planning

### Flow tổng

```
Bronze event log (Gmail/Outlook/Calendar/CSV upload)
    ↓ HeuristicMiner.mine()
MinedWorkflow (direct_follows: dict[(from,to), count])
    ↓ TransitionModel.from_direct_follows()
TransitionModel (learned P(s'|s,a))
    ↓ CDFLAgent(action_space=event_types, ...).score_actions(state)
list[ActionScore] (top-K next-event recommendation)
    ↓ Workflow YAML emitter
Temporal workflow (K-17 side_effect_class declared)
    ↓ Execute (TEMPORAL_ENABLE_WORKER=true)
Insight: "doanh nghiệp đang vận hành như nào + nên làm gì"
```

### API contract (cần build trong Tuần 4-5)

**POST `/api/v1/process-mining/mine`** — mới
```json
// Request
{ "session_id": "uuid", "min_frequency": 2 }

// Response — body
{
  "mined_workflow": {
    "direct_follows": { "[\"login\",\"browse\"]": 100, "[\"browse\",\"checkout\"]": 40 },
    "event_counts": { "login": 105, "browse": 100, "checkout": 40 },
    "avg_durations": { "[\"login\",\"browse\"]": 12.5 },
    "case_count": 100
  }
}
```

**POST `/api/v1/cdfl/plan-next-action`** — mới
```json
// Request
{
  "session_id": "uuid",
  "current_state": "browse",
  "horizon": 5,
  "num_rollouts": 6,
  "top_k": 3
}

// Response
{
  "current_state": "browse",
  "top_actions": [
    { "action": "checkout", "mean_score": 1.42, "best_score": 1.91, "visit_proxy": 40 },
    { "action": "view_product_detail", "mean_score": 1.28, "best_score": 1.67, "visit_proxy": 60 },
    { "action": "exit", "mean_score": 0.83, "best_score": 1.12, "visit_proxy": 30 }
  ],
  "trajectory_explanation": "..."
}
```

**POST `/api/v1/workflow/from-cdfl-plan`** — mới (Tuần 5)
```json
// Request: top-1 action sequence từ CDFL → emit Temporal workflow YAML
// Response: workflow_id sẵn sàng execute
```

### Test fixture cho Build Week demo

`tests/fixtures/demo_phuc_long.py` — fake company "Cà phê Phúc Long":
- 200 customer × 60 day × 3 process variant
- Event types: `view_menu`, `add_cart`, `checkout`, `pay_card`, `pay_cash`, `complete`, `abandon`, `refund`
- 2500+ events → đủ lớn cho CDFL scaling advantage hiển thị

---

## 4. Chức năng 2 — RAG re-ranking với CDFL Information Gain

Khi corpus document lớn (study 1.txt: customer có vài nghìn file), PageIndex retriever trả top-K candidate chunk. Vấn đề: chunks similar về semantics (cosine cao) nhưng không cùng information gain.

### Flow

```
Query → PageIndex top-K (cosine semantic)
    ↓ IGScorer.score(current_chunk, candidate_chunk)
    novelty(candidate) + λ · uncertainty(current, candidate)
    ↓ re-rank by IG
Top-K' presented to LLM context
```

State trong context này:
- `state` = current chunk ID đang được agent "đứng tại"
- `action` = chuyển sang chunk khác (citation jump)
- `next_state` = chunk đích

`TransitionModel` được "seed" từ:
- Click-through log của user trên UI Insight Detail (chunk → chunk navigation)
- Co-occurrence ngữ cảnh (2 chunk được cite cùng trong 1 answer)

Khi tenant mới chưa có log: dùng `freeze_model=True` + pure novelty (uniform uncertainty).

### API contract

**POST `/api/v1/rag/answer?ranking=cdfl_ig`** — extend endpoint hiện có
```json
// Request thêm query param
{ "query_text": "...", "tenant_id": "...", "top_k": 5 }

// Response: citation list được re-ranked bởi IG thay vì raw cosine
```

Endpoint base đã có ở `routers/rag.py` từ P15-S10 D6. Em chỉ wire IGScorer vào retriever output.

---

## 5. Build Week 8/7 — Demo positioning (HONEST)

Theo §7 "Final position statement" của REPORT_V8.md, em đề xuất 3 slide CDFL trong thuyết trình:

### Slide 1 — Theory backbone
> "CDFL = Convergent Dual-Field Learning từ luận văn NNL-NTHT (Nguyễn Trường An, 2026). Agent học cách HIỂU môi trường thay vì tối đa hoá phần thưởng — phù hợp khi customer cần biết 'doanh nghiệp đang vận hành như nào' chứ không phải 'làm sao tối ưu KPI X'."
>
> 1 phương trình: `π* = argmax_π E_τ[Σ novelty(s) + λ·uncertainty(s,a)]`

### Slide 2 — Empirical foundation
> "Validated qua 8 phase benchmark trên gridworld (400 → 2500 states). Scaling advantage: +11.5% ở 900 states → +15.8% ở 2500 states vs count-based exploration."
>
> Hình: `fig_scaling_story.png` từ luận văn.

### Slide 3 — Honest niche statement
> "CDFL **không phải** SOTA RL replacement. Chưa validate vs full neural network methods (PPO/RND/ICM). Niche xác định: **bounded compute, tabular environments, scaling envs**. Đây chính xác là tình huống của SME Việt — dữ liệu rời rạc (event_type), compute hạn chế, scale tăng dần."

→ Tránh overclaim. Giữ uy tín học thuật. Position là "novel ranking layer từ founder's research" thay vì "AI breakthrough".

---

## 6. Implementation status

### ✅ Tuần 1 (15-22/5/2026) — COMPLETED

| File | Status | Tests |
|---|---|---|
| `reasoning/cdfl/__init__.py` | ✅ | — |
| `reasoning/cdfl/types.py` | ✅ | — |
| `reasoning/cdfl/transition_model.py` | ✅ | 10/10 |
| `reasoning/cdfl/information_gain.py` | ✅ | 7/7 |
| `reasoning/cdfl/lookahead.py` | ✅ | 10/10 |
| `reasoning/cdfl/agent.py` + factory | ✅ | 10/10 |
| `docs/strategic/CDFL_INTEGRATION.md` (this doc) | ✅ | — |
| ai-orchestrator full regression | ✅ | 676/676 (was 639, +37) |

### ⏳ Tuần 2-3 (22/5 → 5/6) — UNBLOCK

- Wrap PageIndex thật (PyPI `pageindex==0.2.8`) → bỏ stub leak
- GitHub Actions budget reset 1/6 → push PR #179 → merge S9+S10

### ⏳ Tuần 4-6 (5-26/6) — BUILD 2 FUNCTIONS

- `POST /api/v1/process-mining/mine` endpoint (gap I2)
- `POST /api/v1/cdfl/plan-next-action` endpoint (mới)
- `POST /api/v1/workflow/from-cdfl-plan` (Workflow YAML emitter)
- Temporal cluster docker-compose dev + enable worker
- Test fixture `demo_phuc_long.py` (2500+ events)
- `/api/v1/rag/answer?ranking=cdfl_ig` query param
- E2E test: mine → plan → execute → insight

### ⏳ Tuần 7-8 (26/6 → 8/7) — UI WIRE + DEMO

- 7 màn flagship wire BE
- Demo script 8-12 phút
- Backup video
- 2 dry-run

---

## 7. Module API quick reference

```python
from reasoning.cdfl import (
    CDFLAgent,
    IGScorer,
    LookaheadPlanner,
    TransitionModel,
)
from reasoning.cdfl.agent import cdfl_agent_from_mined_workflow

# Pure: từ event_log đến planning
miner = HeuristicMiner(min_frequency=2)
mined = miner.mine(event_log)
agent = cdfl_agent_from_mined_workflow(mined.direct_follows, seed=42)
top_actions = agent.score_actions("browse")  # list[ActionScore]

# Online learning + step decision
agent = CDFLAgent(
    action_space=["browse", "checkout", "abandon"],
    horizon=5,
    num_rollouts=6,
    uncertainty_weight=1.0,
    temperature=0.1,
    seed=42,
)
action = agent.step("login")
agent.observe_transition("login", action, "browse")

# Standalone RAG re-ranking (stateless mode)
scorer = IGScorer(uncertainty_weight=1.0)
score = scorer.score(model, current_chunk_id, candidate_chunk_id)
```

---

## 8. Cross-references

- `services/ai-orchestrator/org_intel/process_mining/heuristic_miner.py` — Process Mining output cho CDFL transition_model
- `services/ai-orchestrator/reasoning/rag/pageindex/retriever.py` — RAG candidate source cho IG re-ranking
- `services/ai-orchestrator/workflow_runtime/yaml_schema.py` — Workflow YAML từ CDFL plan
- `docs/strategic/REASONING_LAYER.md` — L3 layer placement context
- `docs/strategic/RAG_ADDENDUM_2026_05.md` — RAG router architecture
- `docs/adr/0019-vectorless-tree-retrieval-and-structured-sql-rag.md` — RAG decisions
- Luận văn: `D:\Luận văn nhất nguyên 2 trường luận giao thoa\Dual Field Convergence Theory - Nguyen Truong An.pdf`

---

*Author: Kaori (em) — based on Nguyễn Trường An's NNL-NTHT thesis.*
*Implementation Tuần 1 of 8-week Build Week plan, 2026-05-15.*
