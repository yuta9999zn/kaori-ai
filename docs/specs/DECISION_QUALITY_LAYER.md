# DECISION QUALITY LAYER — Audit, Confidence & Calibration

> Mọi automated decision của Kaori System đều được ghi lại với **confidence, alternatives, và uncertainty flags**.
> Mục tiêu: Evaluate quyết định tốt hay xấu **tại thời điểm ra quyết định** — không phải chờ kết quả.
>
> Adapted từ Kise AI DECISION_QUALITY_LAYER.md cho Kaori general-purpose.

---

## 1. Triết lý cốt lõi

```
QUYẾT ĐỊNH vs KẾT QUẢ là 2 thứ khác nhau:

Good decision + Good outcome = Reinforce (đúng cách, đúng kết quả)
Good decision + Bad outcome  = Investigate (data xấu, không phải logic xấu)
Bad decision  + Good outcome = Flag lucky  (không reinforce — luck ≠ skill)
Bad decision  + Bad outcome  = Compound   (cần fix ngay trước khi lan rộng)
```

**Lý do quan trọng:** Nếu chỉ track outcome, sẽ:
- Reinforce bad decisions khi may mắn
- Punish good decisions khi unlucky
- Mất khả năng học từ failures một cách đúng đắn

---

## 2. Decision Types được audit

| Decision | Nơi ra | Method | Confidence range |
|---|---|---|---|
| `language_detect` | C1 (bronze/column_mapper) | Unicode scan | 0.6–1.0 |
| `column_mapping` | C2 (bronze/column_mapper) | exact→fuzzy→LLM | 0.3–1.0 |
| `purpose_classify` | T1 (silver/rule_catalog) | keyword scoring | 0.2–1.0 |
| `rule_trigger` | T3 (silver/rule_catalog) | condition eval | 0.7–1.0 |
| `preflight_go_nogo` | T4 (data-pipeline) | 6-layer check | 0–1.0 |
| `model_select` | L2 (ai-orchestrator) | template router | 0.8–1.0 |
| `llm_route` | ai-orchestrator engine | consent + provider | 1.0 |
| `framework_select` | framework_router.py | keyword + LLM | 0.6–1.0 |

---

## 3. Decision Audit Log Schema

```sql
-- migrations: thêm vào 008_observability.sql (extend)
CREATE TABLE decision_audit_log (
    id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    enterprise_id    UUID NOT NULL,         -- K-1 multi-tenant
    run_id           UUID REFERENCES pipeline_runs(id),
    decision_type    TEXT NOT NULL,         -- 'column_mapping', 'purpose_classify', ...
    entity_ref       TEXT,                  -- 'column:phone', 'sheet:T4.2026', ...
    confidence       NUMERIC(5,4) NOT NULL, -- K-9
    method           TEXT NOT NULL,         -- 'exact', 'fuzzy', 'llm', 'rule_based'
    decision         JSONB NOT NULL,        -- {chosen: 'phone', reasoning: '...'}
    alternatives     JSONB,                 -- [{name: 'fax', score: 0.62}, ...]
    uncertainty_flags TEXT[],               -- ['low_confidence', 'lang_mismatch']
    needs_user_confirm BOOLEAN DEFAULT FALSE,
    user_confirmed   BOOLEAN,              -- NULL = not reviewed, true/false = reviewed
    confirmed_at     TIMESTAMPTZ,
    created_at       TIMESTAMPTZ DEFAULT NOW()
    -- No UPDATE, No DELETE (K-2 analog)
);

-- Outcome resolution table (async, filled after time window)
CREATE TABLE decision_outcomes (
    id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    audit_id         UUID NOT NULL REFERENCES decision_audit_log(id),
    actual_quality_delta NUMERIC(5,4),     -- observed quality change
    outcome_label    TEXT,                 -- 'as_expected', 'better', 'worse', 'unresolvable'
    resolved_at      TIMESTAMPTZ DEFAULT NOW()
);
```

**Append-only enforcement:**
```sql
CREATE RULE no_update_decision_audit AS ON UPDATE TO decision_audit_log DO INSTEAD NOTHING;
CREATE RULE no_delete_decision_audit AS ON DELETE TO decision_audit_log DO INSTEAD NOTHING;
```

