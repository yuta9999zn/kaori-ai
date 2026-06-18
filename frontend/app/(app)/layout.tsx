'use client';

import { usePathname } from 'next/navigation';
import AppShell from "@/components/layout/AppShell";

/**
 * Two shells live in this codebase:
 *   - components/layout/AppShell  — global P1-style frame (used by
 *     /dashboard, /pipeline, etc).
 *   - components/p2/shell.tsx     — P2 enterprise frame (cream + gold,
 *     workspace-scoped). EVERY P2 template renders this internally.
 *
 * The original layout always wrapped children in the global AppShell, so
 * P2 pages ended up with BOTH shells stacked ("workspace trong
 * workspace"). Pilot UAT 2026-05-05 surfaced it as the headline visual
 * bug.
 *
 * Fix: skip the global AppShell when the active path lives under /p2/*.
 * The P2 template's own AppShell becomes the sole nav frame for that
 * sub-tree. Non-P2 pages (/dashboard, /pipeline, etc.) keep the global
 * shell unchanged.
 *
 * Note: /platform/* lives OUTSIDE the (app) route group entirely and
 * brings its own AppShell via app/platform/layout.tsx — this layout
 * never sees it.
 */
export default function AppLayout({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const isP2 = pathname?.startsWith('/p2');
  if (isP2) return <>{children}</>;
  return <AppShell>{children}</AppShell>;
}
