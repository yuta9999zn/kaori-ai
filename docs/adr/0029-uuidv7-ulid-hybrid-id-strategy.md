# ADR-0029 — UUIDv7 internal + ULID external, hybrid rollout

> **Status:** accepted
> **Date:** 2026-05-23
> **Deciders:** anh Trường An
> **Related:** mig 104, `shared/ids.py`, CLAUDE.md K-21, ADR-0013 (RLS), ADR-0025 (pattern-borrow precedent)

## Context

Through 100 migrations Kaori đã dùng `UUID PRIMARY KEY DEFAULT gen_random_uuid()` ở mọi bảng — tổng cộng ~50 bảng với khóa chính UUIDv4 hoàn toàn random. Postgres B-tree là index có thứ tự, nên insert một UUIDv4 ngẫu nhiên rơi vào trang ngẫu nhiên, gây phân mảnh chỉ mục, write-amplification, và cache miss ngày càng tệ khi bảng phình. Ở mức trăm-nghìn-hàng-mỗi-ngày của Phase 2 (workflow_run, decision_audit_log, adoption_snapshots) chưa thấy đau, nhưng ở mức Phase 3 mục tiêu 1000 khách × hàng trăm workflow/ngày, locality kém của v4 sẽ trở thành bottleneck đo được — Percona đo write throughput cải thiện ~30% với UUIDv7 so v4 trên cùng phần cứng.

Mặt căng thẳng:
- **Pull về v7 cho mọi bảng**: nhất quán, ngay lập tức gặt được locality. Nhưng phá vỡ rule `do NOT restructure mid-pilot` (memory: `project_structure_incremental.md`), yêu cầu rewrite 100 migration headers, FK update, downtime — không đáng cho 10-15 khách hiện tại.
- **Pull về giữ v4 mãi**: zero risk, zero work. Nhưng đẩy debt sang Phase 3 lúc còn ít time hơn nhiều.
- **Pull về ULID cho mọi external ID**: human-readable trong URL/log → onboarding/support dễ hơn (Crockford 26 ký tự đọc được, không có I/L/O/U gây nhầm). Nhưng full-table chuyển TEXT(26) làm FK nặng hơn, mọi join lookup chậm hơn.

Một câu hỏi phụ là generator: Postgres 15 chưa native `gen_uuidv7()` (chỉ có ở Postgres 18 trở lên). Lựa chọn: cài extension `pg_uuidv7` (deployment overhead, FPT Cloud Postgres managed có thể không hỗ trợ), generate ở app layer (mất `DEFAULT` clause → vi phạm writer-path coupling rule `feedback_migration_writer_path_coupling.md`), hoặc viết plpgsql function trong migration.

## Decision

Áp dụng **hybrid rollout**:

1. **Bảng mới Phase 2.9+** dùng `DEFAULT gen_uuid_v7()` thay cho `gen_random_uuid()`. Bảng hiện có giữ UUIDv4, không migrate dữ liệu.
2. **External-facing public IDs** (URL slugs, customer-visible references, log line IDs) dùng `TEXT(26) DEFAULT gen_ulid()`. Áp dụng selective cho cột mới khi nhu cầu human-readability rõ ràng (vd `decision_audit_log.public_id`, `workflow_run.public_id`) — không thay khóa chính.
3. **Generator**: viết hai plpgsql function `gen_uuid_v7()` + `gen_ulid()` trong migration 104, dùng `gen_random_bytes()` từ extension `pgcrypto` đã có sẵn từ `001_init.sql`. Mirror Python ở `services/ai-orchestrator/shared/ids.py` cho test deterministic và caller cần biết ID trước INSERT.

Cả hai function dùng `clock_timestamp()` (không phải `now()`) để nhiều row trong cùng transaction vẫn được timestamp khác nhau. Không monotonic trong cùng millisecond — random tail 74 bit (v7) / 80 bit (ULID) làm collision không đáng lo, và lợi ích B-tree locality vẫn nguyên.

## Consequences

### Positive

