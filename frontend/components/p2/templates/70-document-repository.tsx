// @ts-nocheck — template; tighten types when wiring to real API
// ADR-0039 + ADR-0042 — Kho tài liệu (enterprise DMS, cấu trúc Confluence).
// Bố cục 3-pane kiểu Confluence: page tree trái · nghiệp vụ page giữa (mô tả +
// mẫu + file mẫu + version history + index) · màu giữ nguyên hệ Kaori.
'use client';

import React, { useState, useCallback } from 'react';
import {
  ChevronRight, Home, Search, Loader2, CalendarDays, ListTree, FileText,
  ChevronDown, LayoutTemplate,
} from 'lucide-react';

import {
  Button, Badge, ErrorBanner, cn, api, type ProblemDetails,
} from '@/components/p2/foundation';
import { PageHeader } from '@/components/p2/shell';
import { FolderTree } from '@/components/p2/dms/tree';
import { FolderPage } from '@/components/p2/dms/folder-page';
import { useT } from '@/lib/i18n/provider';

function periodLabel(t: (key: string, params?: Record<string, string | number>) => string, kind: string): string {
  const map: Record<string, string> = {
    day: t('templates70DocumentRepository.periodLabelDay'),
    week: t('templates70DocumentRepository.periodLabelWeek'),
    month: t('templates70DocumentRepository.periodLabelMonth'),
    quarter: t('templates70DocumentRepository.periodLabelQuarter'),
    year: t('templates70DocumentRepository.periodLabelYear'),
  };
  return map[kind] ?? kind;
}

function dateQS(dateFrom: string, dateTo: string, periodKind: string): string {
  const p = new URLSearchParams();
  if (dateFrom) p.set('date_from', dateFrom);
  if (dateTo) p.set('date_to', dateTo);
  if (periodKind) p.set('period_kind', periodKind);
  const s = p.toString();
  return s ? `&${s}` : '';
}

