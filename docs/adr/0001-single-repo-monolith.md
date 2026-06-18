# ADR-0001 — Single-repo monolith for Phase 1

> **Status:** accepted
> **Date:** 2026-04-29
> **Deciders:** Nguyen Truong An (founder/dev)
> **Related:** `CLAUDE.md` §3 Project Structure · `docs/cau-truc-du-an-10diem` (external reference)

## Context

Kaori is currently developed by **one person + one AI assistant**. The system has 6 backend services (Java + Python mix), one Next.js frontend, and a shared infra stack (Postgres + Redis + Kafka + Ollama). The classic enterprise stance — "polyrepo, one repo per service" — would mean 8+ repos, 8+ CI configs, 8+ release pipelines, and a contracts repo on top.

Two forces in tension:

1. **Coordination cost.** Polyrepo wants `contracts/` to be its own repo so multiple teams can version it. We have no second team.
2. **Forking cost.** Single repo means a wrong commit can theoretically affect any service. With 1 dev that's already true at the cognitive level.

A reference doc (`cau-truc-du-an-10diem`) explicitly notes: *"Cấu trúc 10/10 phù hợp team ≥5 người, dự án ≥1 năm. Với MVP/prototype dùng 30% là đủ."*

## Decision

We keep **one Git repository** containing all services, the frontend, infra-as-code, and docs. Inside the repo:

- `services/` — flat, one folder per service (no `services/java/` vs `services/python/` split until we have ≥10 services)
- `frontend/` — Next.js app (no `apps/` rename until a second app appears)
- `infrastructure/`, `docs/`, `scripts/`, `config/` — top-level
- `docs/api-specs/*.openapi.json` is our contracts surface; CI gates on `dump_openapi.py --check` + `gen-api-types.mjs --check`

## Consequences

### Positive

- One `git clone` to onboard. One `docker compose up` to run everything.
- Cross-service refactors (e.g., adding `tools` to `InferRequest` + chat agent in PR1) ship as one atomic change.
- `CLAUDE.md` is one file in one place; AI agents don't need a multi-repo strategy.
- CI matrix is small (~4 jobs) and fast.

### Negative / accepted trade-offs

- **No per-service release cadence.** All services share a `main` branch. We can't ship `auth-service v2.5` while pinning `data-pipeline` at `v2.3`. Acceptable while team = 1.
- **No per-service permissions.** A drive-by collaborator with repo write access has write to everything. Acceptable while collaborators = 0.
- **Repo will get big.** ~80 MB now; budget 1 GB before splitting becomes urgent (LFS for binary fixtures if it pushes earlier).

### Neutral / follow-ups

- Trigger to split: ≥3 contributors with diverging release cadence, OR repo > 1 GB, OR a service starts pulling in a heavyweight stack (e.g., GPU model serving) that drags clone times.
- When we split, the order is: extract `contracts/` first (separate version line), then any service that has crossed the boundary.

## Alternatives considered

- **Polyrepo from day 1** — Rejected. No second team to justify the coordination overhead. Cross-cutting changes (e.g., adding `K-15` audit invariant to every service) would each require N PRs across N repos, and would not be atomic.
- **Monorepo with Bazel/Nx/Turborepo** — Rejected for now. Native build tools (Maven, uv, npm) cover the 6-service case fine. Re-evaluate if incremental build times exceed 5 min on a clean checkout.
- **Vendor a contracts/ subtree** — Rejected. We don't have an external consumer of contracts; `docs/api-specs/` + drift-check CI is sufficient.

## References

- `CLAUDE.md` §3
- `cau-truc-du-an-10diem.docx` (external) §11.4 "Monorepo hay polyrepo?"
- Memory: `project_structure_incremental.md` (Đợt B/C trigger conditions)
