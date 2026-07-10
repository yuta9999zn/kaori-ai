'use client';

// ============================================================================
// /p2/risks/export — Risks CSV Export (F-039 BE PR #126 + #140)
// ----------------------------------------------------------------------------
// Stripped down vs the original 58-risks-export.tsx template. Reasons:
//   * BE does NOT have a server-side export endpoint (no `POST /risks/export`,
//     no audit table). PDF + email + recent-exports table all assume that.
//   * Client-side CSV is enough for v0 — analyst opens the page, picks
//     filters + columns, downloads a UTF-8 BOM CSV that Vietnamese Excel
//     reads correctly. Same pattern as /pipeline/results CSV (Sprint 7 PR A).
//
// Wire:
//   GET /api/v1/enterprises/risks?limit=200&status=&severity=&category=
// then client formats CSV in-memory and triggers a Blob download.
// ============================================================================

import React, { useState } from 'react';
import {
  ArrowLeft, FileSpreadsheet, Download, Calendar, ShieldCheck, Loader2,
} from 'lucide-react';

import {
  Button, Badge, Checkbox, ErrorBanner, SuccessBanner, api,
  type ProblemDetails,
} from '@/components/p2/foundation';
import { PageHeader } from '@/components/p2/shell';
import { useT } from '@/lib/i18n/provider';
// ============================================================================
// Types
// ============================================================================

type Severity = 'low' | 'medium' | 'high' | 'critical';
type Status   = 'open' | 'mitigating' | 'closed';
type Category =
  | 'operational' | 'financial' | 'regulatory'
  | 'reputational' | 'strategic' | 'technical';

interface RiskRow {
  risk_id:             string;
  title:               string;
  description:         string | null;
  category:            Category;
  likelihood:          number;
  impact:              number;
  score:               number;
  severity:            Severity;
  status:              Status;
  mitigation_plan:     string | null;
  mitigation_progress: number;
  owner_user_id:       string | null;
  due_date:            string | null;
  source:              'manual' | 'auto';
  created_by_user:     string | null;
  created_at:          string;
  updated_at:          string;
}

interface ListResponse {
  data: RiskRow[];
  meta: { total: number; page: number; limit: number };
}

type TFunc = (key: string, params?: Record<string, string | number>) => string;

function getCategoryLabel(t: TFunc): Record<Category, string> {
  return {
    operational:  t('templatesF039RisksExport.categoryOperational'),
    financial:    t('templatesF039RisksExport.categoryFinancial'),
    regulatory:   t('templatesF039RisksExport.categoryRegulatory'),
    reputational: t('templatesF039RisksExport.categoryReputational'),
    strategic:    t('templatesF039RisksExport.categoryStrategic'),
    technical:    t('templatesF039RisksExport.categoryTechnical'),
  };
}

function getSeverityLabel(t: TFunc): Record<Severity, string> {
  return {
    low:      t('templatesF039RisksExport.severityLow'),
    medium:   t('templatesF039RisksExport.severityMedium'),
    high:     t('templatesF039RisksExport.severityHigh'),
    critical: t('templatesF039RisksExport.severityCritical'),
  };
}

function getStatusLabel(t: TFunc): Record<Status, string> {
  return {
    open:       t('templatesF039RisksExport.statusOpen'),
    mitigating: t('templatesF039RisksExport.statusMitigating'),
    closed:     t('templatesF039RisksExport.statusClosed'),
  };
}

// ============================================================================
// Columns — headers translated per locale, deterministic order
// ============================================================================

interface ColumnDef {
  key:    keyof RiskRow | 'category_label' | 'severity_label' | 'status_label';
  header: string;
  format: (r: RiskRow) => string;
}

function getColumns(t: TFunc): ColumnDef[] {
  const categoryLabel = getCategoryLabel(t);
  const severityLabel = getSeverityLabel(t);
  const statusLabel   = getStatusLabel(t);

  return [
    { key: 'risk_id',             header: t('templatesF039RisksExport.colRiskId'),         format: (r) => r.risk_id },
    { key: 'title',               header: t('templatesF039RisksExport.colTitle'),           format: (r) => r.title },
    { key: 'category_label',      header: t('templatesF039RisksExport.fieldCategory'),      format: (r) => categoryLabel[r.category] },
    { key: 'likelihood',          header: t('templatesF039RisksExport.colLikelihood'),      format: (r) => String(r.likelihood) },
    { key: 'impact',              header: t('templatesF039RisksExport.colImpact'),          format: (r) => String(r.impact) },
    { key: 'score',               header: t('templatesF039RisksExport.colScore'),           format: (r) => String(r.score) },
    { key: 'severity_label',      header: t('templatesF039RisksExport.fieldSeverity'),      format: (r) => severityLabel[r.severity] },
    { key: 'status_label',        header: t('templatesF039RisksExport.fieldStatus'),        format: (r) => statusLabel[r.status] },
    { key: 'mitigation_progress', header: t('templatesF039RisksExport.colProgress'),        format: (r) => String(r.mitigation_progress) },
    { key: 'mitigation_plan',     header: t('templatesF039RisksExport.colMitigationPlan'),  format: (r) => r.mitigation_plan ?? '' },
    { key: 'owner_user_id',       header: t('templatesF039RisksExport.colOwnerUuid'),       format: (r) => r.owner_user_id ?? '' },
    { key: 'due_date',            header: t('templatesF039RisksExport.colDueDate'),         format: (r) => r.due_date ?? '' },
    { key: 'description',         header: t('templatesF039RisksExport.colDescription'),     format: (r) => r.description ?? '' },
    { key: 'updated_at',          header: t('templatesF039RisksExport.colUpdatedAt'),       format: (r) => r.updated_at },
  ];
}

