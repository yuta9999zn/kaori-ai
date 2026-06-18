# UAT — PERFORMANCE_NFR (P50/P99 cho NFR-P-01..12 trên CI)

> **Function:** Priority 4 — Performance baselines for NFR-P-01..12, automated CI test target
> **Portal:** All portals (cross-cutting)
> **Services:** All services
> **DB:** Use load test seed data
> **Owner:** SRE + QA Lead + Platform Eng
> **Prepared:** 2026-05-21 (Round 5 N4)

---

## 0. NFR targets summary (per NFRS §2)

| NFR | Target Phase 1 | Target Phase 3 | Tool |
|---|---|---|---|
| NFR-P-01 API P99 latency (read) | <200ms | <100ms | k6 + Locust |
| NFR-P-02 API P99 latency (write) | <500ms | <250ms | k6 |
| NFR-P-03 Feature Store online | <20ms | <10ms | Redis benchmark |
| NFR-P-04 Insight 3-tuyến gen | <15s | <10s | k6 |
| NFR-P-05 Qwen 14B 512 tok | <5s | <3s | LLM-specific |
| NFR-P-06 Pipeline 5-step (10k rows) | <5 phút | <2 phút | E2E |
| NFR-P-07 Bronze→Silver throughput | ≥10MB/s/tenant | ≥50MB/s | Stream perf |
| NFR-P-08 Silver→Gold MV refresh | <30 phút daily | <5 phút hourly | DB perf |
| NFR-P-09 Process Mining (50k events) | <10 phút | <3 phút | E2E |
| NFR-P-10 NOV monthly compute / tenant | <2 phút | <30s | Cron |
| NFR-P-11 Org Hierarchy tree load (≤5 cấp, ≤500 nodes) | <1s | <500ms | API |
| NFR-P-12 Document OCR tiếng Việt (1 trang A4) | <8s | <4s | LLM |

---

## 1. Test scenarios

### TC-P01 API read latency (GET endpoints)
- **Given** Seed 10k customers in Silver per tenant
- **When** Run `k6 -d 5m -u 50 -p $endpoint` against GET /enterprise/customers
- **Then** P99 <200ms; ≤1% timeout; 0% 5xx; export results to CI artifact

### TC-P04 LLM insight 3-tuyến generation
- **Given** Sample analysis run với data ready
- **When** Trigger Explain insight
- **Then** Response within <15s P99 (Phase 1 target); confidence + citation present

### TC-P09 Process Mining 50k events
- **Given** 50k events in event stream
- **When** Mining session start → algorithm complete
- **Then** End-to-end <10 phút P99 Phase 1

### TC-P11 Org Hierarchy tree load
- **Given** Seed corporate group: 1 root → 8 divisions → 16 subsidiaries → 50 depts per (Vingroup-class fixture, mig 056)
- **When** GET /enterprises/{id}/org-tree
- **Then** <1s for ≤500 nodes; <2s for 1000+ nodes (warning hint to FE virtualize)

### TC-P12 Document OCR
- **Given** Sample 1-page A4 VN scanned PDF
- **When** /v1/ocr Qwen2-VL
- **Then** Response <8s P99 (P1); confidence ≥0.6 average on test corpus

## 2. Continuous Performance Testing strategy

### CI integration
- Run lightweight perf tests on PR (smoke test, 100 req/endpoint)
- Run full perf suite nightly (against staging)
- Regression alert: P99 increase >20% vs baseline → block merge

### Baselines stored
- `tests/perf/baselines/<endpoint>_p99.json` updated weekly
- Compare against ${baseline} ± 20% tolerance
- Lighthouse CI for FE: LCP <2.5s, CLS <0.1, INP <200ms (cho P2-03 + P2-20)

### Tools
- **Backend:** k6 (preferred) / Locust (fallback)
- **DB:** pgbench
- **Cache:** redis-benchmark
- **LLM:** custom Python harness `scripts/perf_baseline.py` (existing)

## 3. Negative scenarios (graceful degradation)

| NFR breach scenario | Expected |
|---|---|
| API P99 >200ms sustained 5min | Alert SRE + auto-scale trigger (HPA) |
| LLM P99 >5s | Circuit breaker open → fallback Qwen local cũ version hoặc cached |
| Pipeline run timeout | Resume from event store mig 094 (no restart from zero) |

## 4. Performance test deliverables

- [ ] `tests/perf/` test scripts cho mỗi NFR-P-01..12
- [ ] `scripts/perf_baseline.py` runner (existing — extend cho 12 NFRs)
- [ ] CI workflow `.github/workflows/perf.yml` nightly
- [ ] Grafana dashboard `Kaori Performance NFR-P` aggregate live
- [ ] Alert rules in Prometheus: NFR-P-* breach → page on-call

## 5. UAT execution checklist

- [ ] Verify all 12 NFR-P-* have perf test scripts
- [ ] Run full suite against staging; export results
- [ ] Compare vs baselines; flag regressions >20%
- [ ] Lighthouse CI for FE: P2-03 + P2-20 priority screens
- [ ] Document baseline values + last-update date trong `docs/uat/perf_baselines.md`
- [ ] CI green for ≥3 consecutive nightlies before declaring Phase 2.8 perf-ready

---

*UAT ID: UAT-PERF-001 · Owner SRE*
