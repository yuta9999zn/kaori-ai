'use client';

/**
 * P1 Platform Manager — shared AppShell.
 *
 * Mirrors `components/p2/shell.tsx` but for the platform-admin portal:
 *   - Reads `NAV_TREE` from `./navigation` (P1-specific groups)
 *   - Uses Next.js `<Link>` + `usePathname()` instead of state-based routing
 *     (P1 templates baked an internal `activeRoute` state; we drop it)
 *   - Hides role-gated children when the current user does not match
 *   - Reads user identity from `useAuth` (auth-store) — no localStorage
 *     reach-around like the P2 demo shell
 *
 * Strict TS — no `@ts-nocheck`. Consumed by `app/(app)/p1/layout.tsx`,
 * so every P1 page renders inside this shell automatically.
 */

import { useMemo, useState } from 'react';
import Link from 'next/link';
import { usePathname, useRouter } from 'next/navigation';
import {
  Search, Bell, HelpCircle, Settings, LogOut, Menu,
  ChevronRight, ShieldCheck,
} from 'lucide-react';

import { GlobalStyles, KaoriLockup, cn } from './foundation';
import { NAV_TREE, type NavGroup, type NavChild } from './navigation';
import { useAuth, type Role } from '@/lib/auth-store';
import { useT } from '@/lib/i18n/provider';

// ============================================================================
// 1. Helpers
// ============================================================================

function isGroupActive(group: NavGroup, currentPath: string): boolean {
  return group.children.some((c) => currentPath.startsWith(c.path));
}

function isChildVisible(child: NavChild, role: Role | undefined): boolean {
  if (!child.role) return true;
  return role === child.role;
}

function userInitials(email: string | undefined): string {
  if (!email) return '–';
  const local = email.split('@')[0] ?? '';
  return (local.slice(0, 2) || '–').toUpperCase();
}

// ============================================================================
// 2. Sidebar — cream, expandable groups, gold active accent
// ============================================================================

interface SidebarProps {
  currentPath: string;
  isOpen:      boolean;
  onClose:     () => void;
}

function Sidebar({ currentPath, isOpen, onClose }: SidebarProps) {
  const user = useAuth((s) => s.user);

  const initialExpanded = useMemo(
    () => NAV_TREE.filter((g) => isGroupActive(g, currentPath)).map((g) => g.title),
    [currentPath],
  );
  const [expanded, setExpanded] = useState<string[]>(initialExpanded);

  function toggle(title: string) {
    setExpanded((prev) => (prev.includes(title) ? prev.filter((t) => t !== title) : [...prev, title]));
  }

  return (
    <>
      {isOpen && (
        <div
          className="fixed inset-0 bg-[var(--text-primary)]/30 backdrop-blur-sm z-40 lg:hidden"
          onClick={onClose}
        />
      )}

      <aside
        className={cn(
          'fixed top-0 left-0 bottom-0 w-[260px] bg-[var(--bg-sidebar)] border-r border-[var(--border-color)] overflow-y-auto z-40 sidebar-transition',
          'lg:translate-x-0 lg:static lg:h-screen',
          isOpen ? 'translate-x-0' : '-translate-x-full',
        )}
      >
        <div className="h-16 flex items-center px-5 border-b border-[var(--border-color)]/60">
          <KaoriLockup tagline="Platform" />
        </div>

        <div className="h-px bg-gradient-to-r from-transparent via-[var(--primary-gold)] to-transparent opacity-40" />

        <nav className="p-3 space-y-1 pb-20">
          {NAV_TREE.map((group) => {
            const visibleChildren = group.children.filter((c) => isChildVisible(c, user?.role));
            if (visibleChildren.length === 0) return null;

            const isExpanded  = expanded.includes(group.title);
            const groupActive = isGroupActive({ ...group, children: visibleChildren }, currentPath);
            const Icon        = group.icon;

            return (
              <div key={group.title} className="mb-0.5">
                <button
                  type="button"
                  onClick={() => toggle(group.title)}
                  className={cn(
                    'w-full flex items-center justify-between px-3 py-2 text-sm font-medium rounded-md-custom transition-colors',
                    groupActive
                      ? 'text-[var(--text-primary)]'
                      : 'text-[var(--text-secondary)] hover:text-[var(--text-primary)] hover:bg-[var(--bg-card)]/60',
                  )}
                >
                  <div className="flex items-center gap-3">
                    <Icon
                      className={cn(
                        'w-4 h-4',
                        groupActive
                          ? 'text-[var(--primary-gold-dark)]'
                          : 'text-[var(--text-secondary)]',
                      )}
                    />
                    <span>{group.title}</span>
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
                    {visibleChildren.map((child) => {
                      const active = currentPath === child.path;
                      return (
                        <Link
                          key={child.path}
                          href={child.path}
                          onClick={onClose}
                          className={cn(
                            'flex items-center justify-between px-3 py-1.5 text-sm rounded-sm-custom transition-colors',
                            active
                              ? 'bg-[var(--primary-gold)]/15 text-[var(--text-primary)] font-medium border-l-2 border-[var(--primary-gold)] -ml-[2px] pl-[10px]'
                              : 'text-[var(--text-secondary)] hover:text-[var(--text-primary)] hover:bg-[var(--bg-card)]/40',
                          )}
                        >
                          <span>{child.title}</span>
                          {child.phase && child.phase > 1 && (
                            <span className="text-[9px] uppercase tracking-wider text-[var(--text-secondary)]/60 ml-2 shrink-0">
                              {child.phase === 2 ? 'P2' : 'P3'}
                            </span>
                          )}
                        </Link>
                      );
                    })}
                  </div>
                )}
              </div>
            );
          })}
        </nav>
      </aside>
    </>
  );
}

