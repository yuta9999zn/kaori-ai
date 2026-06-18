# `excel_filesystem/` — Excel revision watcher (PM-EVT-002)

> **Status:** skeleton (P1-S3). Full impl P1-S7.

Vietnamese SMEs run most ops in Excel on shared drives. Customer doesn't
adopt the Kaori UI overnight, but their workflow IS the Excel edit
history. This connector reads file changes + revision metadata so
Process Mining can reconstruct ops without forcing a workflow tool change.

## Sources of edit metadata

Phase 1.5+:
- **OneDrive revision API** — file rev history with editor + timestamp
- **SharePoint version history** — version + comment + editor
- **Local filesystem mtime** — fallback (no editor identity)

## Phase 1 v4 P1-S3 scope

Skeleton class + interface only.

## Phase 1 v4 P1-S7 scope

- watchdog filesystem observer for new/modified files
- OneDrive Graph API or SharePoint REST for revision pull
- openpyxl row-diff to detect WHICH cells changed (not just file mtime)
- PII redaction on cell values before publish

## References

- `docs/strategic/WORKFLOW_SYSTEM.md` PART IV Phần 11
- `docs/BACKLOG_V4.md` — PM-EVT-002 (P1-S7)
