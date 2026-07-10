'use client';

// @ts-nocheck
// ============================================================================
// Kaori AI — User Enterprise (P2) — Shared Component Foundation
// ----------------------------------------------------------------------------
// Source of truth for all 74 P2 templates. Mirrors `platform tenant tsx/
// 10Component foundation.tsx` canonical tokens (cream + gold + Playfair).
//
// Usage in each template `.ts`:
//   import {
//     GlobalStyles, KaoriLockup, Button, Input, PasswordField, Checkbox,
//     Badge, ErrorBanner, SuccessBanner, QuotaBar,
//     api, parseProblemDetails, formatVND, formatVNDLong, cn,
//   } from './foundation';
//
// Generated 2026-05-01. When updating tokens, edit here, all templates
// pick up automatically.
// ============================================================================

import React, { useState, forwardRef } from 'react';
import { Eye, EyeOff, Loader2, AlertCircle, CheckCircle2 } from 'lucide-react';
import { useT } from '@/lib/i18n/provider';

// ============================================================================
// 1. UTILS
// ============================================================================

export const cn = (...classes: any[]) => classes.filter(Boolean).join(' ');

/** Format VND with dot thousand separator + ₫ symbol. Never use "1M". */
export function formatVND(amount: number): string {
  return new Intl.NumberFormat('vi-VN').format(amount) + '₫';
}

/** Long form: "1 triệu VNĐ" / "8 triệu VNĐ" / "20 triệu VNĐ". */
export function formatVNDLong(amount: number): string {
  if (amount >= 1_000_000_000) {
    const t = (amount / 1_000_000_000).toFixed(1).replace(/\.0$/, '');
    return `${t} tỷ VNĐ`;
  }
  if (amount >= 1_000_000) {
    const t = (amount / 1_000_000).toFixed(1).replace(/\.0$/, '');
    return `${t} triệu VNĐ`;
  }
  if (amount >= 1_000) {
    return `${(amount / 1_000).toFixed(0)} nghìn VNĐ`;
  }
  return `${amount} VNĐ`;
}

/** Pricing plan VND amounts (CLAUDE.md §10). */
export const PRICING = {
  PILOT:    1_000_000,   // 1.000.000₫
  BASIC:    2_000_000,   // 2.000.000₫
  MID:      5_000_000,   // 5.000.000₫
  MAX:      8_000_000,   // 8.000.000₫
  ROI_BASE: 8_000_000,   // 8M + 1.5% revenue saved
  ROI_CAP:  20_000_000,  // cap 20.000.000₫
};

/**
 * RFC 7807 Problem Details parser (K-14).
 * Backend returns `application/problem+json` on errors.
 */
export interface ProblemDetails {
  type?:     string;
  title:     string;
  status?:   number;
  detail?:   string;
  instance?: string;
  // Kaori extension fields
  lockout_remaining_seconds?: number;
  missing_perms?: string[];
}

export async function parseProblemDetails(res: Response): Promise<ProblemDetails> {
  try {
    const body = await res.json();
    return {
      type:     body.type ?? 'about:blank',
      title:    body.title ?? `HTTP ${res.status}`,
      status:   body.status ?? res.status,
      detail:   body.detail,
      instance: body.instance,
      lockout_remaining_seconds: body.lockout_remaining_seconds,
      missing_perms: body.missing_perms,
    };
  } catch {
    return { title: `HTTP ${res.status}`, status: res.status };
  }
}

/** Generate Idempotency-Key for POST mutations (K-13). */
export function newIdempotencyKey(): string {
  // crypto.randomUUID is widely available in modern browsers
  return (typeof crypto !== 'undefined' && (crypto as any).randomUUID)
    ? (crypto as any).randomUUID()
    : `idem-${Date.now()}-${Math.random().toString(36).slice(2, 10)}`;
}

/**
 * Fetch wrapper:
 * - Auto attaches JWT from localStorage (K-7 — never tenant_id in URL)
 * - Auto adds Idempotency-Key on POST/PATCH/DELETE (K-13)
 * - Throws ProblemDetails on non-2xx (K-14)
 */
// Same env var as frontend/lib/api.ts — when MSW dev mode is on this
// is irrelevant (the worker intercepts before fetch hits the network),
// but the moment NEXT_PUBLIC_DISABLE_MSW=1 is set the absolute origin
// is what routes the request to the api-gateway on :8080 instead of
// looping back to the Next.js dev server on :3000 (which 404s every
// /api/v1/* request).
export const API_BASE =
  (typeof process !== 'undefined' && process.env.NEXT_PUBLIC_API_URL) ||
  'http://localhost:8080';

