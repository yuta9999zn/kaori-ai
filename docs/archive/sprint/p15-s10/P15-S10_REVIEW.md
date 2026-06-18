# P15-S10 Pre-emptive Self-Review

> **Reviewer:** Claude (em) walking own diff `origin/feat/p15-s9-d1..HEAD`
> **Date:** 2026-05-11
> **Scope:** 5 feature commits + 1 skeleton commit, ~4000 lines on top of P15-S9
> **Goal:** soi 6 deliverable đã ship trước khi anh review thật + trước khi push lên `feat/p15-s10-d1`

S10 đã ship 6/8 D-pieces. D1 (Gmail/Outlook) + D2 (Calendar) chưa làm — chưa review.

Severity legend: **CRITICAL** (production-impact bug) · **MEDIUM** (correctness issue, reachable but constrained) · **LOW** (cosmetic / suggested cleanup).

---

## D6 — RAG router (commit `fe7b60b`)

### CRITICAL — R1: NotImplementedError fallback ignores tenant whitelist

**File:** `services/ai-orchestrator/reasoning/rag/router.py:167-178`

```python
try:
    answer = await engine.answer(query)
except NotImplementedError as exc:
    log.warning(...)
    fallback_engine = self.engines["pgvector"]   # ← unconditional
    answer = await fallback_engine.answer(query)
```

`route()` correctly applies the tenant whitelist via `_apply_whitelist` so the initial engine choice respects it. But when the chosen engine raises `NotImplementedError` (DocSage stub does today), the `except` branch falls back to pgvector regardless of whether pgvector is in the tenant's whitelist.

**Reproduction:** Tenant configures `rag_engines = ["docsage"]` (e.g. for data-residency reasons or BYO LLM). Query routes to docsage → docsage stub raises → router silently answers via pgvector. Tenant gets a response from an engine they explicitly excluded.

This is a K-1 / K-15 spirit violation — tenant configuration policy bypassed by an internal fallback.

**Fix recommendation:** re-apply the whitelist to the fallback choice; if whitelist excludes every available engine, raise an explicit `RAGEngineUnavailable` (RFC 7807 503 mapping) instead of silently using a forbidden engine.

### MEDIUM — R2: `_apply_whitelist` has dead code line 195

**File:** `router.py:191-201`

```python
def _apply_whitelist(decision, whitelist):
    if not whitelist:
        return decision
    if decision.engine_name in whitelist:
        return decision
    if not whitelist:           # ← unreachable; same check as line 191
        return decision
    fallback = whitelist[0]
    ...
```

Cosmetic per se but the second `if not whitelist` looks like it was intended to be different logic that got copy-pasted. Either delete it or replace with the intended check (e.g. validate whitelist members are in `ALL_ENGINE_NAMES`).

### LOW — R3: keyword set has trailing-space terms

`_DOC_CITATION_KEYWORDS` contains `"điều "`, `"chương "`, `"mục "` — trailing space is intentional (avoid matching `"điều" `mid-word) but a query like `"điều?"` (no space after) won't match. Same for `"top "` in `_MULTI_ENTITY_KEYWORDS` (query "top5 customer" misses).

**Recommendation:** use word-boundary regex instead of substring `in`. Or document the intent + add a punctuation-edge test case.

### LOW — R4: `.lower()` Vietnamese coverage not tested

`text_lower = query.query_text.lower()` — modern Python handles `Đ → đ` but no test asserts. If a future Vietnamese keyword uses combining diacritics differently (`ề` vs `e + ̀`), unicode-normalisation skew could miss a match. Add a normalisation step + test.

---

## D4 — Intervention engine (commit `aacffff`, part 2)

### CRITICAL — I1: `requires_manager_approval=true` + no telegram → fails OPEN — ✅ FIXED 2026-05-12

> Fix landed: `intervention_engine.py` now raises `InterventionMisconfigError`
> (fail-closed). Test `test_resolve_manager_approval_no_telegram_raises_misconfig`
> replaces the old fail-open assertion. 17/17 intervention tests pass; full
> ai-orchestrator suite 623/623 pass.

**File:** `services/ai-orchestrator/org_intel/adoption/intervention_engine.py:118-129`

```python
if settings.requires_manager_approval:
    if settings.telegram_chat_id:
        gate = ApprovalGate.MANAGER_APPROVAL
    else:
        gate = ApprovalGate.AUTO        # ← fail open
        gate_reason = "...falling back to AUTO; operator should reconcile"
```

When a tenant has explicitly opted into manager approval (compliance requirement: hierarchical sign-off before automated actions per Vietnamese workflow culture per spec D4) but their Telegram isn't bound, the engine returns AUTO. This **bypasses the audit gate the tenant configured**.

