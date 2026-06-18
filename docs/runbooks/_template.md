# {{Symptom}}

> **Severity:** P0 | P1 | P2 | P3
> **Affects:** {{which user-facing feature degrades}}
> **First responder:** anh (single dev). Future: rotation.

## Symptoms

What the user / dashboard / log shows. Be specific — exact error message, exact metric name. The on-caller is searching for the symptom string in this file at 2 AM.

## Quick triage (≤ 60 seconds)

Decision tree in 3-5 bullets:

- [ ] **Is anything still working?** (e.g., dashboard loads but chat fails → llm-gateway specific)
- [ ] **Did this start after a deploy?** → roll back first, diagnose later.
- [ ] **Is the upstream provider OK?** (Anthropic status page, Ollama logs, Postgres connections)

## Diagnosis

Concrete commands. Copy-paste-runnable. No "check if Kafka is OK" without saying *how*.

```bash
# Example
docker compose ps                          # which containers running
docker logs kaori-llm-gateway-1 --tail 100
curl -fsS localhost:8095/health
```

## Mitigation (fastest path to "users unblocked")

Numbered steps. Each step has a verification command so anh knows it actually worked.

1. {{Action}}
2. {{Verify}}: `command that prints OK on success`

Be honest about what's a band-aid vs. a fix. "Restart the container" is fine for mitigation; tag it as such.

## Permanent fix

What needs to change in the code / infra to stop this recurring. Link to the issue / PR if work is queued.

## Postmortem hooks

If this fires more than 2× in a month, escalate to a postmortem. Capture:

- Timeline (when did it start, when was it noticed, when was it mitigated)
- Customer impact (how many users, how many minutes)
- What we'd change in detection (what alert would have caught this earlier)
