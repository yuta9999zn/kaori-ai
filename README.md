# Kaori AI — Decisions from Your Sales Data

> **An agentic AI platform that turns a retailer's raw business data into prioritized,
> explainable next-best-actions — surfacing revenue at risk and recommending what to do,
> with no data engineer required.**

Kaori is a **production multi-tenant B2B SaaS platform** (not a weekend prototype). A
business uploads its messy sales/customer/transaction data; Kaori ingests it through a
12-stage data pipeline, reasons over it with a grounded agent, and hands a manager a
ranked list of *what to do this week* — in plain Vietnamese, with the money impact and an
audit trail attached.

Built for **Agentic AI Build Week (HCMC, July 2026) — Retail & E-Commerce track**.

---

## Why it's different

Most "AI for data" tools either need a data team to run them, or they hallucinate
confidently on your data. Kaori is engineered around three principles:

- **No data engineer required.** Upload raw Excel/CSV → automated Medallion pipeline
  (Bronze → Silver → Gold) handles schema detection, cleaning, PII redaction, and a
  7-dimension quality gate. Bad data is *flagged*, not silently trusted.
- **Grounded, not hallucinated.** The CDFL reasoning engine ("học 1 hiểu 10" — *learn
  one, understand ten*) uses an `|OR|` coverage gate: if the agent lacks enough grounded
  knowledge to answer, **it declines instead of making something up.**
- **Built to be deployed, not just demoed.** Multi-tenant isolation, a decision audit log
  on every automated decision, and **EU AI Act compliance built in** (risk
  classification, human oversight, transparency disclosure, model cards, incident
  register, bias examination).

The North Star metric is deliberately blunt: **revenue at risk that a human actually
actioned.**

---

## What it does

| Stage | What happens |
|---|---|
| **1. Upload** | Messy Excel/CSV of sales, customers, transactions — append-only, SHA-256 deduped. |
| **2–4. Pipeline** | Schema detection → cleaning → Vietnamese-aware PII redaction → 7-dimension quality scorecard (a gate, not a report). |
| **5–7. Enrich** | Semantic enrichment, knowledge extraction, and a memory system that consolidates and ages experience. |
| **8–9. Decide** | Surfaces *revenue at risk* (churning customers, margin-bleeding SKUs) and generates **next-best-actions** ranked by money impact, each explainable and audited. |
| **10–12. Deliver + Loop** | Manager-language reports, adoption tracking, and a feedback loop that re-baselines over time. |

Outputs speak business Vietnamese ("doanh thu có nguy cơ mất", "khách cần giữ chân") —
not "inference" and "dtype".

---

## Architecture

A modular system of 6 services, designed to extract into microservices as it scales:

| Service | Stack | Role |
|---|---|---|
| API Gateway | Java · Spring Cloud Gateway | Routing, JWT, tenant header forwarding |
| Auth Service | Java · Spring Security | Auth, MFA, sessions |
| Data Pipeline | Python · FastAPI | Ingestion · Medallion · quality |
| AI Orchestrator | Python · FastAPI | CDFL reasoning · workflow runtime · org intelligence |
| LLM Gateway | Python · FastAPI | Model routing, output-schema validation, cost governance |
| Notification | Python · FastAPI | Outbound delivery |

**Data & infra:** PostgreSQL 15 + pgvector (row-level-security multi-tenancy), Redis,
Apache Kafka, Temporal, MinIO, ClickHouse, OpenTelemetry.

**LLM (privacy-first):** **Qwen 2.5 14B + BGE-M3 run locally via Ollama by default** —
customer data never leaves the system. External vendors (Anthropic / OpenAI) are strictly
opt-in, gated behind consent + PII masking.

> Deep dive: [`CLAUDE.md`](./CLAUDE.md) — living architecture doc (tech stack ·
> invariants · phase status). Docs index: [`docs/README.md`](./docs/README.md).

---

## Trust & compliance

Engineered so an enterprise can actually say *yes* to a pilot:

- **EU AI Act compliance (built in):** risk classification per AI-use, human-oversight
  gates before high-risk side effects, machine-readable AI-output disclosure, Annex IV
  model cards, an incident register, and bias examination inside the quality gate.
- **Decision traceability:** every automated decision logs confidence, alternatives, and
  lineage — a manager can always ask *"why did the AI say this?"*
- **Multi-tenant by construction:** every query is tenant-scoped; zero cross-tenant
  leakage is an invariant we test, not a hope.

---

## Quick start (local)

```bash
# 1. Configure environment + secrets
cp .env.example .env
bash scripts/generate-jwt-keys.sh     # RS256 keypair for auth
bash scripts/generate-mfa-key.sh      # AES-256 MFA master key
# then set POSTGRES_PASSWORD in .env

# 2. Start the full stack (Postgres, Redis, Kafka, Ollama, 6 services, frontend)
docker compose up -d
#   Windows shortcut that also waits for health + auto-pulls the model:
#   kaori-start.bat

# 3. Pull the local LLM + embedding model (first run only, ~5 GB)
docker compose exec ollama ollama pull qwen2.5:7b
docker compose exec ollama ollama pull bge-m3
```

**Demo logins** (once the stack is up):
- **Enterprise portal** — `http://localhost:3000/login` → `admin@kaori.local` / `Admin@kaori1`
- **Platform admin** — seed once via `kaori-seed-admin.bat`, then `superadmin@kaori.local` / `Kaori@Admin1`

> Full first-run guide: [`docs/HOW_TO_RUN_PILOT.md`](./docs/HOW_TO_RUN_PILOT.md). First build ~15–20 min
> (images + model); subsequent starts ~2–3 min.

**Service URLs:** `:3000` Frontend · `:8080` API Gateway · `:8082` Swagger · `:3001` Grafana · `:11434` Ollama.

---

## Status

A working pilot platform with thousands of automated tests across services. Phase 1 →
Phase 2 backend complete; multi-language frontend (vi / en / ja / ko / zh) in place.

## License

Proprietary — see [`LICENSE`](./LICENSE). Source is shared publicly for evaluation during
Agentic AI Build Week 2026.

---

*Built by the Kaori team for Agentic AI Build Week — Ho Chi Minh City, July 2026.*
