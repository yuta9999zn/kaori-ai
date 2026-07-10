// @ts-nocheck — template import; tighten types when wiring to real API
'use client';

// ============================================================================
// 18. /p2/pipelines — Pipeline Run History (F-022, F-NEW2)
// ----------------------------------------------------------------------------
// GET /api/v1/pipelines?cursor=&limit=50         (cursor pagination)
// GET /api/v1/pipelines/:id/events  (SSE F-NEW2)  — live status stream
//
// Status enum canonical (Sprint 7 PR C — DB CHECK constraint):
//   schema_review     → user has not confirmed column mapping yet
//   analyzing         → analysis engine running (Bronze→Silver→Gold→analysis)
//   analysis_complete → final state, results ready
//
// (FE-only `_pending`/`_running`/`_done` aliases were retired in PR C.)
//
// Row click → wizard detail at /p2/pipelines/{id} (PR C also wired this).
// ============================================================================

import React, { useState, useEffect, useRef } from 'react';
import {
  GitMerge, Plus, Search, Filter, RefreshCw, Activity, CheckCircle2,
  AlertTriangle, Clock, Eye, ChevronRight, Radio,
} from 'lucide-react';

import {
  Button, Badge, ErrorBanner,
  api, cn,
  type ProblemDetails,
} from '@/components/p2/foundation';
import { PageHeader } from '@/components/p2/shell';
import { useT } from '@/lib/i18n/provider';
type PipelineStatus = 'schema_review' | 'analyzing' | 'analysis_complete' | 'failed';

interface PipelineRun {
  id:           string;
  name:         string;
  template_id:  string;
  current_step: 1 | 2 | 3 | 4 | 5;     // 1 Upload, 2 Columns, 3 Clean, 4 Analyze, 5 Results
  status:       PipelineStatus;
  progress_pct: number;
  rows:         number;
  size_bytes:   number;
  created_at:   string;
  updated_at:   string;
  owner_email:  string;
  error?:       { title: string; detail?: string };
}

