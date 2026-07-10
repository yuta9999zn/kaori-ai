// @ts-nocheck — template import; tighten types when wiring to real API
'use client';

// ============================================================================
// 64. /p2/auto-db — Auto DB Hub (F-057 🔵 Phase 2)
// ----------------------------------------------------------------------------
// Trung tâm Auto DB:
//   - 4 KPI tile (schemas active / suggestion chờ duyệt / forms generated /
//     quality avg).
//   - 3 module card (Schema suggestion · Form generate · Quality trend).
//   - List "Schema đang active" với row count + quality score per dataset.
//   - AI cost gauge: usage AI ngoài tháng này (K-4 consent).
//
// Phase 2 (F-057). Wire `GET /api/v1/auto-db/summary`. Mặc định Qwen 2.5 nội
// bộ; chỉ chuyển external khi workspace bật consent (K-4).
// ============================================================================

import React, { useEffect, useMemo, useState } from 'react';
import {
  Cpu, Database, FileText, Sparkles, ArrowRight, TrendingUp,
  CheckCircle2, ShieldCheck, Loader2,
} from 'lucide-react';

import {
  Button, Badge, ErrorBanner, api, cn, type ProblemDetails,
} from '@/components/p2/foundation';
import { PageHeader } from '@/components/p2/shell';
import { useT } from '@/lib/i18n/provider';
// ============================================================================
// Types
// ============================================================================

interface ActiveSchema {
  id:           string;
  name:         string;
  domain:       string;
  rows:         number;
  quality_score: number;  // 0-100
  forms_count:  number;
  last_updated: string;
}

interface AutoDbSummary {
  schemas_active:        number;
  suggestions_pending:   number;
  forms_generated:       number;
  quality_avg:           number;
  ai_external_usage_pct: number;  // 0-100, monthly budget
  active_schemas:        ActiveSchema[];
}

const MOCK_SUMMARY: AutoDbSummary = {
  schemas_active:        8,
  suggestions_pending:   3,
  forms_generated:       42,
  quality_avg:           87,
  ai_external_usage_pct: 32,
  active_schemas: [
    { id: 'sch_1', name: 'customer_master',         domain: 'CRM',         rows: 12_540,  quality_score: 96, forms_count: 8, last_updated: '2026-04-30T10:14:00+07:00' },
    { id: 'sch_2', name: 'order_lifecycle',         domain: 'Bán hàng',    rows: 84_120,  quality_score: 91, forms_count: 6, last_updated: '2026-04-30T08:42:00+07:00' },
    { id: 'sch_3', name: 'product_catalog',         domain: 'Sản phẩm',    rows:  4_220,  quality_score: 88, forms_count: 5, last_updated: '2026-04-29T16:30:00+07:00' },
    { id: 'sch_4', name: 'support_tickets',         domain: 'Dịch vụ',     rows: 18_904,  quality_score: 82, forms_count: 7, last_updated: '2026-04-29T11:00:00+07:00' },
    { id: 'sch_5', name: 'employee_directory',      domain: 'HR',           rows:    412,  quality_score: 95, forms_count: 4, last_updated: '2026-04-25T09:00:00+07:00' },
    { id: 'sch_6', name: 'finance_transactions',    domain: 'Tài chính',    rows:142_380,  quality_score: 78, forms_count: 6, last_updated: '2026-04-30T03:14:00+07:00' },
    { id: 'sch_7', name: 'marketing_campaigns',     domain: 'Marketing',    rows:    298,  quality_score: 85, forms_count: 3, last_updated: '2026-04-22T14:20:00+07:00' },
    { id: 'sch_8', name: 'inventory_movements',     domain: 'Vận hành',     rows: 56_708,  quality_score: 81, forms_count: 3, last_updated: '2026-04-30T01:00:00+07:00' },
  ],
};

const MODULES = [
  { code: 'schema',  titleKey: 'templates64Autodb.moduleSchemaTitle',  descKey: 'templates64Autodb.moduleSchemaDesc',  href: '/p2/auto-db/schema-suggestion', icon: Database },
  { code: 'form',    titleKey: 'templates64Autodb.moduleFormTitle',    descKey: 'templates64Autodb.moduleFormDesc',    href: '/p2/auto-db/forms/generate',    icon: FileText },
  { code: 'quality', titleKey: 'templates64Autodb.moduleQualityTitle', descKey: 'templates64Autodb.moduleQualityDesc', href: '/p2/auto-db/quality-trend',     icon: TrendingUp },
];

// ============================================================================
// Page
// ============================================================================

