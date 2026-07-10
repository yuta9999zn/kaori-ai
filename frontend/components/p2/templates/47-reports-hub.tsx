'use client';

// ============================================================================
// 47. /p2/reports — Reports Hub (F-038 🔵 Phase 2)
// ----------------------------------------------------------------------------
// Trung tâm báo cáo doanh nghiệp. Người dùng:
//   - Xem mọi báo cáo (tự động · tuỳ chỉnh · từ mẫu) trong một bảng.
//   - Lọc theo loại + tìm kiếm theo tên/người tạo.
//   - Mở Report Builder (file 49) để tạo mới hoặc bấm "Tự động" (file 48).
//
// Wires `GET /api/v1/reports` (PR #113). BE shape `ReportListItem` is mapped
// to the template's `ReportRow` at fetch time so visual contract stays stable.
// Builder/templates/distribution screens are still mock-only this round.
// ============================================================================

import React, { useEffect, useMemo, useState } from 'react';
import {
  FileText, FileStack, Clock, CalendarCheck, Share2, Search,
  Plus, Sparkles, Calendar, ListFilter, Send, Trash2, User,
  ArrowRight, Loader2, BookOpen, FileBadge,
} from 'lucide-react';

import { Button, Badge, ErrorBanner, api, cn, type ProblemDetails } from '@/components/p2/foundation';
import { PageHeader } from '@/components/p2/shell';
import { useT } from '@/lib/i18n/provider';
// ============================================================================
// Types & filters
// ============================================================================

type ReportType   = 'auto' | 'custom' | 'template';
type ReportStatus = 'draft' | 'scheduled' | 'published' | 'failed';
type ReportFormat = 'pdf' | 'html' | 'csv';

interface ReportRow {
  id:           string;
  title:        string;
  type:         ReportType;
  format:       ReportFormat;
  owner_email:  string;
  updated_at:   string;
  status:       ReportStatus;
  schedule_cron?: string | null;
}

// BE shape from GET /api/v1/reports (services/ai-orchestrator/routers/reports.py).
// Kept loose-typed because we adapt to ReportRow before rendering.
interface BackendReportItem {
  report_id:    string;
  template_id:  string;
  title:        string;
  owner_email:  string;
  status:       'queued' | 'running' | 'ready' | 'failed';
  narrative?:   string | null;
  created_at:   string;
  completed_at?: string | null;
  last_error?:  string | null;
}

// Stable id of the built-in monthly_summary template seeded by migration 027.
// Anything else is treated as a custom (per-tenant) template for the type tag.
const BUILT_IN_MONTHLY_SUMMARY_ID = '00000000-0000-0000-0000-000000000001';

const BE_TO_FE_STATUS: Record<BackendReportItem['status'], ReportStatus> = {
  queued:  'scheduled',
  running: 'draft',
  ready:   'published',
  failed:  'failed',
};

function adaptBackendReport(item: BackendReportItem): ReportRow {
  return {
    id:          item.report_id,
    title:       item.title,
    type:        item.template_id === BUILT_IN_MONTHLY_SUMMARY_ID ? 'auto' : 'custom',
    format:      'html',          // BE doesn't carry a format; render hint only
    owner_email: item.owner_email,
    updated_at:  item.completed_at ?? item.created_at,
    status:      BE_TO_FE_STATUS[item.status],
  };
}

const TYPE_FILTERS: { value: 'all' | ReportType; labelKey: string }[] = [
  { value: 'all',      labelKey: 'templates47ReportsHub.typeFilterAll' },
  { value: 'auto',     labelKey: 'templates47ReportsHub.typeAuto' },
  { value: 'custom',   labelKey: 'templates47ReportsHub.typeCustom' },
  { value: 'template', labelKey: 'templates47ReportsHub.typeTemplate' },
];

const TYPE_LABEL_KEY: Record<ReportType, string> = {
  auto:     'templates47ReportsHub.typeAuto',
  custom:   'templates47ReportsHub.typeCustom',
  template: 'templates47ReportsHub.typeTemplate',
};

const FORMAT_LABEL: Record<ReportFormat, string> = {
  pdf:  'PDF',
  html: 'HTML',
  csv:  'CSV',
};