- **B-tree locality cho bảng mới**: insert UUIDv7 chèn vào trang gần đây nhất thay vì ngẫu nhiên → ~30% write throughput, ít vacuum hơn.
- **Writer-path coupling giữ nguyên**: `DEFAULT gen_uuid_v7()` clause work giống `gen_random_uuid()` cũ, INSERT statement không cần thay đổi → mọi pattern đã quen vẫn hoạt động.
- **Zero data migration**: cột v4 cũ ngồi cạnh cột v7 mới một cách hoà bình; Postgres UUID type không phân biệt.
- **ULID dễ debug**: log line như `wf_run=01HZQM7K9X4WGY2NBVECTRPS3F` dán vào URL được, copy-paste qua Slack/Zalo không mất escape.
- **Zero external deps**: không cài thêm extension, không thêm Python lib (uuid6 / ulid-py không cần) — chỉ stdlib + pgcrypto đã có.

### Negative / accepted trade-offs

- **Format không nhất quán trong DB**: 50 bảng v4 + N bảng v7 sống chung. Người mới đọc schema cần biết quy ước này — đã ghi trong CLAUDE.md §K-21.
- **Timestamp leak ở v7/ULID**: 48 bit timestamp lộ thời điểm tạo. Với khóa chính nội bộ thì không quan trọng (chỉ tenant thấy ID của tenant nó); với ULID external cần cân nhắc — vd không dùng ULID làm session token / API key.
- **Không strict monotonic trong cùng ms**: hai hàng INSERT cùng millisecond có thứ tự byte ngẫu nhiên. Đủ tốt cho audit log / B-tree, không đủ cho counter primitive.
- **Postgres-side function = vendor lock**: nếu Phase 3 cân nhắc DB khác (CockroachDB, YugabyteDB), plpgsql function phải port. Hiện không có kế hoạch đó → bỏ qua.

### Neutral / follow-ups

- Khi nâng Postgres lên 18 (chưa có roadmap), có thể swap sang built-in `gen_uuidv7()` — `gen_uuid_v7()` function của ta vẫn giữ làm wrapper. Drop khi convenient.
- Nếu một caller cần strict monotonic trong cùng ms (vd event sequencer), thêm per-session counter ở app layer (`shared/ids.py`) — không bump DB function.
- Theo dõi index fragmentation `workflow_run`, `decision_audit_log` sau 3 tháng để xác nhận locality benefit thực sự xuất hiện ở data-volume nội bộ.

## Alternatives considered

- **Full migration v4 → v7 ngay**: rewrite 100 migration, FK update, downtime ~h, vi phạm "no restructure mid-pilot". Cost cao trong khi bottleneck chưa xuất hiện ở 10-15 khách.
- **Extension `pg_uuidv7`**: ít LOC hơn function thủ công, nhưng cần install vào FPT Cloud Postgres (managed có thể không cho phép arbitrary extension), thêm dependency rotation. Function nội bộ kiểm soát được trong git.
- **App-layer generator only (không DEFAULT)**: phá writer-path coupling — mọi INSERT phải explicit ID, dễ quên trong test fixture, mig writer phải đồng bộ. Reject.
- **ULID làm khóa chính internal**: TEXT(26) FK nặng hơn UUID(16 bytes); index size 2x; vô ích cho bảng nội bộ không ai đọc raw ID. ULID chỉ có ý nghĩa khi human đọc được — giới hạn ở external column.
- **ULID stored as UUID binary thay vì TEXT**: tiết kiệm 10 byte/row nhưng mất human-readability — mục đích chính của ULID. Reject.

## References

- RFC 9562 — UUIDv6/v7/v8: https://datatracker.ietf.org/doc/rfc9562/
- ULID spec: https://github.com/ulid/spec
- Postgres B-tree fragmentation under random UUIDs — Percona benchmark
- Mig 104 — `infrastructure/postgres/migrations/104_uuid_v7_and_ulid_functions.sql`
- Mirror — `services/ai-orchestrator/shared/ids.py`
- CLAUDE.md §K-21 (invariant: new tables → v7 default; external → ULID)

---

**Editing note** — ADR-0029 mở rộng quy ước UUID đã ngầm áp dụng qua 100 migration. Khi cần thay đổi (vd Postgres 18 native), append ADR mới superseding nó, không rewrite.
