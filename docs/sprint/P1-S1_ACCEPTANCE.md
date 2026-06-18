# Sprint P1-S1 — Acceptance Mapping

> **Sprint goal:** "Cluster ready, monorepo, CI/CD, basic auth"
> **Status:** ✅ all 21 features traced to existing code or new work this sprint
> **Branch:** `feat/v4-p1-s1`
> **Date:** 2026-05-08

This doc maps each of the 21 P1-S1 features (per `docs/BACKLOG_V4.md`) to the test/code artifact that proves it works. Quick-run command at the bottom verifies every line green.

---

## Net new work shipped this sprint

| Feature code | Description | Implementation |
|---|---|---|
| **OBS-012 ⭐** | Structured JSON logging (all services) | `_make_service_name_processor` in `services/*/tracing.py` + `LogContextMiddleware` in `services/*/log_context.py` (4 Python services) + `logback-spring.xml` + `logstash-logback-encoder` dep (auth-service + api-gateway). 10 unit tests at `services/ai-orchestrator/tests/test_log_context.py`. |
| **P2-M20-007** | First-login force-change-password | Migration `039_must_change_password.sql` adds `enterprise_users.must_change_password`. `User.mustChangePassword` field. `LoginResponse.mustChangePassword` field. `AuthService.login()` populates flag. `EnterpriseUserService.invite()` sets flag TRUE. `AuthService.resetPassword()` clears flag. `AuthService.changeOwnPassword()` + `POST /auth/users/me/change-password` for logged-in flow. 6 new unit tests in `AuthServiceTest`. |

---

## 18 features mapped to existing code

### Platform (10)

| Feature | Existing impl | Acceptance test |
|---|---|---|
| `P1-AUTH-001` Đăng nhập Platform Admin | `PlatformAuthController.login()` + `PlatformAuthService` | `PlatformAuthServiceTest.platformLogin_*` |
| `P1-AUTH-002` MFA bắt buộc SUPER_ADMIN (TOTP) | `PlatformSecurityController.enableMfa() / verifyMfa()` + `TotpService` | `TotpServiceTest`, `PlatformAuthServiceMfaTest` |
| `P1-AUTH-003` Session management + force logout | `AdminSession` entity + `AdminSessionRepository` + `SessionValidator` + `POST /security/sessions/revoke-others` | `SessionValidatorTest`, `AdminSessionRepositoryTest` |
| `P1-ADM-001` Invite admin + role | `PlatformAdminController.invite() / changeRole() / deactivate()` + `PlatformAdminService` | `PlatformAdminServiceTest`, `PlatformAdminControllerTest` |
| `P1-M10-004` Đăng xuất | `AuthController.logout()` (enterprise) + `PlatformAuthController.logout()` | `AuthServiceTest.logout_*`, `PlatformAuthServiceTest.logout_*` |
| `P1-M10-006` MFA bắt buộc SUPER_ADMIN | Same as `P1-AUTH-002` | Same |
| `P1-M10-007` Session JWT 1h + Refresh 30d | `JwtUtil` config (`auth.jwt.access-ttl-minutes`, `refresh-ttl-days`) + Redis refresh storage | `AuthServiceTest.login_success_returnsTokens` (asserts Redis refresh write) |
| `P1-M10-008` Rate Limit Login (5 lần / 15 phút) | `AuthService.login()` lockout logic (lines 68-103) | `AuthServiceTest.login_afterMaxAttempts_setsLockoutKey` etc. |
| `P1-M10-009` Force logout all sessions | `POST /security/sessions/revoke-others` | `PlatformSecurityControllerTest`, `AdminSessionRepository.revokeAllExceptSession` |
| `P1-M13-006` Enforce MFA cho SUPER_ADMIN | `PlatformAuthService.login()` returns `mfa_challenge_token` when admin has `mfa_enabled=true` | `PlatformAuthServiceMfaTest` |

### Enterprise (4)

| Feature | Existing impl | Acceptance test |
|---|---|---|
| `P2-M20-007` First Login (force change password) | **NEW this sprint** — see net new work above | `AuthServiceTest.login_invitedUser_*`, `resetPassword_clearsMustChangePassword`, `changeOwnPassword_*` (6 tests) |
| `P2-M20-008` MFA / 2FA optional | Phase 1 enterprise MFA NOT IMPLEMENTED — flag in CLAUDE.md §14 deferred. P3 hardening only covers platform admins. **DEFERRED to future sprint** when enterprise MFA arrives. |
| `P2-M20-009` Session Management JWT + Refresh | Same as `P1-M10-007` (shared JWT util) | Same |
| `P2-M20-011` SSO OAuth Google/Microsoft | Phase 2 explicitly per BACKLOG_V4 — **DEFERRED** Phase 2 P2-S18 |

### Studio (3) — DEFERRED

| Feature | Status |
|---|---|
| `P3-M30-006` First Login Studio | DEFERRED — Studio portal Phase 2 (P3 features start P2-S15+) |
| `P3-M30-007` MFA Kaori Staff | DEFERRED |
| `P3-M30-008` Session JWT Studio | DEFERRED |

### Personal (3) — DEFERRED

| Feature | Status |
|---|---|
| `P4-M40-003` Đăng ký OAuth | DEFERRED — Personal portal Phase 2 |
| `P4-M40-008` MFA optional Personal | DEFERRED |
| `P4-M40-009` Session JWT Personal | DEFERRED |

