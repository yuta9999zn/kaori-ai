"use client";

/**
 * Đăng ký doanh nghiệp — Phase 1 self-serve activation.
 *
 * Kaori is B2B with a sales-assist motion: a tenant can't fully self-register.
 * The CS team provisions the workspace from /platform/workspaces/new, generates
 * a one-time activation key (`/platform/workspaces/[id]/keys`), and emails it
 * to the customer. This page is what the customer lands on next:
 *
 *   Step 1 — paste the activation key (validated visually only; backend
 *            rejects invalid/revoked keys at submit time).
 *   Step 2 — pick admin email + password + display name → POST
 *            /auth/workspace/activate (gateway PUBLIC_PATHS-listed) → store
 *            JWT → push /dashboard.
 *
 * Replaces the prior /onboarding URL (which now thin-redirects here).
 */

import { useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { Eye, EyeOff, ArrowRight, KeyRound, ChevronLeft, Building2 } from "lucide-react";
import { authApi } from "@/lib/api/client";
import { useAuth } from "@/lib/auth-store";
import { Button } from "@/components/ui/button";
import { Input, Label } from "@/components/ui/input";
import { KaoriLogo } from "@/components/brand/KaoriLogo";
import { useT } from "@/lib/i18n/provider";

const KEY_PATTERN = /^KAORI(-[A-Z0-9]{4,8}){2,5}$/i;

export default function RegisterPage() {
  const t = useT();
  const router = useRouter();
  const { setAuth } = useAuth();

  const [step,        setStep]        = useState<1 | 2>(1);
  const [workspaceKey,setWorkspaceKey]= useState("");
  const [adminName,   setAdminName]   = useState("");
  const [adminEmail,  setAdminEmail]  = useState("");
  const [adminPwd,    setAdminPwd]    = useState("");
  const [adminPwd2,   setAdminPwd2]   = useState("");
  const [showPwd,     setShowPwd]     = useState(false);
  const [error,       setError]       = useState("");
  const [loading,     setLoading]     = useState(false);

  function nextStep(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    const trimmed = workspaceKey.trim();
    if (!KEY_PATTERN.test(trimmed)) {
      setError(t("registerPage.errBadKeyFormat"));
      return;
    }
    setWorkspaceKey(trimmed);
    setStep(2);
  }

  async function handleActivate(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    if (adminPwd !== adminPwd2) {
      setError(t("registerPage.errPwdMismatch"));
      return;
    }
    if (adminPwd.length < 8) {
      setError(t("registerPage.errPwdTooShort"));
      return;
    }

    setLoading(true);
    try {
      const { data } = await authApi.activateWorkspace(
        workspaceKey, adminEmail, adminPwd,
        adminName.trim() || undefined,
      );
      setAuth(
        {
          id:              data.userId ?? data.id,
          email:           data.email ?? adminEmail,
          full_name:       data.fullName ?? data.full_name ?? adminName,
          role:            data.role ?? "MANAGER",
          enterprise_id:   data.enterpriseId ?? data.enterprise_id,
          enterprise_name: data.enterpriseName ?? data.enterprise_name,
        },
        data.accessToken,
        data.refreshToken,
      );
      localStorage.setItem("kaori.refresh_token", data.refreshToken);
      router.push("/p2/dashboard");
    } catch (err: unknown) {
      const res = (err as { response?: { status?: number; data?: { message?: string } } })?.response;
      if (res?.status === 400) {
        setError(res.data?.message ?? t("registerPage.errKeyInvalidOrExpired"));
      } else {
        setError(t("registerPage.errActivateFailed"));
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
            {t("registerPage.heroTitleLine1")}<br />
            <span className="text-[var(--color-ink-muted)] italic">{t("registerPage.heroTitleLine2")}</span>
          </h1>
          <p className="text-[var(--color-ink-muted)] text-lg leading-relaxed">
            {t("registerPage.heroDesc")}
          </p>
        </div>

        <div className="relative z-10 flex items-center gap-4 text-sm text-[var(--color-ink-muted)]">
          <span>© 2026 Kaori Platform</span>
          <span className="w-1 h-1 rounded-full bg-[var(--color-brand-500)]" />
          <Link href="/login" className="hover:text-[var(--color-ink)] transition-colors">
            {t("registerPage.haveAccountLogin")}
          </Link>
        </div>
      </div>

      {/* ── RIGHT — wizard form ─────────────────────────────────────── */}
      <div className="relative flex w-full lg:w-1/2 flex-col items-center justify-center p-6 sm:p-12">
        {/* Mobile logo */}
        <div className="absolute top-8 left-8 flex items-center gap-2 lg:hidden">
          <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-white shadow-sm border border-[var(--color-subtle)]">
            <KaoriLogo size={20} />
          </div>
          <span className="font-serif text-lg font-medium text-[var(--color-ink)]">Kaori</span>
        </div>

        <div className="w-full max-w-[460px] rounded-2xl bg-white p-8 shadow-soft-md border border-[var(--color-subtle)]/60 animate-fade-in">
          {/* Step indicator */}
          <div className="flex items-center gap-3 mb-6">
            <span className={`flex h-7 w-7 items-center justify-center rounded-full text-xs font-semibold ${
              step >= 1 ? 'bg-[var(--color-brand-500)] text-[var(--color-ink)]'
                        : 'bg-[var(--color-subtle)] text-[var(--color-ink-muted)]'
            }`}>1</span>
            <span className="h-px flex-1 bg-[var(--color-subtle)]" />
            <span className={`flex h-7 w-7 items-center justify-center rounded-full text-xs font-semibold ${
              step >= 2 ? 'bg-[var(--color-brand-500)] text-[var(--color-ink)]'
                        : 'bg-[var(--color-subtle)] text-[var(--color-ink-muted)]'
            }`}>2</span>
          </div>

          {step === 1 ? (
            <>
              <div className="flex flex-col space-y-2 mb-6">
                <span className="inline-flex w-fit items-center gap-1 rounded-full bg-[var(--color-brand-500)]/10 px-2.5 py-1 text-[11px] font-semibold uppercase tracking-wide text-[var(--color-brand-700)]">
                  <Building2 className="h-3 w-3" /> {t("registerPage.badgeRegisterBusiness")}
                </span>
                <h2 className="font-serif text-3xl font-semibold tracking-tight text-[var(--color-ink)]">
                  {t("registerPage.step1Title")}
                </h2>
                <p className="text-sm text-[var(--color-ink-muted)]">
                  {t("registerPage.step1Desc")}
                </p>
              </div>

              <form onSubmit={nextStep} className="space-y-5">
                {error && (
                  <div className="rounded-xl bg-[var(--color-danger-50)] p-3 text-sm text-[var(--color-danger-700)] border border-[var(--color-danger-100)]">
                    {error}
                  </div>
                )}

                <div className="space-y-2">
                  <Label htmlFor="workspace-key">{t("registerPage.labelActivationKey")}</Label>
                  <div className="relative">
                    <KeyRound className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-[var(--color-ink-muted)]" />
                    <Input
                      id="workspace-key"
                      type="text"
                      value={workspaceKey}
                      onChange={(e) => setWorkspaceKey(e.target.value.toUpperCase())}
                      required
                      autoFocus
                      placeholder="KAORI-XXXX-XXXX-XXXX-XXXX"
                      className="pl-9 font-mono tracking-wider"
                    />
                  </div>
                  <p className="text-tiny text-[var(--color-ink-muted)]">
                    {t("registerPage.keyFormatHintPrefix")} <code>KAORI-</code> {t("registerPage.keyFormatHintSuffix")}
                  </p>
                </div>

                <Button type="submit" className="w-full" disabled={!workspaceKey.trim()}>
                  {t("registerPage.btnContinue")} <ArrowRight className="w-4 h-4 ml-1.5" />
                </Button>

                <div className="rounded-xl bg-[var(--color-subtle)]/30 border border-[var(--color-subtle)]/60 p-3 text-xs text-[var(--color-ink-muted)]">
                  <strong className="text-[var(--color-ink)]">{t("registerPage.noKeyYet")}</strong>{" "}
                  {t("registerPage.contactSalesPrefix")}{" "}
                  <a href="mailto:hello@kaori.io?subject=Đăng%20ký%20doanh%20nghiệp%20Kaori"
                     className="font-medium text-[var(--color-ink)] underline-offset-2 hover:underline">
                    hello@kaori.io
                  </a>{" "}
                  {t("registerPage.contactSalesSuffix")}
                </div>
              </form>
            </>
          ) : (
            <>
              <button
                type="button"
                onClick={() => { setStep(1); setError(""); }}
                className="text-sm text-[var(--color-ink-muted)] hover:text-[var(--color-ink)] transition-colors flex items-center gap-1 mb-4"
              >
                <ChevronLeft className="w-4 h-4" /> {t("registerPage.btnChangeKey")}
              </button>

              <div className="flex flex-col space-y-2 mb-8">
                <h2 className="font-serif text-3xl font-semibold tracking-tight text-[var(--color-ink)]">
                  {t("registerPage.step2Title")}
                </h2>
                <p className="text-sm text-[var(--color-ink-muted)]">
                  {t("registerPage.step2Desc")}
                </p>
              </div>

              <form onSubmit={handleActivate} className="space-y-4">
                {error && (
                  <div className="rounded-xl bg-[var(--color-danger-50)] p-3 text-sm text-[var(--color-danger-700)] border border-[var(--color-danger-100)]">
                    {error}
                  </div>
                )}

                <div className="space-y-2">
                  <Label htmlFor="admin-name">{t("registerPage.labelFullName")}</Label>
                  <Input
                    id="admin-name"
                    type="text"
                    value={adminName}
                    onChange={(e) => setAdminName(e.target.value)}
                    autoComplete="name"
                    placeholder="Nguyễn Minh Khải"
                    disabled={loading}
                  />
                </div>

                <div className="space-y-2">
                  <Label htmlFor="admin-email">Email</Label>
                  <Input
                    id="admin-email"
                    type="email"
                    value={adminEmail}
                    onChange={(e) => setAdminEmail(e.target.value)}
                    required
                    autoComplete="email"
                    placeholder="you@company.com"
                    disabled={loading}
                  />
                </div>

                <div className="space-y-2">
                  <Label htmlFor="admin-pwd">{t("registerPage.labelPassword")}</Label>
                  <div className="relative">
                    <Input
                      id="admin-pwd"
                      type={showPwd ? "text" : "password"}
                      value={adminPwd}
                      onChange={(e) => setAdminPwd(e.target.value)}
                      required
                      minLength={8}
                      autoComplete="new-password"
                      placeholder={t("registerPage.pwdPlaceholder")}
                      disabled={loading}
                    />
                    <button
                      type="button"
                      onClick={() => setShowPwd(!showPwd)}
                      className="absolute right-3 top-1/2 -translate-y-1/2 text-[var(--color-ink-muted)] hover:text-[var(--color-ink)]"
                      tabIndex={-1}
                    >
                      {showPwd ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                    </button>
                  </div>
                </div>

                <div className="space-y-2">
                  <Label htmlFor="admin-pwd2">{t("registerPage.labelPwdConfirm")}</Label>
                  <Input
                    id="admin-pwd2"
                    type={showPwd ? "text" : "password"}
                    value={adminPwd2}
                    onChange={(e) => setAdminPwd2(e.target.value)}
                    required
                    autoComplete="new-password"
                    disabled={loading}
                  />
                </div>

                <Button type="submit" className="w-full" loading={loading}>
                  {t("registerPage.btnCompleteRegister")}
                </Button>
              </form>
            </>
          )}
        </div>

        <p className="mt-8 text-center text-sm text-[var(--color-ink-muted)] animate-fade-in">
          {t("registerPage.haveAccountQuestion")}{" "}
          <Link
            href="/login"
            className="font-medium text-[var(--color-ink)] hover:text-[var(--color-brand-500)] transition-colors underline-offset-4 hover:underline"
          >
            {t("registerPage.btnLogin")}
          </Link>
        </p>
      </div>
    </div>
  );
}
