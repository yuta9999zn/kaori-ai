# LLM gateway down (Qwen / chat / analysis fail)

> **Severity:** P1 — chat returns error, analysis runs stall, schema mapping LLM fallback fails. App still usable for pipeline upload + dashboard reads.
> **Affects:** `/chat/{enterprise,platform}/stream` (Sprint 8), F-018 schema LLM fallback, F-019 cleaning rule LLM, F-021 narrative generation, F-025 strategy.
> **First responder:** anh

## Symptoms

- Chat panel shows error bubble "LLM Gateway lỗi. Vui lòng thử lại."
- Analysis runs sit at `status='running'` indefinitely; logs show `httpx.ConnectError: All connection attempts failed` from `ai-orchestrator → llm-gateway`.
- `/health` on llm-gateway returns 503 or times out.
- Ollama logs show `out of memory` (most common on the 16 GB pilot laptop) OR `model not loaded`.

## Quick triage (≤ 60 seconds)

- [ ] **Is `llm-gateway` container up?** `docker compose ps llm-gateway` — if exited, restart loop possible (GOTO Mitigation 1).
- [ ] **Is Ollama running and has the right model pulled?**
  ```bash
  docker compose ps ollama
  docker exec kaori-ollama-1 ollama list
  ```
  Pilot expects `qwen2.5:7b` (16 GB box) or `qwen2.5:14b` (32 GB+ box). **No model = no inference.** GOTO Mitigation 2.
- [ ] **Did anh just push a llm-gateway code change?** Roll back the container image to the previous tag; diagnose later.
- [ ] **Is this an external-only outage?** (Anthropic / OpenAI down) — `EXTERNAL_AI_ENABLED=false` and Qwen up means default path still works; only consenting tenants hit external.

## Diagnosis

```bash
# 1. Gateway health + recent errors.
curl -sS localhost:8095/health
docker logs kaori-llm-gateway-1 --tail 100

# 2. Ollama health + memory pressure.
curl -sS localhost:11434/api/tags    # lists pulled models
docker stats --no-stream kaori-ollama-1     # check MEM% — Qwen 7B sits ~6-8 GB; 14B ~10-12 GB.

# 3. Probe gateway end-to-end with a known-good payload.
curl -sS -X POST localhost:8095/v1/infer \
  -H 'Content-Type: application/json' \
  -d '{"task":"smoke","prompt":"hello","enterprise_id":"00000000-0000-0000-0000-000000000001"}'

# 4. Audit log — was the last successful call recent? If yes, this is a fresh outage.
docker exec kaori-postgres-1 psql -U kaori -d kaori -c \
  "SELECT created_at, decision_type, llm_provider, method
     FROM decision_audit_log
    WHERE decision_type='llm_call' ORDER BY created_at DESC LIMIT 5;"
```

## Mitigation (fastest path)

1. **Container down / restart-looping** —
   ```bash
   docker compose restart llm-gateway
   docker logs -f kaori-llm-gateway-1
   ```
   Watch for `kaori.llm_gateway.starting` → `Uvicorn running on 0.0.0.0:8095`. ~5 s.

2. **Ollama OOM (most common on 16 GB laptop)** — Qwen + Postgres + Kafka + Chrome ate the RAM.
   - Stop heavyweight desktop apps (Chrome with many tabs, IDE). `docker stats` should show ~3 GB headroom.
   - If still OOM: switch to a smaller model temporarily.
     ```bash
     docker exec kaori-ollama-1 ollama pull qwen2.5:3b
     # Edit .env: OLLAMA_MODEL=qwen2.5:3b
     docker compose up -d llm-gateway       # picks up new env
     ```
     ⚠ 3B is significantly worse at chat tool calling. Document in the demo session that we're running fallback model.

3. **Model not loaded** —
   ```bash
   docker exec kaori-ollama-1 ollama pull qwen2.5:7b   # ~5 GB download on first pull
   ```
   First call after pull warms the model into memory (~30 s); subsequent calls fast.

4. **External provider outage but Qwen healthy** — no action needed; tenants without `consent_external_ai` see no impact, tenants with it consented gracefully fall back to Qwen (per `services/llm-gateway/providers.py:invoke` — fallback path warns + downgrades to internal).

## Permanent fix

- Pilot 16 GB laptop is at the edge for Qwen 7B + the rest. Document the "stop Chrome before pilot demo" pre-flight in `docs/uat/`.
- Add health-check container restart policy: `restart: on-failure:3` in compose so a one-off OOM auto-recovers.
- Phase 2 F-063: per-provider circuit breaker so Anthropic-down doesn't 502 the whole `/v1/infer` even for non-consenting tenants (today's fallback handles this; F-063 makes it explicit).

## Postmortem hooks

If gateway down fires twice in a month, capture:
- Was the trigger Ollama OOM, container crash, or provider 5xx?
- Did the chat agent's `MAX_HOPS=3` cap save us from cascading retries?
- Should we pull the smaller model proactively as a fallback rather than reactively?
