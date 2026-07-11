/**
 * Typed fetch wrapper. Reads JWT from localStorage, auto-attaches
 * Authorization header, parses JSON, throws on non-2xx.
 *
 * Components from Kise AI that use api() can be imported as-is.
 * Kaori-specific API domains (authApi, pipelineApi, etc.) remain in
 * lib/api/client.ts (axios-based with auto-refresh).
 */

import { safeRandomUUID } from './uuid';

export interface ApiError {
  status: number;
  error: string;
  message: string;
  /** RFC 7807 type URI when the server returns application/problem+json. */
  type?: string;
  /** RFC 7807 detail. Falls back to legacy { message } if absent. */
  detail?: string;
  /** Phase 2 #1 — canonical machine-readable code (DOMAIN.NAME). The FE
   *  maps this to an i18n bundle entry; falls back to `message` for
   *  display when the code isn't recognised. Always emitted by the
   *  gateway + auth-service + the four Python services. */
  code?: string;
  /** 3.1.b — present on 423 responses from /security/mfa/verify. */
  lockout_remaining_seconds?: number;
  trace_id?: string;
}

const BASE = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8080';

// Single-flight access-token refresh on 401 — without it the 15-min access TTL
// 401s long sessions even though the refresh token is valid. Mirrors
// components/p2/foundation.tsx + lib/api/client.ts.
let _refreshInFlight: Promise<string | null> | null = null;

async function _refreshAccessToken(): Promise<string | null> {
  if (typeof window === 'undefined') return null;
  const refresh = localStorage.getItem('kaori.refresh_token');
  if (!refresh) return null;
  const isAdmin = localStorage.getItem('kaori.token_kind') === 'platform';
  try {
    const res = await fetch(`${BASE}${isAdmin ? '/auth/platform/refresh' : '/auth/refresh'}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(isAdmin ? { refresh_token: refresh } : { refreshToken: refresh }),
    });
    if (!res.ok) return null;
    const body = await res.json();
    const a = body.data ?? body;
    const access = a.access_token ?? a.accessToken;
    if (!access) return null;
    localStorage.setItem('kaori.access_token', access);
    const nr = a.refresh_token ?? a.refreshToken;
    if (nr) localStorage.setItem('kaori.refresh_token', nr);
    return access;
  } catch { return null; }
}

export async function api<T>(
  path: string,
  init: RequestInit = {},
): Promise<T> {
  return _apiOnce<T>(path, init, true);
}

async function _apiOnce<T>(
  path: string,
  init: RequestInit,
  allowRetry: boolean,
): Promise<T> {
  const headers = new Headers(init.headers);
  headers.set('Accept', 'application/json');
  if (!(init.body instanceof FormData)) {
    headers.set('Content-Type', 'application/json');
  }
  const token =
    typeof window !== 'undefined' ? localStorage.getItem('kaori.access_token') : null;
  if (token) headers.set('Authorization', `Bearer ${token}`);

  // K-13 — gateway IdempotencyFilter rejects POST/PUT/PATCH/DELETE under
  // /api/v1/** without an Idempotency-Key header (400 RFC 7807). Generate a
  // fresh UUID per call so every mutation is dedup-keyed; callers that want
  // to retry the same logical mutation can pass init.headers['Idempotency-Key']
  // explicitly and we won't overwrite it.
  const method = (init.method ?? 'GET').toUpperCase();
  if (
    ['POST', 'PUT', 'PATCH', 'DELETE'].includes(method) &&
    path.startsWith('/api/v1/') &&
    !headers.has('Idempotency-Key')
  ) {
    headers.set('Idempotency-Key', safeRandomUUID());
  }

  const res = await fetch(`${BASE}${path}`, { ...init, headers });

  // Expired access token → refresh once (single-flight) + retry, reusing the
  // same Idempotency-Key (K-13). Auth endpoints excluded to avoid a loop.
  if (res.status === 401 && allowRetry && typeof window !== 'undefined'
      && !path.includes('/auth/refresh') && !path.includes('/auth/login')) {
    if (!_refreshInFlight) {
      _refreshInFlight = _refreshAccessToken().finally(() => { _refreshInFlight = null; });
    }
    const fresh = await _refreshInFlight;
    if (fresh) {
      const h2 = new Headers(init.headers);
      h2.set('Authorization', `Bearer ${fresh}`);
      const idem = headers.get('Idempotency-Key');
      if (idem) h2.set('Idempotency-Key', idem);
      return _apiOnce<T>(path, { ...init, headers: h2 }, false);
    }
    const isAdmin = localStorage.getItem('kaori.token_kind') === 'platform';
    window.location.href = isAdmin ? '/platform/login' : '/login';
  }

  const text = await res.text();
  const json = text ? JSON.parse(text) : null;

  if (!res.ok) {
    // RFC 7807 envelopes from auth-service / gateway use { type, title,
    // status, detail }; legacy responses use { error, message }. Pull
    // human-readable text from whichever shape applies. The `message`
    // field is what existing components render — preserve it as the
    // single hand-off so call sites don't all need to learn the new shape.
    const humanMsg = json?.detail
                  ?? json?.title
                  ?? json?.message
                  ?? res.statusText;
    const err: ApiError = {
      status:    res.status,
      error:     json?.error ?? json?.title ?? 'unknown',
      message:   humanMsg,
      type:      json?.type,
      detail:    json?.detail,
      code:      json?.code,
      lockout_remaining_seconds: json?.lockout_remaining_seconds,
      trace_id:  json?.trace_id,
    };
    throw err;
  }
  return json as T;
}

export const getAccessToken = () =>
  typeof window !== 'undefined' ? localStorage.getItem('kaori.access_token') : null;

export function setAccessToken(token: string | null) {
  if (typeof window === 'undefined') return;
  if (token) localStorage.setItem('kaori.access_token', token);
  else localStorage.removeItem('kaori.access_token');
}
