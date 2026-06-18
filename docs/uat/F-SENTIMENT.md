# UAT — F-SENTIMENT (AI Node: Sentiment Analysis)

> **Function:** Phase 2.5 AI node `sentiment_analysis` — 5-point symmetric scale + per-aspect VN
> **Portal:** P2 Enterprise (workflow card execution)
> **Service:** ai-orchestrator (`reasoning/sentiment_analyser.py`) → llm-gateway
> **DB:** Catalog mig 086 (category='processing')
> **Owner:** QA Lead + Marketing Analyst (NPS/CS use cases)
> **Prepared:** 2026-05-21 (Round 5 N4)

---

## 0. What landed (Phase 2.5 ship `99471cd`)

| Surface | Purpose |
|---|---|
| `reasoning/sentiment_analyser.py` | 5-point scale (rất tiêu cực / tiêu cực / trung lập / tích cực / rất tích cực) + per-aspect |
| Catalog row mig 086 | `sentiment_analysis` registered read_only |
| "unknown" sentinel | Aspects not mentioned in input → don't fabricate sentiment |
| PII smoke alarm | Warns if input có raw PII (chưa mask) |

Tests pass: `tests/test_sentiment.py` 11/11.

---

## 1. Test scenarios

### TC-1 Happy path (positive customer review)
- **Given** input "Sản phẩm tuyệt vời, giao hàng nhanh, nhưng đóng gói hơi sơ sài"
- **When** sentiment_analysis card với aspects=[product, delivery, packaging]
- **Then** output `{overall: 'tích cực', aspects: {product: 'rất tích cực', delivery: 'tích cực', packaging: 'tiêu cực'}, confidence: ≥0.7}`

### TC-2 "unknown" sentinel cho aspect không mention
- **Given** input "Giao hàng nhanh" + aspects=[product, delivery, packaging, customer_service]
- **When** sentiment
- **Then** `aspects: {delivery: 'tích cực', product: 'unknown', packaging: 'unknown', customer_service: 'unknown'}` — KHÔNG fabricate

### TC-3 PII smoke alarm
- **Given** input chứa raw "Nguyễn Văn A SĐT 0912345678 rất bực"
- **When** sentiment
- **Then** sentiment processed nhưng warning emitted: `pii_smoke_alarm: true, suggested_action: 'mask_before_sentiment'`; K-5 PII redact step missed

## 2. Negative scenarios

| Scenario | Trigger | Expected |
|---|---|---|
| **Happy** | Valid VN review + aspects | TC-1 |
| **Validation** | aspects=[] (empty) | Output `{overall: '...', aspects: {}}` — valid (overall-only mode) |
| **Permission** | VIEWER trigger | 403 |
| **Dependency** | LLM 500 | Per-item degraded entry |

## 3. K-rule invariants

- **K-3** llm-gateway ✓
- **K-4** Default Qwen local
- **K-5** Warn if PII trong input (NFR-PR-01 F1 ≥0.95)
- **K-6** audit mig 098
- **K-17** read_only

## 4. Performance

| NFR | Target |
|---|---|
| NFR-P-05 LLM call P99 | <5s |
| Multi-aspect (5+ aspects) | Same as single (1 call) |

## 5. UAT execution checklist

- [ ] Setup 10 sample VN reviews: 3 positive + 3 neutral + 3 negative + 1 mixed
- [ ] Trigger sentiment với 5 aspects → verify per-aspect score + "unknown" cho aspects không mention
- [ ] PII smoke: inject raw SĐT/CCCD → verify warning emitted (KHÔNG abort)
- [ ] Compare AI sentiment vs human label trên 100-review sample → target F1 ≥0.75 cho VN

---

*UAT ID: UAT-SENTIMENT-001 · Owner QA Lead*