// ── Auto token refresh (single-flight) ──────────────────────────────────────
// On a 401 the P2 `api` helper transparently refreshes the access token using
// the stored refresh token, then retries the request ONCE. Without this an
// expired access token breaks long flows (uploads, the workflow builder) even
// though the refresh token is still valid — the user just got 401'd mid-action.
// Mirrors lib/api/client.ts's axios interceptor (which only covers the axios
// callers, not the fetch-based `api` the P2 portal uses).
let _refreshInFlight: Promise<string | null> | null = null;

async function _refreshAccessToken(): Promise<string | null> {
  if (typeof window === 'undefined') return null;
  const refresh = window.localStorage.getItem('kaori.refresh_token');
  if (!refresh) return null;
  const isAdmin = window.localStorage.getItem('kaori.token_kind') === 'platform';
  try {
    const res = await fetch(
      `${API_BASE}${isAdmin ? '/auth/platform/refresh' : '/auth/refresh'}`,
      {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(isAdmin ? { refresh_token: refresh } : { refreshToken: refresh }),
      },
    );
    if (!res.ok) return null;
    const body = await res.json();
    const a = body.data ?? body;
    const access = a.access_token ?? a.accessToken;
    const newRefresh = a.refresh_token ?? a.refreshToken;
    if (!access) return null;
    window.localStorage.setItem('kaori.access_token', access);
    if (newRefresh) window.localStorage.setItem('kaori.refresh_token', newRefresh);
    // Keep the legacy key in sync so api()'s `kaori_jwt ?? kaori.access_token`
    // read doesn't keep serving the stale token after a refresh.
    if (window.localStorage.getItem('kaori_jwt')) window.localStorage.setItem('kaori_jwt', access);
    return access;
  } catch {
    return null;
  }
}

function _isAuthPath(path: string): boolean {
  return path.includes('/auth/refresh') || path.includes('/auth/login');
}

function _tokenExp(token: string | null): number {
  if (!token) return 0;
  try {
    const payload = JSON.parse(atob(token.split('.')[1] ?? ''));
    return typeof payload.exp === 'number' ? payload.exp : 0;
  } catch { return 0; }
}

// Returns a non-expired access token, refreshing FIRST if the current one is
// expired or within 60s of expiry. Use before a long raw request (the XHR file
// upload) that can't ride api()'s 401-retry — proactively swaps a token that
// would 401 mid-upload. Returns null only if there's no usable session.
export async function ensureFreshToken(): Promise<string | null> {
  if (typeof window === 'undefined') return null;
  const cur = window.localStorage.getItem('kaori.access_token')
    ?? window.localStorage.getItem('kaori_jwt');
  const now = Math.floor(Date.now() / 1000);
  if (cur && _tokenExp(cur) > now + 60) return cur;   // still valid >60s
  if (!_refreshInFlight) {
    _refreshInFlight = _refreshAccessToken().finally(() => { _refreshInFlight = null; });
  }
  const fresh = await _refreshInFlight;
  return fresh ?? cur;
}

export async function api<T = any>(
  path: string,
  init: RequestInit = {},
): Promise<T> {
  return _apiOnce<T>(path, init, true);
}

