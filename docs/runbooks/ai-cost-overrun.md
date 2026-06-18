# AI cost overrun (external LLM bill spike)

> **Severity:** P1 — cost incident; not user-visible until next bill.
> **Affects:** Anthropic / OpenAI bill. Internal Qwen has zero per-call cost.
> **First responder:** anh

## Symptoms

- Anthropic / OpenAI dashboard shows daily token usage 5×+ baseline.
- `decision_audit_log` filtered by `method='external'` shows a sudden burst of rows.
- A specific tenant's `decision_audit_log.reasoning` shows runaway loops (same prompt, dozens of calls within minutes).
- Provider rate-limit warnings in `llm-gateway` logs.

## Quick triage (≤ 60 seconds)

- [ ] **Is this a single tenant?** SELECT below — if one `enterprise_id` accounts for >70% of the spike, isolate them.
- [ ] **Is this from chat, analysis, or schema mapping?** `decision_audit_log.subject` tells us. Chat is Qwen-only by design (CLAUDE.md §8 Rule 7); if chat shows up in `method='external'`, that's a regression.
- [ ] **Did a code change just ship?** Especially anything touching `consent_external` defaults or the chat agent loop's MAX_HOPS.

## Diagnosis

```bash
# 1. Per-tenant external call volume in the last 24 h.
docker exec kaori-postgres-1 psql -U kaori -d kaori -c "
  SELECT enterprise_id, COUNT(*) AS n,
         MIN(created_at) AS first, MAX(created_at) AS last
    FROM decision_audit_log
   WHERE method = 'external'
     AND created_at >= NOW() - INTERVAL '24 hours'
   GROUP BY enterprise_id
   ORDER BY n DESC LIMIT 10;
"

# 2. Per-decision-type breakdown for the noisy tenant.
docker exec kaori-postgres-1 psql -U kaori -d kaori -c "
  SELECT decision_type, llm_provider, COUNT(*) AS n,
         SUM(LENGTH(chosen_value)) AS total_completion_chars
    FROM decision_audit_log
   WHERE method = 'external'
     AND enterprise_id = '<tenant>'
     AND created_at >= NOW() - INTERVAL '24 hours'
   GROUP BY decision_type, llm_provider
   ORDER BY n DESC;
"

# 3. Look for runaway tool loops in chat (should be zero — chat is Qwen).
docker exec kaori-postgres-1 psql -U kaori -d kaori -c "
  SELECT enterprise_id, subject, COUNT(*) AS n
    FROM decision_audit_log
   WHERE decision_type = 'chat.tool_call'
     AND created_at >= NOW() - INTERVAL '1 hour'
   GROUP BY enterprise_id, subject
  HAVING COUNT(*) > 20
   ORDER BY n DESC;
"

# 4. Check llm_router consent cache for any tenant who recently flipped.
docker logs kaori-ai-orchestrator-1 --tail 200 | grep -E "consent_lookup|consent_external"
```

## Mitigation (fastest path)

1. **Single-tenant runaway** — flip their consent flag to false:
   ```sql
   UPDATE tenant_settings SET consent_external_ai = FALSE
    WHERE enterprise_id = '<tenant>';
   -- Cache TTL is 60 s; a wait ensures the next call routes to Qwen.
   ```
   Then reach out to the customer: "We capped your external AI usage temporarily. Re-enable in Settings if intentional."

2. **Code-change regression** (chat path leaking to external, MAX_HOPS too high, etc.) — roll back the offending commit; diagnose with full repro after the bleeding stops.

3. **Provider-side mistake** (e.g., billing alert misconfigured) — verify via provider dashboard before assuming a real spike.

4. **Hard kill switch** — set `EXTERNAL_AI_ENABLED=false` in llm-gateway env and restart. All tenants drop to Qwen. Use only if can't isolate the source.
   ```bash
   # Edit .env, then:
   docker compose up -d llm-gateway
   ```
   Communicate to consenting tenants that external LLM is paused.

## Permanent fix

- Phase 2 F-063: per-tenant token budget enforced at `llm-gateway` (today this is a TODO at `services/llm-gateway/router.py:57`). Once F-063 lands, runaway is throttled before it can spike the bill.
- Add a daily cron that emails anh if `SUM(method='external')` for any tenant exceeds 2× the 7-day moving average.
- The chat agent's `MAX_HOPS=3` + `MAX_TOOL_CALLS_PER_HOP=4` already cap a single chat turn; verify these constants haven't drifted in `services/ai-orchestrator/chat/agent.py`.

## Postmortem hooks

If cost overrun fires for the same root cause twice, capture:
- Tenant signal — did they flag the upgrade themselves, or did we discover via the bill?
- Time from spike start → mitigation. (Bill-after-the-fact = this metric is hours; alert-driven = should be minutes.)
- Was the prompt bloat from a single oversized run (one CSV with 500 columns?) or sustained drip?
