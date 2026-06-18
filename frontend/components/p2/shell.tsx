'use client';

// @ts-nocheck
// ============================================================================
// Kaori AI — User Enterprise (P2) — Shared App Shell
// ----------------------------------------------------------------------------
// Cream sidebar (#F5F1EA) + KaoriLockup + gold accent + Header. Used by every
// signed-in screen (file 9 onwards). Mirrors `frontend/components/layout/
// Sidebar.tsx` and `frontend/app/(app)/layout.tsx` patterns from the real
// codebase but lives standalone so templates have no app-router deps.
//
// Usage:
//   <AppShell currentPath="/p2/dashboard">{...your page content...}</AppShell>
// ============================================================================

import React, { useState, useEffect, useMemo } from 'react';
import { usePathname } from 'next/navigation';
import {
  Search, Bell, HelpCircle, Settings, LogOut, Menu, X,
  ChevronRight, ChevronDown, ShieldCheck,
} from 'lucide-react';

import { GlobalStyles, KaoriLockup, cn } from './foundation';
import { NAV_TREE, SECTION_ORDER, type NavGroup, type NavChild } from './navigation';
import { LocalePicker } from '@/components/i18n/locale-picker';
import { useChromeT } from '@/lib/i18n/chrome-i18n';

// ============================================================================
// 1. Workspace context (replaces hard-coded "Acme Corp")
// ============================================================================

interface WorkspaceContext {
  enterprise_name: string;
  user_email:      string;
  user_initials:   string;
  user_role:       'MANAGER' | 'OPERATOR' | 'ANALYST' | 'VIEWER';
}

function useWorkspace(): WorkspaceContext {
  // In production, hydrate from /api/v1/me. For template preview we read
  // localStorage('kaori_user') if present; otherwise show neutral placeholders
  // so the screen still renders at design time.
  const [ctx, setCtx] = useState<WorkspaceContext>({
    enterprise_name: 'Workspace',
    user_email:      '',
    user_initials:   '–',
    user_role:       'VIEWER',
  });

  useEffect(() => {
    try {
      const raw = window.localStorage.getItem('kaori_user');
      if (raw) {
        const u = JSON.parse(raw);
        setCtx({
          enterprise_name: u.enterprise_name ?? 'Workspace',
          user_email:      u.email ?? '',
          user_initials:   (u.email ?? 'U').slice(0, 2).toUpperCase(),
          user_role:       u.role ?? 'VIEWER',
        });
      }
    } catch { /* swallow */ }
  }, []);

  return ctx;
}

// ============================================================================
// 2. Sidebar — cream, expandable groups, gold active accent
// ============================================================================

function isGroupActive(group: NavGroup, currentPath: string): boolean {
  return group.children.some((c) => currentPath.startsWith(c.path));
}