async function _apiOnce<T = any>(
  path: string,
  init: RequestInit,
  allowRetry: boolean,
): Promise<T> {
  const method = (init.method ?? 'GET').toUpperCase();
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    'Accept':       'application/json, application/problem+json',
    ...((init.headers as any) ?? {}),
  };

  // Two token storage keys exist in the codebase:
  //   * 'kaori_jwt'           — older P2 templates set this on login.
  //   * 'kaori.access_token'  — what frontend/lib/auth-store.ts writes.
  // Read both so a session minted by either path authenticates here.
  const token =
    typeof window !== 'undefined'
      ? (window.localStorage.getItem('kaori_jwt') ??
         window.localStorage.getItem('kaori.access_token'))
      : null;
  if (token) headers['Authorization'] = `Bearer ${token}`;

  if (method !== 'GET' && method !== 'HEAD') {
    headers['Idempotency-Key'] = headers['Idempotency-Key'] ?? newIdempotencyKey();
  }

  // Prepend API_BASE for relative paths (starts with '/'). Absolute
  // URLs pass through unchanged.
  const url = path.startsWith('/') ? `${API_BASE}${path}` : path;
  const res = await fetch(url, { ...init, headers });

  // Expired access token → refresh once (single-flight) + retry. The retry
  // reuses the SAME Idempotency-Key (K-13) so a retried POST isn't a new
  // mutation. Auth endpoints are excluded to avoid a refresh loop.
  if (res.status === 401 && allowRetry && typeof window !== 'undefined' && !_isAuthPath(path)) {
    if (!_refreshInFlight) {
      _refreshInFlight = _refreshAccessToken().finally(() => { _refreshInFlight = null; });
    }
    const fresh = await _refreshInFlight;
    if (fresh) {
      return _apiOnce<T>(path, {
        ...init,
        headers: { ...headers, Authorization: `Bearer ${fresh}` },
      }, false);
    }
    // Refresh failed → the session is truly gone; bounce to the right login.
    const isAdmin = window.localStorage.getItem('kaori.token_kind') === 'platform';
    window.location.href = isAdmin ? '/platform/login' : '/login';
  }

  if (!res.ok) {
    const problem = await parseProblemDetails(res);
    throw problem;
  }
  if (res.status === 204) return undefined as any;
  return res.json();
}

// ============================================================================
// 2. GLOBAL STYLES — design tokens (cream + gold + Playfair)
// ============================================================================

export const GlobalStyles = () => (
  <style>{`
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600&family=Playfair+Display:ital,wght@0,400;0,500;0,600;1,400&display=swap');

    :root {
      /* Brand colors */
      --primary-gold:      #D4B88A;
      --primary-gold-dark: #BFA88C;

      /* Backgrounds */
      --bg-app:     #FAF7F2;
      --bg-sidebar: #F5F1EA;
      --bg-card:    #FFFFFF;

      /* Borders + text */
      --border-color:    #E9E7E2;
      --text-primary:    #2F2F2F;
      --text-secondary:  #8C8173;

      /* State colors (pastel) */
      --state-success: #8FBFA0;
      --state-warning: #E6C07B;
      --state-error:   #D97C7C;
      --state-info:    #A5B4CB;

      /* Shadows */
      --shadow-soft-sm: 0 2px 8px -2px rgba(47,47,47,0.04), 0 1px 3px -1px rgba(47,47,47,0.02);
      --shadow-soft-md: 0 6px 16px -4px rgba(47,47,47,0.06), 0 4px 8px -2px rgba(47,47,47,0.03);
      --shadow-soft-lg: 0 12px 24px -4px rgba(47,47,47,0.08), 0 8px 12px -4px rgba(47,47,47,0.04);

      /* Radii */
      --radius-sm: 8px;
      --radius-md: 12px;
      --radius-lg: 16px;
    }

    body {
      font-family: 'Inter', sans-serif;
      background-color: var(--bg-app);
      color: var(--text-primary);
      margin: 0;
      -webkit-font-smoothing: antialiased;
    }

    .font-serif         { font-family: 'Playfair Display', serif; }
    .shadow-soft-sm     { box-shadow: var(--shadow-soft-sm); }
    .shadow-soft-md     { box-shadow: var(--shadow-soft-md); }
    .shadow-soft-lg     { box-shadow: var(--shadow-soft-lg); }
    .rounded-sm-custom  { border-radius: var(--radius-sm); }
    .rounded-md-custom  { border-radius: var(--radius-md); }
    .rounded-lg-custom  { border-radius: var(--radius-lg); }

    ::-webkit-scrollbar           { width: 6px; height: 6px; }
    ::-webkit-scrollbar-track     { background: transparent; }
    ::-webkit-scrollbar-thumb     { background: #E9E7E2; border-radius: 10px; }
    ::-webkit-scrollbar-thumb:hover { background: #D4B88A; }

    @keyframes slideUpFade {
      from { opacity: 0; transform: translateY(8px); }
      to   { opacity: 1; transform: translateY(0); }
    }
    .animate-slide-up-fade { animation: slideUpFade 0.4s cubic-bezier(0.16, 1, 0.3, 1) forwards; }

    .sidebar-transition {
      transition: width 0.3s cubic-bezier(0.2, 0, 0, 1), padding 0.3s ease, opacity 0.2s ease;
    }
  `}</style>
);

// ============================================================================
// 3. BRAND — KaoriLogo + KaoriLockup
// (mirrors frontend/components/brand/KaoriLogo.tsx)
// ============================================================================