const STATUS_META: Record<ReportStatus, { labelKey: string; variant: 'default' | 'success' | 'warning' | 'error' | 'info' }> = {
  draft:     { labelKey: 'templates47ReportsHub.statusDraft',     variant: 'default' },
  scheduled: { labelKey: 'templates47ReportsHub.statusScheduled', variant: 'info' },
  published: { labelKey: 'templates47ReportsHub.statusPublished', variant: 'success' },
  failed:    { labelKey: 'templates47ReportsHub.statusFailed',    variant: 'error' },
};

// ============================================================================
// Mock fallback (dev preview)
// ============================================================================

const MOCK_REPORTS: ReportRow[] = [
  { id: 'rep_001', title: 'Báo cáo doanh thu tháng 4/2026',         type: 'auto',     format: 'pdf',  owner_email: 'system@kaori',     updated_at: '2026-04-30T08:00:00+07:00', status: 'published', schedule_cron: '0 8 1 * *' },
  { id: 'rep_002', title: 'Phân tích churn quý 1 — Bán lẻ',         type: 'custom',   format: 'html', owner_email: 'minh@acme.vn',    updated_at: '2026-04-29T17:42:00+07:00', status: 'draft' },
  { id: 'rep_003', title: 'Tỷ suất tồn kho ngành Sản xuất',         type: 'template', format: 'pdf',  owner_email: 'huy@acme.vn',     updated_at: '2026-04-28T11:15:00+07:00', status: 'published' },
  { id: 'rep_004', title: 'Nhật ký quyết định AI — tuần này',       type: 'auto',     format: 'csv',  owner_email: 'system@kaori',     updated_at: '2026-04-27T22:00:00+07:00', status: 'scheduled', schedule_cron: '0 22 * * 0' },
  { id: 'rep_005', title: 'Đối chiếu chi phí AI ngoài (consent K-4)', type: 'custom', format: 'html', owner_email: 'lan@acme.vn',     updated_at: '2026-04-26T09:33:00+07:00', status: 'failed' },
];

// ============================================================================
// Page
// ============================================================================

