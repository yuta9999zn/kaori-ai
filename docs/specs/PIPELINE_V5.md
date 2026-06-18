# PIPELINE V5 — Enterprise Extensions

> V5 là bộ extensions enterprise-grade của Pipeline V1 (xem PIPELINE_WORKFLOW.md cho base).
> Roadmap, không bắt buộc cho Phase 1.
>
> Adapted từ Kise AI PIPELINE_V5.md cho Kaori general-purpose.

---

## 1. 8 Extension Modules

| Module | Priority | Vấn đề giải quyết |
|---|---|---|
| Orchestration Layer | P0 (Phase 2) | Retry, timeout, checkpoint |
| Schema Versioning | P1 (Phase 2) | Breaking change detection |
| Feature Store | P2 (Phase 2) | No-recompute cache |
| Quality SLA Gate | P1 (Phase 2) | Block bad data before analysis |
| Late-Arrival Handling | P2 (Phase 3) | Out-of-order data |
| Cost Governance | P1 (Phase 2) | LLM budget control |
| Decision Quality v2 | P3 (Phase 3) | Calibration + feedback loop |
| Observability Suite | P1 (Phase 2) | Prometheus + Grafana + Loki |

---

## 2. Orchestration Layer (P0 — Phase 2)

**Vấn đề:** Nếu T4 fail sau T3 xong, hiện tại cần re-run toàn bộ từ đầu.

**Giải pháp:** Postgres-backed DAG với checkpoint store.

```python
# services/data-pipeline/orchestration/dag_registry.py

PIPELINE_DAG = {
    'E1_file_gate':    StepNode(next=['E2_extract_mode'],  retries=0, timeout=10),
    'E2_extract_mode': StepNode(next=['E3_parse'],         retries=1, timeout=30),
    'E3_parse':        StepNode(next=['E4_bronze_land'],   retries=2, timeout=120),
    'E4_bronze_land':  StepNode(next=['C1_lang_detect'],   retries=2, timeout=30),
    'C1_lang_detect':  StepNode(next=['C2_col_map'],       retries=1, timeout=60),
    'C2_col_map':      StepNode(next=['C3_persist'],       retries=1, timeout=120),
    'C3_persist':      StepNode(next=['T1_classify'],      retries=2, timeout=10),
    'T1_classify':     StepNode(next=['T2_profile'],       retries=1, timeout=30),
    'T2_profile':      StepNode(next=['T3_rules'],         retries=1, timeout=30),
    'T3_rules':        StepNode(next=['T4_preflight'],     retries=1, timeout=60),
    'T4_preflight':    StepNode(next=['T5_silver'],        retries=0, timeout=10),
    'T5_silver':       StepNode(next=['L1_aggregate'],     retries=2, timeout=60),
    'L1_aggregate':    StepNode(next=['L2_analysis'],      retries=1, timeout=120),
    'L2_analysis':     StepNode(next=['L3_publish'],       retries=1, timeout=300),
    'L3_publish':      StepNode(next=[],                   retries=2, timeout=30),
}
```

```sql
-- Checkpoint store
CREATE TABLE pipeline_checkpoints (
    run_id       UUID NOT NULL,
    step_name    TEXT NOT NULL,
    status       TEXT NOT NULL,   -- pending|running|done|error
    started_at   TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    error_msg    TEXT,
    PRIMARY KEY (run_id, step_name)
);
```

**Runner:** Khi resume, skip steps đã `status = done`. Retry chỉ step fail.

---

## 3. Schema Versioning (P1 — Phase 2)

**Vấn đề:** Khi cấu trúc file input thay đổi (cột đổi tên, bị bỏ), cần detect backward compatibility.

**Semver cho canonical schemas:**
```
MAJOR.MINOR.PATCH
  ↑ Breaking: column removed / type incompatible
       ↑ Additive: new optional column
            ↑ Fix: rename only, same canonical

vd: 1.0.0 → 1.1.0 (thêm 'product_code' optional)
    1.1.0 → 2.0.0 (bỏ 'transaction_type' bắt buộc)
```