export default function DocumentRepositoryPage() {
  const t = useT();
  const [current, setCurrent] = useState<string | null>(null);   // null = root
  const [crumbs, setCrumbs] = useState<{ folder_id: string; name_vi: string }[]>([]);
  const [problem, setProblem] = useState<ProblemDetails | null>(null);
  const [treeRefresh, setTreeRefresh] = useState(0);
  const [search, setSearch] = useState('');
  const [results, setResults] = useState<any[] | null>(null);
  const [dateFrom, setDateFrom] = useState('');
  const [dateTo, setDateTo] = useState('');
  const [periodKind, setPeriodKind] = useState('');
  const [view, setView] = useState<'page' | 'time'>('page');

  const select = useCallback(async (id: string | null) => {
    setCurrent(id);
    setResults(null);
    setView('page');
    setProblem(null);
    if (id) {
      try {
        const r = await api<{ items: { folder_id: string; name_vi: string }[] }>(
          `/api/v1/document-folders/${id}/breadcrumb`);
        setCrumbs(r.items || []);
      } catch { setCrumbs([]); }
    } else setCrumbs([]);
  }, []);

  async function runSearch() {
    if (!search.trim() && !dateFrom && !dateTo && !periodKind) { setResults(null); return; }
    try {
      const r = await api<{ items: any[] }>(
        `/api/v1/document-repository/search?q=${encodeURIComponent(search.trim())}${dateQS(dateFrom, dateTo, periodKind)}`);
      setResults(r.items || []);
    } catch (err: any) { setProblem(err); }
  }

  return (
    <div className="space-y-4">
      <PageHeader
        title={t('templates70DocumentRepository.title')}
        description={t('templates70DocumentRepository.pageDescription')}
        actions={
          <a href="/p2/document-templates"
            className="inline-flex items-center gap-1.5 text-sm px-3 py-2 rounded-md-custom border border-[var(--border-color)] bg-white hover:border-[var(--primary-gold)]/60 text-[var(--text-primary)]">
            <LayoutTemplate className="w-4 h-4 text-[var(--primary-gold-dark)]" /> {t('templates70DocumentRepository.templatesLink')}
          </a>
        }
      />

      {/* search + date filters + view switch */}
      <div className="flex items-center gap-2 flex-wrap">
        <div className="relative flex-1 max-w-md min-w-[220px]">
          <Search className="w-4 h-4 text-[var(--text-secondary)] absolute left-3 top-1/2 -translate-y-1/2" />
          <input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && runSearch()}
            placeholder={t('templates70DocumentRepository.searchPlaceholder')}
            className="w-full pl-9 pr-3 py-2 bg-white border border-[var(--border-color)] rounded-md-custom text-sm focus:outline-none focus:ring-2 focus:ring-[var(--primary-gold)]/30"
          />
        </div>
        <input type="date" value={dateFrom} onChange={(e) => setDateFrom(e.target.value)}
          title={t('templates70DocumentRepository.dateFromTitle')}
          className="px-2 py-2 bg-white border border-[var(--border-color)] rounded-md-custom text-sm text-[var(--text-secondary)]" />
        <span className="text-xs text-[var(--text-secondary)]">→</span>
        <input type="date" value={dateTo} onChange={(e) => setDateTo(e.target.value)}
          title={t('templates70DocumentRepository.dateToTitle')}
          className="px-2 py-2 bg-white border border-[var(--border-color)] rounded-md-custom text-sm text-[var(--text-secondary)]" />
        <select value={periodKind} onChange={(e) => setPeriodKind(e.target.value)}
          title={t('templates70DocumentRepository.periodKindTitle')}
          className="px-2 py-2 bg-white border border-[var(--border-color)] rounded-md-custom text-sm text-[var(--text-secondary)]">
          <option value="">{t('templates70DocumentRepository.periodAll')}</option>
          <option value="day">{t('templates70DocumentRepository.periodReportDay')}</option>
          <option value="week">{t('templates70DocumentRepository.periodReportWeek')}</option>
          <option value="month">{t('templates70DocumentRepository.periodReportMonth')}</option>
          <option value="quarter">{t('templates70DocumentRepository.periodReportQuarter')}</option>
          <option value="year">{t('templates70DocumentRepository.periodReportYear')}</option>
        </select>
        <Button variant="secondary" onClick={runSearch}>{t('templates70DocumentRepository.searchButton')}</Button>
        {(dateFrom || dateTo || periodKind) && (
          <button onClick={() => { setDateFrom(''); setDateTo(''); setPeriodKind(''); setResults(null); }}
            className="text-xs text-[var(--text-secondary)] hover:text-[var(--state-error)] underline">
            {t('templates70DocumentRepository.clearFilter')}
          </button>
        )}
        <div className="ml-auto flex items-center rounded-md-custom border border-[var(--border-color)] overflow-hidden">
          <button onClick={() => setView('page')}
            className={cn('px-2.5 py-2 text-xs flex items-center gap-1.5',
              view === 'page' ? 'bg-[var(--primary-gold)]/15 text-[var(--primary-gold-dark)] font-medium' : 'bg-white text-[var(--text-secondary)]')}>
            <ListTree className="w-3.5 h-3.5" /> {t('templates70DocumentRepository.viewTree')}
          </button>
          <button onClick={() => setView('time')}
            className={cn('px-2.5 py-2 text-xs flex items-center gap-1.5',
              view === 'time' ? 'bg-[var(--primary-gold)]/15 text-[var(--primary-gold-dark)] font-medium' : 'bg-white text-[var(--text-secondary)]')}>
            <CalendarDays className="w-3.5 h-3.5" /> {t('templates70DocumentRepository.viewTime')}
          </button>
        </div>
      </div>

      {problem && <ErrorBanner problem={problem} />}

      {results !== null ? (
        <div className="bg-[var(--bg-card)] border border-[var(--border-color)] rounded-lg-custom p-4">
          <p className="text-xs text-[var(--text-secondary)] mb-2">
            {t('templates70DocumentRepository.resultsCount', { count: results.length })}
            {search.trim() ? t('templates70DocumentRepository.resultsFor', { query: search }) : ''}
            {(dateFrom || dateTo) && ` · ${dateFrom || '…'} → ${dateTo || '…'}`}
            {periodKind && ` · ${periodLabel(t, periodKind)}`}
          </p>
          {results.map((r) => (
            <button key={r.doc_id} onClick={() => select(r.folder_id)}
              className="w-full flex items-center gap-2 px-2 py-2 rounded hover:bg-[var(--bg-app)]/50 text-left">
              <FileText className="w-4 h-4 text-emerald-700 shrink-0" />
              <span className="text-sm flex-1 truncate">{r.name_vi}</span>
              {r.doc_date && (
                <span className="text-[10px] text-[var(--text-secondary)] shrink-0 inline-flex items-center gap-1">
                  <CalendarDays className="w-3 h-3" />{r.doc_date}
                </span>
              )}
              {r.period_kind && <Badge variant="default" className="text-[10px] shrink-0">{periodLabel(t, r.period_kind)}</Badge>}
              <span className="text-[10px] text-[var(--text-secondary)] font-mono truncate">{r.path}</span>
            </button>
          ))}
        </div>
      ) : view === 'time' ? (
        <TimeTree
          periodKind={periodKind}
          onPick={async (from, to) => {
            setDateFrom(from); setDateTo(to);
            try {
              const r = await api<{ items: any[] }>(
                `/api/v1/document-repository/search?q=${dateQS(from, to, periodKind)}`);
              setResults(r.items || []);
            } catch (err: any) { setProblem(err); }
          }}
        />
      ) : (
        /* ── 3-pane kiểu Confluence: tree trái · page giữa ─────────────── */
        <div className="grid grid-cols-1 lg:grid-cols-[260px_1fr] gap-4 items-start">
          <aside className="bg-[var(--bg-card)] border border-[var(--border-color)] rounded-lg-custom p-2.5 lg:sticky lg:top-4">
            <button onClick={() => select(null)}
              className={cn('flex items-center gap-1.5 px-1.5 py-1 rounded text-[13px] w-full mb-1',
                current === null ? 'bg-[var(--primary-gold)]/15 text-[var(--primary-gold-dark)] font-medium' : 'hover:bg-[var(--bg-app)]/60')}>
              <Home className="w-3.5 h-3.5" /> {t('templates70DocumentRepository.title')}
            </button>
            <FolderTree selected={current} onSelect={select}
              refreshKey={treeRefresh} onProblem={setProblem} />
          </aside>

          <main className="min-w-0">
            {/* breadcrumb */}
            {current && crumbs.length > 0 && (
              <div className="flex items-center gap-1 text-xs text-[var(--text-secondary)] flex-wrap mb-3">
                <button onClick={() => select(null)} className="hover:text-[var(--primary-gold-dark)]">{t('templates70DocumentRepository.breadcrumbRoot')}</button>
                {crumbs.map((c) => (
                  <React.Fragment key={c.folder_id}>
                    <ChevronRight className="w-3 h-3 opacity-50" />
                    <button onClick={() => select(c.folder_id)}
                      className={cn('hover:text-[var(--primary-gold-dark)]', c.folder_id === current && 'text-[var(--text-primary)] font-medium')}>
                      {c.name_vi}
                    </button>
                  </React.Fragment>
                ))}
              </div>
            )}

            {current ? (
              <FolderPage folderId={current} onUploaded={() => setTreeRefresh((k) => k + 1)} />
            ) : (
              <div className="py-14 text-center text-sm text-[var(--text-secondary)] border border-dashed border-[var(--border-color)] rounded-lg-custom">
                <p className="font-medium text-[var(--text-primary)] mb-1">{t('templates70DocumentRepository.emptyStateTitle')}</p>
                <p>{t('templates70DocumentRepository.emptyStatePre')} <b>{t('templates70DocumentRepository.emptyStateBold')}</b>{t('templates70DocumentRepository.emptyStatePost1')}<br />
                  {t('templates70DocumentRepository.emptyStatePost2')}</p>
              </div>
            )}
          </main>
        </div>
      )}
    </div>
  );
}

