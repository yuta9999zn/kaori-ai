"use client";

/**
 * Login — split-screen brand panel + form, mirroring template
 * `D:\Kaori Document\frontend template\platform tenant\1KaoriLogin.jsx`.
 *
 * Logic preserved from the prior version:
 *   - authApi.login() against MSW or real backend
 *   - 423 lockout response surfaces lockoutRemainingSeconds
 *   - useAuth Zustand hydrate + refresh token persisted to localStorage
 */

import { useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { Eye, EyeOff } from "lucide-react";
import { authApi } from "@/lib/api/client";
import { useAuth } from "@/lib/auth-store";
import { Button } from "@/components/ui/button";
import { Input, Label } from "@/components/ui/input";
import { useT } from "@/lib/i18n/provider";
import { KaoriLogo } from "@/components/brand/KaoriLogo";
import { LocalePicker } from "@/components/i18n/locale-picker";

export default function LoginPage() {
  const router      = useRouter();
  const { setAuth } = useAuth();
  const t           = useT();
  const [email,     setEmail]    = useState("");
  const [password,  setPassword] = useState("");
  const [showPwd,   setShowPwd]  = useState(false);
  const [error,     setError]    = useState("");
  const [lockout,   setLockout]  = useState<number | null>(null);
  const [loading,   setLoading]  = useState(false);
  const [ssoLoading, setSsoLoading] = useState<null | "google" | "microsoft">(null);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    setLockout(null);
    setLoading(true);
    try {
      const { data } = await authApi.login(email, password);
      setAuth(
        {
          id:              data.userId ?? data.id,
          email:           data.email ?? email,
          full_name:       data.fullName ?? data.full_name,
          role:            data.role,
          enterprise_id:   data.enterpriseId ?? data.enterprise_id,
          enterprise_name: data.enterpriseName ?? data.enterprise_name,
        },
        data.accessToken,
        data.refreshToken,
      );
      localStorage.setItem("kaori.refresh_token", data.refreshToken);
      router.push("/p2/dashboard");
    } catch (err: unknown) {
      const res = (err as any)?.response;
      if (res?.status === 423) {
        const secs = res.data?.lockoutRemainingSeconds ?? 900;
        setLockout(secs);
        setError(`Tài khoản bị khóa. Thử lại sau ${Math.ceil(secs / 60)} phút.`);
      } else {
        setError("Email hoặc mật khẩu không đúng.");
      }
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="min-h-screen w-full flex bg-canvas overflow-hidden selection:bg-[var(--color-brand-500)]/30">
      {/* ── LEFT — brand panel (lg only) ─────────────────────────────── */}
      <div className="relative hidden lg:flex w-1/2 flex-col justify-between p-12 overflow-hidden bg-gradient-to-br from-[#FAF7F2] via-[#F4EFE6] to-[#E9E7E2]">
        <div className="absolute inset-0 bg-pattern z-0" />
        <div className="absolute -top-32 -left-32 w-96 h-96 bg-[#D9C6C6] rounded-full mix-blend-multiply filter blur-3xl opacity-20 animate-pulse" />
        <div className="absolute bottom-10 -right-20 w-[30rem] h-[30rem] bg-[#AFC3B1] rounded-full mix-blend-multiply filter blur-[100px] opacity-20" />

        <div className="relative z-10 flex items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-white shadow-sm border border-[var(--color-subtle)]">
            <KaoriLogo size={24} detailed className="text-[var(--color-brand-500)]" />
          </div>
          <span className="font-serif text-xl font-semibold text-[var(--color-ink)] tracking-wide">Kaori</span>
        </div>

        <div className="relative z-10 flex flex-col max-w-lg mb-20 animate-fade-in">
          <h1 className="font-serif text-5xl leading-[1.15] text-[var(--color-ink)] font-medium mb-6">
            Trí tuệ,<br />
            <span className="text-[var(--color-ink-muted)] italic">được trao một cách bình thản.</span>
          </h1>
          <p className="text-[var(--color-ink-muted)] text-lg leading-relaxed">
            Nền tảng phân tích dữ liệu B2B đa khách hàng. Quy mô vững vàng, giao diện rõ ràng, vận hành nhẹ nhàng.
          </p>
        </div>

        <div className="relative z-10 flex items-center gap-4 text-sm text-[var(--color-ink-muted)]">
          <span>© 2026 Kaori Platform</span>
          <span className="w-1 h-1 rounded-full bg-[var(--color-brand-500)]" />
          <a href="#" className="hover:text-[var(--color-ink)] transition-colors">Chính sách bảo mật</a>
        </div>
      </div>

      {/* ── RIGHT — login form ───────────────────────────────────────── */}
      <div className="relative flex w-full lg:w-1/2 flex-col items-center justify-center p-6 sm:p-12">
        {/* Language switcher — pick UI language before signing in (5 locales) */}
        <div className="absolute top-6 right-6 z-20">
          <LocalePicker />
        </div>
        {/* Mobile logo */}
        <div className="absolute top-8 left-8 flex items-center gap-2 lg:hidden">
          <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-white shadow-sm border border-[var(--color-subtle)]">
            <KaoriLogo size={20} />
          </div>
          <span className="font-serif text-lg font-medium text-[var(--color-ink)]">Kaori</span>
        </div>

        <div className="w-full max-w-[420px] rounded-2xl bg-white p-8 shadow-soft-md border border-[var(--color-subtle)]/60 animate-fade-in">
          <div className="flex flex-col space-y-2 mb-8">
            <h2 className="font-serif text-3xl font-semibold tracking-tight text-[var(--color-ink)]">
              Chào mừng trở lại
            </h2>
            <p className="text-sm text-[var(--color-ink-muted)]">
              Đăng nhập vào workspace của bạn
            </p>
          </div>

          <form onSubmit={handleSubmit} className="space-y-5">
            {error && (
              <div className="rounded-xl bg-[var(--color-danger-50)] p-3 text-sm text-[var(--color-danger-700)] border border-[var(--color-danger-100)]">
                {error}
                {lockout != null && (
                  <p className="text-[var(--color-danger-600)] text-tiny mt-1">
                    Còn {lockout}s trước khi thử lại.
                  </p>
                )}
              </div>
            )}

            <div className="space-y-2">
              <Label htmlFor="email">{t("auth.login.email")}</Label>
              <Input
                id="enterprise-email"
                name="enterprise-email"
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
                autoComplete="off"
                placeholder="you@company.com"
                disabled={loading}
              />
            </div>

            <div className="space-y-2">
              <Label htmlFor="password">{t("auth.login.password")}</Label>
              <div className="relative">
                <Input
                  id="enterprise-password"
                  name="enterprise-password"
                  type={showPwd ? "text" : "password"}
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  required
                  autoComplete="new-password"
                  placeholder="••••••••"
                  disabled={loading}
                  className="pr-10"
                />
                <button
                  type="button"
                  onClick={() => setShowPwd((v) => !v)}
                  disabled={loading}
                  aria-label={showPwd ? "Ẩn mật khẩu" : "Hiện mật khẩu"}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-[var(--color-ink-muted)] hover:text-[var(--color-ink)] transition-colors p-1"
                >
                  {showPwd ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                </button>
              </div>
            </div>

            <div className="flex items-center justify-end pt-1">
              <Link
                href="/forgot-password"
                className="text-sm font-medium text-[var(--color-ink)] hover:text-[var(--color-brand-500)] transition-colors"
              >
                {t("auth.login.forgot")}
              </Link>
            </div>

            <Button type="submit" loading={loading} className="w-full mt-2">
              {t("auth.login.submit")}
            </Button>
          </form>

          {/* P2-AUTH-001 — SSO providers. Tách block khỏi password form
              vì SSO bypasses validation + lockout state.
              `return_url` = where /sso-callback page lives in the FE.
              Browser navigates to provider → ai-orchestrator → back here.
              Both buttons share the same flow — only the provider name
              + Vietnamese label differ. */}
          <div className="mt-6 pt-6 border-t border-[var(--color-subtle)]/60 space-y-3">
            <p className="text-xs text-[var(--color-ink-muted)] text-center">
              hoặc đăng nhập bằng
            </p>
            {/* Microsoft button intentionally not listed yet — provider
                code-complete in BE, but no Entra tenant provisioned.
                Re-add `{ id: "microsoft", label: "Microsoft", icon: "microsoft" }`
                here when MICROSOFT_CLIENT_ID/SECRET land in .env. */}
            {([
              { id: "google", label: "Google", icon: "google" },
            ] as const).map((provider) => (
              <button
                key={provider.id}
                type="button"
                disabled={loading || ssoLoading !== null}
                onClick={async () => {
                  setError("");
                  setSsoLoading(provider.id);
                  try {
                    const returnUrl = `${window.location.origin}/sso-callback`;
                    const { data } = await authApi.ssoStart(provider.id, returnUrl);
                    // Don't clear ssoLoading — browser navigation takes over
                    // and the button visibly stays "going" until the window
                    // unloads.
                    window.location.href = data.authorize_url;
                  } catch (err: unknown) {
                    const res = (err as any)?.response;
                    const status = res?.status;
                    if (status === 503) {
                      setError(`Đăng nhập ${provider.label} chưa được cấu hình. Liên hệ quản trị viên.`);
                    } else if (status === 404) {
                      setError("Endpoint SSO không tồn tại. Vui lòng báo team kỹ thuật.");
                    } else if (status >= 500) {
                      setError(`Lỗi máy chủ (${status}). Thử lại sau.`);
                    } else {
                      setError(`Không thể khởi động đăng nhập ${provider.label}${status ? ` (HTTP ${status})` : ""}.`);
                    }
                    setSsoLoading(null);
                  }
                }}
                className="flex w-full items-center justify-center gap-2 rounded-md-custom border border-[var(--color-subtle)] bg-white px-4 py-2.5 text-sm font-medium text-[var(--color-ink)] hover:bg-canvas hover:border-[var(--color-brand-500)]/40 transition-colors disabled:opacity-50"
              >
                {ssoLoading === provider.id ? (
                  <span className="h-4 w-4 inline-block animate-spin rounded-full border-2 border-[var(--color-ink-muted)] border-t-transparent" />
                ) : provider.icon === "google" ? (
                  <svg viewBox="0 0 24 24" className="h-4 w-4">
                    <path fill="#4285F4" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"/>
                    <path fill="#34A853" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84A11 11 0 0 0 12 23z"/>
                    <path fill="#FBBC05" d="M5.84 14.1A6.6 6.6 0 0 1 5.48 12c0-.73.13-1.44.36-2.1V7.06H2.18A11 11 0 0 0 1 12c0 1.77.42 3.45 1.18 4.94l3.66-2.84z"/>
                    <path fill="#EA4335" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.06l3.66 2.84C6.71 7.31 9.14 5.38 12 5.38z"/>
                  </svg>
                ) : (
                  // Microsoft 4-square logo
                  <svg viewBox="0 0 23 23" className="h-4 w-4">
                    <path fill="#F25022" d="M1 1h10v10H1z"/>
                    <path fill="#7FBA00" d="M12 1h10v10H12z"/>
                    <path fill="#00A4EF" d="M1 12h10v10H1z"/>
                    <path fill="#FFB900" d="M12 12h10v10H12z"/>
                  </svg>
                )}
                {ssoLoading === provider.id
                  ? `Đang chuyển sang ${provider.label}…`
                  : `Tiếp tục với ${provider.label}`}
              </button>
            ))}
          </div>

          {/* New-tenant CTA — promoted out of the footer so customers landing
              for the first time see the registration path without scrolling.
              The /register page still asks for the activation key (Kaori is
              sales-assist, not free-tier self-serve), but the surface area is
              framed as registration so the language matches user expectation. */}
          <div className="mt-6 pt-6 border-t border-[var(--color-subtle)]/60">
            <p className="text-xs text-[var(--color-ink-muted)] text-center mb-3">
              Doanh nghiệp lần đầu sử dụng Kaori?
            </p>
            <Link
              href="/register"
              className="block w-full text-center px-4 py-2.5 rounded-md-custom border border-[var(--color-subtle)] text-sm font-medium text-[var(--color-ink)] bg-white hover:bg-canvas hover:border-[var(--color-brand-500)]/40 transition-colors"
            >
              Đăng ký doanh nghiệp với khoá kích hoạt
            </Link>
          </div>
        </div>
      </div>
    </div>
  );
}