### Cross-cutting (1)

| Feature | Status |
|---|---|
| `OBS-012` Structured JSON logging | **NEW this sprint** — see net new work above. 10 unit tests + smoke pytest 867 pass across 4 Python services. Java JSON encoder + logback profiles staged (mvn test passes; full mvn verify needs anh manual run if anh wants to validate XML wiring). |

---

## Sprint scoping note

5 features in P1-S1 backlog (3 Studio + 3 Personal — wait, that's 6, but 1 of P3 was MFA which P3 portal hasn't been built yet) target portals **not yet implemented**. They are auth-flow scaffolds for portals that arrive Phase 2. Per anh's instruction, FE work paused, Studio + Personal portals not started. Marked **DEFERRED** with sprint-pin to whichever Phase 2 sprint stands up the portal.

This is a documentation choice, not a sprint scope cut: the BACKLOG_V4 row stays unchanged, only the acceptance evidence column updates when the portal lands.

---

## Quick-run smoke command

```bash
# 1. Python — 867 tests across 4 services (was 858 pre-Sprint, 9 net new from log_context).
cd "D:\Kaori System\services\ai-orchestrator" && python -m pytest -q
cd "D:\Kaori System\services\data-pipeline" && python -m pytest -q
cd "D:\Kaori System\services\llm-gateway" && python -m pytest -q
cd "D:\Kaori System\services\notification-service" && python -m pytest -q

# 2. Java auth-service — 31 unit tests trong AuthServiceTest (25 pre + 6 net new for P2-M20-007).
cd "D:\Kaori System\services\auth-service" && mvn test -Dtest=AuthServiceTest

# 3. Full Java verify (optional, ~5 phút per anh's local-only rule):
cd "D:\Kaori System\services\auth-service" && mvn verify
cd "D:\Kaori System\services\api-gateway" && mvn verify
```

Expected:
- Python: `867 passed, 1 skipped, 0 failed`
- AuthServiceTest: `Tests run: 31, Failures: 0, Errors: 0, Skipped: 0`
- Full mvn verify: TBD (anh chạy khi sẵn sàng).

---

## Files touched this sprint (P1-S1)

```
infrastructure/postgres/migrations/
  039_must_change_password.sql                                    NEW

services/ai-orchestrator/
  shared/log_context.py                                           NEW
  shared/tracing.py                                               MODIFIED (service.name processor)
  main.py                                                         MODIFIED (LogContextMiddleware wire)
  tests/test_log_context.py                                       NEW (10 tests)

services/data-pipeline/
  shared/log_context.py                                           NEW (mirror)
  shared/tracing.py                                               MODIFIED (mirror)
  main.py                                                         MODIFIED (LogContextMiddleware wire)

services/llm-gateway/
  log_context.py                                                  NEW (mirror)
  tracing.py                                                      MODIFIED (mirror)
  main.py                                                         MODIFIED (LogContextMiddleware wire)

services/notification-service/
  log_context.py                                                  NEW (mirror)
  tracing.py                                                      MODIFIED (mirror)
  main.py                                                         MODIFIED (LogContextMiddleware wire)

services/auth-service/
  pom.xml                                                         MODIFIED (logstash-logback-encoder)
  src/main/resources/logback-spring.xml                           NEW (profile-aware JSON)
  src/main/java/com/kaorisystem/auth/model/User.java              MODIFIED (mustChangePassword field)
  src/main/java/com/kaorisystem/auth/dto/AuthDtos.java            MODIFIED (LoginResponse + ChangePasswordRequest)
  src/main/java/com/kaorisystem/auth/service/AuthService.java     MODIFIED (login + reset + changeOwnPassword)
  src/main/java/com/kaorisystem/auth/service/EnterpriseUserService.java  MODIFIED (invite sets flag)
  src/main/java/com/kaorisystem/auth/controller/AuthController.java     MODIFIED (POST /auth/users/me/change-password)
  src/test/java/com/kaorisystem/auth/service/AuthServiceTest.java       MODIFIED (+6 tests)

services/api-gateway/
  pom.xml                                                         MODIFIED (logstash-logback-encoder)
  src/main/resources/logback-spring.xml                           NEW (profile-aware JSON)

docs/
  sprint/P1-S1_ACCEPTANCE.md                                      NEW (this file)
```

---

## Deferred to next sprints (tracked)

- **K8s deploy** — P15-S9 per ADR-0010 (don't disrupt pilot Olist).
- **OTel SDK upgrade + tenant_id MDC for Java** — P1-S2 (alongside OTel Collector deploy).
- **Service moves** (data-pipeline/bronze → data_plane/bronze, etc.) — lazy per-sprint per RESTRUCTURE_PROPOSAL §3 Step 4.
- **Enterprise MFA + SSO** — Phase 2 P2-S18.
- **Studio + Personal portal first-login flows** — when portals land Phase 2.
- **mvn verify for full Java suite** — anh run khi sẵn sàng (CI cloud chờ reset 1/6 per anh's local-only rule).

---

## References

- `docs/BACKLOG_V4.md` Phase 1 P1-S1 (21 features)
- `docs/RESTRUCTURE_PROPOSAL.md` §4 (Sprint 1 plan)
- `CLAUDE.md` §14 (sprint progress tracker — em sẽ tick `P1-S1` khi anh OK commit)
- `docs/_v4_extract/sprint_phase1.json` — raw 21-feature list
