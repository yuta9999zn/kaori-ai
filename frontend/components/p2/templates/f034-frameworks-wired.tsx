'use client';

// ============================================================================
// F-034 Frameworks — wired hub + per-framework pages (BE PR #119 landed)
// ----------------------------------------------------------------------------
// Single file exports five pages:
//   * FrameworksHub        — /p2/frameworks
//   * SwotRunPage          — /p2/frameworks/swot
//   * SixWRunPage          — /p2/frameworks/6w
//   * TwoHRunPage          — /p2/frameworks/2h
//   * FishboneRunPage      — /p2/frameworks/fishbone-ishikawa
//
// Each framework page is a generate-and-poll flow:
//   1. User fills question + optional source_ref + consent_external toggle
//   2. POST /api/v1/frameworks/generate → 202 + run_id
//   3. Poll GET /api/v1/frameworks/{run_id} every 2s until status='ready' or 'failed'
//   4. Render result with framework-specific layout (SWOT 4-quadrant, 6W list,
//      2H how/how-much, Fishbone categorised)
//
// MoM/YoY (calculation) and Custom (per-tenant prompt store) are intentionally
// NOT in this file — BE deferred to v1. The legacy mock templates 45/46
// stay at /p2/frameworks/{mom-yoy-analysis,custom-analyst} until then.
// ============================================================================

import React, { useEffect, useMemo, useRef, useState } from 'react';
import {
  ArrowRight, Calendar, ChevronLeft, Database, Fish,
  Globe, Grid3x3, HelpCircle, Loader2, Lock, RefreshCw,
  Sparkles, ShieldCheck, Star, TrendingUp, Wrench,
  AlertTriangle, AlertCircle, ChevronRight, Clock,
} from 'lucide-react';

import {
  Button, Badge, Checkbox, ErrorBanner, api, cn, type ProblemDetails,
} from '@/components/p2/foundation';
import { PageHeader } from '@/components/p2/shell';
import { useT } from '@/lib/i18n/provider';
// ============================================================================
// Types — mirror BE Pydantic models in services/ai-orchestrator/routers/frameworks.py
// ============================================================================

type FrameworkCode = 'swot' | '6w' | '2h' | 'fishbone';
type RunStatus = 'queued' | 'running' | 'ready' | 'failed';

interface RunListItem {
  run_id:           string;
  framework_code:   FrameworkCode;
  question:         string;
  source_ref:       string | null;
  consent_external: boolean;
  status:           RunStatus;
  narrative:        string | null;
  created_at:       string;
  completed_at:     string | null;
  last_error:       string | null;
}

interface RunDetail extends RunListItem {
  content_json: any | null;
}

interface RunListResponse  { items: RunListItem[]; next_cursor?: string | null }
interface CatalogueItem    { code: FrameworkCode; name: string; description: string }
interface CatalogueResponse { items: CatalogueItem[] }

// ============================================================================
// Framework metadata — UI-side mirror so we can render icons + colours
// without round-tripping the catalogue endpoint on every page.
// ============================================================================

const META: Record<FrameworkCode, {
  title:        string;
  subtitleKey:  string;
  icon:         any;
  shortLabel:   string;  // breadcrumb / list-row label
}> = {
  swot:     { title: 'SWOT',     subtitleKey: 'templatesF034FrameworksWired.subtitleSwot',     icon: Grid3x3,  shortLabel: 'SWOT' },
  '6w':     { title: '6W',       subtitleKey: 'templatesF034FrameworksWired.subtitle6w',        icon: HelpCircle, shortLabel: '6W' },
  '2h':     { title: '2H',       subtitleKey: 'templatesF034FrameworksWired.subtitle2h',        icon: Wrench,   shortLabel: '2H' },
  fishbone: { title: 'Fishbone (Ishikawa)', subtitleKey: 'templatesF034FrameworksWired.subtitleFishbone', icon: Fish,     shortLabel: 'Fishbone' },
};

// MoM/YoY + Custom are placeholder cards on the hub — link to legacy mock
// templates so the URL still works. BE-side they're v1 follow-ups.
const PLACEHOLDER_CARDS = [
  { code: 'mom-yoy', titleKey: 'templatesF034FrameworksWired.placeholderMomYoyTitle',    subtitleKey: 'templatesF034FrameworksWired.placeholderMomYoySubtitle', icon: TrendingUp, href: '/p2/frameworks/mom-yoy-analysis' },
  { code: 'custom',  titleKey: 'templatesF034FrameworksWired.placeholderCustomTitle',    subtitleKey: 'templatesF034FrameworksWired.placeholderCustomSubtitle', icon: Star,        href: '/p2/frameworks/custom-analyst' },
] as const;

