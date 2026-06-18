# UAT — K_RULE_INVARIANTS (K-4 / K-12 / K-13 / K-17 / K-18 Dedicated Tests)

> **Function:** Priority 4 — dedicated test suite for 5 most critical K-rules (Phase 2 production-blocking invariants)
> **Portal:** All portals (cross-cutting)
> **Services:** All services
> **DB:** Affects all tables
> **Owner:** SEC + Platform Eng + QA Lead
> **Prepared:** 2026-05-21 (Round 5 N4)

---

## K-rules under test

| K-rule | Definition | Test family |
|---|---|---|
| **K-4** | External AI only with consent_external=True; OCR/embed REFUSE consent_external entirely (schema-level) | `tests/test_k4_consent_*.py` |
| **K-12** | tenant_id never accepted via query/body/header — JWT only | `tests/test_k12_idor_*.py` |
| **K-13** | Idempotency-Key on all POST mutations | `tests/test_k13_idempotency_*.py` |
| **K-17** | Every workflow node declares side_effect_class | `tests/test_k17_side_effect_class_*.py` |
| **K-18** | Vault-only secrets in production profile | `tests/test_k18_vault_*.py` |

---

## 1. Test scenarios per K-rule

### K-4 (Consent External + OCR/Embed schema pin)

**TC-K4-1** External LLM call without consent
- **Given** Tenant consent_external_ai=false
- **When** LLM /v1/infer with prefer_external=true
- **Then** Router falls back Qwen local; policy_engine deny rule fires; never reaches vendor

**TC-K4-2** OCR endpoint schema pin (CRITICAL — guards K-4 violation)
- **Given** OCR /v1/ocr endpoint
- **When** Pydantic schema check of OcrRequest
- **Then** Schema has NO `consent_external` field; pinned by test `test_ocr_schema_pinned_no_consent_external`. Any future PR trying to add field → test fails BEFORE merge

**TC-K4-3** Embed endpoint same schema pin
- **Given** /v1/embed endpoint
- **When** Schema check
- **Then** EmbedRequest has NO consent_external; pinned by test

### K-12 (Anti-IDOR)

**TC-K12-1** tenant_id NOT accepted from body
- **Given** Request POST /workflows with body `{tenant_id: "other-tenant", ...}`
- **When** Endpoint processes
- **Then** body tenant_id IGNORED; uses JWT-derived enterprise_id

**TC-K12-2** Path param vs JWT mismatch
- **Given** GET /enterprises/{id}/workspaces with id=other-enterprise but JWT issued for own-enterprise
- **When** Request fires
- **Then** 403 USR-ERR-403-IDOR + audit `idor_attempt` + alert SEC if >3/hour

**TC-K12-3** Cross-tenant resource lookup
- **Given** Workflow ID from another tenant in path
- **When** Tenant A queries /workflows/{tenant_B_wf_id}
- **Then** 404 NOT 403 (don't reveal existence) per NFRS §5 SEC pattern

### K-13 (Idempotency)

**TC-K13-1** Same Idempotency-Key returns cached
- **Given** POST /v1/upload with Idempotency-Key=req-abc
- **When** Second call same key within 24h
- **Then** Returns cached response (Redis API layer); no Bronze duplicate

**TC-K13-2** Idempotency required on POST mutations
- **Given** POST /workflows/{id}/run without Idempotency-Key
- **When** Request fires
- **Then** 400 USR-ERR-400-IDEMPOTENCY-MISSING

**TC-K13-3** Persistent ledger across worker restarts (Phase 2.6 P0.3)
- **Given** workflow_idempotency_records mig 095
- **When** Worker crashes mid-external-call, restarts, retries same key
- **Then** SELECT FOR UPDATE serializes; no double-fire (see F-IDEMPOTENCY-LEDGER.md TC-2)

### K-17 (side_effect_class declared)

**TC-K17-1** node_type_catalog has side_effect_class on every row
- **Given** mig 068 node_type_catalog 45 rows
- **When** Query SELECT count(*) FROM node_type_catalog WHERE side_effect_class IS NULL
- **Then** Returns 0; constraint NOT NULL enforced

**TC-K17-2** Workflow YAML node declares side_effect_class
- **Given** Workflow create via POST /workflows/import with node missing side_effect_class
- **When** Validation
- **Then** 422 USR-ERR-422-NODE-MISSING-SIDE-EFFECT-CLASS

**TC-K17-3** Test mode mock-ability per side_effect_class
- **Given** P2-27 Workflow Testing Mode 1
- **When** Mock external nodes (side_effect_class='external')
- **Then** All `external` nodes mockable; if not → test fails with hint

### K-18 (Vault production)

**TC-K18-1** Production profile refuses env-var fallback
- **Given** `KAORI_PROFILE=production` + secret missing in Vault
- **When** Service starts
- **Then** Fails to boot with `RuntimeError: K-18 violation — secret X must resolve from Vault in production`

**TC-K18-2** Dev profile allows env fallback with warning
- **Given** `KAORI_PROFILE=dev` + no Vault configured
- **When** Service reads MFA master key
- **Then** Falls back to KAORI_MFA_KEY env; logs warning `k18.dev_fallback`

**TC-K18-3** Vault rotation no downtime
- **Given** New key written to Vault at v2; service running with v1
- **When** Next secret read
- **Then** v2 fetched; old ciphertext still decryptable (field_key_history mig 080)

## 2. K-rule violation alerts

Per NFRS §5 SEC:
- K-4 violation (vendor call without consent) → alert SEC + block via policy_engine
- K-12 violation (IDOR attempt) → audit + alert if >3/hour
- K-13 violation (missing key) → 400 + log
- K-17 violation (missing side_effect_class) → reject at admission control (workflow create endpoint)
- K-18 violation (env fallback in production) → boot fails

## 3. Performance

K-rule checks must be lightweight (<5ms overhead per request).

## 4. UAT execution checklist

- [ ] Run all 15 TCs (3 per K-rule) green
- [ ] Verify SEC alerts fire on intentional violations (red team test)
- [ ] Boot service with intentional K-18 violation → verify hard fail
- [ ] Pen-test K-12: try IDOR with crafted JWT manipulations → all blocked
- [ ] Regression: add K-4 schema pin test guards against future regression

---

*UAT ID: UAT-K-RULE-001 · Owner SEC + Compliance*