The docstring's rationale ("rather than block + lose the intervention") prioritises action over compliance. But for an intervention that mutates customer-facing state (CSM email sent, ticket created, customer marked at-risk), losing the gate is worse than losing the action — the action can be retried, the audit trail can't.

**Fix recommendation:** raise `InterventionMisconfigError` so the workflow surfaces the misconfig as a Temporal failure (operator pages). Alternatively, route the intervention into a quarantine queue for manual triage. Either way, **don't auto-fire**.

### LOW — I2: locale comparison is exact-string

```python
locale = (settings.locale or "vi").lower()
if locale == "vi": ...
else: ...           # everything not 'vi' → EMAIL
```

`"vi-VN"`, `"vie"`, `"vi_VN"` all fall through to the international branch. Today every Olist tenant is `"vi"` so harmless; future BCP-47 tags break silently. Either parse to language subtag (`"vi-VN".split("-")[0]`) or document the strict-string contract.

---

## D3 — Intervention tracker + migration 044 (commit `aacffff`, part 1)

### MEDIUM — T1: migration 044 has no CHECK on score columns

**File:** `infrastructure/postgres/migrations/044_intervention_outcomes.sql:26-33`

```sql
pre_score    NUMERIC(5, 2) NOT NULL,        -- composite 0-100
post_score   NUMERIC(5, 2) NOT NULL,
improvement  NUMERIC(5, 2) NOT NULL,
```

`NUMERIC(5, 2)` permits up to `999.99`. The application-layer `capture_baseline` raises on `pre_score not in [0, 100]`, but a code bug elsewhere (or direct DB write from a debugging session) can land `150.00` or `-1.50` and the row sticks. K-9 says "NUMERIC for precision, never FLOAT" — defense in depth on RANGE is missing.

**Fix recommendation:** add `CHECK (pre_score BETWEEN 0 AND 100)` + same on `post_score`; let `improvement` stay free since it's a delta.

### MEDIUM — T2: `intervention_id` non-empty not validated

**File:** `services/ai-orchestrator/org_intel/adoption/intervention_tracker.py:100-128`

`capture_baseline` accepts `intervention_id: str` and constructs the dataclass without validation. If a caller passes `""`, downstream UPSERT keyed by `intervention_id` collapses every empty-id intervention to the same row across all tenants of a workflow run.

The unique index `intervention_outcomes_intervention_checkpoint_uniq` keeps things from duplicating but cross-baseline overwrite is now silent.

**Fix recommendation:** raise `ValueError` when `not intervention_id.strip()`.

### LOW — T3: `evaluate_at_checkpoint` doesn't verify the checkpoint elapsed

The function accepts `checkpoint_days in {14, 30}` but doesn't compare `now - baseline.triggered_at` to that value. The Temporal workflow controls timing via `workflow.sleep(14d)`, so in practice the call only fires after the right interval. But a unit test (or a buggy caller) can compute a "14-day result" at t=baseline → silently misclassify.

**Fix recommendation:** add `assert (now - baseline.triggered_at) >= timedelta(days=checkpoint_days - 1)` (1d slop for clock skew).

### LOW — T4: classification boundary asymmetry at exactly ±5

`improvement > 5` → EFFECTIVE; `improvement < -5` → REGRESSION; `improvement == 5` → NEUTRAL; `improvement == -5` → NEUTRAL.

Per spec §31.4 ">5 = effective" the EFFECTIVE side is correct; the REGRESSION side may be intended as `≤ -5` (mirror). Marginal in practice (continuous float). Worth confirming with the spec author.

### LOW — T5: `intervention_id TEXT` column vs UUID elsewhere

Migration 044 declares `intervention_id TEXT` while `enterprise_id` is UUID, `workflow_run_id` is TEXT. Mixed conventions. `intervention_id` likely will remain a structured identifier (e.g. `csm_email_2026-05-11_olist_abc`) so TEXT is defensible — but no schema comment explains the choice.

---

## D5 — A/B revenue attribution (commit `12b53ac`)

### MEDIUM — A1: `total_population` is unchecked extrapolation factor

**File:** `services/ai-orchestrator/org_intel/economics/revenue.py:147-150`

```python
population = total_population if total_population is not None else (
    control_group_size + treatment_group_size
)
revenue = (delta_per_user * Decimal(population)).quantize(Decimal("0.0001"))
```

Caller passes `total_population`; revenue scales linearly. A caller who passes the entire enterprise customer count when only a tiny opted-in cohort actually ran the experiment will balloon the estimate.

**Fix recommendation:** when `total_population > 10 × (control_n + treatment_n)`, attach a `note` warning that this is high-leverage extrapolation. Or refuse `total_population > 100 × cohort_size` outright as obviously wrong.

### LOW — A2: confidence thresholds are sample-size only

Thresholds `[30, 100, 1000]` ignore variance and effect size. The docstring is honest about Phase 2 plans; flag here so reviewers don't assume the 0.9 number is statistical power.