```sql
CREATE TABLE canonical_schema_versions (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    enterprise_id UUID NOT NULL,
    schema_hash  TEXT NOT NULL,
    version      TEXT NOT NULL,    -- semver
    columns_json JSONB NOT NULL,
    change_type  TEXT,             -- 'MAJOR', 'MINOR', 'PATCH'
    diff_summary TEXT,
    created_at   TIMESTAMPTZ DEFAULT NOW()
);
```

**Breaking change alert:** Email enterprise admin nếu MAJOR bump (họ cần review mapping).

---

## 4. Feature Store (P2 — Phase 2)

**Vấn đề:** RFM features cùng enterprise, cùng Silver run → recompute nhiều lần khi user chạy lại.

**Giải pháp:** Redis (online) + Postgres (offline) cache.

```python
# services/ai-orchestrator/engine/feature_store.py

class FeatureStore:
    async def get_or_compute(
        self,
        enterprise_id: str,
        run_id: str,
        feature_name: str,   # 'rfm_recency', 'monthly_revenue', ...
        compute_fn: Callable,
        ttl: int = 3600,
    ):
        key = f"features:{enterprise_id}:{run_id}:{feature_name}"

        # Online: Redis (fast lookup)
        cached = await redis.get(key)
        if cached:
            return json.loads(cached)

        # Offline: Postgres (persist across Redis evictions)
        stored = await db.fetchrow(
            "SELECT value FROM feature_cache WHERE key = $1", key
        )
        if stored:
            await redis.set(key, stored['value'], ex=ttl)
            return json.loads(stored['value'])

        # Compute
        result = await compute_fn()

        # Store both
        serialized = json.dumps(result)
        await redis.set(key, serialized, ex=ttl)
        await db.execute("""
            INSERT INTO feature_cache (key, value, enterprise_id, run_id, feature_name)
            VALUES ($1, $2::jsonb, $3, $4, $5)
            ON CONFLICT (key) DO UPDATE SET value = $2, updated_at = NOW()
        """, key, serialized, enterprise_id, run_id, feature_name)

        return result
```

**Result:** RFM computation với 10,000 khách = 2.3s → 0.02s (Redis hit rate ~90%).

---

## 5. Quality SLA Gate (P1 — Phase 2)

**Vấn đề:** Đôi khi Silver layer qua nhưng data quality quá thấp → analysis meaningless.

**Giải pháp:** Quality gate sau T5, trước L1.

```python
# services/data-pipeline/silver/quality_gate.py

SLA_THRESHOLDS = {
    'min_quality_score': 0.60,    # overall
    'max_null_rate':     0.40,    # per key column
    'min_type_consistency': 0.85, # per typed column
    'min_row_count':     5,       # absolute minimum
}

async def check_quality_sla(silver_result: SilverResult) -> QualitySLAResult:
    violations = []
    for threshold_name, threshold_value in SLA_THRESHOLDS.items():
        actual = get_actual(silver_result, threshold_name)
        if not meets_threshold(actual, threshold_value):
            violations.append(QualityViolation(
                name=threshold_name,
                actual=actual,
                threshold=threshold_value,
                message=format_vi_message(threshold_name, actual, threshold_value)
            ))

    return QualitySLAResult(
        passed=len(violations) == 0,
        violations=violations,
        overall_score=silver_result.quality_score,
    )
```

**UI**: Nếu không pass SLA gate → hiện warning với số liệu cụ thể, cho phép user quyết định tiếp tục hay không.

---

## 6. Cost Governance (P1 — Phase 2)

**Vấn đề:** LLM calls (Qwen local = free, Claude/GPT = tốn tiền) cần budget control.

