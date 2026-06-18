import type { ReactNode } from 'react';
import { AppShell } from '@/components/p2/shell';

export const metadata = {
  title: 'Kaori Enterprise',
};

/**
 * P2 enterprise portal layout — wraps every `/p2/*` page in the shared
 * cream/gold AppShell (parallel to /platform/layout.tsx).
 *
 * Prior to this refactor each P2 template carried its own <AppShell>
 * wrap with a hard-coded `currentPath` prop. That worked but meant 74
 * templates had to import shell + foundation. Now the shell lives at
 * the layout level and pages just render content. The grandparent
 * `app/(app)/layout.tsx` skips the global enterprise frame for /p2/*
 * (commit 2b0d164), so this AppShell is the sole nav frame.
 *
 * AppShell reads `usePathname()` to mark the active sidebar entry — no
 * `currentPath` prop needed at this level.
 */
export default function P2Layout({ children }: { children: ReactNode }) {
  return <AppShell>{children}</AppShell>;
}
