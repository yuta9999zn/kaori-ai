'use client';

/**
 * Platform admin portal layout.
 *
 * Cream/gold AppShell from `components/platform/shell` (template tokens —
 * `--primary-gold`, `--bg-sidebar`, `--text-primary`) replaces the prior
 * inline 266-line sidebar. Visual layer is now shared with anything else
 * that mounts the same `<AppShell>` (currently only this tree).
 *
 * Preserved from the prior layout:
 *   - /platform/login renders without a shell (public)
 *   - Every other /platform/* path requires a platform-tier role
 *     (SUPER_ADMIN / ADMIN / SUPPORT); the rest of the auth-store roles
 *     get redirected to /platform/login
 *
 * Hydration gate: zustand persist loads the user from localStorage AFTER
 * first paint, so we wait for `useAuth.persist.hasHydrated()` before
 * running the role check. Otherwise the very first render sees user=null
 * and bounces a logged-in admin straight to /platform/login.
 *
 * Sub-layouts under /platform/billing, /platform/security, and
 * /platform/workspaces/[id] keep rendering their own section headers +
 * tab bars inside the AppShell `<main>`.
 */

import { useEffect, useState } from 'react';
import { usePathname, useRouter } from 'next/navigation';
import { useAuth, type Role } from '@/lib/auth-store';
import { AppShell } from '@/components/platform/shell';

const PLATFORM_ROLES: readonly Role[] = ['SUPER_ADMIN', 'ADMIN', 'SUPPORT'];

export default function PlatformLayout({ children }: { children: React.ReactNode }) {
  const path   = usePathname() ?? '';
  const router = useRouter();
  const role   = useAuth((s) => s.user?.role);

  const [hydrated, setHydrated] = useState<boolean>(
    () => (useAuth.persist?.hasHydrated?.() ?? false),
  );
  useEffect(() => {
    if (hydrated) return;
    const unsub = useAuth.persist?.onFinishHydration?.(() => setHydrated(true));
    if (useAuth.persist?.hasHydrated?.()) setHydrated(true);
    return unsub;
  }, [hydrated]);

  const isPublicPath    = path === '/platform/login';
  const hasPlatformRole = !!role && PLATFORM_ROLES.includes(role);

  useEffect(() => {
    if (isPublicPath) return;
    if (!hydrated) return;
    if (!hasPlatformRole) router.replace('/platform/login');
  }, [isPublicPath, hasPlatformRole, hydrated, router]);

  if (isPublicPath) return <>{children}</>;

  // Avoid flashing the empty shell before persist finishes loading the user
  // and before the auth gate has had a chance to redirect.
  if (!hydrated || !hasPlatformRole) return null;

  return <AppShell>{children}</AppShell>;
}