export function KaoriLogo({
  size = 24,
  className = 'text-[var(--primary-gold)]',
  detailed = false,
}: { size?: number; className?: string; detailed?: boolean }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.5"
      className={className}
      aria-hidden="true"
    >
      <path
        d="M12 22C12 22 10 16 4 16C4 16 8 13 12 14C16 13 20 16 20 16C14 16 12 22 12 22Z"
        fill="currentColor"
        fillOpacity="0.1"
      />
      <path
        d="M12 14C12 14 10 8 12 2C14 8 12 14 12 14Z"
        fill="currentColor"
        fillOpacity="0.1"
      />
      {detailed && (
        <>
          <path d="M4 16C4 16 1 12 5 8C6.5 11 9.5 13 12 14" strokeLinecap="round" />
          <path d="M20 16C20 16 23 12 19 8C17.5 11 14.5 13 12 14" strokeLinecap="round" />
        </>
      )}
    </svg>
  );
}

export function KaoriLockup({
  tagline = 'Workspace',
  iconOnly = false,
}: { tagline?: string; iconOnly?: boolean }) {
  return (
    <div className="flex items-center gap-3">
      <div className="flex h-8 w-8 items-center justify-center rounded-md-custom bg-white shadow-soft-sm border border-[var(--border-color)] shrink-0">
        <KaoriLogo size={20} />
      </div>
      {!iconOnly && (
        <div className="flex flex-col overflow-hidden">
          <span className="font-serif text-[17px] leading-none font-semibold text-[var(--text-primary)] tracking-wide">
            Kaori
          </span>
          {tagline && (
            <span className="text-[10px] uppercase tracking-wider font-medium text-[var(--text-secondary)] mt-0.5">
              {tagline}
            </span>
          )}
        </div>
      )}
    </div>
  );
}

// ============================================================================
// 4. PRIMITIVES — Button, Label, Input, PasswordField, Checkbox, Badge
// ============================================================================

type ButtonVariant = 'primary' | 'secondary' | 'tertiary' | 'destructive';
type ButtonSize    = 'sm' | 'md' | 'lg' | 'icon';

interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?:   ButtonVariant;
  size?:      ButtonSize;
  isLoading?: boolean;
}

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant = 'primary', size = 'md', isLoading, disabled, children, ...props }, ref) => {
    const variants: Record<ButtonVariant, string> = {
      primary:     'bg-[var(--primary-gold)] text-[var(--text-primary)] hover:bg-[var(--primary-gold-dark)] active:scale-[0.98] shadow-soft-sm border border-transparent',
      secondary:   'border border-[var(--border-color)] bg-[var(--bg-card)] text-[var(--text-primary)] hover:bg-[var(--bg-app)] active:scale-[0.98] shadow-sm',
      tertiary:    'bg-transparent text-[var(--text-secondary)] hover:text-[var(--text-primary)] hover:bg-[var(--border-color)]/30 active:scale-[0.98]',
      destructive: 'bg-[var(--state-error)] text-white hover:bg-[#C26B6B] active:scale-[0.98] shadow-soft-sm border border-transparent',
    };
    const sizes: Record<ButtonSize, string> = {
      sm:   'h-8 px-3 text-xs rounded-sm-custom',
      md:   'h-10 px-4 py-2 text-sm rounded-md-custom',
      lg:   'h-12 px-6 py-3 text-base rounded-md-custom',
      icon: 'h-10 w-10 rounded-md-custom',
    };
    return (
      <button
        ref={ref}
        disabled={isLoading || disabled}
        className={cn(
          'inline-flex items-center justify-center font-medium transition-all duration-200 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--primary-gold)]/50 disabled:opacity-50 disabled:pointer-events-none',
          variants[variant],
          sizes[size],
          className,
        )}
        {...props}
      >
        {isLoading && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
        {children}
      </button>
    );
  },
);
Button.displayName = 'Button';

export const Label = forwardRef<HTMLLabelElement, React.LabelHTMLAttributes<HTMLLabelElement>>(
  ({ className, ...props }, ref) => (
    <label
      ref={ref}
      className={cn(
        'text-sm font-medium leading-none text-[var(--text-primary)] peer-disabled:cursor-not-allowed peer-disabled:opacity-70',
        className,
      )}
      {...props}
    />
  ),
);
Label.displayName = 'Label';

interface InputProps extends React.InputHTMLAttributes<HTMLInputElement> {
  label?:      string;
  error?:      boolean | string;
  helperText?: string;
}