export default function PipelineManager() {
  const t = useT();

  // BE pipeline_runs.status carries the full lifecycle (uploading → bronze →
  // schema → silver → analyzing → done/error), not just the 4 FE display states
  // the wizard badge knew about. Listing a run whose status wasn't a key here
  // crashed the WHOLE page: `STATUS_META[r.status].icon` threw on undefined
  // (the GET /pipelines call itself returns 200 — this was a pure render crash).
  // Cover every real status; `done`/`error` synonyms are normalised in mapBeRow.
  const STATUS_META: Record<string, any> = {
    uploading:            { variant: 'info',    label: t('templates18DataPipelineManager.statusUploading'),           icon: Clock },
    bronze_complete:      { variant: 'info',    label: t('templates18DataPipelineManager.statusBronzeComplete'),      icon: Clock },
    unstructured_pending: { variant: 'info',    label: t('templates18DataPipelineManager.statusUnstructuredPending'), icon: Clock },
    schema_review:        { variant: 'info',    label: t('templates18DataPipelineManager.statusSchemaReview'),        icon: Eye },
    cleaning:             { variant: 'warning', label: t('templates18DataPipelineManager.statusCleaning'),            icon: Activity },
    silver_complete:      { variant: 'info',    label: t('templates18DataPipelineManager.statusSilverComplete'),      icon: CheckCircle2 },
    analyzing:            { variant: 'warning', label: t('templates18DataPipelineManager.statusAnalyzing'),           icon: Activity },
    analysis_complete:    { variant: 'success', label: t('templates18DataPipelineManager.statusAnalysisComplete'),    icon: CheckCircle2 },
    failed:               { variant: 'error',   label: t('templates18DataPipelineManager.statusFailed'),              icon: AlertTriangle },
    cancelled:            { variant: 'info',    label: t('templates18DataPipelineManager.statusCancelled'),           icon: Clock },
  };

  const STEP_LABEL = [
    '',
    t('templates18DataPipelineManager.stepUpload'),
    t('templates18DataPipelineManager.stepColumn'),
    t('templates18DataPipelineManager.stepClean'),
    t('templates18DataPipelineManager.stepAnalyze'),
    t('templates18DataPipelineManager.stepResult'),
  ];

  const [runs,    setRuns]    = useState<PipelineRun[]>([]);
  const [cursor,  setCursor]  = useState<string | null>(null);
  const [hasMore, setHasMore] = useState(true);
  const [loading, setLoading] = useState(true);
  const [problem, setProblem] = useState<ProblemDetails | null>(null);
  const [search,  setSearch]  = useState('');
  const [statusFilter, setStatusFilter] = useState<PipelineStatus | 'all'>('all');
  const [sseConnected, setSseConnected] = useState(false);

  // Map BE pipeline_runs row shape → FE PipelineRun. The BE returns
  // run_id/filename/row_count_bronze/created_at/etc. while this template
  // declared id/name/rows/current_step/etc. Without the bridge the
  // table renders undefined for every column.
  function mapBeRow(r: any): PipelineRun {
    // The analysis layer reports done/error; the pipeline layer uses
    // analysis_complete/failed. Fold the synonyms so STATUS_META resolves and
    // the wizard's analyzing/complete branches below behave consistently.
    const raw = String(r.status ?? 'schema_review');
    const status = ({ done: 'analysis_complete', error: 'failed' }[raw] ?? raw) as PipelineStatus;
    const stepByStatus: Record<string, 1 | 2 | 3 | 4 | 5> = {
      uploading:            1,
      bronze_complete:      1,
      unstructured_pending: 1,
      schema_review:        2,
      silver_complete:      3,
      analyzing:            4,
      analysis_complete:    5,
      failed:               1,
      cancelled:            1,
    };
    return {
      id:           String(r.run_id ?? r.id ?? ''),
      name:         String(r.filename ?? r.name ?? '(unnamed)'),
      template_id:  String(r.template_id ?? '—'),
      // Dùng `status` đã normalise (done→analysis_complete, error→failed)
      // để synonym branch không chết, và để unstructured_pending resolve đúng.
      current_step: stepByStatus[status] ?? 1,
      status,
      progress_pct: status === 'analyzing' ? 50 : status === 'analysis_complete' ? 100 : 0,
      rows:         Number(r.row_count_silver ?? r.row_count_bronze ?? r.rows ?? 0),
      size_bytes:   Number(r.original_size_bytes ?? r.size_bytes ?? 0),
      created_at:   r.created_at,
      updated_at:   r.updated_at ?? r.created_at,
      owner_email:  r.owner_email ?? r.uploaded_by ?? '—',
      error: r.error_message ? { title: t('templates18DataPipelineManager.errRunTitle'), detail: r.error_message } : undefined,
    };
  }

  // Initial + cursor-based load. BE envelope is `{ data, meta:{cursor,...} }`.
  async function load(reset = false) {
    setLoading(true);
    setProblem(null);
    try {
      const path = reset
        ? '/api/v1/pipelines?limit=50'
        : `/api/v1/pipelines?limit=50&cursor=${encodeURIComponent(cursor ?? '')}`;
      const res = await api<{ data: any[]; meta?: { cursor: string | null } }>(path);
      const rows = (res.data ?? []).map(mapBeRow);
      setRuns((prev) => reset ? rows : [...prev, ...rows]);
      const next = res.meta?.cursor ?? null;
      setCursor(next);
      setHasMore(!!next);
    } catch (err: any) {
      setProblem(err);
    } finally {
      setLoading(false);
    }
  }
  useEffect(() => { load(true); }, []);

  // F-NEW2 SSE stream — disabled until BE wires /api/v1/pipelines/stream/token
  // + /api/v1/pipelines/events handlers. Without the guard the page fires a
  // POST that 404s on every mount, noising the console and triggering global
  // error banners. Re-enable by flipping SSE_ENABLED once the BE handler ships.
  const SSE_ENABLED = false;
  useEffect(() => {
    if (!SSE_ENABLED) return;
    let es: EventSource | null = null;
    let cancelled = false;
    (async () => {
      try {
        const tok = await api<{ stream_token: string }>('/api/v1/pipelines/stream/token', { method: 'POST' });
        if (cancelled) return;
        es = new EventSource(`/api/v1/pipelines/events?token=${encodeURIComponent(tok.stream_token)}`);
        es.onopen    = () => setSseConnected(true);
        es.onerror   = () => setSseConnected(false);
        es.addEventListener('run.update', (e: any) => {
          try {
            const patch: PipelineRun = JSON.parse(e.data);
            setRuns((prev) => prev.map((r) => (r.id === patch.id ? { ...r, ...patch } : r)));
          } catch { /* swallow */ }
        });
      } catch { /* SSE optional — fall back to manual refresh */ }
    })();
    return () => { cancelled = true; es?.close(); };
  }, []);

  const filtered = runs.filter((r) => {
    if (statusFilter !== 'all' && r.status !== statusFilter) return false;
    if (search.trim() && !r.name.toLowerCase().includes(search.toLowerCase())) return false;
    return true;
  });

  return (
    <>
      <PageHeader
        title={t('templates18DataPipelineManager.title')}
        description={t('templates18DataPipelineManager.description')}
        actions={
          <>
            <Button variant="secondary" onClick={() => load(true)} disabled={loading}>
              <RefreshCw className={'w-4 h-4 mr-2 ' + (loading ? 'animate-spin' : '')} />
              {t('templates18DataPipelineManager.refresh')}
            </Button>
            <Button onClick={() => (window.location.href = '/p2/pipelines/new')}>
              <Plus className="w-4 h-4 mr-2" />
              {t('templates18DataPipelineManager.newPipeline')}
            </Button>
          </>
        }
      />

      <div className="px-6 lg:px-8 py-6 max-w-[1400px] mx-auto space-y-4">
        {/* SSE connection status */}
        <div className={cn(
          'flex items-center gap-2 text-xs px-3 py-1.5 rounded-sm-custom w-fit',
          sseConnected
            ? 'bg-[var(--state-success)]/10 text-[#5C856A]'
            : 'bg-[var(--bg-app)] text-[var(--text-secondary)]',
        )}>
          <Radio className={cn('w-3 h-3', sseConnected && 'animate-pulse')} />
          {sseConnected
            ? t('templates18DataPipelineManager.sseConnected')
            : t('templates18DataPipelineManager.sseDisconnected')}
        </div>

        <ErrorBanner problem={problem} />

        <div className="flex flex-col sm:flex-row gap-3">
          <div className="relative flex-1">
            <Search className="w-4 h-4 text-[var(--text-secondary)] absolute left-3 top-1/2 -translate-y-1/2" />
            <input
              type="text"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder={t('templates18DataPipelineManager.searchPlaceholder')}
              className="w-full bg-[var(--bg-card)] border border-[var(--border-color)] rounded-md-custom pl-9 pr-4 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-[var(--primary-gold)]/30 focus:border-[var(--primary-gold)]"
            />
          </div>
          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value as any)}
            className="bg-[var(--bg-card)] border border-[var(--border-color)] rounded-md-custom px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-[var(--primary-gold)]/30"
          >
            <option value="all">{t('templates18DataPipelineManager.allStatuses')}</option>
            {(Object.keys(STATUS_META) as PipelineStatus[]).map((s) => (
              <option key={s} value={s}>{STATUS_META[s].label}</option>
            ))}
          </select>
        </div>

        <div className="bg-[var(--bg-card)] rounded-lg-custom border border-[var(--border-color)] overflow-hidden shadow-soft-sm">
          {loading && runs.length === 0 ? (
            <div className="p-6 space-y-3">
              {[1,2,3,4].map((i) => <div key={i} className="h-16 rounded-md-custom bg-[var(--bg-app)]/60 animate-pulse" />)}
            </div>
          ) : filtered.length === 0 ? (
            <p className="p-12 text-center text-[var(--text-secondary)]">{t('templates18DataPipelineManager.emptyFiltered')}</p>
          ) : (
            <table className="w-full">
              <thead className="bg-[var(--bg-app)]/50 border-b border-[var(--border-color)]">
                <tr>
                  <Th>{t('templates18DataPipelineManager.thPipeline')}</Th>
                  <Th>{t('templates18DataPipelineManager.thStep')}</Th>
                  <Th>{t('templates18DataPipelineManager.thStatus')}</Th>
                  <Th>{t('templates18DataPipelineManager.thRows')}</Th>
                  <Th>{t('templates18DataPipelineManager.thOwner')}</Th>
                  <Th>{t('templates18DataPipelineManager.thUpdated')}</Th>
                  <Th></Th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[var(--border-color)]/60">
                {filtered.map((r) => {
                  // Defensive: never let an unmapped status crash the list again.
                  const meta = STATUS_META[r.status] ?? STATUS_META.schema_review;
                  const Icon = meta.icon;
                  return (
                    <tr
                      key={r.id}
                      onClick={() => (window.location.href = `/p2/pipelines/${r.id}`)}
                      className="hover:bg-[var(--bg-app)]/40 cursor-pointer transition-colors"
                    >
                      <Td>
                        <div className="flex items-center gap-3">
                          <div className="w-9 h-9 rounded-md-custom bg-[var(--primary-gold)]/12 flex items-center justify-center shrink-0">
                            <GitMerge className="w-4 h-4 text-[var(--primary-gold-dark)]" />
                          </div>
                          <div className="min-w-0">
                            <p className="text-sm font-medium text-[var(--text-primary)] truncate">{r.name}</p>
                            <p className="text-[11px] text-[var(--text-secondary)]">
                              {r.template_id} · {t('templates18DataPipelineManager.rowsSuffix', { count: r.rows.toLocaleString('vi-VN') })}
                            </p>
                          </div>
                        </div>
                      </Td>
                      <Td>
                        <div className="flex items-center gap-2">
                          <span className="text-xs text-[var(--text-secondary)]">{r.current_step}/5</span>
                          <span className="text-xs text-[var(--text-primary)]">{STEP_LABEL[r.current_step]}</span>
                        </div>
                      </Td>
                      <Td>
                        <div className="space-y-1">
                          <div className="flex items-center gap-1.5">
                            <Icon className={cn(
                              'w-3.5 h-3.5',
                              r.status === 'analyzing' && 'animate-pulse',
                            )} />
                            <Badge variant={meta.variant}>{meta.label}</Badge>
                          </div>
                          {r.status === 'analyzing' && (
                            <div className="h-1 w-32 rounded-full bg-[var(--border-color)]/40 overflow-hidden">
                              <div className="h-full bg-[var(--primary-gold)] transition-all duration-500" style={{ width: `${r.progress_pct}%` }} />
                            </div>
                          )}
                        </div>
                      </Td>
                      <Td>
                        <span className="text-sm font-mono text-[var(--text-primary)]">
                          {r.rows.toLocaleString('vi-VN')}
                        </span>
                      </Td>
                      <Td><span className="text-sm text-[var(--text-secondary)]">{r.owner_email}</span></Td>
                      <Td><span className="text-sm text-[var(--text-secondary)]">{r.updated_at}</span></Td>
                      <Td><ChevronRight className="w-4 h-4 text-[var(--text-secondary)]" /></Td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          )}

          {hasMore && filtered.length > 0 && (
            <div className="border-t border-[var(--border-color)]/60 p-4 text-center">
              <Button variant="secondary" onClick={() => load(false)} isLoading={loading}>
                {t('templates18DataPipelineManager.loadMore')}
              </Button>
            </div>
          )}
        </div>
      </div>
    </>
  );
}

function Th({ children }: any) {
  return <th className="px-5 py-3 text-left text-[11px] font-semibold uppercase tracking-wider text-[var(--text-secondary)]">{children}</th>;
}
function Td({ children, className }: any) {
  return <td className={cn('px-5 py-3', className)}>{children}</td>;
}
