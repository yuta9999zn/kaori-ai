# ADR-0009 — Localhost-runner pilot deployment, not Kubernetes

> **Status:** accepted
> **Date:** 2026-04-29 (originally landed PR #89)
> **Deciders:** Nguyen Truong An
> **Related:** `kaori-start.bat` · `kaori-stop.bat` · `kaori-status.bat` · `docker-compose.yml` · Memory: `project_pilot_deployment.md`

## Context

Phase 1 pilot needs to run somewhere. The natural Phase 2 target is Kubernetes (EKS / GKE) with proper HA, autoscaling, and external load balancers. But Phase 1 pilot has:

- **1 dev (anh)** running ops solo.
- **3–5 pilot tenants** at once, low concurrent traffic.
- **Hardware: a single 16 GB laptop**, currently anh's primary dev machine.
- **No paying customers yet** — every dollar of cloud spend comes from anh's pocket.

Three options:

1. **Cloud K8s** — EKS small cluster, ~$200–400/mo for control plane + 2 spot t3.medium workers + RDS. Realistic but burns runway.
2. **Cloud VPS / single node** — DigitalOcean / Hetzner $20–40/mo, Docker Compose on a 4 GB / 8 GB box. Fits budget but Qwen 7B needs GPU or fast CPU.
3. **Localhost runner** — anh's laptop, Docker Compose, 4 batch scripts (`kaori-start.bat`, `-stop`, `-status`, plus init). Free, fast iteration, but not 24×7.

## Decision

Phase 1 pilot runs on **anh's laptop via the localhost runner** (4 batch scripts, PR #89). Default LLM is **Qwen 2.5 7B** (sized for 16 GB RAM with the rest of the stack). Pilot UAT sessions are **scheduled** — anh starts the stack ~30 min before a session, runs the demo, stops it after.

Cloud deploy is deferred until: paying customer signed, OR ≥3 concurrent pilot tenants needing 24×7, OR Phase 2 kicks off.

## Consequences

### Positive

- **Zero cost.** No cloud bill before revenue.
- **Fast iteration.** Code change → `kaori-start.bat` → 30 s warm-up → demo. No CI/CD pipeline waiting for ECS / Helm rollouts.
- **Anh's machine is the gold environment.** Bugs reproducible by definition. No "works in dev, breaks in prod" until prod actually exists.
- **Qwen 7B fits.** 8 GB model + 4 GB Postgres/Redis/Kafka/Ollama runtime + 4 GB OS + Chrome + Claude Code = workable on 16 GB.

### Negative / accepted trade-offs

- **No 24×7 availability.** Pilot users can only demo when anh starts the stack. Acceptable: pilot UAT is scheduled, not self-serve.
- **Qwen 7B is weaker than 14B** (Sprint 8 plan §10 Q7). Tool calling reliability ~80% vs ~95% on 14B. Documented in `docs/uat/CHAT_PANEL.md` §H — pilot caveat.
- **No backups, no disaster recovery.** A laptop disk failure = lose pilot demo data. Mitigation: pilot tenants are seeded fresh each session; no persistent customer data on the laptop yet.
- **Anh's machine becomes the SPOF.** If laptop dies the day before a demo, the pilot stops. Mitigation: `docker-compose up` on any 16 GB Windows / macOS laptop reproduces the env.

### Neutral / follow-ups

- **Trigger to move to cloud**: first paying customer signs (committed MRR ≥ 1M VND/mo) — single VPS DigitalOcean, $20/mo. Or ≥3 concurrent tenants — 4 GB VPS not enough, jump to small K8s.
- **Trigger to upgrade Qwen 7B → 14B**: customer-reported chat tool calling failures > 1/session OR migration to a 32 GB cloud box (no upgrade cost).
- **Migration path**: `docker-compose.yml` is the source of truth. Same compose runs on a VPS (single-node) or as a starting point for K8s manifests when the day comes. No Phase-1 lock-in.

## Alternatives considered

- **Cloud K8s from day 1** — Rejected. ~$300/mo before the first paying customer is irresponsible. K8s also adds operational complexity (cert-manager, ingress controller, Prometheus stack) that 1 dev doesn't have time for during pilot.
- **Cloud single VPS now** — Rejected for now. Same Qwen RAM constraint applies (need 16 GB box, ~$60/mo on Hetzner). Defer until pilot signals demand.
- **Docker Desktop with hosted Postgres (Neon / Supabase)** — Considered. Rejected because: (a) RLS is migration-bound to a specific Postgres role + grant pattern; verifying that on a managed DB is fiddly; (b) latency to a hosted DB makes the localhost demo feel slower than fully-local. Not worth the bookkeeping.

## References

- PR #89 (localhost runner scripts)
- Memory: `project_pilot_deployment.md`
- `docker-compose.yml`
- `docs/uat/CHAT_PANEL.md` §H Qwen 7B caveat
- `CLAUDE.md` §11 Development Setup