### LOW — A3: module docstring overstates "shipped"

The header claims `NOV-REV-004 ✅` and `NOV-REV-005 ✅` shipped this sprint. NOV-REV-004 (KPI-to-revenue mapper) is the `INDUSTRY_BENCHMARKS` dict that was already present in P1-S7. NOV-REV-005 (confidence scoring) is the `confidence` field on `RevenueEstimate` — also pre-existing. Only NOV-REV-002 (A/B) is truly new this sprint.

**Fix recommendation:** rewrite header to mark NOV-REV-002 as this-sprint addition; leave 004/005 as "already shipped P1-S7" lineage notes.

### LOW — A4: industry rates have no provenance comment

`INDUSTRY_BENCHMARKS` rates 3-6% are pinned constants. No comment cites where they come from (Vietnam SME baseline data? Bain industry study?). Snapshot test would catch silent drift.

---

## D7 — PageIndex tree builder (commit `4ad4160`)

### LOW — P1: `cache_key` uses `|` separator (UUID-safe but document)

`raw = f"{self.tenant_id}|{self.doc_sha256}|{self.schema_version}".encode("utf-8")`

UUIDs and SHA-256 hex never contain `|`, so collision-free in practice. If `tenant_id` ever becomes a non-UUID identifier (string subdomain), `|` collision becomes possible. Comment the assumption or use length-prefixed serialisation.

### LOW — P2: `StubPageIndexTreeBuilder.schema_version` shadows base

`PageIndexTreeBuilder.schema_version = 1` (base class) and `StubPageIndexTreeBuilder.schema_version = 1` (subclass). When the upstream wrapper bumps to 2 by updating only its own subclass, the stub silently stays at 1 → cache keys diverge between stub-built trees and real-built trees for the same `(tenant_id, doc_sha256)`. Already a non-bug because operators never run both simultaneously, but worth a comment that subclasses MUST keep `schema_version` in sync.

---

## D8 — PageIndex retriever (commit `fe7b60b`, part 2)

### LOW — P3: stub answer text leaks tenant_id into user-visible answer

**File:** `services/ai-orchestrator/reasoning/rag/pageindex/retriever.py:49-53`

```python
f"[STUB pageindex] Would have traversed the {_count_nodes(tree.root)}-node "
f"tree for tenant={tree.tenant_id} and returned the matching leaf. "
```

If this stub ever reaches a production answer (operator forgot to swap to upstream), the tenant_id UUID appears in the user-visible chat reply. Not a cross-tenant leak (same tenant queries it) but bad hygiene — UI dashboards prefer display names. Drop `tenant={tree.tenant_id}` from the answer string; keep it in the structured log.

### LOW — P4: recursive helpers have no depth limit

`_first_leaf` / `_path_to_leaf` / `_count_nodes` recurse without depth guard. PageIndex trees are typically <10 levels; Python default recursion limit is 1000. Theoretical issue only.

---

## Phase 2 skeleton services (commit `297b7e3`)

No findings beyond expected stub behaviour. Each skeleton has minimal `/health` returning `{status, service, phase, code_location_today}` — exactly enough for the Helm chart + CI smoke build target to reference `services/{process-mining,adoption-intel,economics,workflow-engine}/` without duplicating real logic. The docstrings explicitly warn "DO NOT add real route handlers here until the Phase 2 extract starts."

---

## Runbooks (commit `9a4f254`)

Not code; review separately if anh wants. 4 ops playbooks (temporal-down, dlq-flooding, vault-rotation, ck-replication-lag) — covered the K-18 / K-19 ops surface that landed in S9.

---

## Summary

| Severity | Count | Action |
|---|---|---|
| **CRITICAL** | 2 (R1 router whitelist bypass ✅ FIXED `abc9097`, I1 intervention fail-open ✅ FIXED 2026-05-12) | Both shipped before June re-push |
| MEDIUM | 5 (R2 dead code, T1 score CHECK, T2 intervention_id empty, A1 population extrapolation, P2 schema_version sync) | Note for reviewer; cheap follow-ups |
| LOW | 13+ | Defer to next sprint cleanup pass |

**Recommendation: fix R1 + I1 before pushing the S10 branch.** Both are short:
- R1: ~10 lines — re-apply whitelist in `answer()` fallback, raise `RAGEngineUnavailable` when no whitelisted engine works
- I1: ~5 lines — raise `InterventionMisconfigError` (or route to quarantine queue) instead of returning AUTO when manager-approval-required + no Telegram

If anh muốn merge S10 nhanh sau khi S9 lên main, fix 2 CRITICAL trước, MEDIUM + LOW gom thành 1 cleanup commit cuối sprint.

---

*Companion to: `docs/sprint/P15-S9_REVIEW.md` (S9 pre-emptive review)*
*Plan source: `docs/sprint/P15-S10_PLAN.md`*
