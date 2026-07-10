"use client";

import { useState } from "react";
import Link from "next/link";
import { MailCheck } from "lucide-react";
import { authApi } from "@/lib/api/client";
import { Button } from "@/components/ui/button";
import { Input, Label } from "@/components/ui/input";
import { useT } from "@/lib/i18n/provider";

export default function ForgotPasswordPage() {
  const t = useT();
  const [email,     setEmail]     = useState("");
  const [submitted, setSubmitted] = useState(false);
  const [loading,   setLoading]   = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    await authApi.forgotPassword(email).catch(() => {});
    setSubmitted(true);
    setLoading(false);
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-canvas">
      <div className="w-full max-w-md px-4">
        <div className="bg-surface rounded-2xl border border-subtle shadow-card p-8">
          {/* Wordmark */}
          <div className="text-center mb-8">
            <h1 className="text-h1 font-serif text-brand-700">Kaori</h1>
            <p className="text-small text-ink-muted mt-1">{t("forgotPasswordPage.tagline")}</p>
          </div>

          {submitted ? (
            <div className="text-center space-y-4">
              <div className="flex justify-center">
                <div className="w-14 h-14 rounded-full bg-brand-50 flex items-center justify-center">
                  <MailCheck className="w-7 h-7 text-brand-600" strokeWidth={1.5} />
                </div>
              </div>
              <div>
                <h2 className="text-h2 font-serif text-ink">{t("forgotPasswordPage.checkEmailTitle")}</h2>
                <p className="text-small text-ink-muted mt-2">
                  {t("forgotPasswordPage.checkEmailDescPre")} <strong className="text-ink">{email}</strong> {t("forgotPasswordPage.checkEmailDescPost")}
                </p>
              </div>
              <Link href="/login" className="text-small text-brand-600 hover:text-brand-700 block mt-2">
                ← {t("forgotPasswordPage.backToLogin")}
              </Link>
            </div>
          ) : (
            <>
              <div className="text-center mb-6">
                <h2 className="text-h2 font-serif text-ink">{t("auth.forgot.title")}</h2>
                <p className="text-small text-ink-muted mt-1">
                  {t("forgotPasswordPage.subtitle")}
                </p>
              </div>

              <form onSubmit={handleSubmit} className="space-y-4">
                <div className="space-y-1.5">
                  <Label htmlFor="email">{t("forgotPasswordPage.emailLabel")}</Label>
                  <Input
                    id="email"
                    type="email"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    required
                    autoComplete="email"
                    placeholder="you@company.com"
                  />
                </div>

                <Button type="submit" loading={loading} className="w-full mt-2">
                  {loading ? t("forgotPasswordPage.sending") : t("forgotPasswordPage.submitButton")}
                </Button>
              </form>

              <div className="text-center mt-5">
                <Link href="/login" className="text-small text-brand-600 hover:text-brand-700">
                  ← {t("forgotPasswordPage.backToLogin")}
                </Link>
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
