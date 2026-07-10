"use client";

/**
 * Reset password — split-screen brand + card form, mirroring login pattern.
 * Logic preserved: token from query, 8-char min, confirm match, redirect on success.
 */

import { Suspense, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import Link from "next/link";
import { AlertCircle, ArrowLeft } from "lucide-react";
import { authApi } from "@/lib/api/client";
import { Button } from "@/components/ui/button";
import { Input, Label } from "@/components/ui/input";
import { useT } from "@/lib/i18n/provider";
import { AuthBrandPanel, MobileLogo } from "../_components/BrandPanel";

function ResetPasswordForm() {
  const router  = useRouter();
  const params  = useSearchParams();
  const t       = useT();
  const token   = params.get("token") ?? "";

  const [password, setPassword] = useState("");
  const [confirm,  setConfirm]  = useState("");
  const [error,    setError]    = useState("");
  const [loading,  setLoading]  = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (password !== confirm) { setError(t("resetPasswordPage.errMismatch")); return; }
    if (password.length < 8)  { setError(t("resetPasswordPage.errTooShort")); return; }
    setError("");
    setLoading(true);
    try {
      await authApi.resetPassword(token, password);
      router.push("/login?reset=success");
    } catch {
      setError(t("resetPasswordPage.errInvalidExpired"));
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="min-h-screen w-full flex bg-canvas overflow-hidden">
      <AuthBrandPanel
        headline={t("resetPasswordPage.brandHeadline")}
        italicTail={t("resetPasswordPage.brandItalicTail")}
        subhead={t("resetPasswordPage.brandSubhead")}
      />

      <div className="relative flex w-full lg:w-1/2 flex-col items-center justify-center p-6 sm:p-12">
        <MobileLogo />

        <div className="w-full max-w-[420px] rounded-2xl bg-white p-8 shadow-soft-md border border-[var(--color-subtle)]/60 animate-fade-in">
          {!token ? (
            <div className="text-center space-y-4">
              <div className="flex justify-center">
                <div className="w-14 h-14 rounded-full bg-[var(--color-danger-50)] flex items-center justify-center">
                  <AlertCircle className="w-7 h-7 text-[var(--color-danger-600)]" strokeWidth={1.5} />
                </div>
              </div>
              <p className="text-sm text-[var(--color-danger-700)]">{t("resetPasswordPage.linkInvalid")}</p>
              <Link
                href="/forgot-password"
                className="inline-flex items-center gap-1.5 text-sm font-medium text-[var(--color-ink)] hover:text-[var(--color-brand-500)] transition-colors"
              >
                {t("resetPasswordPage.requestNewLink")}
              </Link>
            </div>
          ) : (
            <>
              <div className="flex flex-col space-y-2 mb-8">
                <h2 className="font-serif text-3xl font-semibold tracking-tight text-[var(--color-ink)]">
                  {t("auth.reset.title")}
                </h2>
                <p className="text-sm text-[var(--color-ink-muted)]">
                  {t("resetPasswordPage.subtitle")}
                </p>
              </div>

              <form onSubmit={handleSubmit} className="space-y-5">
                <div className="space-y-2">
                  <Label htmlFor="password">{t("resetPasswordPage.newPasswordLabel")}</Label>
                  <Input
                    id="password"
                    type="password"
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    required
                    minLength={8}
                    autoComplete="new-password"
                    placeholder="••••••••"
                    disabled={loading}
                  />
                </div>

                <div className="space-y-2">
                  <Label htmlFor="confirm">{t("resetPasswordPage.confirmPasswordLabel")}</Label>
                  <Input
                    id="confirm"
                    type="password"
                    value={confirm}
                    onChange={(e) => setConfirm(e.target.value)}
                    required
                    autoComplete="new-password"
                    placeholder="••••••••"
                    disabled={loading}
                  />
                </div>

                {error && (
                  <div className="rounded-xl bg-[var(--color-danger-50)] border border-[var(--color-danger-100)] px-4 py-3 flex items-start gap-2">
                    <AlertCircle className="w-4 h-4 text-[var(--color-danger-600)] mt-0.5 shrink-0" />
                    <p className="text-[var(--color-danger-700)] text-sm">{error}</p>
                  </div>
                )}

                <Button type="submit" loading={loading} className="w-full">
                  {loading ? t("resetPasswordPage.saving") : t("resetPasswordPage.submitButton")}
                </Button>
              </form>

              <div className="text-center mt-6">
                <Link
                  href="/login"
                  className="inline-flex items-center gap-1.5 text-sm font-medium text-[var(--color-ink-muted)] hover:text-[var(--color-ink)] transition-colors"
                >
                  <ArrowLeft className="w-4 h-4" /> {t("resetPasswordPage.backToLogin")}
                </Link>
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  );
}

export default function ResetPasswordPage() {
  return (
    <Suspense fallback={
      <div className="min-h-screen flex items-center justify-center bg-canvas">
        <div className="w-8 h-8 rounded-full border-2 border-[var(--color-brand-200)] border-t-[var(--color-brand-500)] animate-spin" />
      </div>
    }>
      <ResetPasswordForm />
    </Suspense>
  );
}
