# ADR-0038 — Memory-safety stance: stack is already memory-safe; no Java→Rust rewrite

> **Status:** accepted
> **Date:** 2026-06-01
> **Deciders:** Nguyen Truong An
> **Related:** ADR-0010 (service split + Java gateway/auth) · ADR-0015 (LLM stack) · §2 CLAUDE.md (Tech Stack) · CISA/NSA "The Case for Memory Safe Roadmaps" (2023)

## Context

US infrastructure-security bodies (CISA, NSA, FBI, plus the 2024 White House ONCD report "Back to the Building Blocks") have publicly pushed software away from **memory-unsafe languages** toward **memory-safe** ones, citing that ~70% of severe CVEs are memory-safety bugs (buffer overflow, use-after-free, out-of-bounds). This is widely summarised in the press as "C/C++ is a national-security hazard, rewrite in Rust."

Question raised: should Kaori migrate its backend from **Java / Spring Boot to Rust**?

The premise behind the question conflates two different things, so the decision rests on one factual clarification.

## The clarification

**The guidance targets C and C++ specifically** — languages with manual memory management and no bounds checking. It does **not** target garbage-collected / bounds-checked languages.

A language is "memory-safe" if the runtime prevents the bug classes above. By that definition the memory-safe set includes: **Rust, Java, Kotlin, C#, Go, Python, JavaScript/TypeScript, Swift.** The unsafe set is essentially **C and C++** (and assembly).

→ **Java is on the SAFE side, in the same category as Rust.** "Rewrite C in Rust" and "Java is memory-unsafe" are unrelated claims; the second is false.

## Kaori's actual memory-safety posture

| Component | Language | Memory-safe? |
|---|---|---|
| api-gateway | Java (Spring Cloud Gateway) | ✅ JVM — GC, bounds-checked, no raw pointers |
| auth-service | Java (Spring Security) | ✅ JVM |
| data-pipeline · ai-orchestrator · llm-gateway · notification | Python (FastAPI) | ✅ CPython — GC, no manual memory |
| frontend | TypeScript / Next.js | ✅ V8 |
| PostgreSQL · Redis · Kafka | infra (vendor binaries) | n/a — operated, not authored; patched via normal upgrades |

**There is no C/C++ in code Kaori authors.** The stack already satisfies the CISA/NSA memory-safety guidance. There is zero memory-safety risk of the kind the news describes.

## Decision

**Do NOT migrate Java/Spring Boot (or Python) to Rust.** Keep the current stack.

Rationale:
- **No safety gain.** Java and Python are already memory-safe; a Rust rewrite removes a risk that does not exist here.
- **Large cost, high risk.** Spring Security (MFA, sessions, JWT RS256, lockout) and Spring Cloud Gateway (routing, rate-limit, idempotency, JWT filter, RLS header forwarding — K-7/K-12) have no drop-in Rust equivalent; a rewrite is multi-month, halts the roadmap, and reintroduces bugs into systems that run today.
- **Wrong tool fit.** Rust's edge is latency-/throughput-critical or systems code where GC pauses hurt. A B2B-SaaS gateway/auth is not that profile; the JVM is well within budget.

**When Rust WOULD be reconsidered (future, case-by-case):** a *new, greenfield* performance-critical service (e.g. a high-throughput ingestion proxy) where measured GC/latency is a real bottleneck — written in Rust *alongside* the existing services, never a big-bang rewrite. That would get its own ADR with benchmarks justifying it.

## Consequences

### Positive
- Settles the question with facts, not a rewrite. Roadmap continues uninterrupted.
- Gives a clear, citable answer for security questionnaires, audits (SOC 2), customer/investor due-diligence: *"Kaori is written entirely in memory-safe languages (Java/JVM, Python, TypeScript) — no C/C++ — and meets the CISA/NSA memory-safe-roadmap guidance. No memory-unsafe code is authored or shipped."*

### Neutral / follow-ups
- The real memory-safety hygiene that DOES apply to us is **dependency/vendor patching** (PostgreSQL, Redis, Kafka, the JVM, native Python wheels are C under the hood) — covered by the existing Dependabot + upgrade cadence (see the cryptography 42→48 CVE bump as precedent). That's where memory-safety effort is actually spent, not in a language rewrite.
- If a true latency hotspot is ever measured, evaluate a scoped Rust microservice then — with numbers.