// ═══════════════════════════════════════════════════════════════════
// TimeTree — cây ẢO Năm → Quý → Tháng → Ngày (mig 138).
// Thời gian là metadata, không phải folder vật lý: mỗi cấp là một lần
// GROUP BY trên COALESCE(doc_date, uploaded_at) — không nổ thư mục,
// và báo cáo tuần (vắt qua 2 tháng) vẫn lọc được qua kỳ/khoảng ngày.
// ═══════════════════════════════════════════════════════════════════

interface Bucket { doc_count: number; year: number; quarter?: number; month?: number; day?: number; }

function bucketRange(b: Bucket): [string, string] {
  const pad = (n: number) => String(n).padStart(2, '0');
  if (b.day != null) {
    const d = `${b.year}-${pad(b.month!)}-${pad(b.day)}`;
    return [d, d];
  }
  if (b.month != null) {
    const last = new Date(b.year, b.month, 0).getDate();
    return [`${b.year}-${pad(b.month)}-01`, `${b.year}-${pad(b.month)}-${pad(last)}`];
  }
  if (b.quarter != null) {
    const m0 = (b.quarter - 1) * 3 + 1;
    const last = new Date(b.year, m0 + 2, 0).getDate();
    return [`${b.year}-${pad(m0)}-01`, `${b.year}-${pad(m0 + 2)}-${pad(last)}`];
  }
  return [`${b.year}-01-01`, `${b.year}-12-31`];
}

function bucketLabel(b: Bucket, t: (key: string, params?: Record<string, string | number>) => string): string {
  if (b.day != null) return t('templates70DocumentRepository.bucketDay', { day: String(b.day).padStart(2, '0') });
  if (b.month != null) return t('templates70DocumentRepository.bucketMonth', { month: b.month });
  if (b.quarter != null) return t('templates70DocumentRepository.bucketQuarter', { quarter: b.quarter });
  return t('templates70DocumentRepository.bucketYear', { year: b.year });
}