---

## 4. Decision Score Formula

```python
def compute_decision_score(
    confidence: float,
    method: str,
    sample_coverage: float,     # phần trăm rows có sample values
    uncertainty_flags: list[str],
) -> float:
    METHOD_WEIGHTS = {
        'exact':     1.0,
        'fuzzy':     0.9,
        'llm':       0.7,
        'heuristic': 0.6,
        'user_override': 1.0,   # user xác nhận → always high quality
    }
    UNCERTAINTY_PENALTIES = {
        'low_confidence':    0.15,
        'ambiguous_top2':    0.10,
        'lang_mismatch':     0.08,
        'no_sample_values':  0.12,
        'llm_fallback_used': 0.05,
    }

    base = confidence * METHOD_WEIGHTS.get(method, 0.8)
    coverage_bonus = 0.1 * sample_coverage
    penalty = sum(UNCERTAINTY_PENALTIES.get(f, 0) for f in uncertainty_flags)

    return max(0.0, min(1.0, base + coverage_bonus - penalty))
```

---

## 5. Uncertainty Flags

| Flag | Khi nào | Action |
|---|---|---|
| `low_confidence` | confidence < 0.70 | Show warning badge, suggest user review |
| `ambiguous_top2` | top-2 scores within 0.05 | Show both options, ask user to pick |
| `lang_mismatch` | detected_lang ≠ file dominant lang | Show "bất thường" warning |
| `no_sample_values` | header-only column | Cannot verify — flag optional |
| `llm_fallback_used` | LLM was needed (exact + fuzzy failed) | Note in UI |
| `override_history` | User đã từng override decision này | Apply their preference |
| `low_sample_size` | < 10 rows → unreliable stats | Show sample size warning |
| `high_null_rate` | null_rate > 50% | Column unreliable |

**Rule (K-6):** Khi `needs_user_confirm = true`, frontend hiển thị badge ⚠️ và không tự động tiến sang bước tiếp theo.

---

## 6. Python Implementation — Decision Logger

```python
# services/data-pipeline/shared/decision_logger.py

import uuid
from dataclasses import dataclass, field
from typing import Any
import asyncpg

@dataclass
class DecisionEntry:
    enterprise_id: str
    run_id: str
    decision_type: str
    entity_ref: str
    confidence: float
    method: str
    decision: dict
    alternatives: list[dict] = field(default_factory=list)
    uncertainty_flags: list[str] = field(default_factory=list)
    needs_user_confirm: bool = False

    def __post_init__(self):
        # needs_user_confirm = true nếu có bất kỳ uncertainty flag nào
        if self.uncertainty_flags and not self.needs_user_confirm:
            self.needs_user_confirm = True


class DecisionLogger:
    def __init__(self, pool: asyncpg.Pool):
        self.pool = pool

    async def log(self, entry: DecisionEntry) -> str:
        """Insert decision and return audit_id."""
        audit_id = str(uuid.uuid4())
        await self.pool.execute("""
            INSERT INTO decision_audit_log
            (id, enterprise_id, run_id, decision_type, entity_ref,
             confidence, method, decision, alternatives, uncertainty_flags, needs_user_confirm)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8::jsonb, $9::jsonb, $10, $11)
        """,
            audit_id, entry.enterprise_id, entry.run_id,
            entry.decision_type, entry.entity_ref,
            entry.confidence, entry.method,
            json.dumps(entry.decision), json.dumps(entry.alternatives),
            entry.uncertainty_flags, entry.needs_user_confirm
        )
        return audit_id

    async def resolve_outcome(self, audit_id: str, delta: float, label: str):
        """Called async after actual outcome is known."""
        await self.pool.execute("""
            INSERT INTO decision_outcomes (audit_id, actual_quality_delta, outcome_label)
            VALUES ($1, $2, $3)
        """, audit_id, delta, label)
```

---

## 7. Usage Example — Column Mapper với Decision Logging

