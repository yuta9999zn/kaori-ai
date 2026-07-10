'use client';

/**
 * Platform admin MFA verification — second leg of the 2-step gate.
 *
 * Re-skinned 2026-05-18 to share AuthBrandPanel + p1/foundation Button.
 * Flow + RFC 7807 code handling preserved verbatim.
 *
 * Lands here from /platform/login with `kaori.mfa_challenge_token` +
 * email + expires_at in sessionStorage. 6-digit OTP with auto-advance,
 * paste support, auto-submit when complete. POST /auth/platform/mfa/verify
 * on success setAuth + redirect to /platform.
 *
 * RFC 7807 codes:
 *   AUTH.MFA_INVALID_CODE        → shake + retry
 *   AUTH.MFA_CHALLENGE_EXPIRED   → bounce to /platform/login?mfa_expired=1
 *   AUTH.MFA_CHALLENGE_INVALID   → bounce to /platform/login?mfa_expired=1
 */

import { useEffect, useRef, useState } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import { ArrowLeft, ShieldCheck } from 'lucide-react';

import { authApi } from '@/lib/api/client';
import { useAuth, type Role } from '@/lib/auth-store';
import { Button } from '@/components/platform/foundation';
import { AuthBrandPanel, MobileLogo } from '../../../(auth)/_components/BrandPanel';
import { useT } from '@/lib/i18n/provider';

const TOTP_STEP_SECONDS = 30;

