import { create } from 'zustand';
import { persist } from 'zustand/middleware';

export type Role = 'MANAGER' | 'OPERATOR' | 'ANALYST' | 'VIEWER'
                 | 'SUPER_ADMIN' | 'ADMIN' | 'SUPPORT';

export type TokenKind = 'enterprise' | 'platform';

interface User {
  id: string;
  email: string;
  full_name?: string;
  role: Role;
  // Platform admins have no enterprise binding — keep these optional so the
  // same store can hold either an enterprise user or a Phase 3 platform admin.
  enterprise_id?: string;
  enterprise_name?: string;
  // Phase 3 Batch 3.1.a — present only for platform admins; the gateway
  // forwards it as X-Session-Id and idle/absolute timeouts revoke it.
  session_id?: string;
}

interface AuthState {
  user: User | null;
  accessToken: string | null;
  refreshToken: string | null;
  tokenKind: TokenKind | null;
  setAuth: (u: User, access: string, refresh: string, kind?: TokenKind) => void;
  clear: () => void;
  canSee: (allowed: Role[]) => boolean;
}

export const useAuth = create<AuthState>()(
  persist(
    (set, get) => ({
      user: null,
      accessToken: null,
      refreshToken: null,
      tokenKind: null,
      setAuth: (user, access, refresh, kind = 'enterprise') => {
        if (typeof window !== 'undefined') {
          localStorage.setItem('kaori.access_token', access);
          localStorage.setItem('kaori.refresh_token', refresh);
          localStorage.setItem('kaori.token_kind',    kind);
        }
        set({ user, accessToken: access, refreshToken: refresh, tokenKind: kind });
      },
      clear: () => {
        if (typeof window !== 'undefined') {
          localStorage.removeItem('kaori.access_token');
          localStorage.removeItem('kaori.refresh_token');
          localStorage.removeItem('kaori.token_kind');
        }
        set({ user: null, accessToken: null, refreshToken: null, tokenKind: null });
      },
      canSee: (allowed) => {
        const r = get().user?.role;
        return !!r && allowed.includes(r);
      },
    }),
    { name: 'kaori.auth' },
  ),
);
