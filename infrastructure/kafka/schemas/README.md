# Kafka Event Schemas

Each `.json` file in this directory is a [JSON Schema 2020-12](https://json-schema.org/draft/2020-12/release-notes.html) describing the payload of one Kaori Kafka topic. The file name MUST match the topic name (`<topic>.json`).

## Why these exist

Per `CLAUDE.md` Tenet #8, Kafka contracts are additive-only. Before this directory existed that rule lived only in the developer's head; producers and consumers agreed on payload shapes via convention and the documentation block at the bottom of `infrastructure/kafka/topics.yml`. The schemas here turn the convention into a runtime check (validated on every `enqueue_event` and on every consumer dispatch) and into a CI guard (`scripts/check-kafka-contracts.py` blocks PRs that rename or remove fields).

## What "additive-only" means here

| Change | Allowed? | Why |
|---|---|---|
| Add a new optional field | ✅ | Backward compatible. Old consumers ignore the field; new ones use it. |
| Add a new required field | ⚠️ | Allowed by the lint **only when the topic is brand new** (i.e. the schema file was added in the same PR). Adding `required` to an existing topic breaks every running consumer. |
| Mark an existing optional field required | ❌ | Producers may still be sending payloads without it. Stage in two PRs: producers start emitting → consumers move the field to required next release. |
| Rename a field | ❌ | Equivalent to remove-then-add. Use a deprecation window: add the new name as optional, dual-emit, drop the old name later. |
| Remove a field | ❌ | Same reason as rename. Dual-emit + deprecation. |
| Tighten a type (`string` → `enum`) or narrow a `format` | ❌ | Existing producers may send values outside the new constraint. |
| Loosen a type (`integer` → `number`) | ⚠️ | Allowed by the lint, but think twice — consumers that did `int(...)` will start crashing. |

The lint (`scripts/check-kafka-contracts.py`) enforces the ❌ rows by diffing the committed file against `main` (or `HEAD~1` when run locally).

## Required vs optional

Topics are consumed by services on different release schedules. The runtime validator treats `required` strictly:

- **Producer side** (`shared.event_schema.validate_event` called inside `enqueue_event`): missing required field → **raise**, the caller's transaction rolls back, the bug surfaces immediately at the producer side rather than rotting silently in the queue.
- **Consumer side** (validation before handler dispatch): missing required field → **DLQ** (`kaori.dlq.<topic>`), the consumer logs `event.schema.invalid` + commits the offset and moves on. We never crash the consumer over a bad payload — that turns one bad row into a head-of-line block.

## Adding a new topic

1. Pick a name under the `kaori.<domain>.<event>` namespace. Register it in `infrastructure/kafka/topics.yml`.
2. Add `infrastructure/kafka/schemas/<topic>.json` with the payload shape.
3. Add the constant to `services/<svc>/shared/kafka_topics.py` for every service that produces or consumes the topic.
4. Producers: call `enqueue_event(...)` with the topic constant — validation is automatic.
5. Consumers: validation runs on receive; nothing to wire by hand.

## Modifying an existing schema

The lint refuses anything beyond "additive". For breaking changes, version the topic instead:

```
kaori.pipeline.silver.complete         (v1, current)
kaori.pipeline.silver.complete.v2      (new shape; producers dual-emit; old topic deleted later)
```

This costs less than a contested PR and gives consumers a deprecation window.
