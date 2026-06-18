# Redis OOM / eviction storm

> **Severity:** P1 — auth slows down, idempotency-key dedup misses → potential double-write on retries.
> **Affects:** auth-service rate limit, K-13 idempotency-key dedup, MFA verify counter, llm_router consent cache.
> **First responder:** anh

## Symptoms

- Login latency P99 jumps from ~300 ms to ~2 s.
- `auth-service` logs show `redis.exceptions.ResponseError: OOM command not allowed when used memory > 'maxmemory'`.
- Same Idempotency-Key submitted twice within seconds → both get processed (dedup miss because key was evicted).
- Redis `INFO memory` shows `evicted_keys` rising rapidly.

## Quick triage (≤ 60 seconds)

- [ ] **Is Redis up?** `docker compose ps redis` → if down, `docker compose up -d redis`. Cold-start cache miss is annoying but not OOM.
- [ ] **Is the eviction policy sane?** `docker exec kaori-redis-1 redis-cli CONFIG GET maxmemory-policy` — should be `allkeys-lru` (per `docker-compose.yml`). If different, **GOTO Mitigation step 2**.
- [ ] **Is a single key set hogging memory?** Mitigation step 3.

## Diagnosis

```bash
# 1. Memory usage breakdown.
docker exec kaori-redis-1 redis-cli INFO memory | head -20

# 2. Eviction stats — rising = real OOM, flat = misconfigured maxmemory.
docker exec kaori-redis-1 redis-cli INFO stats | grep -E "evicted_keys|expired_keys|keyspace_hits|keyspace_misses"

# 3. Top key prefixes by count (Phase 1 has 4 prefixes: idem:, mfa:, consent:, ratelimit:).
docker exec kaori-redis-1 redis-cli --scan --pattern "idem:*" | head -5
docker exec kaori-redis-1 redis-cli DBSIZE

# 4. Big-key scan — finds the elephant if there is one.
docker exec kaori-redis-1 redis-cli --bigkeys
```

## Mitigation (fastest path)

1. **Quick reclaim** — flush only the rate-limit + cache prefixes (idempotency-key MUST be preserved during in-flight POSTs):

   ```bash
   # Safe: rate-limit keys are short-TTL, regenerable in seconds.
   docker exec kaori-redis-1 redis-cli --scan --pattern "ratelimit:*" | \
     xargs -I {} docker exec kaori-redis-1 redis-cli DEL {}
   ```

   Verify: `INFO memory` shows reclaim. If still OOM, GOTO 2.

2. **Confirm eviction policy is `allkeys-lru`** — without it, `noeviction` will reject writes:
   ```bash
   docker exec kaori-redis-1 redis-cli CONFIG SET maxmemory-policy allkeys-lru
   ```
   This is runtime-only; the persistent config in `docker-compose.yml` already sets it. If somehow drifted, fix the compose file.

3. **Bump maxmemory** — pilot Redis is sized 512 MB (compose). If anh's laptop has headroom:
   ```bash
   docker exec kaori-redis-1 redis-cli CONFIG SET maxmemory 1gb
   ```
   Permanent fix in `docker-compose.yml`. Coordinate with Ollama / Postgres total RAM budget on a 16 GB laptop.

4. **If a single key is pathological** (from `--bigkeys`) — investigate before deleting. Most likely culprit: a tenant's MFA verify counter that wasn't TTL'd correctly. Delete the offending key only after confirming it's not auth-state-bearing.

## Permanent fix

- Audit TTLs on every `SET` in code: idempotency-key 24 h (per K-13), rate-limit 60 s, MFA verify counter 15 min, consent cache 60 s. Any `SET` without TTL is a bug.
- Consider dedicated Redis instances per concern (separate ratelimit Redis from idempotency Redis) when pilot scales beyond 5 tenants.
- Prometheus alert: `redis_memory_used_bytes / redis_memory_max_bytes > 0.85` for 5 min.

## Postmortem hooks

If OOM fires twice, capture:
- Which prefix grew unbounded? (Likely a missed TTL bug.)
- Was the workload anomalous (e.g., a load test pointed at staging by mistake)?
- Did K-13 dedup actually miss in production? Check `decision_audit_log` for duplicate decision_id rows on the same minute.