export const Input = forwardRef<HTMLInputElement, InputProps>(
  ({ className, label, error, helperText, ...props }, ref) => {
    const errorMsg = typeof error === 'string' ? error : undefined;
    return (
      <div className="space-y-2 w-full">
        {label && <Label>{label}</Label>}
        <input
          ref={ref}
          className={cn(
            'flex h-10 w-full rounded-md-custom border bg-white px-3 py-2 text-sm text-[var(--text-primary)] placeholder:text-[var(--text-secondary)]/60 transition-all duration-200',
            'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--primary-gold)]/40 focus-visible:border-[var(--primary-gold)]',
            error
              ? 'border-[var(--state-error)] focus-visible:ring-[var(--state-error)]/30 focus-visible:border-[var(--state-error)]'
              : 'border-[var(--border-color)]',
            'disabled:cursor-not-allowed disabled:opacity-50',
            className,
          )}
          {...props}
        />
        {(errorMsg || helperText) && (
          <p
            className={cn(
              'text-xs',
              error ? 'text-[var(--state-error)]' : 'text-[var(--text-secondary)]',
            )}
          >
            {errorMsg || helperText}
          </p>
        )}
      </div>
    );
  },
);
Input.displayName = 'Input';

export function PasswordField({
  label,
  error,
  ...props
}: InputProps) {
  const t = useT();
  const [show, setShow] = useState(false);
  return (
    <div className="space-y-2 w-full">
      {label && <Label>{label}</Label>}
      <div className="relative">
        <input
          type={show ? 'text' : 'password'}
          className={cn(
            'flex h-10 w-full rounded-md-custom border bg-white pl-3 pr-11 py-2 text-sm text-[var(--text-primary)] placeholder:text-[var(--text-secondary)]/60 transition-all',
            'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--primary-gold)]/40 focus-visible:border-[var(--primary-gold)]',
            error
              ? 'border-[var(--state-error)] focus-visible:ring-[var(--state-error)]/30'
              : 'border-[var(--border-color)]',
            'disabled:opacity-50',
          )}
          {...props}
        />
        <button
          type="button"
          onClick={() => setShow(!show)}
          disabled={props.disabled}
          className="absolute right-3 top-1/2 -translate-y-1/2 text-[var(--text-secondary)] hover:text-[var(--text-primary)] disabled:opacity-50"
          tabIndex={-1}
          aria-label={show ? t('foundation.hidePassword') : t('foundation.showPassword')}
        >
          {show ? <EyeOff size={18} /> : <Eye size={18} />}
        </button>
      </div>
    </div>
  );
}

export function Checkbox({
  label,
  checked,
  onChange,
  disabled,
}: {
  label?: React.ReactNode;
  checked?: boolean;
  onChange?: (e: React.ChangeEvent<HTMLInputElement>) => void;
  disabled?: boolean;
}) {
  return (
    <label className="flex items-center space-x-2 cursor-pointer group">
      <div className="relative flex items-center justify-center w-4 h-4">
        <input
          type="checkbox"
          checked={checked}
          onChange={onChange}
          disabled={disabled}
          className="peer appearance-none w-4 h-4 border border-[var(--border-color)] rounded-sm-custom bg-white checked:bg-[var(--primary-gold)] checked:border-[var(--primary-gold)] focus:outline-none focus:ring-2 focus:ring-[var(--primary-gold)]/30 focus:ring-offset-1 transition-colors disabled:opacity-50"
        />
        <svg
          className="absolute w-3 h-3 text-white pointer-events-none opacity-0 peer-checked:opacity-100 transition-opacity"
          fill="none"
          viewBox="0 0 24 24"
          stroke="currentColor"
          strokeWidth="3"
        >
          <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
        </svg>
      </div>
      {label && (
        <span className="text-sm text-[var(--text-secondary)] group-hover:text-[var(--text-primary)] transition-colors">
          {label}
        </span>
      )}
    </label>
  );
}

type BadgeVariant =
  | 'default' | 'success' | 'warning' | 'error' | 'info' | 'current'
  | 'operational' | 'degraded';