function Sidebar({
  currentPath,
  isOpen,
  onClose,
}: { currentPath: string; isOpen: boolean; onClose: () => void }) {
  const ws = useWorkspace();

  // Auto-expand group containing current path; manual toggle for others.
  const initialExpanded = useMemo(
    () => NAV_TREE.filter((g) => isGroupActive(g, currentPath)).map((g) => g.title),
    [currentPath],
  );
  const [expanded, setExpanded] = useState<string[]>(initialExpanded);
  // Localize sidebar display labels (section/group/child) per current locale.
  // State + active-route matching still key off the raw VN title.
  const cT = useChromeT();

  function toggle(title: string) {
    setExpanded((prev) => (prev.includes(title) ? prev.filter((t) => t !== title) : [...prev, title]));
  }

  return (
    <>
      {isOpen && (
        <div className="fixed inset-0 bg-[var(--text-primary)]/30 backdrop-blur-sm z-40 lg:hidden" onClick={onClose} />
      )}

      <aside
        className={cn(
          'fixed top-0 left-0 bottom-0 w-[260px] bg-[var(--bg-sidebar)] border-r border-[var(--border-color)] overflow-y-auto z-40 sidebar-transition',
          // lg: sticky (not static) so the sidebar stays pinned while a long
          // page scrolls — `static` let the whole nav (brand + top groups)
          // scroll off-screen on tall screens like the wizard results page.
          // The header is already sticky; this keeps the two consistent.
          'lg:translate-x-0 lg:sticky lg:top-0 lg:self-start lg:h-screen',
          isOpen ? 'translate-x-0' : '-translate-x-full',
        )}
      >
        {/* Brand block */}
        <div className="h-16 flex items-center px-5 border-b border-[var(--border-color)]/60">
          <KaoriLockup tagline={ws.enterprise_name} />
        </div>

        {/* Gold accent bar */}
        <div className="h-px bg-gradient-to-r from-transparent via-[var(--primary-gold)] to-transparent opacity-40" />

        {/* Nav */}
        <nav className="p-3 space-y-1 pb-20">
          {SECTION_ORDER.map((section) => (
            <div key={section} className="mb-2">
              <div className="px-3 pt-3 pb-1 text-[10px] font-semibold uppercase tracking-wider text-[var(--text-secondary)]/70">
                {cT(section)}
              </div>
              {NAV_TREE.filter((g) => g.section === section).map((group) => {
            const isExpanded = expanded.includes(group.title);
            const groupActive = isGroupActive(group, currentPath);
            const Icon = group.icon;
            return (
              <div key={group.title} className="mb-0.5">
                <button
                  onClick={() => toggle(group.title)}
                  className={cn(
                    'w-full flex items-center justify-between px-3 py-2 text-sm font-medium rounded-md-custom transition-colors',
                    groupActive
                      ? 'text-[var(--text-primary)]'
                      : 'text-[var(--text-secondary)] hover:text-[var(--text-primary)] hover:bg-[var(--bg-card)]/60',
                  )}
                >
                  <div className="flex items-center gap-3">
                    <Icon className={cn('w-4 h-4', groupActive ? 'text-[var(--primary-gold-dark)]' : 'text-[var(--text-secondary)]')} />
                    <span>{cT(group.title)}</span>
                  </div>
                  <ChevronRight
                    className={cn(
                      'w-4 h-4 text-[var(--text-secondary)] transition-transform duration-200',
                      isExpanded && 'rotate-90',
                    )}
                  />
                </button>

                {isExpanded && (
                  <div className="mt-1 ml-4 pl-3 border-l border-[var(--border-color)]/60 space-y-0.5 animate-slide-up-fade">
                    {group.children.map((child) => {
                      const active = currentPath === child.path;
                      return (
                        <a
                          key={child.path}
                          href={child.path}
                          className={cn(
                            'flex items-center justify-between px-3 py-1.5 text-sm rounded-sm-custom transition-colors',
                            active
                              ? 'bg-[var(--primary-gold)]/15 text-[var(--text-primary)] font-medium border-l-2 border-[var(--primary-gold)] -ml-[2px] pl-[10px]'
                              : 'text-[var(--text-secondary)] hover:text-[var(--text-primary)] hover:bg-[var(--bg-card)]/40',
                          )}
                        >
                          <span>{cT(child.title)}</span>
                          {child.phase && child.phase > 1 && (
                            <span className="text-[9px] uppercase tracking-wider text-[var(--text-secondary)]/60 ml-2 shrink-0">
                              {child.phase === 2 ? 'P2' : 'P3'}
                            </span>
                          )}
                        </a>
                      );
                    })}
                  </div>
                )}
              </div>
            );
          })}
            </div>
          ))}
        </nav>
      </aside>
    </>
  );
}

// ============================================================================
// 3. Header — search + bell + user menu
// ============================================================================

