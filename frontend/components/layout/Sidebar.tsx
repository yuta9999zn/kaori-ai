'use client';
import { useState } from 'react';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { useQuery } from '@tanstack/react-query';
import { cn } from '@/lib/cn';
import { api } from '@/lib/api';
import { useT } from '@/lib/i18n/provider';
import { KaoriLockup } from '@/components/brand/KaoriLogo';
import {
  LayoutDashboard, Database, PlayCircle, List, LineChart, Settings, FileText,
  Sparkles, Users, ChevronDown, ChevronRight, BarChart2, GitBranch,
  TrendingUp, Layers, PieChart, ScatterChart, Activity, Brain, Banknote,
  Briefcase, Building2, FileSignature,
} from 'lucide-react';

interface NavItem {
  href?: string;
  label: string;
  icon: any;
  activeWhen?: (path: string) => boolean;
  children?: NavItem[];
}

const TEMPLATE_ICON: Record<string, any> = {
  summary_stats:  BarChart2,
  time_series:    TrendingUp,
  distribution:   Layers,
  correlation:    ScatterChart,
  clustering:     PieChart,
  cohort:         Users,
  churn:          Activity,
  anomaly:        Brain,
  regression:     GitBranch,
  bank_classify:  Banknote,
};
const TEMPLATE_KEY: Record<string, string> = {
  summary_stats:  'analytics.summary_stats.title',
  time_series:    'analytics.time_series.title',
  distribution:   'analytics.distribution.title',
  correlation:    'analytics.correlation.title',
  clustering:     'analytics.clustering.title',
  cohort:         'analytics.cohort.title',
  churn:          'analytics.churn.title',
  anomaly:        'analytics.anomaly.title',
  regression:     'analytics.regression.title',
  bank_classify:  'analytics.bank_classify.title',
};

function isActive(item: NavItem, path: string): boolean {
  return item.activeWhen ? item.activeWhen(path) : !!item.href && path.startsWith(item.href);
}

export default function Sidebar() {
  const t = useT();
  const path = usePathname() ?? '';

  const { data: runsData } = useQuery<{ data: Array<{ template_id: string }> }>({
    queryKey: ['sidebar-analysis-runs'],
    queryFn: () => api('/api/v1/analytics/runs?limit=50'),
    staleTime: 60_000,
  });
  const ranTemplates: string[] = Array.from(
    new Set((runsData?.data ?? []).map((r) => r.template_id)),
  );

  const analyticsChildren: NavItem[] = [
    { href: '/analytics', label: t('nav.analytics.all'), icon: List, activeWhen: (p) => p === '/analytics' },
    ...ranTemplates.map((tid) => ({
      href: `/analytics/${tid}`,
      label: TEMPLATE_KEY[tid] ? t(TEMPLATE_KEY[tid]) : tid,
      icon: TEMPLATE_ICON[tid] ?? LineChart,
      activeWhen: (p: string) => p === `/analytics/${tid}`,
    })),
  ];

  const NAV: NavItem[] = [
    { href: '/dashboard', label: t('nav.dashboard'), icon: LayoutDashboard },
    {
      label: t('nav.pipeline'), icon: Database,
      activeWhen: (p) => p.startsWith('/pipeline'),
      children: [
        { href: '/pipeline/new', label: t('nav.pipeline.new'), icon: PlayCircle,
          activeWhen: (p) => p.startsWith('/pipeline/new') },
        { href: '/pipeline', label: t('nav.pipeline.list'), icon: List,
          activeWhen: (p) => p === '/pipeline' || (p.startsWith('/pipeline/') && !p.startsWith('/pipeline/new')) },
      ],
    },
    {
      label: t('nav.analytics'), icon: LineChart,
      activeWhen: (p) => p.startsWith('/analytics'),
      children: analyticsChildren,
    },
    { href: '/insights',  label: t('nav.insights'),  icon: Sparkles },
    { href: '/decisions', label: t('nav.decisions'), icon: FileText },
    { href: '/users',     label: t('nav.users'),     icon: Users },
    // P15-S11 — customer / vendor / contract (mig 062/063). Top-level
    // entries; FE templates may reshuffle later.
    { href: '/customers', label: 'Khách hàng',      icon: Briefcase },
    { href: '/vendors',   label: 'Nhà cung cấp',    icon: Building2 },
    { href: '/contracts', label: 'Hợp đồng',         icon: FileSignature },
    { href: '/settings',  label: t('nav.settings'),  icon: Settings },
  ];

  // Sprint 7 PR C — visual closeness with the platform redesign:
  //  * Sidebar bg flipped from `bg-surface` (white) to `var(--color-sidebar)`
  //    (cream #F5F1EA) so /login → /dashboard is one continuous brand surface
  //    instead of a sudden cream→white cut.
  //  * Wordmark replaced with <KaoriLockup tagline="Workspace"> for parity
  //    with the platform shell's Lockup.
  //  * Hex colors replaced with the canonical CSS vars (--color-ink,
  //    --color-ink-muted, --color-subtle) so future palette tweaks need
  //    one edit in globals.css instead of six greps.
  //  * Active nav items get the gold accent bar on the left edge that
  //    the platform sidebar uses, so the active-state pattern is
  //    recognisable across both portals.
  return (
    <aside className="w-60 border-r border-[var(--color-subtle)] shrink-0 hidden md:flex flex-col"
           style={{ background: 'var(--color-sidebar)' }}>
      <div className="px-5 h-16 flex items-center border-b border-[var(--color-subtle)]/60 shrink-0">
        <Link href="/dashboard" className="inline-flex items-center">
          <KaoriLockup tagline="Workspace" />
        </Link>
      </div>
      <nav className="p-3 space-y-1 flex-1 overflow-y-auto">
        {NAV.map((item) =>
          item.children
            ? <NavGroup key={item.label} item={item} path={path} />
            : <NavLeaf  key={item.href ?? item.label} item={item} path={path} />
        )}
      </nav>
    </aside>
  );
}