```python
# services/data-pipeline/bronze/column_mapper.py (excerpt)

async def map_column(
    raw_name: str,
    sample_values: list[Any],
    enterprise_id: str,
    run_id: str,
    decision_logger: DecisionLogger,
) -> ColumnMapping:

    # Step 1: Exact match
    result = try_exact_match(raw_name, LANGUAGE_DICT)
    if result.confidence >= 0.99:
        entry = DecisionEntry(
            enterprise_id=enterprise_id, run_id=run_id,
            decision_type='column_mapping', entity_ref=f'column:{raw_name}',
            confidence=result.confidence, method='exact',
            decision={'canonical': result.canonical, 'reasoning': 'Exact keyword match'},
            alternatives=result.alternatives,
            uncertainty_flags=[],
        )
        audit_id = await decision_logger.log(entry)
        return result.with_audit_id(audit_id)

    # Step 2: Fuzzy
    result = try_fuzzy_match(raw_name, LANGUAGE_DICT, sample_values)
    flags = build_uncertainty_flags(result)

    # Step 3: LLM fallback if still uncertain
    if result.confidence < 0.65:
        result = await llm_map_column(raw_name, sample_values)
        flags.append('llm_fallback_used')

    entry = DecisionEntry(
        enterprise_id=enterprise_id, run_id=run_id,
        decision_type='column_mapping', entity_ref=f'column:{raw_name}',
        confidence=result.confidence, method=result.method,
        decision={'canonical': result.canonical, 'reasoning': result.reasoning},
        alternatives=result.alternatives,
        uncertainty_flags=flags,
    )
    audit_id = await decision_logger.log(entry)
    return result.with_audit_id(audit_id)
```

---

## 8. Frontend — Uncertainty Badges

```typescript
// frontend/src/components/pipeline/SchemaReview.tsx (cần thêm)

function ColumnMappingRow({ mapping }: { mapping: ColumnMapping }) {
  const hasWarning = mapping.uncertainty_flags.length > 0;
  return (
    <div className={cn("row", hasWarning && "border-amber-300")}>
      <span>{mapping.raw_name}</span>
      <span>→ {mapping.canonical_name}</span>
      <ConfidenceBadge value={mapping.confidence} />
      {hasWarning && (
        <Tooltip content={formatUncertaintyFlags(mapping.uncertainty_flags)}>
          <AlertTriangle className="text-amber-500" />
        </Tooltip>
      )}
      {mapping.needs_user_confirm && (
        <Button size="sm" onClick={() => confirmMapping(mapping)}>
          Xác nhận
        </Button>
      )}
    </div>
  );
}
```

---

## 9. Calibration Monitoring (Phase 2)

**Monthly calibration check:**
```python
# Decisions with confidence 0.80 should be correct ~80% of the time
calibration_query = """
    SELECT
        ROUND(confidence::numeric, 1) AS confidence_bucket,
        COUNT(*) AS n_decisions,
        AVG(CASE WHEN o.outcome_label = 'as_expected' THEN 1 ELSE 0 END) AS actual_accuracy
    FROM decision_audit_log d
    JOIN decision_outcomes o ON o.audit_id = d.id
    WHERE d.created_at >= NOW() - INTERVAL '30 days'
    GROUP BY confidence_bucket
    ORDER BY confidence_bucket
"""
# If actual_accuracy >> confidence_bucket: model underconfident → increase confidence
# If actual_accuracy << confidence_bucket: model overconfident → decrease confidence or add penalties
```

**Grafana alerts (Phase 2):**
- `decision_score < 0.5` more than 10% of runs → alert
- `bad_decision + bad_outcome` rate > 5% → critical alert
- Calibration deviation > 0.15 → warning

---

## 10. Implementation Status (2026-04-22)

| Thành phần | Status |
|---|---|
| `decision_audit_log` table (in migrations) | ⚠️ Pending — cần thêm vào 001_init.sql |
| `decision_outcomes` table | ⚠️ Pending |
| `DecisionLogger` class | ⚠️ Pending — `data-pipeline/shared/decision_logger.py` |
| column_mapper.py wiring (log on each mapping decision) | ⚠️ Pending |
| Frontend uncertainty badges in SchemaReview | ⚠️ Pending |
| `needs_user_confirm` blocking flow | ⚠️ Pending |
| Outcome resolution (async, after time window) | Phase 2 |
| Calibration monitoring + Grafana | Phase 2 |