// ============================================================================
// Hub — gallery + recent runs
// ============================================================================

export function FrameworksHub() {
  const t = useT();
  const [catalogue, setCatalogue] = useState<CatalogueItem[]>([]);
  const [recent, setRecent]       = useState<RunListItem[]>([]);
  const [loading, setLoading]     = useState(true);
  const [problem, setProblem]     = useState<ProblemDetails | null>(null);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const [cat, runs] = await Promise.all([
          api<CatalogueResponse>('/api/v1/frameworks/templates'),
          api<RunListResponse>('/api/v1/frameworks?limit=10'),
        ]);
        if (cancelled) return;
        setCatalogue(cat.items ?? []);
        setRecent(runs.items ?? []);
      } catch (e: any) {
        if (!cancelled) setProblem(e);
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => { cancelled = true; };
  }, []);

  return (
    <>
      <PageHeader
        title={t('templatesF034FrameworksWired.hubTitle')}
        description={t('templatesF034FrameworksWired.hubDescription')}
      />

      <div className="px-6 lg:px-8 py-6 max-w-[1200px] mx-auto space-y-6">
        {problem && (
          <ErrorBanner
            problem={{
              ...problem,
              title:  t('templatesF034FrameworksWired.errCatalogueTitle'),
              detail: `${problem.title}${problem.detail ? ' — ' + problem.detail : ''}.`,
            }}
          />
        )}

        {/* K-10 banner */}
        <div className="bg-[var(--state-warning)]/8 rounded-lg-custom border border-[var(--state-warning)]/30 p-4 shadow-soft-sm">
          <div className="flex items-start gap-3">
            <ShieldCheck className="w-5 h-5 text-[var(--state-warning)] shrink-0 mt-0.5" />
            <div>
              <p className="font-serif text-sm text-[var(--text-primary)]">{t('templatesF034FrameworksWired.k10Title')}</p>
              <p className="text-xs text-[var(--text-secondary)] mt-1 leading-relaxed">
                {t('templatesF034FrameworksWired.k10Body')}
              </p>
            </div>
          </div>
        </div>

        {/* Gallery — wired frameworks */}
        <div>
          <h2 className="font-serif text-lg text-[var(--text-primary)] mb-3">{t('templatesF034FrameworksWired.sectionReady')}</h2>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
            {catalogue.map((c) => {
              const m = META[c.code];
              if (!m) return null;
              const Icon = m.icon;
              return (
                <a
                  key={c.code}
                  href={`/p2/frameworks/${c.code === 'fishbone' ? 'fishbone-ishikawa' : c.code}`}
                  className="group bg-[var(--bg-card)] border border-[var(--border-color)] rounded-lg-custom p-5 hover:border-[var(--primary-gold)] hover:shadow-soft-md transition-all"
                >
                  <div className="flex items-center gap-3 mb-2">
                    <div className="w-10 h-10 rounded-md-custom bg-[var(--primary-gold)]/10 flex items-center justify-center text-[var(--primary-gold-dark)]">
                      <Icon className="w-5 h-5" />
                    </div>
                    <h3 className="font-serif text-base text-[var(--text-primary)]">{c.name}</h3>
                  </div>
                  <p className="text-sm text-[var(--text-secondary)] line-clamp-2 mb-3">{c.description}</p>
                  <span className="text-xs text-[var(--primary-gold-dark)] inline-flex items-center font-medium">
                    {t('templatesF034FrameworksWired.openFramework')} <ArrowRight className="w-3 h-3 ml-1 group-hover:translate-x-0.5 transition-transform" />
                  </span>
                </a>
              );
            })}
          </div>
        </div>

        {/* Placeholder cards — BE deferred to v1 */}
        <div>
          <h2 className="font-serif text-lg text-[var(--text-primary)] mb-3">
            {t('templatesF034FrameworksWired.sectionUpcoming')}
          </h2>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
            {PLACEHOLDER_CARDS.map((p) => {
              const Icon = p.icon;
              return (
                <a
                  key={p.code}
                  href={p.href}
                  className="bg-[var(--bg-card)]/60 border border-dashed border-[var(--border-color)] rounded-lg-custom p-5 hover:bg-[var(--bg-card)] transition-colors"
                >
                  <div className="flex items-center gap-3 mb-2">
                    <div className="w-10 h-10 rounded-md-custom bg-[var(--bg-app)] flex items-center justify-center text-[var(--text-secondary)]">
                      <Icon className="w-5 h-5" />
                    </div>
                    <div className="flex-1">
                      <h3 className="font-serif text-base text-[var(--text-primary)]">{t(p.titleKey)}</h3>
                    </div>
                    <Badge variant="default">v1</Badge>
                  </div>
                  <p className="text-sm text-[var(--text-secondary)] line-clamp-2">{t(p.subtitleKey)}</p>
                </a>
              );
            })}
          </div>
        </div>

        {/* Recent runs */}
        <div>
          <h2 className="font-serif text-lg text-[var(--text-primary)] mb-3">{t('templatesF034FrameworksWired.sectionHistory')}</h2>
          <div className="bg-[var(--bg-card)] border border-[var(--border-color)] rounded-lg-custom shadow-soft-sm overflow-hidden">
            {loading ? (
              <div className="px-5 py-12 text-center text-[var(--text-secondary)]">
                <Loader2 className="w-5 h-5 animate-spin inline mr-2" /> {t('templatesF034FrameworksWired.loadingEllipsis')}
              </div>
            ) : recent.length === 0 ? (
              <div className="px-5 py-12 text-center">
                <Clock className="w-10 h-10 mx-auto text-[var(--text-secondary)]/30 mb-3" />
                <p className="text-sm text-[var(--text-secondary)]">
                  {t('templatesF034FrameworksWired.emptyHistory')}
                </p>
              </div>
            ) : (
              <table className="w-full text-sm text-left">
                <thead className="bg-[var(--bg-app)] border-b border-[var(--border-color)] text-[11px] font-medium uppercase tracking-wider text-[var(--text-secondary)]">
                  <tr>
                    <th className="px-5 py-3">{t('templatesF034FrameworksWired.colFramework')}</th>
                    <th className="px-5 py-3">{t('templatesF034FrameworksWired.colQuestionResult')}</th>
                    <th className="px-5 py-3">{t('templatesF034FrameworksWired.colStatus')}</th>
                    <th className="px-5 py-3 text-right">{t('templatesF034FrameworksWired.colTime')}</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-[var(--border-color)]/60">
                  {recent.map((r) => {
                    const m = META[r.framework_code];
                    if (!m) return null;
                    const Icon = m.icon;
                    const detailHref = `/p2/frameworks/${r.framework_code === 'fishbone' ? 'fishbone-ishikawa' : r.framework_code}?run=${r.run_id}`;
                    return (
                      <tr key={r.run_id} className="hover:bg-[var(--bg-app)]/40 transition-colors">
                        <td className="px-5 py-4">
                          <span className="inline-flex items-center gap-2 text-xs">
                            <Icon className="w-3.5 h-3.5 text-[var(--primary-gold-dark)]" />
                            <span className="font-medium text-[var(--text-primary)]">{m.shortLabel}</span>
                          </span>
                        </td>
                        <td className="px-5 py-4 max-w-md">
                          <a href={detailHref} className="text-sm text-[var(--text-primary)] hover:text-[var(--primary-gold-dark)] line-clamp-1">
                            {r.question}
                          </a>
                          {r.narrative && (
                            <p className="text-[11px] text-[var(--text-secondary)] mt-0.5 line-clamp-1">{r.narrative}</p>
                          )}
                        </td>
                        <td className="px-5 py-4">
                          <StatusBadge status={r.status} />
                        </td>
                        <td className="px-5 py-4 text-xs text-[var(--text-secondary)] text-right">
                          {formatRelative(r.completed_at ?? r.created_at, t)}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            )}
          </div>
        </div>
      </div>
    </>
  );
}

// ============================================================================
// Per-framework page — generic shell + framework-specific result renderer
// ============================================================================

interface FrameworkPageProps {
  code: FrameworkCode;
  /** Route segment for breadcrumb back-link — e.g. 'fishbone-ishikawa'. */
  routeSegment: string;
}

export function FrameworkRunPage({ code, routeSegment }: FrameworkPageProps) {
  const t = useT();
  const m = META[code];

  // Generate-and-poll state
  const [question, setQuestion] = useState('');
  const [sourceRef, setSourceRef] = useState('');
  const [consentExternal, setConsentExternal] = useState(false);

  const [runId, setRunId] = useState<string | null>(null);
  const [run, setRun] = useState<RunDetail | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [problem, setProblem] = useState<ProblemDetails | null>(null);

  // On mount, check ?run=<id> in URL — lets the hub link straight into a
  // completed run.
  useEffect(() => {
    if (typeof window === 'undefined') return;
    const params = new URLSearchParams(window.location.search);
    const r = params.get('run');
    if (r) setRunId(r);
  }, []);

  // Poll the active run.
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);
  useEffect(() => {
    if (!runId) {
      setRun(null);
      return;
    }
    let cancelled = false;
    const tick = async () => {
      try {
        const r = await api<RunDetail>(`/api/v1/frameworks/${runId}`);
        if (cancelled) return;
        setRun(r);
        if (r.status === 'ready' || r.status === 'failed') {
          if (pollRef.current) {
            clearInterval(pollRef.current);
            pollRef.current = null;
          }
        }
      } catch (e: any) {
        if (!cancelled) {
          setProblem(e);
          if (pollRef.current) {
            clearInterval(pollRef.current);
            pollRef.current = null;
          }
        }
      }
    };
    tick();
    pollRef.current = setInterval(tick, 2000);
    return () => {
      cancelled = true;
      if (pollRef.current) clearInterval(pollRef.current);
    };
  }, [runId]);

  async function generate() {
    if (!question.trim() || question.trim().length < 3) return;
    setSubmitting(true);
    setProblem(null);
    try {
      const r = await api<{ run_id: string; status: string }>('/api/v1/frameworks/generate', {
        method: 'POST',
        body: JSON.stringify({
          framework_code:   code,
          question:         question.trim(),
          source_ref:       sourceRef.trim() || null,
          consent_external: consentExternal,
        }),
      });
      setRunId(r.run_id);
      setRun(null);                      // clear stale rendering while polling restarts
      // Update URL so refresh keeps the run open. Replace history so
      // back-button still goes to the hub.
      if (typeof window !== 'undefined') {
        const url = new URL(window.location.href);
        url.searchParams.set('run', r.run_id);
        window.history.replaceState({}, '', url);
      }
    } catch (e: any) {
      setProblem(e);
    } finally {
      setSubmitting(false);
    }
  }

  function reset() {
    setRunId(null);
    setRun(null);
    setProblem(null);
    if (typeof window !== 'undefined') {
      const url = new URL(window.location.href);
      url.searchParams.delete('run');
      window.history.replaceState({}, '', url);
    }
  }

  const Icon = m.icon;

  return (
    <>
      <PageHeader
        title={m.title}
        description={t(m.subtitleKey)}
        actions={
          <Button variant="tertiary" onClick={() => (window.location.href = '/p2/frameworks')}>
            <ChevronLeft className="w-4 h-4 mr-1" /> {t('templatesF034FrameworksWired.backToFrameworks')}
          </Button>
        }
      />

      <div className="px-6 lg:px-8 py-6 max-w-[1100px] mx-auto space-y-5">
        {problem && (
          <ErrorBanner
            problem={{
              ...problem,
              title:  problem.title ?? t('templatesF034FrameworksWired.errRunIncomplete'),
              detail: problem.detail ?? '',
            }}
          />
        )}

        {/* Form */}
        <div className="bg-[var(--bg-card)] rounded-lg-custom border border-[var(--border-color)] p-5 shadow-soft-sm space-y-4">
          <div className="flex items-center gap-3 mb-1">
            <div className="w-10 h-10 rounded-md-custom bg-[var(--primary-gold)]/10 flex items-center justify-center text-[var(--primary-gold-dark)]">
              <Icon className="w-5 h-5" />
            </div>
            <div>
              <h2 className="font-serif text-base text-[var(--text-primary)]">{t('templatesF034FrameworksWired.yourQuestion')}</h2>
              <p className="text-xs text-[var(--text-secondary)]">
                {t('templatesF034FrameworksWired.llmFillHint', { framework: m.shortLabel })}
              </p>
            </div>
          </div>

          <textarea
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            placeholder={questionPlaceholder(code, t)}
            rows={3}
            maxLength={2000}
            className="w-full px-3 py-2.5 bg-[var(--bg-app)] border border-[var(--border-color)] rounded-md-custom text-sm placeholder:text-[var(--text-secondary)]/60 focus:outline-none focus:ring-2 focus:ring-[var(--primary-gold)]/30 focus:border-[var(--primary-gold)] resize-none transition-all"
          />

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <label className="block">
              <span className="text-[11px] uppercase tracking-wider font-medium text-[var(--text-secondary)] mb-1.5 block">
                {t('templatesF034FrameworksWired.sourceRefLabel')}
              </span>
              <div className="relative">
                <Database className="w-4 h-4 text-[var(--text-secondary)] absolute left-3 top-1/2 -translate-y-1/2" />
                <input
                  type="text"
                  value={sourceRef}
                  onChange={(e) => setSourceRef(e.target.value)}
                  maxLength={200}
                  placeholder={t('templatesF034FrameworksWired.sourceRefPlaceholder')}
                  className="w-full pl-9 pr-3 py-2 bg-[var(--bg-app)] border border-[var(--border-color)] rounded-md-custom text-sm placeholder:text-[var(--text-secondary)]/60 focus:outline-none focus:ring-2 focus:ring-[var(--primary-gold)]/30 transition-all"
                />
              </div>
            </label>

            <label className="block">
              <span className="text-[11px] uppercase tracking-wider font-medium text-[var(--text-secondary)] mb-1.5 block">
                {t('templatesF034FrameworksWired.aiLabel')}
              </span>
              <div className="flex items-center gap-2 h-9">
                <Checkbox
                  checked={consentExternal}
                  onChange={(e) => setConsentExternal(e.target.checked)}
                />
                <span className="text-xs text-[var(--text-primary)] inline-flex items-center gap-1">
                  {consentExternal ? <Globe className="w-3.5 h-3.5 text-[var(--state-warning)]" /> : <Lock className="w-3.5 h-3.5 text-[var(--state-success)]" />}
                  {consentExternal ? t('templatesF034FrameworksWired.aiExternalAllowed') : t('templatesF034FrameworksWired.aiInternalOnly')}
                </span>
              </div>
            </label>
          </div>

          <div className="flex items-center justify-between">
            <p className="text-[11px] text-[var(--text-secondary)]">
              {t('templatesF034FrameworksWired.charCount', { len: question.length })}
            </p>
            <div className="inline-flex items-center gap-2">
              {runId && (
                <Button variant="tertiary" onClick={reset}>
                  <RefreshCw className="w-3.5 h-3.5 mr-1" /> {t('templatesF034FrameworksWired.newRun')}
                </Button>
              )}
              <Button
                variant="primary"
                onClick={generate}
                disabled={submitting || question.trim().length < 3}
              >
                {submitting
                  ? <><Loader2 className="w-4 h-4 mr-1.5 animate-spin" /> {t('templatesF034FrameworksWired.submitting')}</>
                  : <><Sparkles className="w-4 h-4 mr-1.5" /> {t('templatesF034FrameworksWired.analyzeButton')}</>}
              </Button>
            </div>
          </div>
        </div>

        {/* Status / result */}
        {runId && (
          <RunStatusPanel
            run={run}
            framework={code}
          />
        )}
      </div>
    </>
  );
}

function questionPlaceholder(code: FrameworkCode, t: ReturnType<typeof useT>): string {
  switch (code) {
    case 'swot':     return t('templatesF034FrameworksWired.placeholderSwot');
    case '6w':       return t('templatesF034FrameworksWired.placeholder6w');
    case '2h':       return t('templatesF034FrameworksWired.placeholder2h');
    case 'fishbone': return t('templatesF034FrameworksWired.placeholderFishbone');
  }
}

// ============================================================================
// Status panel + result renderer
// ============================================================================

function RunStatusPanel({ run, framework }: { run: RunDetail | null; framework: FrameworkCode }) {
  const t = useT();
  if (!run) {
    return (
      <div className="bg-[var(--bg-card)] rounded-lg-custom border border-[var(--border-color)] p-8 text-center shadow-soft-sm">
        <Loader2 className="w-6 h-6 mx-auto text-[var(--primary-gold-dark)] animate-spin mb-3" />
        <p className="text-sm text-[var(--text-secondary)]">{t('templatesF034FrameworksWired.initializingRun')}</p>
      </div>
    );
  }

  if (run.status === 'queued' || run.status === 'running') {
    return (
      <div className="bg-[var(--bg-card)] rounded-lg-custom border border-[var(--border-color)] p-8 text-center shadow-soft-sm">
        <Loader2 className="w-6 h-6 mx-auto text-[var(--primary-gold-dark)] animate-spin mb-3" />
        <p className="text-sm text-[var(--text-primary)] font-medium">
          {run.status === 'queued' ? t('templatesF034FrameworksWired.statusQueued') : t('templatesF034FrameworksWired.statusRunningLLM')}
        </p>
        <p className="text-xs text-[var(--text-secondary)] mt-1">
          {t('templatesF034FrameworksWired.etaHint')}
        </p>
      </div>
    );
  }

  if (run.status === 'failed') {
    return (
      <div className="bg-[var(--state-error)]/8 border border-[var(--state-error)]/30 rounded-lg-custom p-5 shadow-soft-sm">
        <div className="flex items-start gap-3">
          <AlertTriangle className="w-5 h-5 text-[var(--state-error)] shrink-0 mt-0.5" />
          <div className="min-w-0">
            <p className="text-sm font-medium text-[var(--text-primary)]">{t('templatesF034FrameworksWired.runFailed')}</p>
            <p className="text-xs text-[var(--text-secondary)] mt-1 break-words">
              {run.last_error || t('templatesF034FrameworksWired.noErrorDetail')}
            </p>
            <p className="text-[11px] text-[var(--text-secondary)] mt-2">
              {t('templatesF034FrameworksWired.failedHint')}
            </p>
          </div>
        </div>
      </div>
    );
  }

  // status === 'ready'
  if (!run.content_json) {
    return (
      <div className="bg-[var(--bg-card)] rounded-lg-custom border border-[var(--border-color)] p-5 shadow-soft-sm">
        <p className="text-sm text-[var(--text-secondary)]">{t('templatesF034FrameworksWired.emptyResult')}</p>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {run.narrative && (
        <div className="bg-[var(--primary-gold)]/8 border border-[var(--primary-gold)]/30 rounded-lg-custom p-4 shadow-soft-sm">
          <div className="flex items-start gap-2">
            <Sparkles className="w-4 h-4 text-[var(--primary-gold-dark)] shrink-0 mt-0.5" />
            <p className="text-sm text-[var(--text-primary)]">{run.narrative}</p>
          </div>
        </div>
      )}

      {framework === 'swot'     && <SwotResult content={run.content_json} />}
      {framework === '6w'       && <SixWResult content={run.content_json} />}
      {framework === '2h'       && <TwoHResult content={run.content_json} />}
      {framework === 'fishbone' && <FishboneResult content={run.content_json} />}
    </div>
  );
}

// ============================================================================
// SWOT — 4 quadrant grid
// ============================================================================

function SwotResult({ content }: { content: any }) {
  const t = useT();
  const quadrants: Array<{ key: string; label: string; tone: string; data: any }> = [
    { key: 'strengths',     label: 'Strengths',     tone: 'text-[var(--state-success)] border-[var(--state-success)]/30 bg-[var(--state-success)]/5', data: content?.strengths },
    { key: 'weaknesses',    label: 'Weaknesses',    tone: 'text-[var(--state-warning)] border-[var(--state-warning)]/30 bg-[var(--state-warning)]/5', data: content?.weaknesses },
    { key: 'opportunities', label: 'Opportunities', tone: 'text-[var(--primary-gold-dark)] border-[var(--primary-gold)]/40 bg-[var(--primary-gold)]/5', data: content?.opportunities },
    { key: 'threats',       label: 'Threats',       tone: 'text-[var(--state-error)] border-[var(--state-error)]/30 bg-[var(--state-error)]/5', data: content?.threats },
  ];

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
      {quadrants.map((q) => (
        <div key={q.key} className={cn('rounded-lg-custom border p-4 shadow-soft-sm', q.tone.split(' ').slice(2).join(' '), q.tone.split(' ')[1])}>
          <h3 className={cn('font-serif text-sm font-medium mb-3', q.tone.split(' ')[0])}>{q.label}</h3>
          <ul className="space-y-2">
            {Array.isArray(q.data?.items) && q.data.items.length > 0 ? q.data.items.map((it: any, idx: number) => (
              <li key={idx} className="text-sm text-[var(--text-primary)] flex items-start gap-2">
                <span className="font-mono text-[10px] text-[var(--text-secondary)] mt-0.5 shrink-0 w-12 text-right">
                  {Math.round((it.confidence ?? 0) * 100)}%
                </span>
                <span>{it.text}</span>
              </li>
            )) : (
              <li className="text-xs text-[var(--text-secondary)] italic">{t('templatesF034FrameworksWired.noItems')}</li>
            )}
          </ul>
        </div>
      ))}
    </div>
  );
}

// ============================================================================
// 6W — 6 fields list
// ============================================================================

function SixWResult({ content }: { content: any }) {
  const t = useT();
  const fields: Array<{ key: string; labelKey: string }> = [
    { key: 'who',   labelKey: 'templatesF034FrameworksWired.sixwWho' },
    { key: 'what',  labelKey: 'templatesF034FrameworksWired.sixwWhat' },
    { key: 'when',  labelKey: 'templatesF034FrameworksWired.sixwWhen' },
    { key: 'where', labelKey: 'templatesF034FrameworksWired.sixwWhere' },
    { key: 'why',   labelKey: 'templatesF034FrameworksWired.sixwWhy' },
    { key: 'how',   labelKey: 'templatesF034FrameworksWired.sixwHow' },
  ];
  return (
    <div className="bg-[var(--bg-card)] rounded-lg-custom border border-[var(--border-color)] divide-y divide-[var(--border-color)]/60 shadow-soft-sm">
      {fields.map((f) => (
        <div key={f.key} className="px-5 py-4">
          <p className="text-[11px] uppercase tracking-wider font-medium text-[var(--text-secondary)] mb-1">{t(f.labelKey)}</p>
          <p className="text-sm text-[var(--text-primary)] leading-relaxed">{content?.[f.key] ?? '—'}</p>
        </div>
      ))}
    </div>
  );
}

// ============================================================================
// 2H — How section + How much section
// ============================================================================

function TwoHResult({ content }: { content: any }) {
  const t = useT();
  const how = content?.how ?? {};
  const hm  = content?.how_much ?? {};
  return (
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
      <div className="bg-[var(--bg-card)] rounded-lg-custom border border-[var(--border-color)] p-5 shadow-soft-sm">
        <h3 className="font-serif text-sm font-medium text-[var(--text-primary)] mb-3 inline-flex items-center gap-2">
          <Wrench className="w-4 h-4 text-[var(--primary-gold-dark)]" /> {t('templatesF034FrameworksWired.twohHowTitle')}
        </h3>
        <p className="text-sm text-[var(--text-primary)] mb-3">{how.approach ?? '—'}</p>
        <ol className="list-decimal list-inside space-y-1.5 text-sm text-[var(--text-primary)]">
          {Array.isArray(how.steps) && how.steps.length > 0 ? how.steps.map((s: string, i: number) => (
            <li key={i}>{s}</li>
          )) : (
            <li className="text-xs text-[var(--text-secondary)] italic list-none">{t('templatesF034FrameworksWired.noSteps')}</li>
          )}
        </ol>
      </div>

      <div className="bg-[var(--bg-card)] rounded-lg-custom border border-[var(--border-color)] p-5 shadow-soft-sm">
        <h3 className="font-serif text-sm font-medium text-[var(--text-primary)] mb-3 inline-flex items-center gap-2">
          <TrendingUp className="w-4 h-4 text-[var(--primary-gold-dark)]" /> {t('templatesF034FrameworksWired.twohHowMuchTitle')}
        </h3>
        <p className="font-serif text-2xl text-[var(--text-primary)] mb-1">
          {hm.estimate ?? '—'} <span className="text-base text-[var(--text-secondary)]">{hm.unit ?? ''}</span>
        </p>
        <p className="text-xs text-[var(--text-secondary)] mb-3">
          {t('templatesF034FrameworksWired.confidenceLabel', { value: typeof hm.confidence === 'number' ? `${Math.round(hm.confidence * 100)}%` : '—' })}
        </p>
        {Array.isArray(hm.assumptions) && hm.assumptions.length > 0 && (
          <>
            <p className="text-[11px] uppercase tracking-wider font-medium text-[var(--text-secondary)] mb-1.5">{t('templatesF034FrameworksWired.assumptions')}</p>
            <ul className="list-disc list-inside space-y-0.5 text-xs text-[var(--text-secondary)]">
              {hm.assumptions.map((a: string, i: number) => <li key={i}>{a}</li>)}
            </ul>
          </>
        )}
      </div>
    </div>
  );
}

// ============================================================================
// Fishbone — categories grid + root cause callout
// ============================================================================

function FishboneResult({ content }: { content: any }) {
  const t = useT();
  const categories: any[] = Array.isArray(content?.categories) ? content.categories : [];
  return (
    <div className="space-y-4">
      <div className="bg-[var(--bg-card)] rounded-lg-custom border border-[var(--border-color)] p-5 shadow-soft-sm">
        <p className="text-[11px] uppercase tracking-wider font-medium text-[var(--text-secondary)] mb-1">{t('templatesF034FrameworksWired.problemLabel')}</p>
        <p className="text-sm text-[var(--text-primary)] font-medium">{content?.problem ?? '—'}</p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {categories.map((cat, i) => (
          <div key={i} className="bg-[var(--bg-card)] rounded-lg-custom border border-[var(--border-color)] p-5 shadow-soft-sm">
            <h3 className="font-serif text-sm font-medium text-[var(--text-primary)] mb-3 inline-flex items-center gap-2">
              <Fish className="w-4 h-4 text-[var(--primary-gold-dark)]" /> {cat.name}
            </h3>
            <ul className="space-y-2">
              {(Array.isArray(cat.causes) ? cat.causes : []).map((c: any, idx: number) => (
                <li key={idx} className="flex items-start gap-2 text-sm">
                  <DepthBadge depth={c.depth} />
                  <span className="text-[var(--text-primary)]">{c.text}</span>
                </li>
              ))}
            </ul>
          </div>
        ))}
      </div>

      <div className="bg-[var(--state-error)]/5 border border-[var(--state-error)]/30 rounded-lg-custom p-5 shadow-soft-sm">
        <p className="text-[11px] uppercase tracking-wider font-medium text-[var(--state-error)] mb-1">{t('templatesF034FrameworksWired.rootCauseLabel')}</p>
        <p className="text-sm text-[var(--text-primary)]">{content?.root_cause_hypothesis ?? '—'}</p>
      </div>
    </div>
  );
}

function DepthBadge({ depth }: { depth: number | undefined }) {
  const t = useT();
  const d = Number(depth) || 1;
  const label = d === 1 ? t('templatesF034FrameworksWired.depthSymptom') : d === 2 ? t('templatesF034FrameworksWired.depthDirect') : t('templatesF034FrameworksWired.depthRoot');
  const tone = d === 1
    ? 'bg-[var(--state-warning)]/10 text-[var(--state-warning)]'
    : d === 2
      ? 'bg-[var(--primary-gold)]/15 text-[var(--primary-gold-dark)]'
      : 'bg-[var(--state-error)]/10 text-[var(--state-error)]';
  return (
    <span className={cn('font-mono text-[10px] uppercase tracking-wider px-1.5 py-0.5 rounded-sm-custom shrink-0 mt-0.5', tone)}>
      {label}
    </span>
  );
}

// ============================================================================
// Helpers
// ============================================================================

function StatusBadge({ status }: { status: RunStatus }) {
  const t = useT();
  if (status === 'ready')   return <Badge variant="success">{t('templatesF034FrameworksWired.statusReadyBadge')}</Badge>;
  if (status === 'failed')  return <Badge variant="error">{t('templatesF034FrameworksWired.statusFailedBadge')}</Badge>;
  if (status === 'running') return <Badge variant="info">{t('templatesF034FrameworksWired.statusRunningBadge')}</Badge>;
  return <Badge variant="default">{t('templatesF034FrameworksWired.statusQueuedBadge')}</Badge>;
}

function formatRelative(iso: string, t: ReturnType<typeof useT>): string {
  const diff = Date.now() - +new Date(iso);
  if (diff < 60_000)        return t('templatesF034FrameworksWired.relativeJustNow');
  if (diff < 3_600_000)     return t('templatesF034FrameworksWired.relativeMinutesAgo', { n: Math.round(diff / 60_000) });
  if (diff < 86_400_000)    return t('templatesF034FrameworksWired.relativeHoursAgo', { n: Math.round(diff / 3_600_000) });
  if (diff < 7 * 86_400_000) return t('templatesF034FrameworksWired.relativeDaysAgo', { n: Math.round(diff / 86_400_000) });
  return new Date(iso).toLocaleDateString('vi-VN');
}
