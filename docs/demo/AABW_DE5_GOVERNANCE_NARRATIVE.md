# Kaori AI — Organizational AI Memory (AABW Problem Statement 5)

> **One-pager for judges.** How Kaori makes AI capability belong to the company — not the employee who built it — with governance that is already running in code, not on slides.
>
> *Tóm tắt tiếng Việt ở cuối trang.*

---

## The claim

Every AI artifact a team produces inside Kaori — workflows, prompts, decisions, extracted knowledge, even the AI's own memories — is captured as a **tenant-owned, versioned, governed asset in the database**. When an employee leaves, nothing leaves with them. When a new employee joins, the organization's AI capability onboards *them*.

## 1. An actual capture mechanism — not a wiki with extra steps

| What gets captured | How (shipped code) |
|---|---|
| **Workflows** | Visual builder → BPMN + typed nodes persisted per tenant; 45-node catalog, 25 live templates; every node declares a `side_effect_class` so the engine knows what is safe to retry (K-17) |
| **Decisions** | `decision_audit_log` + `ai_decision_audit`: every automated decision stores model version, prompt hash, output hash, confidence, and alternatives (K-6) — written at the single LLM chokepoint every call must pass through (K-3) |
| **Knowledge** | Document ingestion (PDF/Word/scan → OCR) → knowledge base with **version history and aging** (ADR-0033); a Document Tree DMS with classification and lifecycle (ADR-0039) |
| **AI memory itself** | 4-tier memory hierarchy with **trust decay / verify / reinforce** (ADR-0030) and palace-style consolidation + associative recall (ADR-0032) — memories mature into foundational knowledge over time (memory → KB promotion) |

Capture is a **side effect of doing the work**, not an extra documentation step. That is the difference from "a wiki with extra steps."

## 2. A real knowledge-transfer / onboarding flow

- New staff are onboarded from a CSV in one call; they immediately inherit the org's full AI context — every workflow, decision rationale, and document their department owns.
- They ask questions in Vietnamese through a chat grounded **only** in the org's knowledge base. The retrieval gate ("học 1 hiểu 10", CDFL coverage gate) checks whether foundational knowledge actually covers the question: enough coverage → generalize and answer with citations; not enough → **decline instead of hallucinate**. Institutional memory stays trustworthy.
- Knowledge doesn't rot silently: entries age, carry version history, and recall is trust-weighted — recently verified knowledge outranks stale knowledge.

## 3. Governance: ownership, versioning, approval — and beyond

Problem statement 5 asks for "basic governance." Kaori ships **EU-AI-Act-grade governance**, live in the product:

| Ask | Kaori invariant (enforced in code + tests) |
|---|---|
| Ownership | Row-level security per tenant on every table (K-1); tenant identity only ever from JWT (K-12); department-level ABAC |
| Versioning | KB version history (ADR-0033); node `type_version` + pinned LLM `model@version` per workflow — no silent vendor upgrade (K-20) |
| Approval | Multi-step **approval chains** with delegation and escalation; a `risk_tier=high` workflow pauses at a human-oversight gate before any irreversible action — approve resumes, stop triggers saga compensation (K-23) |
| Risk classification | Every registered AI use carries `risk_tier ∈ {prohibited, high, limited, minimal}`; prohibited uses are blocked at publish **and** at run (K-22) |
| Transparency | Every generative output carries a machine-readable AI disclosure; the chatbot self-identifies (K-24) |
| Technical documentation | Annex IV-lite **model card** per model + version, with a completeness check (K-25) |
| Post-market monitoring | AI incident register (serious = Art-73-reportable) + bias examination in the data quality gate (K-26) |

Every span carries `tenant_id` for cross-tenant leak detection (K-19); secrets live in Vault (K-18); external LLM calls require explicit consent with PII redaction first — local Qwen is the default (K-4/K-5).

## Why this can run after the build week

Kaori is not a hackathon scaffold: multi-tenant SaaS (6 services), 3,200+ backend tests, 137 database migrations, a real pilot deployment, and a compliance framework (ADR-0041) designed trust-first / conformity-ready. The demo you see is the product.

---

## Tóm tắt tiếng Việt

Kaori biến **năng lực AI thành tài sản của công ty**: workflow, prompt, quyết định, tri thức và cả "trí nhớ" của AI đều được lưu, đánh version, và quản trị theo tenant. Nhân viên nghỉ — tri thức ở lại; nhân viên mới — hỏi đáp trên chính tri thức công ty, thiếu căn cứ thì **từ chối thay vì bịa**. Quản trị không dừng ở "ownership/versioning/approval" mà đạt chuẩn EU AI Act: phân loại rủi ro (K-22), người phê duyệt trước hành động không đảo ngược (K-23), minh bạch AI (K-24), model card (K-25), giám sát sự cố + kiểm tra bias (K-26), audit mọi quyết định (K-6).
