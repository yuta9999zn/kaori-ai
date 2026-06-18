# ADR-0027 — Spring Boot 4.x + Java 25 Phase 3 Holster

| | |
|---|---|
| **Status**   | Accepted |
| **Date**     | 2026-05-23 |
| **Phase**    | Phase 3 (Year 2) — holster Phase 1-2 |
| **Anh ref**  | Session 2026-05-22 EOD ("Java 25 đã trên main — cần kiểm Spring Boot 4.x ADR") |
| **Related**  | ADR-0010 (modular monolith → microservices), CLAUDE.md §2 (Tech Stack PINNED), PR #8 (Dependabot Java 25 api-gateway, merged 2026-05-22), PR #202 (OTel/Spring 3.2.5 eco-system lock) |

## Context

Trạng thái 2026-05-23 sau Dependabot #8 merge:

| Service | Base image | `<java.version>` pom | Spring Boot |
|---|---|---|---|
| api-gateway | `eclipse-temurin:25-jre-alpine` | 21 | 3.2.5 |
| auth-service | `eclipse-temurin:21-jre-alpine` | 21 | 3.2.5 |

Sự bất nhất `25 base / 21 bytecode` trên api-gateway **vẫn chạy** vì Java backward-compatible với bytecode 21 — nhưng Spring Boot 3.2.5 chỉ được vendor test trên JDK 17 & 21. Java 25 GA (2025-09) chưa nằm trong compatibility matrix chính thức.

