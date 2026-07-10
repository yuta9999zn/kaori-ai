// @ts-nocheck — template import; tighten types when wiring to real API
'use client';

// ============================================================================
// 35. /p2/analysis — Multi-tier Analysis Hub (F-033 PR A wired — basic + intermediate)
// ----------------------------------------------------------------------------
// 3 tiers + scope selector + recent-runs section sourced from
// GET /api/v1/analysis/runs.
//
//   - Basic         (single pipeline, N templates, Qwen narrative)
//   - Intermediate  (2-5 silver/gold sources, 1 framework, Qwen)
//   - Advanced      (PR B — cross-workspace cohort, K-4 external AI,
//                    MANAGER approval queue when privacy=strict)
//
// PR A's hub turns the basic + intermediate tile buttons live; advanced
// stays linkable but with a "PR B" badge so users know what's gated.
// ============================================================================

import React, { useEffect, useState } from 'react';
import {
  FlaskConical, Sparkles, Layers, Network, Globe, Lock,
  ArrowRight, ShieldCheck, CheckCircle2, AlertTriangle, Activity, Clock,
} from 'lucide-react';

import { Button, Badge, ErrorBanner, cn, api, type ProblemDetails } from '@/components/p2/foundation';
import { PageHeader } from '@/components/p2/shell';
import { useT } from '@/lib/i18n/provider';
type Tier  = 'basic' | 'intermediate' | 'advanced';
type Scope = 'single' | 'multi' | 'cross';

interface TierDef {
  code:        Tier;
  title:       string;
  tagline:     string;
  duration:    string;
  consent_external_default: boolean;
  bullets:     string[];
  href:        string;
}

function buildTiers(t: ReturnType<typeof useT>): TierDef[] {
  return [
    {
      code:    'basic',
      title:   t('templates35AnalystHub.tierBasicTitle'),
      tagline: t('templates35AnalystHub.tierBasicTagline'),
      duration: t('templates35AnalystHub.tierBasicDuration'),
      consent_external_default: false,
      href:    '/p2/analysis/basic',
      bullets: [
        t('templates35AnalystHub.tierBasicBullet1'),
        t('templates35AnalystHub.tierBasicBullet2'),
        t('templates35AnalystHub.tierBasicBullet3'),
      ],
    },
    {
      code:    'intermediate',
      title:   t('templates35AnalystHub.tierIntermediateTitle'),
      tagline: t('templates35AnalystHub.tierIntermediateTagline'),
      duration: t('templates35AnalystHub.tierIntermediateDuration'),
      consent_external_default: false,
      href:    '/p2/analysis/intermediate',
      bullets: [
        t('templates35AnalystHub.tierIntermediateBullet1'),
        t('templates35AnalystHub.tierIntermediateBullet2'),
        t('templates35AnalystHub.tierIntermediateBullet3'),
      ],
    },
    {
      code:    'advanced',
      title:   t('templates35AnalystHub.tierAdvancedTitle'),
      tagline: t('templates35AnalystHub.tierAdvancedTagline'),
      duration: t('templates35AnalystHub.tierAdvancedDuration'),
      consent_external_default: true,
      href:    '/p2/analysis/advanced',
      bullets: [
        t('templates35AnalystHub.tierAdvancedBullet1'),
        t('templates35AnalystHub.tierAdvancedBullet2'),
        t('templates35AnalystHub.tierAdvancedBullet3'),
      ],
    },
  ];
}

function buildScopes(t: ReturnType<typeof useT>): Array<{ code: Scope; title: string; description: string; icon: any }> {
  return [
    { code: 'single', title: t('templates35AnalystHub.scopeSingleTitle'), description: t('templates35AnalystHub.scopeSingleDesc'), icon: Layers },
    { code: 'multi',  title: t('templates35AnalystHub.scopeMultiTitle'),  description: t('templates35AnalystHub.scopeMultiDesc'), icon: Network },
    { code: 'cross',  title: t('templates35AnalystHub.scopeCrossTitle'),  description: t('templates35AnalystHub.scopeCrossDesc'), icon: Globe },
  ];
}

interface RecentRun {
  id:               string;
  tier:             Tier;
  scope:            Scope;
  framework:        string | null;
  question:         string | null;
  status:           'queued' | 'running' | 'done' | 'error';
  narrative:        string | null;
  created_at:       string;
}