export default function ReportsHubPage() {
  const t = useT();
  const [reports, setReports] = useState<ReportRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [problem, setProblem] = useState<ProblemDetails | null>(null);

  const [search, setSearch]       = useState('');
  const [typeFilter, setTypeFilter] = useState<'all' | ReportType>('all');

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const data = await api<{ items: BackendReportItem[]; next_cursor: string | null }>(
          '/api/v1/reports?limit=200',
        );
        if (!cancelled) setReports((data.items ?? []).map(adaptBackendReport));
      } catch (e: any) {
        if (!cancelled) {
          setProblem(e);
          setReports(MOCK_REPORTS); // graceful preview fallback
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => { cancelled = true; };
  }, []);

  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase();
    return reports.filter((r) => {
      const matchType = typeFilter === 'all' || r.type === typeFilter;
      const matchSearch = q === '' || r.title.toLowerCase().includes(q) || r.owner_email.toLowerCase().includes(q);
      return matchType && matchSearch;
    });
  }, [reports, search, typeFilter]);

  const stats = useMemo(() => {
    const draft     = reports.filter((r) => r.status === 'draft').length;
    const scheduled = reports.filter((r) => r.status === 'scheduled').length;
    const published = reports.filter((r) => r.status === 'published').length;
    return [
      { label: t('templates47ReportsHub.statTotal'),       value: reports.length, icon: FileStack,    tone: 'text-[var(--text-primary)]' },
      { label: t('templates47ReportsHub.statusDraft'),     value: draft,          icon: Clock,        tone: 'text-[var(--state-warning)]' },
      { label: t('templates47ReportsHub.statusScheduled'), value: scheduled,      icon: CalendarCheck, tone: 'text-[var(--primary-gold-dark)]' },
      { label: t('templates47ReportsHub.statusPublished'), value: published,      icon: Share2,       tone: 'text-[var(--state-success)]' },
    ];
  }, [reports, t]);

  return (
    <>
      <PageHeader
        title={t('templates47ReportsHub.pageTitle')}
        description={t('templates47ReportsHub.pageDescription')}
        actions={
          <>
            <Badge variant="info">Phase 2 · F-038</Badge>
            <a href="/p2/reports/auto">
              <Button variant="secondary" size="md">
                <Sparkles className="w-4 h-4 mr-2 text-[var(--primary-gold-dark)]" />
                {t('templates47ReportsHub.typeAuto')}
              </Button>
            </a>
            <a href="/p2/reports/builder">
              <Button variant="primary" size="md">
                <Plus className="w-4 h-4 mr-2" />
                {t('templates47ReportsHub.btnCreate')}
              </Button>
            </a>
          </>
        }
      />

      <div className="px-6 lg:px-8 py-6 max-w-[1400px] mx-auto space-y-6">
        {problem && (
          <ErrorBanner
            problem={{
              ...problem,
              title:  t('templates47ReportsHub.errFallbackTitle'),
              detail: `${problem.title}${problem.detail ? ' — ' + problem.detail : ''}. ${t('templates47ReportsHub.errFallbackDetail')}`,
            }}
          />
        )}

        {/* KPI tiles */}
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
          {stats.map((s) => {
            const Icon = s.icon;
            return (
              <div key={s.label} className="bg-[var(--bg-card)] border border-[var(--border-color)] rounded-lg-custom p-5 shadow-soft-sm">
                <div className="flex items-center justify-between mb-2">
                  <span className="text-[11px] uppercase tracking-wider font-medium text-[var(--text-secondary)]">{s.label}</span>
                  <Icon className={cn('w-5 h-5', s.tone)} />
                </div>
                <p className="font-serif text-3xl text-[var(--text-primary)]">{loading ? '–' : s.value}</p>
              </div>
            );
          })}
        </div>

        {/* AI suggestion banner */}
        <AiSuggestionBanner />

        {/* Toolbar */}
        <div className="bg-[var(--bg-card)] border border-[var(--border-color)] rounded-lg-custom p-3 flex flex-col lg:flex-row items-stretch lg:items-center gap-3 shadow-soft-sm">
          <div className="relative flex-1">
            <Search className="w-4 h-4 text-[var(--text-secondary)] absolute left-3 top-1/2 -translate-y-1/2" />
            <input
              type="text"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder={t('templates47ReportsHub.searchPlaceholder')}
              className="w-full pl-9 pr-3 py-2 bg-[var(--bg-app)] border border-[var(--border-color)] rounded-md-custom text-sm text-[var(--text-primary)] placeholder:text-[var(--text-secondary)]/60 focus:outline-none focus:ring-2 focus:ring-[var(--primary-gold)]/30 focus:border-[var(--primary-gold)] transition-all"
            />
          </div>
          <div className="flex items-center gap-1.5 overflow-x-auto">
            {TYPE_FILTERS.map((tf) => (
              <button
                key={tf.value}
                onClick={() => setTypeFilter(tf.value)}
                className={cn(
                  'px-3 py-1.5 text-xs font-medium rounded-sm-custom transition-colors whitespace-nowrap',
                  typeFilter === tf.value
                    ? 'bg-[var(--primary-gold)]/15 text-[var(--text-primary)] border border-[var(--primary-gold)]/40'
                    : 'text-[var(--text-secondary)] hover:bg-[var(--bg-app)] border border-transparent',
                )}
              >
                {t(tf.labelKey)}
              </button>
            ))}
          </div>
          <div className="flex items-center gap-1 border-l border-[var(--border-color)] pl-3 ml-1">
            <a href="/p2/reports/distribution" title={t('templates47ReportsHub.tooltipDistribution')} className="p-2 text-[var(--text-secondary)] hover:text-[var(--text-primary)] hover:bg-[var(--bg-app)] rounded-sm-custom transition-colors">
              <Calendar className="w-4 h-4" />
            </a>
            <a href="/p2/reports/templates" title={t('templates47ReportsHub.tooltipTemplates')} className="p-2 text-[var(--text-secondary)] hover:text-[var(--text-primary)] hover:bg-[var(--bg-app)] rounded-sm-custom transition-colors">
              <BookOpen className="w-4 h-4" />
            </a>
            <button title={t('templates47ReportsHub.tooltipAdvancedFilter')} className="p-2 text-[var(--text-secondary)] hover:text-[var(--text-primary)] hover:bg-[var(--bg-app)] rounded-sm-custom transition-colors">
              <ListFilter className="w-4 h-4" />
            </button>
          </div>
        </div>

        {/* Table */}
        <div className="bg-[var(--bg-card)] border border-[var(--border-color)] rounded-lg-custom shadow-soft-sm overflow-hidden">
          <div className="overflow-auto">
            <table className="w-full text-sm text-left">
              <thead className="bg-[var(--bg-app)] border-b border-[var(--border-color)] text-[11px] font-medium uppercase tracking-wider text-[var(--text-secondary)]">
                <tr>
                  <th className="px-5 py-3">{t('templates47ReportsHub.colTitle')}</th>
                  <th className="px-5 py-3">{t('templates47ReportsHub.colType')}</th>
                  <th className="px-5 py-3">{t('templates47ReportsHub.colFormat')}</th>
                  <th className="px-5 py-3">{t('templates47ReportsHub.colOwner')}</th>
                  <th className="px-5 py-3">{t('templates47ReportsHub.colUpdated')}</th>
                  <th className="px-5 py-3">{t('templates47ReportsHub.colStatus')}</th>
                  <th className="px-5 py-3 text-right">{t('templates47ReportsHub.colActions')}</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[var(--border-color)]/60">
                {loading ? (
                  <tr><td colSpan={7} className="px-5 py-16 text-center text-[var(--text-secondary)]">
                    <Loader2 className="w-5 h-5 animate-spin inline mr-2" /> {t('templates47ReportsHub.loading')}
                  </td></tr>
                ) : filtered.length === 0 ? (
                  <tr><td colSpan={7} className="px-5 py-16 text-center">
                    <FileStack className="w-10 h-10 mx-auto text-[var(--text-secondary)]/40 mb-3" />
                    <p className="text-sm text-[var(--text-secondary)]">{t('templates47ReportsHub.emptyState')}</p>
                    <a href="/p2/reports/builder" className="inline-flex items-center mt-3 text-xs font-medium text-[var(--primary-gold-dark)] hover:underline">
                      {t('templates47ReportsHub.emptyCreateFirst')} <ArrowRight className="w-3 h-3 ml-1" />
                    </a>
                  </td></tr>
                ) : (
                  filtered.map((r) => <ReportRowItem key={r.id} report={r} />)
                )}
              </tbody>
            </table>
          </div>
        </div>

        {/* K-3/K-4 footer */}
        <div className="flex items-start gap-2 p-3 rounded-md-custom bg-[var(--bg-app)]/40 border border-[var(--border-color)] text-xs text-[var(--text-secondary)]">
          <Sparkles className="w-4 h-4 text-[var(--primary-gold-dark)] shrink-0 mt-0.5" />
          <p>
            {t('templates47ReportsHub.footerText1')} <span className="font-mono">llm_router.py</span> {t('templates47ReportsHub.footerText2')}
            <code>consent_external=true</code> {t('templates47ReportsHub.footerText3')}
          </p>
        </div>
      </div>
    </>
  );
}