```python
# services/ai-orchestrator/engine/cost_governor.py

COST_PER_TOKEN = {
    'qwen':        0.0,         # local, free
    'claude-sonnet-4-6': 0.003, # $0.003/1K tokens
    'gpt-4o':     0.005,        # $0.005/1K tokens
}

DAILY_BUDGET_USD = float(os.getenv("DAILY_LLM_BUDGET_USD", "10.0"))

class CostGovernor:
    async def check_budget_and_bill(
        self,
        enterprise_id: str,
        provider: str,
        estimated_tokens: int,
    ) -> bool:
        cost = (estimated_tokens / 1000) * COST_PER_TOKEN.get(provider, 0)
        daily_total = await get_daily_total(enterprise_id)

        if daily_total + cost > DAILY_BUDGET_USD:
            log.warning("llm.budget.exceeded",
                       enterprise=enterprise_id, provider=provider)
            return False  # Fall back to Qwen

        await record_cost(enterprise_id, provider, cost, estimated_tokens)
        return True
```

7 scaling thresholds (từ 10% budget → 100%):
- 80%: warning header `X-Budget-Warning`
- 95%: soft limit warning in response
- 100%: hard stop → fallback to Qwen local

---

## 7. Late-Arrival Data (P2 — Phase 3)

**Vấn đề:** File của tháng trước upload trễ → Silver không consistent với Gold.

**Giải pháp:** Watermark + quarantine queue.

```python
LATE_ARRIVAL_THRESHOLD = 7  # days

class LateArrivalDetector:
    def classify(self, row_date: datetime, pipeline_run_date: datetime) -> str:
        delta = (pipeline_run_date - row_date).days
        if delta <= LATE_ARRIVAL_THRESHOLD:
            return 'on_time'
        elif delta <= 30:
            return 'late_arrival'  # Reprocess
        else:
            return 'very_late'     # Manual review required
```

Late arrivals → Kafka topic `pipeline.late_arrival` → low-priority consumer → reprocess Silver.

---

## 8. Observability Suite (P1 — Phase 2)

### Kafka Topics to add
```yaml
# infrastructure/kafka/topics.yml
topics:
  - name: pipeline.late_arrival
    partitions: 3
    retention_ms: 604800000  # 7 days
  - name: pipeline.quality_sla_fail
    partitions: 3
  - name: billing.cost_event
    partitions: 3
  - name: decision.needs_review
    partitions: 3
```

### Grafana Dashboards (Phase 2)
```
1. Pipeline Health
   - P95 processing time per step
   - Retry rate per step
   - Quality SLA pass/fail rate

2. Decision Quality
   - Confidence distribution over time
   - Rule effectiveness (expected vs actual delta)
   - LLM fallback rate (indicate mapping problems)

3. Cost Governance
   - Daily LLM cost per enterprise
   - External AI vs local Qwen ratio
   - Budget burn rate

4. Data Quality
   - Null rate trends per enterprise
   - Type consistency trends
   - Schema version bump frequency
```

---

## 9. Migration Roadmap (Phase 2 SQL)

```
009_orchestration.sql      Checkpoint store, DAG step log
010_schema_versioning.sql  canonical_schema_versions
011_feature_cache.sql      feature_cache (Redis offline backup)
012_quality_sla.sql        quality_sla_results
013_late_arriving.sql      late_arrival_queue
014_cost_governance.sql    llm_cost_log, enterprise_daily_budget
015_decision_quality_v2.sql calibration tables, outcome feedback
```

---

## 10. V5 vs V1 — Feature Comparison

| Feature | V1 (Phase 1) | V5 (Phase 2+) |
|---|---|---|
| Pipeline execution | Linear, no retry | DAG with checkpoint + retry |
| Schema tracking | None | Versioned with MAJOR/MINOR/PATCH |
| Feature caching | None | Redis + Postgres feature store |
| Quality gate | Preflight only | Post-Silver SLA gate |
| Late data | Ignored | Watermark + quarantine |
| LLM cost | Uncapped | Budget per enterprise per day |
| Decision feedback | Log only | Outcome resolution + calibration |
| Observability | Structlog only | Prometheus + Grafana + Loki |

**V1 is sufficient for Phase 1 launch.** V5 adds production hardening when enterprise scale kicks in.