function NavGroup({ item, path }: { item: NavItem; path: string }) {
  const parentActive = isActive(item, path);
  const [manualOpen, setManualOpen] = useState<boolean | null>(null);
  const open = manualOpen ?? parentActive;
  const Icon = item.icon;

  return (
    <div>
      <button
        type="button"
        onClick={() => setManualOpen(!open)}
        className={cn(
          'relative w-full flex items-center gap-3 rounded-md-custom px-3 py-2 text-body transition-colors',
          parentActive
            ? 'bg-[var(--color-brand-500)]/10 text-[var(--color-ink)] font-medium'
            : 'text-[var(--color-ink-muted)] hover:bg-canvas hover:text-[var(--color-ink)]',
        )}
      >
        {parentActive && (
          <span className="absolute left-0 top-1/2 -translate-y-1/2 w-[3px] h-5 rounded-r-md bg-[var(--color-brand-500)]" />
        )}
        <Icon className={cn('w-[18px] h-[18px] shrink-0',
          parentActive && 'text-[var(--color-brand-500)]')} strokeWidth={1.75} />
        <span className="flex-1 text-left">{item.label}</span>
        {open
          ? <ChevronDown className="w-4 h-4 text-[var(--color-ink-muted)]" />
          : <ChevronRight className="w-4 h-4 text-[var(--color-ink-muted)]" />}
      </button>
      {open && item.children && (
        <div className="mt-1 ml-3 pl-3 border-l border-[var(--color-subtle)] space-y-0.5">
          {item.children.map((child) => {
            const active = isActive(child, path);
            const ChildIcon = child.icon;
            return (
              <Link
                key={child.href ?? child.label}
                href={child.href ?? '#'}
                className={cn(
                  'flex items-center gap-2.5 rounded-md-custom px-2.5 py-1.5 text-small transition-colors',
                  active
                    ? 'bg-[var(--color-brand-500)]/10 text-[var(--color-ink)] font-medium'
                    : 'text-[var(--color-ink-muted)] hover:bg-canvas hover:text-[var(--color-ink)]',
                )}
              >
                <ChildIcon className={cn('w-4 h-4 shrink-0',
                  active && 'text-[var(--color-brand-500)]')} strokeWidth={1.75} />
                <span className="truncate">{child.label}</span>
              </Link>
            );
          })}
        </div>
      )}
    </div>
  );
}

function NavLeaf({ item, path }: { item: NavItem; path: string }) {
  const active = isActive(item, path);
  const Icon = item.icon;
  return (
    <Link
      href={item.href ?? '#'}
      className={cn(
        'relative flex items-center gap-3 rounded-md-custom px-3 py-2 text-body transition-colors',
        active
          ? 'bg-[var(--color-brand-500)]/10 text-[var(--color-ink)] font-medium'
          : 'text-[var(--color-ink-muted)] hover:bg-canvas hover:text-[var(--color-ink)]',
      )}
    >
      {active && (
        <span className="absolute left-0 top-1/2 -translate-y-1/2 w-[3px] h-5 rounded-r-md bg-[var(--color-brand-500)]" />
      )}
      <Icon className={cn('w-[18px] h-[18px] shrink-0',
        active && 'text-[var(--color-brand-500)]')} strokeWidth={1.75} />
      <span>{item.label}</span>
    </Link>
  );
}