// ============================================================================
// Sub-components
// ============================================================================

function AiSuggestionBanner() {
  const t = useT();
  return (
    <div className="bg-gradient-to-br from-[var(--primary-gold)]/10 to-[var(--bg-card)] border border-[var(--primary-gold)]/30 rounded-lg-custom p-5 shadow-soft-sm">
      <div className="flex flex-col md:flex-row items-start md:items-center justify-between gap-4">
        <div className="flex items-start gap-3">
          <div className="w-10 h-10 rounded-md-custom bg-[var(--primary-gold)]/15 flex items-center justify-center shrink-0">
            <Sparkles className="w-5 h-5 text-[var(--primary-gold-dark)]" />
          </div>
          <div>
            <h3 className="font-serif text-base text-[var(--text-primary)]">{t('templates47ReportsHub.aiSuggestionTitle')}</h3>
            <p className="text-xs text-[var(--text-secondary)] mt-1 leading-relaxed max-w-2xl">
              {t('templates47ReportsHub.aiSuggestionText1')} <span className="font-medium text-[var(--text-primary)]">12%</span>{t('templates47ReportsHub.aiSuggestionText2')}
              <span className="font-medium text-[var(--text-primary)]"> {t('templates47ReportsHub.aiSuggestionReportName')}</span> {t('templates47ReportsHub.aiSuggestionText3')}
            </p>
          </div>
        </div>
        <a href="/p2/reports/builder?suggestion=apac-roi">
          <Button variant="primary" size="sm">
            {t('templates47ReportsHub.btnCreateNow')}
            <ArrowRight className="w-3.5 h-3.5 ml-1.5" />
          </Button>
        </a>
      </div>
    </div>
  );
}

