import { http, HttpResponse, delay } from "msw";

const BASE = "http://localhost:8080";

const MOCK_USER = {
  userId: "user_1abc",
  email: "demo@kaori.io",
  fullName: "Nguyễn Minh Khải",
  role: "MANAGER" as const,
  enterpriseId: "ent_demo1",
  enterpriseName: "Công ty TNHH Demo Kaori",
  accessToken: "mock_access_xxxx",
  refreshToken: "mock_refresh_xxxx",
};

export const authHandlers = [
  http.post(`${BASE}/auth/login`, async ({ request }) => {
    const body = (await request.json()) as { email: string; password: string };
    await delay(400);
    if (body.email === "locked@test.com") {
      return HttpResponse.json({ lockoutRemainingSeconds: 840 }, { status: 423 });
    }
    if (body.email === "error@test.com") {
      return HttpResponse.json({ message: "Invalid credentials" }, { status: 401 });
    }
    return HttpResponse.json({ ...MOCK_USER, email: body.email });
  }),

  http.post(`${BASE}/auth/logout`, async () => {
    await delay(150);
    return HttpResponse.json({ message: "ok" });
  }),

  http.post(`${BASE}/auth/forgot-password`, async () => {
    await delay(500);
    return HttpResponse.json({ message: "ok" });
  }),

  http.post(`${BASE}/auth/reset-password`, async ({ request }) => {
    const body = (await request.json()) as { token: string; newPassword: string };
    await delay(400);
    if (body.token === "invalid") {
      return HttpResponse.json({ message: "Token expired" }, { status: 400 });
    }
    return HttpResponse.json({ message: "ok" });
  }),

  http.post(`${BASE}/auth/refresh`, async () => {
    await delay(200);
    return HttpResponse.json({
      accessToken: "mock_access_refreshed",
      refreshToken: "mock_refresh_refreshed",
    });
  }),

  // ── Platform admin auth (Phase 3 Batch 3.1.a) ──────────────────────────
  // Backend wraps the success body under {data:{...}} and returns RFC 7807
  // problem+json on 401/423; the FE tolerates both wrapped + flat shapes.
  http.post(`${BASE}/auth/platform/login`, async ({ request }) => {
    const body = (await request.json()) as { email: string; password: string };
    await delay(400);
    if (body.email === "locked@test.com") {
      return HttpResponse.json(
        {
          type:   "/docs/errors/account-locked",
          title:  "Account locked",
          status: 423,
          detail: "Quá 5 lần thất bại trong 15 phút.",
          lockout_remaining_seconds: 840,
        },
        { status: 423 },
      );
    }
    if (body.email === "error@test.com") {
      return HttpResponse.json(
        {
          type:   "/docs/errors/invalid-credentials",
          title:  "Invalid credentials",
          status: 401,
          detail: "Email hoặc mật khẩu không đúng.",
        },
        { status: 401 },
      );
    }
    // B3 PR #8 — emulate the MFA-required first leg when the admin email
    // contains "mfa" (e.g. mfa@test.com). Lets the FE walk through the
    // 2-step path in MSW dev without an Ollama / DB.
    if (body.email.toLowerCase().includes("mfa")) {
      return HttpResponse.json({
        data: {
          mfa_required:                  true,
          mfa_challenge_token:           "mock_mfa_challenge_token",
          mfa_challenge_expires_in_sec:  300,
          admin_id:                      "admin_1abc",
        },
      });
    }
    return HttpResponse.json({
      data: {
        access_token:   "mock_admin_access",
        refresh_token:  "mock_admin_refresh",
        session_id:     "sess_mock_admin",
        admin_id:       "admin_1abc",
        role:           "SUPER_ADMIN",
        mfa_enabled:    false,
        mfa_required:   false,
        expires_in_sec: 1800,
      },
    });
  }),

  // B3 PR #8 — second leg of platform 2-step login. Accepts code "000000"
  // as the dev shortcut (RFC 7807 401 for anything else). Same envelope as
  // a no-MFA login.
  http.post(`${BASE}/auth/platform/mfa/verify`, async ({ request }) => {
    const body = (await request.json()) as {
      mfaChallengeToken: string; code: string;
    };
    await delay(400);
    if (body.code !== "000000") {
      return HttpResponse.json(
        {
          type:   "/docs/errors/mfa-verify-failed",
          title:  "MFA verification failed",
          status: 401,
          code:   "AUTH.MFA_INVALID_CODE",
          detail: "Mã xác thực không đúng.",
        },
        { status: 401 },
      );
    }
    return HttpResponse.json({
      data: {
        access_token:   "mock_admin_access_post_mfa",
        refresh_token:  "mock_admin_refresh_post_mfa",
        session_id:     "sess_mock_admin",
        admin_id:       "admin_1abc",
        role:           "SUPER_ADMIN",
        mfa_enabled:    true,
        mfa_required:   false,
        expires_in_sec: 1800,
      },
    });
  }),

  http.post(`${BASE}/auth/platform/refresh`, async () => {
    await delay(200);
    return HttpResponse.json({
      data: {
        access_token:   "mock_admin_access_refreshed",
        refresh_token:  "mock_admin_refresh_refreshed",
        session_id:     "sess_mock_admin",
        admin_id:       "admin_1abc",
        role:           "SUPER_ADMIN",
        mfa_enabled:    false,
        expires_in_sec: 1800,
      },
    });
  }),

  // Sprint 7 PR D — F-013 onboarding activation. Accepts any KAORI-formatted
  // key for dev convenience; rejects "KAORI-INVALID-KEY" so the error path
  // is testable. Returns the same LoginResponse shape /auth/login uses.
  http.post(`${BASE}/auth/workspace/activate`, async ({ request }) => {
    const body = (await request.json()) as {
      workspaceKey: string; adminEmail: string;
      adminPassword: string; adminName?: string;
    };
    await delay(400);
    if (body.workspaceKey?.toUpperCase().includes("INVALID")) {
      return HttpResponse.json(
        { status: 400, error: "INVALID_KEY", message: "Khoá kích hoạt không hợp lệ hoặc đã được sử dụng." },
        { status: 400 },
      );
    }
    return HttpResponse.json({
      userId:         "user_onboard_1",
      email:          body.adminEmail,
      fullName:       body.adminName ?? "Admin",
      role:           "MANAGER",
      enterpriseId:   "11111111-1111-1111-1111-111111111111",
      enterpriseName: "Pilot tenant (mock)",
      accessToken:    "mock_access_onboard",
      refreshToken:   "mock_refresh_onboard",
    });
  }),
];