// ============================================================================
// 3. Header — env badge + search + user menu
// ============================================================================

function Header({ onMenuToggle }: { onMenuToggle: () => void }) {
  const t      = useT();
  const user   = useAuth((s) => s.user);
  const clear  = useAuth((s) => s.clear);
  const router = useRouter();
  const [openMenu, setOpenMenu] = useState(false);

  function logout() {
    clear();
    router.replace('/platform/login');
  }

  return (
    <header className="h-16 bg-[var(--bg-card)] border-b border-[var(--border-color)] flex items-center justify-between px-4 sm:px-6 sticky top-0 z-30 shrink-0">
      <div className="flex items-center gap-3">
        <button
          type="button"
          onClick={onMenuToggle}
          className="lg:hidden p-2 text-[var(--text-secondary)] hover:bg-[var(--bg-app)] rounded-md-custom"
          aria-label={t('platformShell.menuAriaLabel')}
        >
          <Menu className="w-5 h-5" />
        </button>
        <div className="hidden md:flex items-center px-3 py-1.5 rounded-md-custom bg-[var(--bg-app)] border border-[var(--border-color)] text-sm text-[var(--text-primary)]">
          <ShieldCheck className="w-3.5 h-3.5 text-[var(--primary-gold-dark)] mr-2" />
          <span className="font-medium">{t('platformShell.brandBadge')}</span>
        </div>
      </div>

      <div className="flex-1 max-w-xl px-6 hidden md:block">
        <div className="relative">
          <Search className="w-4 h-4 text-[var(--text-secondary)] absolute left-3 top-1/2 -translate-y-1/2" />
          <input
            type="text"
            placeholder={t('platformShell.searchPlaceholder')}
            className="w-full bg-[var(--bg-app)] border border-[var(--border-color)] rounded-md-custom pl-9 pr-12 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-[var(--primary-gold)]/30 focus:border-[var(--primary-gold)] transition-all hover:bg-[var(--bg-card)]"
          />
          <kbd className="hidden lg:inline-flex absolute right-3 top-1/2 -translate-y-1/2 items-center border border-[var(--border-color)] rounded px-1.5 text-[10px] font-medium text-[var(--text-secondary)] bg-[var(--bg-card)]">
            ⌘K
          </kbd>
        </div>
      </div>

      <div className="flex items-center gap-1">
        <button
          type="button"
          className="p-2 text-[var(--text-secondary)] hover:bg-[var(--bg-app)] rounded-full relative"
          aria-label={t('platformShell.notificationsAriaLabel')}
        >
          <Bell className="w-5 h-5" />
          <span className="absolute top-1.5 right-1.5 w-2 h-2 bg-[var(--state-error)] rounded-full border-2 border-[var(--bg-card)]" />
        </button>
        <button
          type="button"
          className="hidden sm:block p-2 text-[var(--text-secondary)] hover:bg-[var(--bg-app)] rounded-full"
          aria-label={t('platformShell.helpAriaLabel')}
        >
          <HelpCircle className="w-5 h-5" />
        </button>

        <div className="relative">
          <button
            type="button"
            onClick={() => setOpenMenu((v) => !v)}
            className="ml-2 w-9 h-9 rounded-full bg-[var(--primary-gold)]/15 border border-[var(--primary-gold)]/30 flex items-center justify-center hover:ring-2 hover:ring-[var(--primary-gold)]/30 transition-all"
            aria-label={t('platformShell.accountAriaLabel')}
          >
            <span className="text-xs font-semibold text-[var(--primary-gold-dark)]">
              {userInitials(user?.email)}
            </span>
          </button>

          {openMenu && (
            <div className="absolute right-0 mt-2 w-60 bg-[var(--bg-card)] border border-[var(--border-color)] rounded-md-custom shadow-soft-md py-1 animate-slide-up-fade z-50">
              <div className="px-4 py-3 border-b border-[var(--border-color)]/60">
                <p className="text-sm font-semibold text-[var(--text-primary)]">
                  {user?.email ?? t('platformShell.accountFallback')}
                </p>
                <p className="text-xs text-[var(--text-secondary)] mt-0.5">
                  {t('platformShell.roleLabel')} <span className="font-medium">{user?.role ?? 'GUEST'}</span>
                </p>
              </div>
              <Link
                href="/platform/security/sessions"
                onClick={() => setOpenMenu(false)}
                className="flex items-center px-4 py-2 text-sm text-[var(--text-primary)] hover:bg-[var(--bg-app)]"
              >
                <Settings className="w-4 h-4 mr-2 text-[var(--text-secondary)]" /> {t('platformShell.sessionsSecurity')}
              </Link>
              <div className="border-t border-[var(--border-color)]/60 mt-1 pt-1">
                <button
                  type="button"
                  onClick={logout}
                  className="w-full flex items-center px-4 py-2 text-sm text-[var(--state-error)] hover:bg-[var(--state-error)]/8"
                >
                  <LogOut className="w-4 h-4 mr-2" /> {t('platformShell.logout')}
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
// 4. AppShell — public wrapper used by app/(app)/p1/layout.tsx
// ============================================================================

export function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname() ?? '/p1';
  const [sidebarOpen, setSidebarOpen] = useState(false);

  return (
    <>
      <GlobalStyles />
      <div className="flex min-h-screen bg-[var(--bg-app)] text-[var(--text-primary)]">
        <Sidebar
          currentPath={pathname}
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
// 5. PageHeader — section title + actions slot (mirrors p2 shell)
// ============================================================================

export function PageHeader({
  title,
  description,
  actions,
}: {
  title:       string;
  description?: string;
  actions?:     React.ReactNode;
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