export default function AutoDbHubPage() {
  const t = useT();
  const [summary, setSummary] = useState<AutoDbSummary>(MOCK_SUMMARY);
  const [loading, setLoading] = useState(true);
  const [problem, setProblem] = useState<ProblemDetails | null>(null);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const data = await api<AutoDbSummary>('/api/v1/auto-db/summary');
        if (!cancelled) setSummary(data);
      } catch (e: any) {
        if (!cancelled) setProblem(e);
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => { cancelled = true; };
  }, []);

  const aiUsageVariant: 'success' | 'warning' | 'error' =
    summary.ai_external_usage_pct >= 95 ? 'error' :
    summary.ai_external_usage_pct >= 80 ? 'warning' :
    'success';

  return (
    <>
      <PageHeader
        title={t('templates64Autodb.pageTitle')}
        description={t('templates64Autodb.pageDescription')}
        actions={<Badge variant="info">{t('templates64Autodb.badgePhase')}</Badge>}
      />

      <div className="px-6 lg:px-8 py-6 max-w-[1300px] mx-auto space-y-6">
        {problem && (
          <ErrorBanner
            problem={{
              ...problem,
              title:  t('templates64Autodb.errFallbackTitle'),
              detail: t('templates64Autodb.errFallbackDetail', { prefix: `${problem.title}${problem.detail ? ' — ' + problem.detail : ''}` }),
            }}
          />
        )}

        {/* KPI tiles */}
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
          <StatTile label={t('templates64Autodb.statSchemasActive')}    value={summary.schemas_active}       icon={Database}     tone="text-[var(--text-primary)]" />
          <StatTile label={t('templates64Autodb.statSuggestionsPending')}     value={summary.suggestions_pending}  icon={Sparkles}     tone="text-[var(--primary-gold-dark)]" />
          <StatTile label={t('templates64Autodb.statFormsGenerated')}          value={summary.forms_generated}      icon={FileText}     tone="text-[var(--state-info)]" />
          <StatTile label={t('templates64Autodb.statQualityAvg')}    value={summary.quality_avg}          icon={CheckCircle2} tone="text-[var(--state-success)]" suffix="%" />
        </div>

        {/* AI cost gauge + 3 module */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
          {MODULES.map((m) => <ModuleCard key={m.code} module={m} />)}
        </div>

        {/* AI usage banner */}
        <div className="bg-[var(--bg-card)] border border-[var(--border-color)] rounded-lg-custom p-5 shadow-soft-sm">
          <div className="flex items-center justify-between gap-3 mb-3">
            <div>
              <h3 className="font-serif text-base text-[var(--text-primary)]">{t('templates64Autodb.aiQuotaTitle')}</h3>
              <p className="text-xs text-[var(--text-secondary)] mt-1">
                {t('templates64Autodb.aiQuotaDescPrefix')}<code>consent_external=true</code>{t('templates64Autodb.aiQuotaDescSuffix')}
              </p>
            </div>
            <Badge variant={aiUsageVariant}>{summary.ai_external_usage_pct}%</Badge>
          </div>
          <div className="h-2 w-full rounded-sm-custom bg-[var(--border-color)]/40 overflow-hidden">
            <div
              className={cn(
                'h-full transition-all duration-500',
                aiUsageVariant === 'error' ? 'bg-[var(--state-error)]' :
                aiUsageVariant === 'warning' ? 'bg-[var(--state-warning)]' :
                'bg-[var(--primary-gold)]',
              )}
              style={{ width: `${Math.min(100, summary.ai_external_usage_pct)}%` }}
            />
          </div>
        </div>

        {/* Active schemas */}
        <div className="bg-[var(--bg-card)] border border-[var(--border-color)] rounded-lg-custom shadow-soft-sm overflow-hidden">
          <div className="px-5 py-4 border-b border-[var(--border-color)] flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Database className="w-4 h-4 text-[var(--primary-gold-dark)]" />
              <h3 className="font-serif text-base text-[var(--text-primary)]">{t('templates64Autodb.statSchemasActive')}</h3>
              <Badge variant="default">{summary.active_schemas.length}</Badge>
            </div>
            <a href="/p2/data" className="text-xs font-medium text-[var(--primary-gold-dark)] hover:underline">{t('templates64Autodb.viewAll')}</a>
          </div>
          <div className="overflow-auto">
            {loading ? (
              <div className="px-5 py-12 text-center text-[var(--text-secondary)]">
                <Loader2 className="w-5 h-5 animate-spin inline mr-2" /> {t('templates64Autodb.loading')}
              </div>
            ) : (
              <table className="w-full text-sm text-left">
                <thead className="bg-[var(--bg-app)] border-b border-[var(--border-color)] text-[11px] font-medium uppercase tracking-wider text-[var(--text-secondary)]">
                  <tr>
                    <th className="px-5 py-3">{t('templates64Autodb.thSchema')}</th>
                    <th className="px-5 py-3">{t('templates64Autodb.thDomain')}</th>
                    <th className="px-5 py-3">{t('templates64Autodb.thRows')}</th>
                    <th className="px-5 py-3">{t('templates64Autodb.thQuality')}</th>
                    <th className="px-5 py-3">{t('templates64Autodb.thForms')}</th>
                    <th className="px-5 py-3">{t('templates64Autodb.thUpdated')}</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-[var(--border-color)]/60">
                  {summary.active_schemas.map((s) => <SchemaRow key={s.id} schema={s} />)}
                </tbody>
              </table>
            )}
          </div>
        </div>

        <div className="flex items-start gap-2 p-3 rounded-md-custom bg-[var(--bg-app)]/40 border border-[var(--border-color)] text-xs text-[var(--text-secondary)]">
          <ShieldCheck className="w-4 h-4 text-[var(--primary-gold-dark)] shrink-0 mt-0.5" />
          <p>
            {t('templates64Autodb.footNote')}
          </p>
        </div>
      </div>
    </>
  );
}