export default function AnalystHubPage() {
  const t = useT();
  const [scope, setScope] = useState<Scope>('single');
  const [recent, setRecent] = useState<RecentRun[]>([]);
  const [problem, setProblem] = useState<ProblemDetails | null>(null);

  useEffect(() => {
    api<{ items: RecentRun[] }>('/api/v1/analysis/runs?limit=10')
      .then((r) => setRecent(r.items))
      .catch((err) => setProblem(err));
  }, []);

  const tiers  = buildTiers(t);
  const scopes = buildScopes(t);

  return (
    <>
      <PageHeader
        title={t('templates35AnalystHub.pageTitle')}
        description={t('templates35AnalystHub.pageDescription')}
        actions={<Badge variant="info">F-033</Badge>}
      />

      <div className="px-6 lg:px-8 py-6 max-w-[1200px] mx-auto space-y-6">
        <ErrorBanner problem={problem} />

        {/* Scope picker */}
        <div className="bg-[var(--bg-card)] rounded-lg-custom border border-[var(--border-color)] p-4 shadow-soft-sm">
          <p className="text-[11px] uppercase tracking-wider text-[var(--text-secondary)] mb-3">{t('templates35AnalystHub.scopePickerLabel')}</p>
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
            {scopes.map((s) => {
              const isActive = s.code === scope;
              const Icon = s.icon;
              return (
                <button
                  key={s.code}
                  type="button"
                  onClick={() => setScope(s.code)}
                  className={cn(
                    'text-left p-3 rounded-md-custom border transition-all',
                    isActive
                      ? 'border-[var(--primary-gold)] bg-[var(--primary-gold)]/8'
                      : 'border-[var(--border-color)] bg-[var(--bg-card)] hover:border-[var(--primary-gold)]/40 hover:bg-[var(--bg-app)]/40',
                  )}
                >
                  <div className="flex items-start justify-between gap-2">
                    <Icon className="w-4 h-4 text-[var(--primary-gold-dark)] shrink-0 mt-0.5" />
                    {isActive && <CheckCircle2 className="w-4 h-4 text-[var(--primary-gold-dark)]" />}
                  </div>
                  <p className="font-medium text-sm text-[var(--text-primary)] mt-2">{s.title}</p>
                  <p className="text-xs text-[var(--text-secondary)] mt-0.5 leading-snug">{s.description}</p>
                </button>
              );
            })}
          </div>
          {scope === 'cross' && (
            <div className="mt-3 flex items-start gap-2 p-3 rounded-md-custom bg-[var(--state-warning)]/10 border border-[var(--state-warning)]/30 text-xs text-[#9E814D]">
              <AlertTriangle className="w-4 h-4 shrink-0 mt-0.5" />
              <p>
                {t('templates35AnalystHub.crossWarning')}
              </p>
            </div>
          )}
        </div>

        {/* Tier cards */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
          {tiers.map((tier) => <TierCard key={tier.code} tier={tier} scope={scope} />)}
        </div>

        {/* Recent runs */}
        <div className="bg-[var(--bg-card)] rounded-lg-custom border border-[var(--border-color)] shadow-soft-sm overflow-hidden">
          <div className="px-5 py-3 border-b border-[var(--border-color)]/60 flex items-center justify-between">
            <h3 className="font-serif text-base text-[var(--text-primary)]">{t('templates35AnalystHub.recentRunsTitle')}</h3>
            <Badge variant="default">{recent.length}</Badge>
          </div>
          {recent.length === 0 ? (
            <p className="px-5 py-8 text-sm text-[var(--text-secondary)] text-center">
              {t('templates35AnalystHub.emptyRecent')}
            </p>
          ) : (
            <ul className="divide-y divide-[var(--border-color)]/50">
              {recent.map((r) => (
                <li key={r.id}>
                  <a
                    href={`/p2/analysis/runs/${r.id}`}
                    className="flex items-start gap-3 px-5 py-3 hover:bg-[var(--bg-app)]/40 transition-colors"
                  >
                    <RecentStatusIcon status={r.status} />
                    <div className="flex-1 min-w-0">
                      <div className="flex items-baseline gap-2 flex-wrap">
                        <Badge variant={r.tier === 'advanced' ? 'warning' : r.tier === 'intermediate' ? 'info' : 'default'}>
                          {r.tier}
                        </Badge>
                        {r.framework && <Badge variant="current">{r.framework.toUpperCase()}</Badge>}
                        <p className="text-sm font-medium text-[var(--text-primary)] truncate">
                          {r.question || t('templates35AnalystHub.noQuestion')}
                        </p>
                      </div>
                      {r.narrative && (
                        <p className="text-xs text-[var(--text-secondary)] mt-1 line-clamp-2">{r.narrative}</p>
                      )}
                    </div>
                    <span className="text-[11px] text-[var(--text-secondary)] shrink-0 flex items-center gap-1">
                      <Clock className="w-3 h-3" />
                      {formatRelative(r.created_at, t)}
                    </span>
                  </a>
                </li>
              ))}
            </ul>
          )}
        </div>

        {/* Footer note */}
        <div className="flex items-start gap-2 p-3 rounded-md-custom bg-[var(--bg-app)]/40 border border-[var(--border-color)] text-xs text-[var(--text-secondary)]">
          <ShieldCheck className="w-4 h-4 text-[var(--primary-gold-dark)] shrink-0 mt-0.5" />
          <p>
            {t('templates35AnalystHub.footerPre')} <span className="font-mono">llm_router.py</span> {t('templates35AnalystHub.footerMid1')} <span className="font-medium text-[var(--text-primary)]">{t('templates35AnalystHub.footerTierName')}</span> {t('templates35AnalystHub.footerMid2')}{' '}
            <span className="font-mono">consent_external=true</span> {t('templates35AnalystHub.footerMid3')} <span className="font-mono">privacy=strict</span>.
          </p>
        </div>
      </div>
    </>
  );
}

function TierCard({ tier, scope }: { tier: TierDef; scope: Scope }) {
  const t = useT();
  return (
    <div className="bg-[var(--bg-card)] rounded-lg-custom border border-[var(--border-color)] shadow-soft-sm flex flex-col overflow-hidden">
      <div className="px-5 py-4 border-b border-[var(--border-color)]/60 bg-[var(--bg-app)]/30">
        <div className="flex items-start justify-between gap-2">
          <div>
            <h3 className="font-serif text-base text-[var(--text-primary)]">{tier.title}</h3>
            <p className="text-xs text-[var(--text-secondary)] mt-0.5">{tier.tagline}</p>
          </div>
          <Badge variant={tier.consent_external_default ? 'warning' : 'success'}>
            {tier.consent_external_default
              ? <><Globe className="w-3 h-3 mr-1 inline" /> {t('templates35AnalystHub.badgeExternalAi')}</>
              : <><Lock className="w-3 h-3 mr-1 inline" /> {t('templates35AnalystHub.badgeInternalQwen')}</>}
          </Badge>
        </div>
      </div>
      <div className="p-5 flex-1">
        <ul className="space-y-2 text-sm">
          {tier.bullets.map((b, i) => (
            <li key={i} className="flex items-start gap-2">
              <CheckCircle2 className="w-4 h-4 text-[var(--state-success)] shrink-0 mt-0.5" />
              <span className="text-[var(--text-primary)]">{b}</span>
            </li>
          ))}
        </ul>
        <p className="text-[11px] text-[var(--text-secondary)] mt-4">
          {t('templates35AnalystHub.durationLabel')} <span className="font-medium text-[var(--text-primary)]">{tier.duration}</span>
        </p>
      </div>
      <div className="px-5 py-3 border-t border-[var(--border-color)]/60 bg-[var(--bg-app)]/30">
        <Button
          onClick={() => (window.location.href = `${tier.href}?scope=${scope}`)}
          className="w-full"
          variant="primary"
        >
          {t('templates35AnalystHub.openTier', { tierTitle: tier.title })}
          <ArrowRight className="w-4 h-4 ml-2" />
        </Button>
      </div>
    </div>
  );
}

function RecentStatusIcon({ status }: { status: RecentRun['status'] }) {
  const cfg = ({
    queued:  { className: 'text-[var(--text-secondary)]',         label: 'Q' },
    running: { className: 'text-[var(--state-warning)] animate-pulse', label: 'R' },
    done:    { className: 'text-[var(--state-success)]',          label: '✓' },
    error:   { className: 'text-[var(--state-error)]',            label: '!' },
  } as const)[status];
  return (
    <span className={cn('w-5 h-5 rounded-full border flex items-center justify-center text-[10px] shrink-0 mt-0.5', cfg.className)}>
      {status === 'running' ? <Activity className="w-3 h-3" /> : cfg.label}
    </span>
  );
}

function formatRelative(iso: string, t: ReturnType<typeof useT>): string {
  const diff = Date.now() - +new Date(iso);
  if (Number.isNaN(diff))    return iso;
  if (diff < 60_000)         return t('templates35AnalystHub.relJustNow');
  if (diff < 3_600_000)      return t('templates35AnalystHub.relMinutes', { n: Math.round(diff / 60_000) });
  if (diff < 86_400_000)     return t('templates35AnalystHub.relHours', { n: Math.round(diff / 3_600_000) });
  if (diff < 7 * 86_400_000) return t('templates35AnalystHub.relDays', { n: Math.round(diff / 86_400_000) });
  return new Date(iso).toLocaleDateString('vi-VN');
}
