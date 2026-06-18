# `zalo_metadata/` — Zalo Business API metadata reader (PM-EVT-003)

> **Status:** skeleton (P1-S3). Full impl P1-S7.
> **Tag:** CRITICAL Vietnam — Zalo is the dominant ops channel for VN SMEs.

Reads message **metadata** (NOT content) from a tenant's Zalo Business
account so Process Mining can surface customer-service + order-confirmation
workflows that happen entirely in Zalo.

## Privacy boundary (PM-PII-013 mining session approval)

Captured:
- sender / recipient ids
- timestamp + thread id + reply-to id
- message type (text / image / file / sticker / call)
- read receipt timestamps

NOT captured:
- message body
- file content
- location data
- payment intents

Customer must explicitly opt this connector in via Mining Session
Approval Gate before any read happens.

## Phase 1 v4 P1-S3 scope

Skeleton class + interface only.

## Phase 1 v4 P1-S7 scope

- Zalo Open Platform OAuth flow (refresh token in Vault)
- Pull-based metadata retrieval (REST API, no streaming yet)
- PII normalization (Zalo user_id → internal stable hash)
- Thread + reply-to graph reconstruction

## References

- `docs/strategic/WORKFLOW_SYSTEM.md` PART IV Phần 11 (Event Log Sources) + Phần 13.3 (Privacy Architecture)
- `docs/BACKLOG_V4.md` — PM-EVT-003 (P1-S7)
- Zalo OA docs — https://developers.zalo.me/docs/api/official-account-api
