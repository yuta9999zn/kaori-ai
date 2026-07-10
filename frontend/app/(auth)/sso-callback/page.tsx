"use client";

/**
 * P2-AUTH-001 SSO callback page.
 *
 * Lands at /auth/sso-callback?sso_code=<X> after ai-orchestrator's
 * /p2/auth/sso/{provider}/callback redirects the browser here.
 *
 * Responsibility: swap sso_code for a real JWT via auth-service
 * (POST /auth/sso/exchange), then hydrate the Zustand auth store and
 * push to /dashboard. On error, display the message + a "Back to
 * login" link.
 *
 * Mirrors the login page's success path verbatim — once `setAuth` runs,
 * downstream behaviour is identical regardless of how the token was
 * acquired (password vs SSO).
 */

import { Suspense, useEffect, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import Link from "next/link";
import { authApi } from "@/lib/api/client";
import { useAuth } from "@/lib/auth-store";
import { KaoriLogo } from "@/components/brand/KaoriLogo";
import { useT } from "@/lib/i18n/provider";

// Suspense wrapper required by Next.js 16 strict prerender for any
// client component that calls useSearchParams() — otherwise
// `next build` fails with "missing-suspense-with-csr-bailout".
export default function SsoCallbackPage() {
  return (
    <Suspense fallback={<SsoCallbackFallback />}>
      <SsoCallbackInner />
    </Suspense>
  );
}

function SsoCallbackFallback() {
  const t = useT();
  return (
    <div className="min-h-screen w-full flex items-center justify-center bg-canvas p-6">
      <div className="w-full max-w-[420px] rounded-2xl bg-white p-8 shadow-soft-md border border-[var(--color-subtle)]/60">
        <div className="flex items-center gap-3 mb-6">
          <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-white shadow-sm border border-[var(--color-subtle)]">
            <KaoriLogo size={24} detailed className="text-[var(--color-brand-500)]" />
          </div>
          <span className="font-serif text-xl font-semibold text-[var(--color-ink)]">Kaori</span>
        </div>
        <div className="space-y-2">
          <h2 className="font-serif text-xl font-medium text-[var(--color-ink)]">{t('ssoCallbackPage.loadingEllipsis')}</h2>
        </div>
      </div>
    </div>
  );
}

function SsoCallbackInner() {
  const t            = useT();
  const router       = useRouter();
  const params       = useSearchParams();
  const { setAuth }  = useAuth();
  const [error, setError] = useState<string | null>(null);
  const [phase, setPhase] = useState<"exchanging" | "redirecting" | "error">(
    "exchanging",
  );

  useEffect(() => {
    const ssoCode = params.get("sso_code");
    if (!ssoCode) {
      setError(t('ssoCallbackPage.errMissingCode'));
      setPhase("error");
      return;
    }

    let cancelled = false;
    (async () => {
      try {
        const { data } = await authApi.ssoExchange(ssoCode);
        if (cancelled) return;
        setAuth(
          {
            id:              data.userId ?? data.id,
            email:           data.email,
            full_name:       data.fullName ?? data.full_name,
            role:            data.role,
            enterprise_id:   data.enterpriseId ?? data.enterprise_id,
            enterprise_name: data.enterpriseName ?? data.enterprise_name,
          },
          data.accessToken,
          data.refreshToken,
        );
        localStorage.setItem("kaori.refresh_token", data.refreshToken);
        setPhase("redirecting");
        router.replace("/dashboard");
      } catch (err: unknown) {
        if (cancelled) return;
        const res = (err as any)?.response;
        const status = res?.status;
        if (status === 410) {
          setError(t('ssoCallbackPage.errCodeExpired'));
        } else if (status === 404) {
          setError(t('ssoCallbackPage.errCodeInvalid'));
        } else if (status === 502 || status === 503) {
          setError(t('ssoCallbackPage.errAuthUnavailable'));
        } else {
          setError(t('ssoCallbackPage.errSsoFailed'));
        }
        setPhase("error");
      }
    })();

    return () => { cancelled = true; };
  // Run exactly once on mount — re-running on dep change would replay the code.
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <div className="min-h-screen w-full flex items-center justify-center bg-canvas p-6">
      <div className="w-full max-w-[420px] rounded-2xl bg-white p-8 shadow-soft-md border border-[var(--color-subtle)]/60">
        <div className="flex items-center gap-3 mb-6">
          <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-white shadow-sm border border-[var(--color-subtle)]">
            <KaoriLogo size={24} detailed className="text-[var(--color-brand-500)]" />
          </div>
          <span className="font-serif text-xl font-semibold text-[var(--color-ink)]">Kaori</span>
        </div>

        {phase === "exchanging" && (
          <div className="space-y-2">
            <h2 className="font-serif text-xl font-medium text-[var(--color-ink)]">
              {t('ssoCallbackPage.authenticating')}
            </h2>
            <p className="text-sm text-[var(--color-ink-muted)]">
              {t('ssoCallbackPage.exchangingDesc')}
            </p>
          </div>
        )}

        {phase === "redirecting" && (
          <div className="space-y-2">
            <h2 className="font-serif text-xl font-medium text-[var(--color-ink)]">
              {t('ssoCallbackPage.loginSuccess')}
            </h2>
            <p className="text-sm text-[var(--color-ink-muted)]">
              {t('ssoCallbackPage.redirectingDesc')}
            </p>
          </div>
        )}

        {phase === "error" && (
          <div className="space-y-4">
            <div className="rounded-xl bg-[var(--color-danger-50)] p-3 text-sm text-[var(--color-danger-700)] border border-[var(--color-danger-100)]">
              {error}
            </div>
            <Link
              href="/login"
              className="inline-block text-sm font-medium text-[var(--color-brand-500)] hover:underline"
            >
              {t('ssoCallbackPage.backToLogin')}
            </Link>
          </div>
        )}
      </div>
    </div>
  );
}