// ============================================================================
// Sub-components
// ============================================================================

function StatTile({
  label, value, icon: Icon, tone, suffix,
}: { label: string; value: number; icon: any; tone: string; suffix?: string }) {
  return (
    <div className="bg-[var(--bg-card)] border border-[var(--border-color)] rounded-lg-custom p-5 shadow-soft-sm">
      <div className="flex items-center justify-between mb-2">
        <span className="text-[11px] uppercase tracking-wider font-medium text-[var(--text-secondary)]">{label}</span>
        <Icon className={cn('w-5 h-5', tone)} />
      </div>
      <p className="font-serif text-3xl text-[var(--text-primary)]">
        {value.toLocaleString('vi-VN')}{suffix}
      </p>
    </div>
  );
}

function ModuleCard({ module: m }: { module: any }) {
  const t = useT();
  const Icon = m.icon;
  return (
    <a
      href={m.href}
      className="group block bg-[var(--bg-card)] rounded-lg-custom border border-[var(--border-color)] hover:border-[var(--primary-gold)]/50 hover:shadow-soft-md transition-all p-5"
    >
      <div className="flex items-start justify-between gap-2 mb-3">
        <div className="w-10 h-10 rounded-md-custom bg-[var(--primary-gold)]/10 flex items-center justify-center">
          <Icon className="w-5 h-5 text-[var(--primary-gold-dark)]" />
        </div>
        <Badge variant="info">P2</Badge>
      </div>
      <h3 className="font-serif text-base text-[var(--text-primary)] group-hover:text-[var(--primary-gold-dark)] transition-colors">{t(m.titleKey)}</h3>
      <p className="text-xs text-[var(--text-secondary)] mt-1 leading-relaxed">{t(m.descKey)}</p>
      <div className="mt-3 inline-flex items-center text-xs font-medium text-[var(--primary-gold-dark)] group-hover:translate-x-0.5 transition-transform">
        {t('templates64Autodb.moduleEnter')} <ArrowRight className="w-3 h-3 ml-1" />
      </div>
    </a>
  );
}

function SchemaRow({ schema: s }: { schema: ActiveSchema }) {
  const qualityVariant: 'success' | 'info' | 'warning' | 'error' =
    s.quality_score >= 90 ? 'success' :
    s.quality_score >= 80 ? 'info' :
    s.quality_score >= 70 ? 'warning' : 'error';
  return (
    <tr className="hover:bg-[var(--bg-app)]/40 transition-colors">
      <td className="px-5 py-3">
        <div className="flex items-center gap-2">
          <span className="w-7 h-7 rounded-md-custom bg-[var(--primary-gold)]/10 flex items-center justify-center shrink-0">
            <Database className="w-3.5 h-3.5 text-[var(--primary-gold-dark)]" />
          </span>
          <span className="font-mono text-sm text-[var(--text-primary)]">{s.name}</span>
        </div>
      </td>
      <td className="px-5 py-3 text-xs text-[var(--text-secondary)]">{s.domain}</td>
      <td className="px-5 py-3 text-xs text-[var(--text-primary)]">{s.rows.toLocaleString('vi-VN')}</td>
      <td className="px-5 py-3"><Badge variant={qualityVariant}>{s.quality_score}%</Badge></td>
      <td className="px-5 py-3 text-xs text-[var(--text-primary)]">{s.forms_count}</td>
      <td className="px-5 py-3 text-xs text-[var(--text-secondary)]">
        {new Date(s.last_updated).toLocaleString('vi-VN', { day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit' })}
      </td>
    </tr>
  );
}