function Header({ onMenuToggle }: { onMenuToggle: () => void }) {
  const ws = useWorkspace();
  const [openMenu, setOpenMenu] = useState(false);

  function logout() {
    window.localStorage.removeItem('kaori_jwt');
    window.localStorage.removeItem('kaori_refresh');
    window.localStorage.removeItem('kaori_user');
    window.location.href = '/p2/auth/login';
  }

  return (
    <header className="h-16 bg-[var(--bg-card)] border-b border-[var(--border-color)] flex items-center justify-between px-4 sm:px-6 sticky top-0 z-30 shrink-0">
      <div className="flex items-center gap-3">
        <button
          onClick={onMenuToggle}
          className="lg:hidden p-2 text-[var(--text-secondary)] hover:bg-[var(--bg-app)] rounded-md-custom"
        >
          <Menu className="w-5 h-5" />
        </button>
        <div className="hidden md:flex items-center px-3 py-1.5 rounded-md-custom bg-[var(--bg-app)] border border-[var(--border-color)] text-sm text-[var(--text-primary)]">
          <ShieldCheck className="w-3.5 h-3.5 text-[var(--primary-gold-dark)] mr-2" />
          <span className="font-medium">{ws.enterprise_name}</span>
        </div>
      </div>

      {/* Global search */}
      <div className="flex-1 max-w-xl px-6 hidden md:block">
        <div className="relative">
          <Search className="w-4 h-4 text-[var(--text-secondary)] absolute left-3 top-1/2 -translate-y-1/2" />
          <input
            type="text"
            placeholder="Tìm dataset, pipeline, insight..."
            className="w-full bg-[var(--bg-app)] border border-[var(--border-color)] rounded-md-custom pl-9 pr-12 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-[var(--primary-gold)]/30 focus:border-[var(--primary-gold)] transition-all hover:bg-[var(--bg-card)]"
          />
          <kbd className="hidden lg:inline-flex absolute right-3 top-1/2 -translate-y-1/2 items-center border border-[var(--border-color)] rounded px-1.5 text-[10px] font-medium text-[var(--text-secondary)] bg-[var(--bg-card)]">
            ⌘K
          </kbd>
        </div>
      </div>

      <div className="flex items-center gap-1">
        {/* Language switcher — 5 locales (vi/en/ja/ko/zh), S0b i18n foundation */}
        <LocalePicker />
        <button className="p-2 text-[var(--text-secondary)] hover:bg-[var(--bg-app)] rounded-full relative" aria-label="Thông báo">
          <Bell className="w-5 h-5" />
          <span className="absolute top-1.5 right-1.5 w-2 h-2 bg-[var(--state-error)] rounded-full border-2 border-[var(--bg-card)]" />
        </button>
        <button className="hidden sm:block p-2 text-[var(--text-secondary)] hover:bg-[var(--bg-app)] rounded-full" aria-label="Trợ giúp">
          <HelpCircle className="w-5 h-5" />
        </button>

        <div className="relative">
          <button
            onClick={() => setOpenMenu(!openMenu)}
            className="ml-2 w-9 h-9 rounded-full bg-[var(--primary-gold)]/15 border border-[var(--primary-gold)]/30 flex items-center justify-center hover:ring-2 hover:ring-[var(--primary-gold)]/30 transition-all"
            aria-label="Tài khoản"
          >
            <span className="text-xs font-semibold text-[var(--primary-gold-dark)]">{ws.user_initials}</span>
          </button>

          {openMenu && (
            <div className="absolute right-0 mt-2 w-60 bg-[var(--bg-card)] border border-[var(--border-color)] rounded-md-custom shadow-soft-md py-1 animate-slide-up-fade z-50">
              <div className="px-4 py-3 border-b border-[var(--border-color)]/60">
                <p className="text-sm font-semibold text-[var(--text-primary)]">{ws.user_email || 'Tài khoản'}</p>
                <p className="text-xs text-[var(--text-secondary)] mt-0.5">Vai trò: <span className="font-medium">{ws.user_role}</span></p>
              </div>
              <a href="/settings" className="flex items-center px-4 py-2 text-sm text-[var(--text-primary)] hover:bg-[var(--bg-app)]">
                <Settings className="w-4 h-4 mr-2 text-[var(--text-secondary)]" /> Cài đặt
              </a>
              <a href="/p2/auth/sessions" className="flex items-center px-4 py-2 text-sm text-[var(--text-primary)] hover:bg-[var(--bg-app)]">
                <ShieldCheck className="w-4 h-4 mr-2 text-[var(--text-secondary)]" /> Phiên đăng nhập
              </a>
              <div className="border-t border-[var(--border-color)]/60 mt-1 pt-1">
                <button onClick={logout} className="w-full flex items-center px-4 py-2 text-sm text-[var(--state-error)] hover:bg-[var(--state-error)]/8">
                  <LogOut className="w-4 h-4 mr-2" /> Đăng xuất
                </button>
              </div>
            </div>
          )}
        </div>
      </div>
    </header>
  );
}

// ============================================================================
// 4. AppShell — public wrapper
// ============================================================================

export function AppShell({
  currentPath,
  children,
}: {
  /** Optional override — defaults to Next.js usePathname(). Layout-level
   * wrap should omit this and let the shell auto-detect; legacy template
   * callers that hard-coded their own path still work. */
  currentPath?: string;
  children: React.ReactNode;
}) {
  const detectedPath = usePathname() ?? '/p2';
  const path = currentPath ?? detectedPath;
  const [sidebarOpen, setSidebarOpen] = useState(false);
  return (
    <>
      <GlobalStyles />
      <div className="flex min-h-screen bg-[var(--bg-app)] text-[var(--text-primary)]">
        <Sidebar
          currentPath={path}
          isOpen={sidebarOpen}
          onClose={() => setSidebarOpen(false)}
        />
        <div className="flex-1 flex flex-col min-w-0">
          <Header onMenuToggle={() => setSidebarOpen(true)} />
          <main className="flex-1 min-h-0">{children}</main>
        </div>
      </div>
    </>
  );
}

// ============================================================================
// 5. Page header — section title + breadcrumbs + action slot
// ============================================================================

export function PageHeader({
  title, description, actions,
}: {
  title: string;
  description?: string;
  actions?: React.ReactNode;
}) {
  return (
    <div className="px-6 lg:px-8 py-6 border-b border-[var(--border-color)] bg-[var(--bg-card)]">
      <div className="flex flex-col sm:flex-row sm:items-end justify-between gap-4">
        <div>
          <h1 className="font-serif text-2xl text-[var(--text-primary)]">{title}</h1>
          {description && (
            <p className="text-sm text-[var(--text-secondary)] mt-1">{description}</p>
          )}
        </div>
        {actions && <div className="flex items-center gap-2 shrink-0">{actions}</div>}
      </div>
    </div>
  );
}