function bucketKey(b: Bucket): string {
  return [b.year, b.quarter ?? '', b.month ?? '', b.day ?? ''].join('-');
}

function TimeTree({ periodKind, onPick }: {
  periodKind: string;
  onPick: (from: string, to: string) => void;
}) {
  const t = useT();
  const NEXT: Record<string, string | null> = { year: 'quarter', quarter: 'month', month: 'day', day: null };
  const [years, setYears] = useState<Bucket[] | null>(null);
  const [children, setChildren] = useState<Record<string, Bucket[]>>({});
  const [open, setOpen] = useState<Record<string, boolean>>({});
  const [err, setErr] = useState<ProblemDetails | null>(null);

  React.useEffect(() => {
    api<{ buckets: Bucket[] }>('/api/v1/document-repository/timeline?granularity=year')
      .then((r) => setYears(r.buckets || []))
      .catch(setErr);
  }, []);

  async function toggle(b: Bucket, level: string) {
    const key = bucketKey(b);
    if (open[key]) { setOpen((o) => ({ ...o, [key]: false })); return; }
    setOpen((o) => ({ ...o, [key]: true }));
    const next = NEXT[level];
    if (!next || children[key]) return;
    const p = new URLSearchParams({ granularity: next, year: String(b.year) });
    if (b.quarter != null) p.set('quarter', String(b.quarter));
    if (b.month != null) p.set('month', String(b.month));
    try {
      const r = await api<{ buckets: Bucket[] }>(`/api/v1/document-repository/timeline?${p}`);
      setChildren((c) => ({ ...c, [key]: r.buckets || [] }));
    } catch (e: any) { setErr(e); }
  }

  function renderLevel(buckets: Bucket[], level: string, depth: number) {
    return buckets.map((b) => {
      const key = bucketKey(b);
      const expandable = NEXT[level] !== null;
      const [from, to] = bucketRange(b);
      return (
        <div key={key}>
          <div className="flex items-center gap-1.5 py-1.5 px-2 rounded hover:bg-[var(--bg-app)]/50"
            style={{ paddingLeft: `${8 + depth * 20}px` }}>
            {expandable ? (
              <button onClick={() => toggle(b, level)} className="text-[var(--text-secondary)] shrink-0">
                {open[key] ? <ChevronDown className="w-3.5 h-3.5" /> : <ChevronRight className="w-3.5 h-3.5" />}
              </button>
            ) : <span className="w-3.5 shrink-0" />}
            <CalendarDays className="w-4 h-4 text-[var(--primary-gold-dark)] shrink-0" />
            <button onClick={() => (expandable ? toggle(b, level) : onPick(from, to))}
              className="text-sm font-medium hover:text-[var(--primary-gold-dark)]">
              {bucketLabel(b, t)}
            </button>
            <button onClick={() => onPick(from, to)}
              title={t('templates70DocumentRepository.viewRangeTitle')}
              className="ml-auto text-[10px] text-[var(--text-secondary)] hover:text-[var(--primary-gold-dark)] tabular-nums">
              {b.doc_count} {t('templates70DocumentRepository.docCountSuffix')} →
            </button>
          </div>
          {open[key] && children[key] && renderLevel(children[key], NEXT[level]!, depth + 1)}
          {open[key] && !children[key] && expandable && (
            <div className="py-1 text-center"><Loader2 className="w-3.5 h-3.5 animate-spin inline text-[var(--text-secondary)]" /></div>
          )}
        </div>
      );
    });
  }

  if (err) return <ErrorBanner problem={err} />;
  if (years === null)
    return <div className="py-10 text-center text-[var(--text-secondary)]"><Loader2 className="w-5 h-5 animate-spin inline" /></div>;
  if (years.length === 0)
    return <div className="py-10 text-center text-sm text-[var(--text-secondary)]">{t('templates70DocumentRepository.noDocsTimeline')}</div>;

  return (
    <div className="bg-[var(--bg-card)] border border-[var(--border-color)] rounded-lg-custom p-2">
      <p className="px-2 pt-1 pb-2 text-[11px] text-[var(--text-secondary)]">
        {t('templates70DocumentRepository.timelineIntroPre')} <b>{t('templates70DocumentRepository.timelineIntroBold')}</b>
        {t('templates70DocumentRepository.timelineIntroPost')}
        {periodKind ? t('templates70DocumentRepository.timelineFilterSuffix', { period: periodLabel(t, periodKind) }) : ''}.
      </p>
      {renderLevel(years, 'year', 0)}
    </div>
  );
}