// ============================================================================
// Page
// ============================================================================

export default function RisksExportPage() {
  const t = useT();

  const COLUMNS = getColumns(t);
  const categoryLabel = getCategoryLabel(t);
  const severityLabel = getSeverityLabel(t);
  const statusLabel   = getStatusLabel(t);

  const [statusFilter,   setStatusFilter]   = useState<'all' | Status>('all');
  const [severityFilter, setSeverityFilter] = useState<'all' | Severity>('all');
  const [categoryFilter, setCategoryFilter] = useState<'all' | Category>('all');

  const [columns, setColumns] = useState<Record<string, boolean>>(
    Object.fromEntries(COLUMNS.map((c) => [c.key, true])),
  );

  const [submitting, setSubmitting] = useState(false);
  const [problem, setProblem]       = useState<ProblemDetails | null>(null);
  const [success, setSuccess]       = useState<string | null>(null);

  const selected = COLUMNS.filter((c) => columns[c.key]);

  async function onExport() {
    if (selected.length === 0) {
      setProblem({ title: t('templatesF039RisksExport.errPickColumn') });
      return;
    }
    setSubmitting(true);
    setProblem(null);
    setSuccess(null);
    try {
      const params = new URLSearchParams({ limit: '200' });
      if (statusFilter   !== 'all') params.set('status',   statusFilter);
      if (severityFilter !== 'all') params.set('severity', severityFilter);
      if (categoryFilter !== 'all') params.set('category', categoryFilter);

      const list = await api<ListResponse>(`/api/v1/enterprises/risks?${params}`);
      const rows = list.data ?? [];

      const csv = toCsv(rows, selected);
      // UTF-8 BOM so Vietnamese Excel decodes accents correctly.
      const blob = new Blob(['﻿' + csv], { type: 'text/csv;charset=utf-8' });
      const url  = URL.createObjectURL(blob);
      const a    = document.createElement('a');
      a.href     = url;
      a.download = `risks-${new Date().toISOString().slice(0, 10)}.csv`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);

      setSuccess(
        t('templatesF039RisksExport.successBase', { rows: rows.length, cols: selected.length })
        + (rows.length === 200 ? t('templatesF039RisksExport.successCapped') : ''),
      );
    } catch (e) {
      setProblem(e as ProblemDetails);
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <>
      <PageHeader
        title={t('templatesF039RisksExport.title')}
        description={t('templatesF039RisksExport.description')}
        actions={
          <>
            <Badge variant="info">F-039</Badge>
            <a href="/p2/risks">
              <Button variant="tertiary" size="md"><ArrowLeft className="w-4 h-4 mr-2" /> {t('templatesF039RisksExport.backToList')}</Button>
            </a>
          </>
        }
      />

      <div className="px-6 lg:px-8 py-6 max-w-[1100px] mx-auto space-y-6">
        {problem && <ErrorBanner problem={problem} />}
        {success && <SuccessBanner message={success} />}

        <Section title={t('templatesF039RisksExport.sectionScope')} icon={Calendar}>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
            <SelectField
              label={t('templatesF039RisksExport.fieldStatus')} value={statusFilter} onChange={setStatusFilter}
              options={[
                { value: 'all',        label: t('templatesF039RisksExport.all') },
                { value: 'open',       label: statusLabel.open },
                { value: 'mitigating', label: statusLabel.mitigating },
                { value: 'closed',     label: statusLabel.closed },
              ]}
            />
            <SelectField
              label={t('templatesF039RisksExport.fieldSeverity')} value={severityFilter} onChange={setSeverityFilter}
              options={[
                { value: 'all',      label: t('templatesF039RisksExport.all') },
                { value: 'critical', label: severityLabel.critical },
                { value: 'high',     label: severityLabel.high },
                { value: 'medium',   label: severityLabel.medium },
                { value: 'low',      label: severityLabel.low },
              ]}
            />
            <SelectField
              label={t('templatesF039RisksExport.fieldCategory')} value={categoryFilter} onChange={setCategoryFilter}
              options={[
                { value: 'all', label: t('templatesF039RisksExport.all') },
                { value: 'operational',  label: categoryLabel.operational },
                { value: 'financial',    label: categoryLabel.financial },
                { value: 'regulatory',   label: categoryLabel.regulatory },
                { value: 'reputational', label: categoryLabel.reputational },
                { value: 'strategic',    label: categoryLabel.strategic },
                { value: 'technical',    label: categoryLabel.technical },
              ]}
            />
          </div>
        </Section>

        <Section title={t('templatesF039RisksExport.sectionColumns')} icon={FileSpreadsheet}>
          <div className="grid grid-cols-2 md:grid-cols-3 gap-2">
            {COLUMNS.map((c) => (
              <Checkbox
                key={c.key}
                checked={!!columns[c.key]}
                onChange={(e) => setColumns((prev) => ({ ...prev, [c.key]: e.target.checked }))}
                label={<span className="text-sm">{c.header}</span>}
              />
            ))}
          </div>
          <p className="text-xs text-[var(--text-secondary)] mt-3">
            {t('templatesF039RisksExport.columnsSelected', { selected: selected.length, total: COLUMNS.length })}
          </p>
        </Section>

        <div className="sticky bottom-0 bg-[var(--bg-card)]/95 backdrop-blur-sm border-t border-[var(--border-color)] -mx-6 lg:-mx-8 px-6 lg:px-8 py-4 flex items-center justify-between">
          <p className="text-xs text-[var(--text-secondary)] flex items-center gap-2">
            <ShieldCheck className="w-4 h-4 text-[var(--primary-gold-dark)]" />
            {t('templatesF039RisksExport.footerNote')}
          </p>
          <Button
            variant="primary" size="md" onClick={onExport}
            disabled={submitting || selected.length === 0}
            isLoading={submitting}
          >
            {submitting ? (
              <><Loader2 className="w-4 h-4 mr-2 animate-spin" /> {t('templatesF039RisksExport.creating')}</>
            ) : (
              <><Download className="w-4 h-4 mr-2" /> {t('templatesF039RisksExport.downloadCsv')}</>
            )}
          </Button>
        </div>
      </div>
    </>
  );
}

