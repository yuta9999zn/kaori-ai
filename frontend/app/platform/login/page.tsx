'use client';

/**
 * Platform admin login — separate path from the enterprise /login.
 *
 * Re-skinned 2026-05-18 to share the same AuthBrandPanel as /login and
 * use p1/foundation form primitives. Two-step gate logic preserved
 * verbatim (B3 PR #8): MFA-required response stashes challenge into
 * sessionStorage + routes to /platform/login/mfa.
 *
 * Backend: POST /auth/platform/login (Batch 3.1.a / PlatformAuthController).
 *   • success (no MFA) → 200 { data: { access_token, refresh_token,
 *                                       session_id, admin_id, role,
 *                                       mfa_enabled, mfa_required:false,
 *                                       expires_in_sec } }
 *   • MFA required     → 200 { data: { mfa_required:true,
 *                                       mfa_challenge_token,
 *                                       mfa_challenge_expires_in_sec,
 *                                       admin_id } }
 *   • bad creds        → 401 RFC 7807 problem+json
 *   • lockout          → 423 RFC 7807 with `lockout_remaining_seconds`
 */

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import { Eye, EyeOff, Shield } from 'lucide-react';

import { authApi } from '@/lib/api/client';
import { useAuth, type Role } from '@/lib/auth-store';
import {
  Button, Input, Label, ErrorBanner, type ProblemDetails,
} from '@/components/platform/foundation';
import { AuthBrandPanel, MobileLogo } from '../../(auth)/_components/BrandPanel';

interface PlatformLoginData {
  mfa_required?:                 boolean;
  mfa_challenge_token?:          string;
  mfa_challenge_expires_in_sec?: number;
  access_token?:                 string;
  refresh_token?:                string;
  session_id?:                   string;
  admin_id:                      string;
  role?:                         Role;
  mfa_enabled?:                  boolean;
}

export default function PlatformLoginPage() {
  const router   = useRouter();
  const setAuth  = useAuth((s) => s.setAuth);
  const [email,    setEmail]    = useState('');
  const [password, setPassword] = useState('');
  const [showPwd,  setShowPwd]  = useState(false);
  const [error,    setError]    = useState<ProblemDetails | null>(null);
  const [lockout,  setLockout]  = useState<number | null>(null);
  const [loading,  setLoading]  = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setLockout(null);
    setLoading(true);
    try {
      const res = await authApi.platformLogin(email, password);
      const d   = (res.data?.data ?? res.data) as PlatformLoginData;

      if (d.mfa_required && d.mfa_challenge_token) {
        sessionStorage.setItem('kaori.mfa_challenge_token', d.mfa_challenge_token);
        sessionStorage.setItem('kaori.mfa_challenge_email', email);
        sessionStorage.setItem(
          'kaori.mfa_challenge_expires_at',
          String(Date.now() + (d.mfa_challenge_expires_in_sec ?? 300) * 1000),
        );
        router.push('/platform/login/mfa');
        return;
      }

      if (!d.access_token || !d.refresh_token || !d.role) {
        setError({ title: 'Phản hồi không hợp lệ từ máy chủ. Vui lòng thử lại.' });
        return;
      }

      setAuth(
        { id: d.admin_id, email, role: d.role, session_id: d.session_id },
        d.access_token,
        d.refresh_token,
        'platform',
      );
      router.push('/platform');
    } catch (err: unknown) {
      const res = (err as { response?: { status?: number; data?: Record<string, unknown> } })?.response;
      if (res?.status === 423) {
        const secs = (res.data?.lockout_remaining_seconds as number | undefined) ?? 900;
        setLockout(secs);
        setError({
          title: `Tài khoản bị khóa. Thử lại sau ${Math.ceil(secs / 60)} phút.`,
          lockout_remaining_seconds: secs,
        });
      } else if (res?.status === 401) {
        setError({ title: 'Email hoặc mật khẩu không đúng.' });
      } else {
        setError({ title: 'Không thể đăng nhập. Vui lòng thử lại.' });
      }
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="min-h-screen w-full flex bg-canvas overflow-hidden selection:bg-[var(--primary-gold)]/30">
      <AuthBrandPanel
        headline="Khu vực vận hành,"
        italicTail="dành cho đội Kaori."
        subhead="Trang đăng nhập cho quản trị viên nền tảng. Cần MFA và phiên kiểm soát chặt; khách hàng doanh nghiệp vui lòng dùng cổng /login."
      />

      <div className="relative flex w-full lg:w-1/2 flex-col items-center justify-center p-6 sm:p-12">
        <MobileLogo />

        <div className="w-full max-w-[420px] rounded-md-custom bg-white p-8 shadow-soft-md border border-[var(--border-color)]/60 animate-fade-in">
          <div className="flex flex-col space-y-2 mb-8">
            <span className="inline-flex w-fit items-center gap-1 rounded-full bg-[var(--primary-gold)]/15 px-2.5 py-1 text-[11px] font-semibold uppercase tracking-wide text-[var(--primary-gold-dark)]">
              <Shield className="h-3 w-3" /> Platform admin
            </span>
            <h2 className="font-serif text-3xl font-semibold tracking-tight text-[var(--text-primary)]">
              Đăng nhập quản trị
            </h2>
            <p className="text-sm text-[var(--text-secondary)]">
              Tài khoản nhân sự Kaori (SUPER_ADMIN / ADMIN / SUPPORT).
            </p>
          </div>

          <form onSubmit={handleSubmit} className="space-y-5">
            {error && <ErrorBanner problem={error} />}

            <div className="space-y-2">
              <Label htmlFor="email">Email công vụ</Label>
              <Input
                id="email"
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
                autoComplete="email"
                placeholder="ops@kaori.io"
                disabled={loading}
              />
            </div>

            <div className="space-y-2">
              <Label htmlFor="password">Mật khẩu</Label>
              <div className="relative">
                <Input
                  id="password"
                  type={showPwd ? 'text' : 'password'}
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  required
                  autoComplete="current-password"
                  placeholder="••••••••"
                  disabled={loading}
                  className="pr-10"
                />
                <button
                  type="button"
                  onClick={() => setShowPwd((v) => !v)}
                  disabled={loading}
                  aria-label={showPwd ? 'Ẩn mật khẩu' : 'Hiện mật khẩu'}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-[var(--text-secondary)] hover:text-[var(--text-primary)] transition-colors p-1"
                >
                  {showPwd ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                </button>
              </div>
              {lockout != null && (
                <p className="text-xs text-[#9B5050]">Còn {lockout}s trước khi thử lại.</p>
              )}
            </div>

            <Button type="submit" isLoading={loading} className="w-full mt-2">
              Đăng nhập vào Platform
            </Button>
          </form>

          <p className="mt-6 text-center text-xs text-[var(--text-secondary)]">
            Sau khi đăng nhập, anh/chị có thể bật MFA tại{' '}
            <span className="font-medium text-[var(--text-primary)]">Bảo mật → MFA</span>.
          </p>
        </div>

        <p className="mt-8 text-center text-sm text-[var(--text-secondary)] animate-fade-in">
          Không phải nhân sự Kaori?{' '}
          <Link
            href="/login"
            className="font-medium text-[var(--text-primary)] hover:text-[var(--primary-gold-dark)] transition-colors underline-offset-4 hover:underline"
          >
            Cổng đăng nhập doanh nghiệp
          </Link>
        </p>
      </div>
    </div>
  );
}
