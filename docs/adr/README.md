# Architecture Decision Records

This folder tracks the **non-obvious architectural decisions** we've made on Kaori — the ones that future-you (or a new hire) would otherwise spend a week reverse-engineering by reading commit messages and Slack scrollback.

## What goes here

A decision belongs in an ADR if it has at least one of:

- **Two or more reasonable options were on the table** and we picked one (e.g., "RLS vs filtered views").
- **The choice constrains future code** — it says "no" to a category of solutions, not just "yes" to this one.
- **Reverting later would cost more than a sprint** (schema, contract, infra cluster, partner integration).
- **The reasoning lives in someone's head** rather than in code or BACKLOG.md.

## What does NOT go here

- One-off bug fixes. The commit message is the record.
- Library version bumps. `git log` + `package.json` are the record.
- Refactors that don't change semantics. The diff is the record.
- Anything already documented in `CLAUDE.md` § Invariants — those are stronger than ADRs (they're rules), and an ADR for K-1..K-16 would just duplicate.

## Index

> 0031 is intentionally absent — its foundational-KB design was folded into ADR-0033.

| #    | Title                                              | Status   | Date       |
|------|----------------------------------------------------|----------|------------|
| 0001 | [Single-repo monolith for Phase 1](0001-single-repo-monolith.md) | accepted | 2026-04-29 |
| 0002 | [Medallion (Bronze / Silver / Gold) architecture](0002-medallion-architecture.md) | accepted | 2026-04-29 |
| 0003 | [Postgres RLS for tenant isolation](0003-postgres-rls-tenant-isolation.md) | accepted | 2026-04-29 |
| 0004 | [Centralised LLM gateway service](0004-llm-gateway-service.md) | accepted | 2026-04-29 |
| 0005 | [Append-only audit trail in `decision_audit_log`](0005-decision-audit-log.md) | accepted | 2026-04-29 |
| 0006 | [Defer standalone MCP server to Phase 2](0006-defer-mcp-server.md) | accepted | 2026-04-29 |
| 0007 | [Curated chat tool registry — no generic SQL executor](0007-curated-chat-tool-registry.md) | accepted | 2026-04-29 |
| 0008 | [Stateless chat in Phase 1.5](0008-stateless-chat-phase-1-5.md) | accepted | 2026-04-29 |
| 0009 | [Localhost-runner pilot deployment, not Kubernetes](0009-localhost-runner-pilot.md) | accepted | 2026-04-29 |
| 0010 | [Modular monolith Phase 1, selective microservices Phase 2+](0010-modular-monolith-then-microservices.md) | accepted | 2026-05-08 |
| 0011 | [Temporal.io for workflow orchestration](0011-temporal-for-workflow-orchestration.md) | proposed | 2026-05-08 |
| 0012 | [Postgres + ClickHouse polyglot persistence](0012-postgres-clickhouse-polyglot-persistence.md) | proposed | 2026-05-08 |
| 0013 | [Multi-tenancy via RLS + tenant_id everywhere (v4 formalize)](0013-rls-multi-tenancy-formalize-v4.md) | accepted | 2026-05-08 |
| 0014 | [At-least-once delivery + idempotency, not exactly-once](0014-at-least-once-plus-idempotency.md) | proposed | 2026-05-08 |
| 0015 | [Qwen-first LLM with pluggable vendor adapters](0015-qwen-first-with-pluggable-vendor-adapters.md) | accepted | 2026-05-08 |
| 0016 | [Vietnam region hosting (FPT Cloud / Viettel IDC)](0016-fpt-viettel-vn-hosting.md) | proposed | 2026-05-08 |
| 0017 | [Redis Streams event backbone Phase 1, Kafka Phase 2+](0017-redis-streams-phase-1-kafka-phase-2.md) | proposed | 2026-05-08 |
| 0018 | [Pluggable bot adapter (Telegram default Phase 1)](0018-pluggable-bot-adapter-telegram-default.md) | accepted | 2026-05-08 |
| 0019 | [Vectorless tree retrieval (PageIndex) + structured SQL RAG (DocSage)](0019-vectorless-tree-retrieval-and-structured-sql-rag.md) | proposed | 2026-05-08 |
| 0020 | [Accept CDFL v10/v11 as descriptive framework, port primitives only](0020-cdfl-v10-v11-verified-as-descriptive-framework.md) | accepted | 2026-05-17 |
| 0021 | [Trace-augmented reasoning via T-Cube distillation](0021-trace-augmented-reasoning-via-tcube.md) | accepted | 2026-05-17 |
| 0022 | [Org-tree first, workflow second, data third onboarding order](0022-org-first-onboarding-then-workflow-then-data.md) | accepted | 2026-05-17 |
| 0023 | [Heuristic tool-necessity gate (knowing-doing gap)](0023-knowing-doing-gap-tool-necessity-heuristic.md) | accepted | 2026-05-17 |
| 0024 | [Mem0-inspired ports into Stage 7 Memory (extend, don't replace)](0024-mem0-inspired-ports-into-stage-7-memory.md) | accepted | 2026-05-17 |
| 0025 | [Borrow MinerU patterns, do NOT vendor the library](0025-mineru-borrow-patterns-not-lib.md) | accepted | 2026-05-19 |
| 0026 | [Industry Template 3-Tier Bootstrap](0026-industry-template-3-tier-bootstrap.md) | accepted | 2026-05-20 |
| 0027 | [Spring Boot 4.x + Java 25 Phase 3 holster](0027-spring-boot-4x-java-25-phase3-holster.md) | accepted | 2026-05-23 |
| 0028 | [OpenTelemetry forward sync Phase 3 (1.28 / 0.49b2 holster)](0028-otel-forward-sync-phase3.md) | accepted | 2026-05-23 |
| 0029 | [UUIDv7 internal + ULID external, hybrid rollout](0029-uuidv7-ulid-hybrid-id-strategy.md) | accepted | 2026-05-23 |
| 0030 | [Memory trust layer (decay + verify + reinforce)](0030-memory-trust-layer.md) | accepted | 2026-05-27 |
| 0031 | _absent — foundational-KB design folded into 0033_ | — | — |
| 0032 | [Memory palace: consolidation + associative recall](0032-memory-palace-consolidation-associative-recall.md) | accepted | 2026-05-27 |
| 0033 | [Foundational knowledge: aging, history, CDFL \|OR\| coupling](0033-foundational-knowledge-aging-history-cdfl-or-coupling.md) | accepted | 2026-05-28 |
| 0034 | [Workflow item envelope + declarative node schema](0034-workflow-item-envelope-declarative-node-schema.md) | accepted | 2026-05-28 |
| 0035 | [Workflow typed connection ports + trigger nodes](0035-workflow-typed-ports-and-trigger-nodes.md) | accepted | 2026-05-28 |
| 0036 | [Memory axes cleanup + classic view + KB promotion](0036-memory-axes-cleanup-classic-view-kb-promotion.md) | accepted | 2026-05-28 |
| 0037 | [Tier-3: documents, contracts, approval chains + RBAC](0037-tier3-documents-contracts-approvals-rbac.md) | accepted | 2026-05-30 |
| 0038 | [Memory-safety stance: stack already memory-safe; no Java→Rust rewrite](0038-memory-safety-stance-no-rust-rewrite.md) | accepted | 2026-06-01 |
| 0039 | [Enterprise Document Repository (DMS) — 10-year hierarchical store](0039-enterprise-document-repository-dms.md) | accepted (building) | 2026-06-01 |
| 0040 | [Qwen Workflow Advisor (workflow evaluation)](0040-qwen-workflow-advisor.md) | accepted (building) | 2026-06-01 |
| 0041 | [EU AI Act control framework (trust-first, conformity-ready)](0041-eu-ai-act-control-framework.md) | accepted | 2026-06-03 |
| 0042 | [Confluence-style document structure: doc-type templates + typed metadata + labels + auto-index](0042-confluence-style-document-templates.md) | accepted (building) | 2026-07-05 |

## How to add a new ADR

```bash
N=$(printf "%04d" $(( $(ls docs/adr/0*.md 2>/dev/null | wc -l) + 1 )))
cp docs/adr/_template.md docs/adr/${N}-short-slug.md
# Edit the file. Append a row to the index above.
git add docs/adr/${N}-*.md docs/adr/README.md
git commit -m "docs(adr): ${N} short summary"
```

ADRs are **append-only by convention**. To revise a decision, mark the old one `Status: superseded by ADR-XXXX` and write a new one. Don't rewrite — future readers want to see what we believed and when.
