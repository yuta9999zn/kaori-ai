'use client';

import { useState } from 'react';
import { useMutation } from '@tanstack/react-query';
import { Download, FileText, AlertCircle, CheckCircle2 } from 'lucide-react';

import { platformBillingApi, type BillingStatus } from '@/lib/api/platform';
import {
  Button, Input, Label, ErrorBanner, type ProblemDetails,
} from '@/components/platform/foundation';
import { useT } from '@/lib/i18n/provider';

const PLAN_OPTIONS = ['', 'PILOT', 'ENT_BASIC', 'ENT_MID', 'ENT_MAX', 'ENT_ROI'];
const STATUS_OPTIONS: ('' | BillingStatus)[] = ['', 'normal', 'warn', 'critical', 'overage'];
const STATUS_LABEL_KEY: Record<BillingStatus, string> = {
  normal:   'exportPage.statusNormal',
  warn:     'exportPage.statusWarn',
  critical: 'exportPage.statusCritical',
  overage:  'exportPage.statusOverage',
};

function currentMonthYM() {
  const d = new Date();
  return `${d.getUTCFullYear()}-${String(d.getUTCMonth() + 1).padStart(2, '0')}`;
}

export default function PlatformBillingExportPage() {
  const t = useT();
  const [month,  setMonth]  = useState<string>(currentMonthYM());
  const [plan,   setPlan]   = useState<string>('');
  const [status, setStatus] = useState<'' | BillingStatus>('');
  const [lastDownload, setLastDownload] = useState<string | null>(null);

  const exportMut = useMutation({
    mutationFn: () => platformBillingApi.exportCsv({
      month: month || undefined,
      plan:  plan  || undefined,
      status: status || undefined,
    }),
    onSuccess: ({ blob, filename }) => {
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = filename;
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(url);
      setLastDownload(filename);
    },
  });

  const monthValid = !month || /^\d{4}-\d{2}$/.test(month);
  const exportError = exportMut.error ? (exportMut.error as unknown as ProblemDetails) : null;

  return (
    <div className="max-w-2xl space-y-5">
      <section className="rounded-md-custom border border-[var(--border-color)] bg-[var(--bg-card)] shadow-soft-sm p-6 space-y-5">
        <div className="flex items-start gap-3">
          <div className="w-10 h-10 rounded-md-custom bg-[var(--primary-gold)]/15 flex items-center justify-center shrink-0">
            <FileText className="w-5 h-5 text-[var(--primary-gold-dark)]" strokeWidth={1.5} />
          </div>
          <div>
            <h2 className="font-medium text-[var(--text-primary)]">{t('exportPage.title')}</h2>
            <p className="text-sm text-[var(--text-secondary)]">
              {t('exportPage.description')}
            </p>
          </div>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <div className="space-y-1.5">
            <Label htmlFor="export-month">{t('exportPage.labelMonth')}</Label>
            <Input
              id="export-month"
              placeholder="YYYY-MM"
              pattern="\d{4}-\d{2}"
              value={month}
              onChange={(e) => setMonth(e.target.value)}
            />
            <p className="text-xs text-[var(--text-secondary)]">{t('exportPage.hintMonthEmpty')}</p>
          </div>

          <div className="space-y-1.5">
            <Label htmlFor="export-plan">{t('exportPage.labelPlan')}</Label>
            <select
              id="export-plan"
              value={plan}
              onChange={(e) => setPlan(e.target.value)}
              className="h-10 w-full rounded-md-custom border border-[var(--border-color)] bg-[var(--bg-card)] px-3 text-sm text-[var(--text-primary)] focus:outline-none focus:ring-2 focus:ring-[var(--primary-gold)]/30"
            >
              {PLAN_OPTIONS.map((p) => (
                <option key={p || 'all'} value={p}>{p || t('exportPage.allPlans')}</option>
              ))}
            </select>
          </div>

          <div className="space-y-1.5">
            <Label htmlFor="export-status">{t('exportPage.labelStatus')}</Label>
            <select
              id="export-status"
              value={status}
              onChange={(e) => setStatus(e.target.value as '' | BillingStatus)}
              className="h-10 w-full rounded-md-custom border border-[var(--border-color)] bg-[var(--bg-card)] px-3 text-sm text-[var(--text-primary)] focus:outline-none focus:ring-2 focus:ring-[var(--primary-gold)]/30"
            >
              {STATUS_OPTIONS.map((s) => (
                <option key={s || 'all'} value={s}>{s ? t(STATUS_LABEL_KEY[s]) : t('exportPage.allStatuses')}</option>
              ))}
            </select>
          </div>
        </div>

        {!monthValid && (
          <div className="flex items-start gap-2 text-xs text-[#9E814D] bg-[var(--state-warning)]/12 border border-[var(--state-warning)]/30 rounded-md-custom px-3 py-2">
            <AlertCircle className="w-4 h-4 shrink-0 mt-0.5" />
            {t('exportPage.errFormatPrefix')} <code className="font-mono">YYYY-MM</code>{t('exportPage.errFormatExample')}{' '}
            <code className="font-mono">2026-04</code>.
          </div>
        )}

        {exportError && <ErrorBanner problem={exportError} />}

        {lastDownload && !exportMut.isPending && !exportMut.isError && (
          <div className="flex items-start gap-2 text-xs text-[#5C856A] bg-[var(--state-success)]/12 border border-[var(--state-success)]/30 rounded-md-custom px-3 py-2">
            <CheckCircle2 className="w-4 h-4 shrink-0 mt-0.5" />
            {t('exportPage.downloadedPrefix')} <code className="font-mono">{lastDownload}</code>.
          </div>
        )}

        <div className="pt-2">
          <Button
            isLoading={exportMut.isPending}
            disabled={!monthValid}
            onClick={() => exportMut.mutate()}
          >
            <Download className="w-4 h-4 mr-1.5" />
            {t('exportPage.downloadCsv')}
          </Button>
        </div>
      </section>

      <section className="rounded-md-custom border border-[var(--border-color)] bg-[var(--bg-card)] shadow-soft-sm p-6 space-y-2 text-sm text-[var(--text-secondary)]">
        <p className="font-medium text-[var(--text-primary)]">{t('exportPage.columnsInFile')}</p>
        <code className="block text-xs font-mono bg-[var(--bg-app)]/60 rounded-md-custom px-3 py-2 overflow-x-auto">
          enterprise_id, enterprise_name, plan_code, billing_month, unique_customers,
          quota, usage_pct, overage_units, base_amount_vnd, overage_amount_vnd,
          total_amount_vnd, status
        </code>
        <p className="text-xs">
          {t('exportPage.maxRowsPrefix')} <code className="font-mono">X-Truncated</code>{' '}
          {t('exportPage.maxRowsMid')} <code className="font-mono">true</code>.
        </p>
      </section>
    </div>
  );
}