// ============================================================================
// CSV builder
// ============================================================================

function toCsv(rows: RiskRow[], columns: ColumnDef[]): string {
  const header = columns.map((c) => quote(c.header)).join(',');
  const lines  = rows.map((r) =>
    columns.map((c) => quote(c.format(r))).join(','),
  );
  return [header, ...lines].join('\r\n');
}

/**
 * RFC 4180-ish quoting — wrap fields with commas/quotes/newlines in double
 * quotes, escape internal quotes by doubling. Excel-friendly.
 */
function quote(value: string): string {
  if (value === '' || value == null) return '';
  const v = String(value);
  if (/[",\r\n]/.test(v)) {
    return '"' + v.replace(/"/g, '""') + '"';
  }
  return v;
}

// ============================================================================
// Sub-components (local — not worth a shared file)
// ============================================================================

function Section({
  title, icon: Icon, children,
}: {
  title: string;
  icon: React.ComponentType<{ className?: string }>;
  children: React.ReactNode;
}) {
  return (
    <section className="bg-[var(--bg-card)] border border-[var(--border-color)] rounded-lg-custom p-5 lg:p-6 shadow-soft-sm">
      <div className="flex items-center gap-2 mb-4 pb-3 border-b border-[var(--border-color)]/60">
        <Icon className="w-4 h-4 text-[var(--primary-gold-dark)]" />
        <h3 className="font-serif text-base text-[var(--text-primary)]">{title}</h3>
      </div>
      {children}
    </section>
  );
}

function SelectField<T extends string>({
  label, value, onChange, options,
}: {
  label: string;
  value: T;
  onChange: (v: T) => void;
  options: { value: T; label: string }[];
}) {
  return (
    <div className="space-y-2">
      <label className="text-sm font-medium text-[var(--text-primary)]">{label}</label>
      <select
        value={value}
        onChange={(e) => onChange(e.target.value as T)}
        className="w-full h-10 px-3 bg-white border border-[var(--border-color)] rounded-md-custom text-sm focus:outline-none focus:ring-2 focus:ring-[var(--primary-gold)]/30 focus:border-[var(--primary-gold)]"
      >
        {options.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
      </select>
    </div>
  );
}