export default function PlatformMfaVerifyPage() {
  const t = useT();
  const router  = useRouter();
  const setAuth = useAuth((s) => s.setAuth);

  const [challengeToken, setChallengeToken] = useState<string | null>(null);
  const [email,          setEmail]          = useState<string>('');
  const [expiresAt,      setExpiresAt]      = useState<number>(0);

  const [code,    setCode]    = useState<string[]>(Array(6).fill(''));
  const [error,   setError]   = useState<string>('');
  const [shake,   setShake]   = useState<boolean>(false);
  const [loading, setLoading] = useState<boolean>(false);

  const [stepRemaining, setStepRemaining] = useState<number>(
    TOTP_STEP_SECONDS - (Math.floor(Date.now() / 1000) % TOTP_STEP_SECONDS),
  );
  const [challengeRemaining, setChallengeRemaining] = useState<number>(0);

  const inputRefs = useRef<(HTMLInputElement | null)[]>([]);

  useEffect(() => {
    const t = sessionStorage.getItem('kaori.mfa_challenge_token');
    const e = sessionStorage.getItem('kaori.mfa_challenge_email');
    const x = sessionStorage.getItem('kaori.mfa_challenge_expires_at');
    if (!t || !x) {
      router.replace('/platform/login');
      return;
    }
    setChallengeToken(t);
    setEmail(e ?? '');
    setExpiresAt(Number(x));
  }, [router]);

  useEffect(() => {
    const id = setInterval(() => {
      setStepRemaining(TOTP_STEP_SECONDS - (Math.floor(Date.now() / 1000) % TOTP_STEP_SECONDS));
      if (expiresAt > 0) {
        const left = Math.max(0, Math.ceil((expiresAt - Date.now()) / 1000));
        setChallengeRemaining(left);
        if (left === 0) {
          sessionStorage.removeItem('kaori.mfa_challenge_token');
          sessionStorage.removeItem('kaori.mfa_challenge_email');
          sessionStorage.removeItem('kaori.mfa_challenge_expires_at');
          router.replace('/platform/login?mfa_expired=1');
        }
      }
    }, 1000);
    return () => clearInterval(id);
  }, [expiresAt, router]);

  useEffect(() => {
    const filled = code.every((d) => d !== '');
    if (filled && !loading && !error && challengeToken) {
      void handleVerify(code.join(''));
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [code]);

  async function handleVerify(fullCode: string) {
    if (!challengeToken || fullCode.length !== 6) return;
    setLoading(true);
    setError('');
    try {
      const res = await authApi.platformVerifyMfa(challengeToken, fullCode);
      const d   = (res.data?.data ?? res.data) as {
        access_token:  string;
        refresh_token: string;
        session_id?:   string;
        admin_id:      string;
        role:          Role;
      };
      sessionStorage.removeItem('kaori.mfa_challenge_token');
      sessionStorage.removeItem('kaori.mfa_challenge_email');
      sessionStorage.removeItem('kaori.mfa_challenge_expires_at');
      setAuth(
        { id: d.admin_id, email, role: d.role, session_id: d.session_id },
        d.access_token,
        d.refresh_token,
        'platform',
      );
      router.push('/platform');
    } catch (err: unknown) {
      const res = (err as { response?: { status?: number; data?: { code?: string } } })?.response;
      const code = res?.data?.code;
      if (code === 'AUTH.MFA_CHALLENGE_EXPIRED' || code === 'AUTH.MFA_CHALLENGE_INVALID') {
        sessionStorage.removeItem('kaori.mfa_challenge_token');
        sessionStorage.removeItem('kaori.mfa_challenge_email');
        sessionStorage.removeItem('kaori.mfa_challenge_expires_at');
        router.replace('/platform/login?mfa_expired=1');
        return;
      }
      setError(t('mfaPage.errInvalidCode'));
      setShake(true);
      setCode(Array(6).fill(''));
      setTimeout(() => setShake(false), 500);
      inputRefs.current[0]?.focus();
    } finally {
      setLoading(false);
    }
  }

  function handleKeyDown(e: React.KeyboardEvent<HTMLInputElement>, index: number) {
    if (e.key === 'Backspace') {
      if (!code[index] && index > 0) {
        const next = [...code];
        next[index - 1] = '';
        setCode(next);
        inputRefs.current[index - 1]?.focus();
      }
    } else if (e.key === 'ArrowLeft' && index > 0) {
      inputRefs.current[index - 1]?.focus();
    } else if (e.key === 'ArrowRight' && index < 5) {
      inputRefs.current[index + 1]?.focus();
    }
  }

  function handleChange(e: React.ChangeEvent<HTMLInputElement>, index: number) {
    const value = e.target.value;
    if (!/^\d*$/.test(value)) return;
    const next = [...code];
    if (value.length > 1) {
      const pasted = value.slice(0, 6).split('');
      for (let i = 0; i < pasted.length && index + i < 6; i++) {
        next[index + i] = pasted[i];
      }
      setCode(next);
      const nextIdx = Math.min(index + pasted.length, 5);
      inputRefs.current[nextIdx]?.focus();
      return;
    }
    next[index] = value;
    setCode(next);
    if (value && index < 5) inputRefs.current[index + 1]?.focus();
    if (error) setError('');
  }

  function handlePaste(e: React.ClipboardEvent<HTMLInputElement>) {
    e.preventDefault();
    const pasted = e.clipboardData.getData('text').replace(/\D/g, '').slice(0, 6);
    if (!pasted) return;
    const next = [...code];
    for (let i = 0; i < pasted.length; i++) next[i] = pasted[i];
    setCode(next);
    inputRefs.current[Math.min(pasted.length, 5)]?.focus();
    if (error) setError('');
  }

  const maskedEmail = email
    ? email.replace(/^(.).+(@.+)$/, (_m, a, b) => `${a}***${b}`)
    : '';

  return (
    <div className="min-h-screen w-full flex bg-canvas overflow-hidden selection:bg-[var(--primary-gold)]/30">
      <AuthBrandPanel
        headline={t('mfaPage.headline')}
        italicTail={t('mfaPage.italicTail')}
        subhead={t('mfaPage.subhead')}
      />

      <div className="relative flex w-full lg:w-1/2 flex-col items-center justify-center p-6 sm:p-12">
        <MobileLogo />

        <div
          className={`w-full max-w-[420px] rounded-md-custom bg-white p-8 shadow-soft-md border border-[var(--border-color)]/60 transition-all duration-300 ${
            shake ? 'animate-shake border-[var(--state-error)]/30' : 'animate-fade-in'
          }`}
        >
          <div className="flex flex-col space-y-3 mb-8">
            <div className="w-12 h-12 rounded-md-custom bg-canvas border border-[var(--border-color)] flex items-center justify-center mb-2">
              <ShieldCheck className="w-6 h-6 text-[var(--primary-gold-dark)]" />
            </div>
            <h2 className="font-serif text-3xl font-semibold tracking-tight text-[var(--text-primary)]">
              {t('mfaPage.title')}
            </h2>
            <p className="text-sm text-[var(--text-secondary)] leading-relaxed">
              {t('mfaPage.enterCodeIntro')}
              {maskedEmail && (
                <>
                  {' '}{t('mfaPage.forLabel')}{' '}
                  <span className="font-medium text-[var(--text-primary)]">{maskedEmail}</span>
                </>
              )}
              .
            </p>
          </div>

          <form
            onSubmit={(e) => { e.preventDefault(); void handleVerify(code.join('')); }}
            className="space-y-6"
          >
            <div className="flex justify-between items-center gap-2">
              {code.map((digit, index) => (
                <input
                  key={index}
                  ref={(el) => { inputRefs.current[index] = el; }}
                  type="text"
                  inputMode="numeric"
                  pattern="\d*"
                  maxLength={6}
                  value={digit}
                  onChange={(e) => handleChange(e, index)}
                  onKeyDown={(e) => handleKeyDown(e, index)}
                  onPaste={handlePaste}
                  disabled={loading}
                  aria-label={t('mfaPage.digitAriaLabel', { n: index + 1 })}
                  className={`w-12 h-14 sm:w-14 sm:h-16 text-center text-2xl font-medium rounded-md-custom border bg-white transition-all duration-200 outline-none tabular-nums focus:scale-105 focus:-translate-y-1 focus:shadow-sm disabled:opacity-50 disabled:cursor-not-allowed ${
                    error
                      ? 'border-[var(--state-error)]/40 text-[#9B5050] bg-[var(--state-error)]/8 focus:border-[var(--state-error)] focus:ring-2 focus:ring-[var(--state-error)]/20'
                      : 'border-[var(--border-color)] text-[var(--text-primary)] focus:border-[var(--primary-gold)] focus:ring-2 focus:ring-[var(--primary-gold)]/40'
                  }`}
                />
              ))}
            </div>

            <div className="h-5 flex items-center justify-center text-sm">
              {error ? (
                <span className="text-[#9B5050] font-medium">{error}</span>
              ) : challengeRemaining > 0 ? (
                <span className="text-[var(--text-secondary)]">
                  {t('mfaPage.codeRefreshesIn')}{' '}
                  <span className="font-medium tabular-nums text-[var(--text-primary)]">
                    00:{stepRemaining.toString().padStart(2, '0')}
                  </span>
                  {' '}— {t('mfaPage.sessionExpiresIn')}{' '}
                  <span className="font-medium tabular-nums text-[var(--text-primary)]">
                    {Math.floor(challengeRemaining / 60)}:{(challengeRemaining % 60).toString().padStart(2, '0')}
                  </span>
                </span>
              ) : (
                <span className="text-[var(--text-secondary)]">{t('mfaPage.restoringSession')}</span>
              )}
            </div>

            <Button
              type="submit"
              isLoading={loading}
              disabled={code.some((d) => !d) || !challengeToken}
              className="w-full"
            >
              {t('mfaPage.verifyButton')}
            </Button>
          </form>
        </div>

        <div className="mt-8 animate-fade-in">
          <Link
            href="/platform/login"
            className="inline-flex items-center text-sm font-medium text-[var(--text-secondary)] hover:text-[var(--text-primary)] transition-colors group"
          >
            <ArrowLeft className="w-4 h-4 mr-2 group-hover:-translate-x-1 transition-transform" />
            {t('mfaPage.backToLogin')}
          </Link>
        </div>
      </div>
    </div>
  );
}
