# ADR-NNNN — {{Decision title in 5-9 words}}

> **Status:** proposed | accepted | superseded by ADR-XXXX | deprecated
> **Date:** YYYY-MM-DD
> **Deciders:** {{names — at least one}}
> **Related:** {{ADR / spec / PR / issue links}}

## Context

What is the issue that we're seeing that motivates this decision? Plain prose, 1–3 paragraphs. Pull in numbers when they matter (latency, error rate, cost, headcount).

State the **forces in tension**: what's pulling us toward option A, what's pulling us toward option B. The next reader will only believe the choice if they see the conflict it resolved.

## Decision

What we're going to do, in one paragraph. Active voice, present tense ("We use Kafka with 24 partitions on `kaori.ingest.bronze`."). One decision per ADR — split if you find yourself writing "and also".

## Consequences

### Positive

- {{What gets easier or faster}}
- {{What risk we eliminate}}

### Negative / accepted trade-offs

- {{What gets harder}}
- {{What we deliberately give up}}

### Neutral / follow-ups

- {{What we'll need to revisit / monitor}}
- {{Triggers that would make us reconsider}}

## Alternatives considered

Brief — one paragraph each. **Why we didn't pick them**, not just what they were.

- **Alt 1**: …
- **Alt 2**: …

## References

- {{links to specs, runbooks, external articles, PRs}}

---

**Editing note** — ADRs are append-only by convention. If a decision is superseded, set `Status: superseded by ADR-XXXX` here and write the new one. Don't rewrite history; future readers want to see what we believed and when.