Anh đã reject 4 lần piecemeal Dependabot major bumps trong Phase 1-2 (springdoc 2→3 PR #130, OTel 1.28→1.30 piece, Spring 3.2.5→3.3 piece, Java 21→25 ngoài api-gateway). Precedent rõ: **"không bump major mid-Phase 2"** (memory `feedback_dependabot_piecemeal_bumps.md`).

Forces in tension:

- **Pull toward upgrade**: Java 25 là LTS mới (replaces Java 21 LTS); Spring Boot 4.0 (ship 2025-11) bring Jakarta EE 11 + virtual threads default + Micrometer 2 + Spring AI 1.0 GA; Dependabot sẽ tiếp tục fire PR.
- **Pull toward hold**: Phase 2 đang chạy (250+ commits ahead main pre-PR #179, 2350+ tests trên ai-orchestrator), risk break mid-sprint cao; eco-system constraint (`springdoc 3.x → SB 3.5+`, `OTel agent → JDK 21`), nhiều dep chưa SB4-ready; modular monolith plan (ADR-0010) đang giữa quá trình tách extract Phase 3 — không muốn cuộn 2 chuyển động lớn vào nhau.

## Decision

**Hold Spring Boot 3.2.5 + pom `<java.version>21` qua hết Phase 2. Phase 3 mới bump coordinated.**

### Phase 1-2 (now → 2026-06-30, Phase 2 close)

- Spring Boot **3.2.5** pin, không nâng minor/major. Dependabot security patches (3.2.5 → 3.2.x) auto-merge OK.
- `<java.version>` trong pom: **21** (giữ nguyên cả 2 service).
- Base image: api-gateway = `25-jre-alpine` (đã merge — chấp nhận do backward compat); auth-service = `21-jre-alpine` (giữ).
- Cấm: SB 3.3+ / SB 4.x / pom `<java.version>22+`. Dependabot ignore Spring Boot major bump (đã có ignore springdoc semver-major; thêm `org.springframework.boot:spring-boot-*` semver-major + semver-minor cho Phase 1-2 — sẽ add vào `.github/dependabot.yml` cùng PR follow-up ADR này).
- Test gate: `java / api-gateway` + `java / auth-service` xanh trên Java 25 runtime trong CI là điều kiện đủ để giữ inconsistency này. Nếu rơi đỏ → revert base image về 21.

### Phase 3 (Year 2, theo CLAUDE.md §1 phase table)

Coordinated bump theo thứ tự bắt buộc:

1. **Bump `<java.version>` 21 → 25** trên cả 2 service pom (cùng commit).
2. **Bump Spring Boot 3.2.5 → 4.0.x** (cùng commit hoặc commit kế tiếp). Spring Boot 4.0 yêu cầu Java 17+; với target Java 25 không có vấn đề runtime.
3. **Bump springdoc 2.x → 3.x** (đã defer trong dependabot.yml ignore — unlock cùng đợt này).
4. **Bump base image auth-service 21 → 25** (api-gateway đã ở 25).
5. **Eco-system follow-up**: OTel agent → JDK 21+ compat (ADR-0028 separate), Jakarta EE 9 → 11 namespace migration (Spring Boot 4 đã handle), resilience4j semver check.

Mỗi bước riêng PR, nhưng **không merge bước N+1 trước khi bước N CI green ≥48h**. Total expected: 1 sprint Phase 3 (≈ 2 tuần).

### Forbid (cả Phase 1-2 lẫn Phase 3)

- Bump base image trước khi bump pom `<java.version>` (gây inconsistency runtime/bytecode > 4 versions — Java compat formally 1 LTS gap).
- Bump Spring Boot trước khi bump Java target (SB 4 không build trên Java 17 nếu pom locked 17 — `<java.version>` phải bump trước hoặc cùng commit).
- Piecemeal merge giữa các bước Phase 3 (revert risk cao do entangled deps).

## Consequences

### Positive

- **Eliminate piecemeal Dependabot pressure** Phase 1-2 — anh không phải reject từng PR major bump.
- **Test surface stable**: 2350 tests trên ai-orchestrator + 210 llm-gateway + 695 data-pipeline đang xanh trên matrix Java 21/Python 3.11 — giữ matrix này cho tới phase close giảm noise.
- **Phase 3 cutover atomic**: cùng đợt với Python 3.12+ (ADR follow-up), OTel forward-sync (ADR-0028), Spring Boot 4 + Java 25 — 1 sprint scope rõ.
- **Java 25 trên api-gateway đã verified** (PR #8 CI xanh) — Phase 3 cutover bớt rủi ro vì runtime đã chạy thực.

### Negative / accepted trade-offs

- **Inconsistency 25 base / 21 bytecode** trên api-gateway (~7 tháng cho tới Phase 3 close). Vendor compatibility matrix unofficial — chấp nhận rủi ro vì CI xanh.
- **Trễ Java 25 LTS adoption** ~7 tháng so với GA — không tận dụng được virtual threads default + Generational ZGC mới.
- **Spring Boot 4 features defer**: Jakarta EE 11, Spring AI 1.0 GA, Micrometer 2 — Phase 2 phải workaround nếu cần.
- **Dependabot config phình thêm**: cần thêm ignore rules cho `spring-boot-*` semver-major + semver-minor.

### Neutral / follow-ups

- **Trigger reconsider sớm**: CVE critical trong Spring Boot 3.2.x không patch được trong 3.2.x stream → buộc bump 3.3+. Monitor Spring Security CVE feed.
- **Trigger reconsider sớm**: Java 25 runtime crash trên api-gateway prod → revert base image về 21 (rollback dễ, 1 commit).
- **Phase 3 prep**: viết runbook bước-bước cho coordinated bump (docs/runbooks/spring-boot-4-java-25-cutover.md) **trước** khi bắt đầu — không freestyle.
- **Update `.github/dependabot.yml`**: add ignore `org.springframework.boot:*` semver-major + semver-minor trong group `spring` của auth-service + api-gateway. PR riêng follow-up ADR này.
- **Update CLAUDE.md §2**: ghi rõ "Spring Boot 3.2.5 pinned Phase 1-2; bump Spring Boot 4.x + Java 25 Phase 3 (ADR-0027)" để future agent đọc context.

## Alternatives considered

- **Alt 1 — Bump Spring Boot 3.2.5 → 3.4.x now (no Java bump)**. SB 3.4 supports Java 17-24 → compatible với Java 25 backward bytecode. Nhược: SB 3.4 không bring Jakarta EE 11; vẫn phải bump lần 2 lên SB 4 trong Phase 3; piecemeal pattern lặp lại (anh đã reject). Khả năng break: springdoc 2.x phải bump 3.x cùng đợt (đã trong dependabot ignore). Quyết định: không — bump 1 lần Phase 3 hơn 2 lần.
- **Alt 2 — Bump full Spring Boot 4 + Java 25 now**. Atomicity tốt nhưng risk cao mid-Phase 2: 250+ commits ahead main, Industry Template Phase 2.8 vừa close, Phase 2.9 K-13 coverage đang chạy. Eco-system constraints chưa kiểm xong (springdoc, OTel agent, Spring Cloud Gateway 4.x với Spring Boot 4 — Spring Cloud chu kỳ release không khớp Spring Boot). Quyết định: không — Phase 3 mới đủ thời gian kiểm.
- **Alt 3 — Revert Java 25 base image về 21 trên api-gateway**. Khôi phục consistency 21/21. Nhược: mất verified-on-Java-25 đã có, anh đã override merge, Dependabot sẽ fire lại tuần sau. Quyết định: không — Java 25 base image OK giữ vì runtime backward compat + CI xanh.
- **Alt 4 — Bump auth-service base image lên 25 để consistent với api-gateway**. Khôi phục cross-service consistency. Nhược: không có lợi ích nghiệp vụ trước Phase 3; thêm 1 PR Dependabot phải approve mà chưa cần. Quyết định: không — đợi Phase 3 cutover atomic.

## References

- CLAUDE.md §2 (Tech Stack PINNED) — Spring Boot 3.2.5 + Java 21 trạng thái hiện tại
- ADR-0010 — modular monolith Phase 1-2, microservices Phase 3 (cùng timeline với ADR này)
- PR #8 (merged 2026-05-22) — Dependabot Java 21 → 25 api-gateway
- PR #14/#25/#26 (closed 2026-05-22) — precedent Python piecemeal bumps blocked
- PR #130 (closed earlier) — springdoc 2.5.0 → 3.0.3 reject (EndpointCondition errors trong Spring Boot 3.2.5)
- PR #202 — OTel 1.28/0.49b2 + Spring Boot 3.2.5 lock fix
- Memory `feedback_dependabot_piecemeal_bumps.md` — anh's precedent stance
- Spring Boot 4.0 release notes: https://spring.io/blog/2025/11/spring-boot-4-0-ga (canonical reference; verify before Phase 3 cutover)
- JDK 25 LTS announcement: https://openjdk.org/projects/jdk/25/

---

**Editing note** — ADRs are append-only. Trước khi superseded, cập nhật Status line. Phase 3 cutover sẽ ship ADR-0027a (runbook companion) hoặc ADR-0029 (post-cutover lessons) tùy outcome.