export function Badge({
  variant = 'default',
  children,
  className,
}: { variant?: BadgeVariant; children: React.ReactNode; className?: string }) {
  const variants: Record<BadgeVariant, string> = {
    default:     'bg-[var(--bg-app)] text-[var(--text-secondary)] border-[var(--border-color)]',
    success:     'bg-[var(--state-success)]/10 text-[#5C856A] border-[var(--state-success)]/30',
    warning:     'bg-[var(--state-warning)]/10 text-[#9E814D] border-[var(--state-warning)]/30',
    error:       'bg-[var(--state-error)]/10 text-[#9B5050] border-[var(--state-error)]/30',
    info:        'bg-[var(--state-info)]/10 text-[#52647D] border-[var(--state-info)]/30',
    current:     'bg-[var(--primary-gold)]/10 text-[#9E814D] border-[var(--primary-gold)]/30',
    operational: 'bg-[#F3F9F5] text-[#427A5B] border-[#8FBFA0]/40',
    degraded:    'bg-[#FDF9F0] text-[#9E814D] border-[#E6C07B]/40',
  };
  return (
    <span
      className={cn(
        'inline-flex items-center px-2 py-0.5 rounded-sm-custom text-[11px] font-medium border',
        variants[variant],
        className,
      )}
    >
      {children}
    </span>
  );
}

// ============================================================================
// 5. FEEDBACK — ErrorBanner (RFC 7807 aware), SuccessBanner
// ============================================================================

export function ErrorBanner({
  problem,
  message,
}: {
  problem?: ProblemDetails | null;
  message?: string;
}) {
  const t = useT();
  if (!problem && !message) return null;
  const title  = problem?.title ?? message ?? t('foundation.genericError');
  const detail = problem?.detail;
  return (
    <div
      role="alert"
      className="flex items-start space-x-3 p-3 rounded-md-custom bg-[var(--state-error)]/10 border border-[var(--state-error)]/30 text-[#9B5050] animate-slide-up-fade"
    >
      <AlertCircle className="h-5 w-5 shrink-0 mt-0.5 text-[var(--state-error)]" />
      <div className="flex-1 min-w-0">
        <p className="text-sm font-medium">{title}</p>
        {detail && <p className="text-xs mt-0.5 opacity-80">{detail}</p>}
        {problem?.lockout_remaining_seconds != null && (
          <p className="text-xs mt-0.5">
            {t('foundation.retryAfter', { minutes: Math.ceil(problem.lockout_remaining_seconds / 60) })}
          </p>
        )}
      </div>
    </div>
  );
}

export function SuccessBanner({ message }: { message: string }) {
  return (
    <div className="flex items-start space-x-3 p-4 rounded-md-custom bg-[var(--state-success)]/10 border border-[var(--state-success)]/30 text-[#5C856A] animate-slide-up-fade">
      <CheckCircle2 className="h-5 w-5 shrink-0 mt-0.5 text-[var(--state-success)]" />
      <span className="text-sm font-medium">{message}</span>
    </div>
  );
}

// ============================================================================
// 6. QUOTA BAR — F-030 + K-11 (DISTINCT customer_external_id per month)
// ============================================================================

export function QuotaBar({
  current,
  limit,
  unit,
}: { current: number; limit: number; unit?: string }) {
  const t = useT();
  const displayUnit = unit ?? t('foundation.customerUnit');
  const pct = Math.min(100, Math.round((current / Math.max(1, limit)) * 100));
  const variant: BadgeVariant =
    pct >= 95 ? 'error' : pct >= 80 ? 'warning' : 'success';
  const barColor =
    pct >= 95 ? 'bg-[var(--state-error)]'
    : pct >= 80 ? 'bg-[var(--state-warning)]'
    : 'bg-[var(--primary-gold)]';

  return (
    <div className="space-y-2">
      <div className="flex items-baseline justify-between">
        <span className="text-sm text-[var(--text-secondary)]">
          {current.toLocaleString('vi-VN')} / {limit.toLocaleString('vi-VN')} {displayUnit}
        </span>
        <Badge variant={variant}>{pct}%</Badge>
      </div>
      <div className="h-2 w-full rounded-sm-custom bg-[var(--border-color)]/40 overflow-hidden">
        <div
          className={cn('h-full transition-all duration-500', barColor)}
          style={{ width: `${pct}%` }}
        />
      </div>
      {pct >= 80 && pct < 95 && (
        <p className="text-xs text-[#9E814D]">
          {t('foundation.quotaWarning', { pct })}
        </p>
      )}
      {pct >= 95 && (
        <p className="text-xs text-[#9B5050]">
          {t('foundation.quotaCritical', { pct })}
        </p>
      )}
    </div>
  );
}