function ReportRowItem({ report: r }: { report: ReportRow }) {
  const t = useT();
  const meta = STATUS_META[r.status];
  const ownerInitials = r.owner_email.slice(0, 2).toUpperCase();

  return (
    <tr className="hover:bg-[var(--bg-app)]/50 transition-colors group">
      <td className="px-5 py-4">
        <div className="flex items-center gap-3">
          <div className="w-9 h-9 rounded-md-custom bg-[var(--primary-gold)]/10 flex items-center justify-center shrink-0">
            <FileText className="w-4 h-4 text-[var(--primary-gold-dark)]" />
          </div>
          <div className="flex flex-col">
            <a href={`/p2/reports/${r.id}`} className="text-sm font-medium text-[var(--text-primary)] group-hover:text-[var(--primary-gold-dark)] transition-colors">
              {r.title}
            </a>
            <span className="text-[11px] text-[var(--text-secondary)] mt-0.5">{t('templates47ReportsHub.idLabel', { id: r.id })}</span>
          </div>
        </div>
      </td>
      <td className="px-5 py-4">
        <Badge variant={r.type === 'auto' ? 'info' : r.type === 'custom' ? 'warning' : 'default'}>{t(TYPE_LABEL_KEY[r.type])}</Badge>
      </td>
      <td className="px-5 py-4">
        <span className="inline-flex items-center gap-1 text-xs text-[var(--text-secondary)]">
          <FileBadge className="w-3.5 h-3.5" /> {FORMAT_LABEL[r.format]}
        </span>
      </td>
      <td className="px-5 py-4">
        <div className="flex items-center gap-2">
          <div className="w-6 h-6 rounded-full bg-[var(--bg-app)] border border-[var(--border-color)] flex items-center justify-center">
            <span className="text-[10px] font-semibold text-[var(--text-secondary)]">{ownerInitials}</span>
          </div>
          <span className="text-xs text-[var(--text-primary)]">{r.owner_email}</span>
        </div>
      </td>
      <td className="px-5 py-4 text-xs text-[var(--text-secondary)]">{formatRelative(r.updated_at)}</td>
      <td className="px-5 py-4"><Badge variant={meta.variant}>{t(meta.labelKey)}</Badge></td>
      <td className="px-5 py-4 text-right">
        <div className="inline-flex items-center gap-1">
          {/* F-038 distribution (PR #118) — only ready reports can be
              dispatched, so the share button stays disabled for other states.
              Status comes from STATUS_META keys (BE → FE adapter), not from
              the BE shape directly. */}
          {r.status === 'published' ? (
            <a
              href={`/p2/reports/distribution?report=${r.id}`}
              title={t('templates47ReportsHub.tooltipPublish')}
              className="p-1.5 text-[var(--text-secondary)] hover:text-[var(--primary-gold-dark)] hover:bg-[var(--bg-app)] rounded-sm-custom transition-colors"
            >
              <Send className="w-4 h-4" />
            </a>
          ) : (
            <button
              title={t('templates47ReportsHub.tooltipPublishDisabled', { status: t('templates47ReportsHub.statusPublished') })}
              disabled
              className="p-1.5 text-[var(--text-secondary)]/40 rounded-sm-custom cursor-not-allowed"
            >
              <Send className="w-4 h-4" />
            </button>
          )}
          <button title={t('templates47ReportsHub.tooltipDelete')} className="p-1.5 text-[var(--text-secondary)] hover:text-[var(--state-error)] hover:bg-[var(--bg-app)] rounded-sm-custom transition-colors">
            <Trash2 className="w-4 h-4" />
          </button>
          <a href={`/p2/reports/${r.id}`} className="ml-1 px-3 py-1.5 text-xs font-medium text-[var(--text-primary)] border border-[var(--border-color)] hover:bg-[var(--bg-app)] rounded-sm-custom transition-colors">
            {t('templates47ReportsHub.viewLink')}
          </a>
        </div>
      </td>
    </tr>
  );
}

function formatRelative(iso: string): string {
  try {
    const d = new Date(iso);
    return d.toLocaleString('vi-VN', { day: '2-digit', month: '2-digit', year: 'numeric', hour: '2-digit', minute: '2-digit' });
  } catch {
    return iso;
  }
}
