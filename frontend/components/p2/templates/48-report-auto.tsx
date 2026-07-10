'use client';

// ============================================================================
// 48. /p2/reports/auto — Auto Report Configuration (F-038 🔵 Phase 2)
// ----------------------------------------------------------------------------
// Cấu hình báo cáo tự động: chọn Gold dataset, mục tiêu báo cáo, lịch chạy,
// người nhận → Kaori AI sinh narrative + biểu đồ qua llm_router (K-3 + K-4
// + K-5).
//
// Wires `POST /api/v1/reports/generate` (PR #113) using the built-in
// monthly_summary template. Goal/cadence/dataset are packed into `params{}`
// for the template's system prompt (Issue #3 output_schema enforces the
// kpi_overview/trends/top_risks/recommendations shape). Single recipient v0
// — fan-out distribution is a follow-up PR.
//
// Gold dataset picker still calls `/api/v1/data/gold/datasets` which 404s in
// dev — it falls back to MOCK_DATASETS. That endpoint belongs to a separate
// data-exploration feature surface (Phase 2).
// ============================================================================

import React, { useEffect, useMemo, useState } from 'react';
import {
  Sparkles, Activity, TrendingUp, LayoutGrid, Crown, Users, Clock,
  CalendarCheck, Mail, Save, Play, ArrowLeft, ShieldCheck, Loader2,
  CheckCircle2, AlertTriangle,
} from 'lucide-react';

import {
  Button, Badge, Input, ErrorBanner, SuccessBanner, api, cn,
  type ProblemDetails,
} from '@/components/p2/foundation';
import { PageHeader } from '@/components/p2/shell';
import { useT } from '@/lib/i18n/provider';
// ============================================================================
// Types
// ============================================================================

interface GoldDataset {
  id:     string;
  name:   string;
  domain: string;
  rows:   number;
}

// Stable id of the built-in monthly_summary template seeded by migration 027.
const BUILT_IN_MONTHLY_SUMMARY_ID = '00000000-0000-0000-0000-000000000001';

type ReportGoal = 'performance' | 'trend' | 'segment' | 'executive';

interface GoalMeta {
  code:        ReportGoal;
  label:       string;
  description: string;
  icon:        any;
}

function buildGoals(t: (key: string, params?: Record<string, any>) => string): GoalMeta[] {
  return [
    { code: 'performance', label: t('templates48ReportAuto.goalPerformanceLabel'), description: t('templates48ReportAuto.goalPerformanceDesc'), icon: Activity },
    { code: 'trend',       label: t('templates48ReportAuto.goalTrendLabel'),       description: t('templates48ReportAuto.goalTrendDesc'),       icon: TrendingUp },
    { code: 'segment',     label: t('templates48ReportAuto.goalSegmentLabel'),     description: t('templates48ReportAuto.goalSegmentDesc'),     icon: LayoutGrid },
    { code: 'executive',   label: t('templates48ReportAuto.goalExecutiveLabel'),   description: t('templates48ReportAuto.goalExecutiveDesc'),   icon: Crown },
  ];
}

type Cadence = 'daily' | 'weekly' | 'monthly';

interface CadenceMeta {
  code:    Cadence;
  label:   string;
  cron:    string;
  helper:  string;
}

function buildCadences(t: (key: string, params?: Record<string, any>) => string): CadenceMeta[] {
  return [
    { code: 'daily',   label: t('templates48ReportAuto.cadenceDailyLabel'),   cron: '0 7 * * *',  helper: t('templates48ReportAuto.cadenceDailyHelper') },
    { code: 'weekly',  label: t('templates48ReportAuto.cadenceWeeklyLabel'),  cron: '0 7 * * 1',  helper: t('templates48ReportAuto.cadenceWeeklyHelper') },
    { code: 'monthly', label: t('templates48ReportAuto.cadenceMonthlyLabel'), cron: '0 7 1 * *',  helper: t('templates48ReportAuto.cadenceMonthlyHelper') },
  ];
}

function buildMockDatasets(t: (key: string, params?: Record<string, any>) => string): GoldDataset[] {
  return [
    { id: 'ds_revenue',  name: 'monthly_revenue_gold',       domain: t('templates48ReportAuto.domainFinance'),   rows: 124_530 },
    { id: 'ds_customer', name: 'customer_behavior_metrics',  domain: t('templates48ReportAuto.domainProduct'),   rows:  68_242 },
    { id: 'ds_market',   name: 'marketing_roi_performance',  domain: t('templates48ReportAuto.domainMarketing'), rows:  41_088 },
    { id: 'ds_ops',      name: 'operations_kpi_daily',       domain: t('templates48ReportAuto.domainOps'),       rows: 312_104 },
  ];
}

// ============================================================================
// Page
// ============================================================================

export default function ReportAutoPage() {
  const t = useT();
  const [datasets, setDatasets] = useState<GoldDataset[]>([]);
  const [loading,  setLoading]  = useState(true);
  const [problem,  setProblem]  = useState<ProblemDetails | null>(null);
  const [success,  setSuccess]  = useState<string | null>(null);

  const GOALS = useMemo(() => buildGoals(t), [t]);
  const CADENCES = useMemo(() => buildCadences(t), [t]);
  const MOCK_DATASETS = useMemo(() => buildMockDatasets(t), [t]);

  // Form state
  const [name,      setName]      = useState(t('templates48ReportAuto.defaultReportName'));
  const [datasetId, setDatasetId] = useState<string>('');
  const [goal,      setGoal]      = useState<ReportGoal>('performance');
  const [cadence,   setCadence]   = useState<Cadence>('weekly');
  const [recipients, setRecipients] = useState('manager@acme.vn');
  const [allowExternal, setAllowExternal] = useState(false);
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const data = await api<{ items: GoldDataset[] }>('/api/v1/data/gold/datasets');
        if (!cancelled) {
          setDatasets(data.items ?? []);
          if ((data.items ?? []).length > 0) setDatasetId(data.items[0].id);
        }
      } catch (e: any) {
        if (!cancelled) {
          setProblem(e);
          setDatasets(MOCK_DATASETS);
          setDatasetId(MOCK_DATASETS[0].id);
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => { cancelled = true; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const cadenceMeta = useMemo(() => CADENCES.find((c) => c.code === cadence)!, [cadence, CADENCES]);
  const recipientList = useMemo(
    () => recipients.split(/[,\n]/).map((s) => s.trim()).filter(Boolean),
    [recipients],
  );
  const formValid = name.trim().length >= 3 && datasetId !== '' && recipientList.length > 0;

  async function onSubmit(action: 'save' | 'run') {
    setSubmitting(true);
    setProblem(null);
    setSuccess(null);
    try {
      // BE accepts a single owner_email per report (v0). Use the first recipient
      // and pack the rest into params for the template prompt; fan-out is a
      // follow-up PR per the F-038 spec (notification dispatcher → multi-channel).
      const [primaryRecipient, ...additionalRecipients] = recipientList;
      const resp = await api<{ report_id: string; status: string }>(
        '/api/v1/reports/generate',
        {
          method: 'POST',
          body: JSON.stringify({
            template_id:  BUILT_IN_MONTHLY_SUMMARY_ID,
            title:        name,
            owner_email:  primaryRecipient,
            params: {
              goal,
              cadence,
              schedule_cron:           cadenceMeta.cron,
              dataset_id:              datasetId,
              consent_external:        allowExternal,
              additional_recipients:   additionalRecipients,
              triggered_via:           action === 'run' ? 'auto_form_run_now' : 'auto_form_save',
            },
          }),
        },
      );
      // 'save' acts identically to 'run' under v0 — no scheduler service exists
      // yet, so every submission queues one report immediately. Phase 2 follow-up
      // wires schedule_cron to a runner.
      setSuccess(
        additionalRecipients.length > 0
          ? t('templates48ReportAuto.successMsgWithFanout', {
              reportId: resp.report_id,
              email: primaryRecipient,
              count: additionalRecipients.length,
            })
          : t('templates48ReportAuto.successMsg', {
              reportId: resp.report_id,
              email: primaryRecipient,
            }),
      );
    } catch (e: any) {
      setProblem(e);
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <>
      <PageHeader
        title={t('templates48ReportAuto.pageTitle')}
        description={t('templates48ReportAuto.pageDescription')}
        actions={
          <>
            <Badge variant="info">Phase 2 · F-038</Badge>
            <a href="/p2/reports">
              <Button variant="tertiary" size="md">
                <ArrowLeft className="w-4 h-4 mr-2" /> {t('templates48ReportAuto.backToList')}
              </Button>
            </a>
          </>
        }
      />

      <div className="px-6 lg:px-8 py-6 max-w-[1100px] mx-auto space-y-6">
        {problem && (
          <ErrorBanner
            problem={{
              ...problem,
              title:  problem.status && problem.status >= 500 ? t('templates48ReportAuto.serverErrorTitle') : problem.title,
              detail: `${problem.detail ?? ''} ${t('templates48ReportAuto.errBannerDetailSuffix')}`.trim(),
            }}
          />
        )}
        {success && <SuccessBanner message={success} />}

        {/* Section 1 — Tên báo cáo + nguồn */}
        <Section
          step={1}
          title={t('templates48ReportAuto.section1Title')}
          description={t('templates48ReportAuto.section1Description')}
        >
          <Input
            label={t('templates48ReportAuto.reportNameLabel')}
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder={t('templates48ReportAuto.reportNamePlaceholder')}
            helperText={t('templates48ReportAuto.reportNameHelper')}
            error={name.length > 0 && name.length < 3}
          />
          <div className="mt-4 space-y-2">
            <label className="text-sm font-medium text-[var(--text-primary)]">{t('templates48ReportAuto.goldDatasetLabel')}</label>
            {loading ? (
              <div className="flex items-center text-sm text-[var(--text-secondary)] py-3">
                <Loader2 className="w-4 h-4 mr-2 animate-spin" /> {t('templates48ReportAuto.loadingDatasets')}
              </div>
            ) : (
              <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
                {datasets.map((d) => (
                  <DatasetCard
                    key={d.id}
                    dataset={d}
                    selected={datasetId === d.id}
                    onSelect={() => setDatasetId(d.id)}
                  />
                ))}
              </div>
            )}
          </div>
        </Section>

        {/* Section 2 — Mục tiêu */}
        <Section step={2} title={t('templates48ReportAuto.section2Title')} description={t('templates48ReportAuto.section2Description')}>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
            {GOALS.map((g) => (
              <GoalCard key={g.code} goal={g} selected={goal === g.code} onSelect={() => setGoal(g.code)} />
            ))}
          </div>
        </Section>

        {/* Section 3 — Lịch chạy */}
        <Section step={3} title={t('templates48ReportAuto.section3Title')} description={t('templates48ReportAuto.section3Description')}>
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
            {CADENCES.map((c) => (
              <button
                key={c.code}
                onClick={() => setCadence(c.code)}
                className={cn(
                  'text-left p-4 rounded-md-custom border transition-all shadow-soft-sm',
                  cadence === c.code
                    ? 'border-[var(--primary-gold)] bg-[var(--primary-gold)]/10'
                    : 'border-[var(--border-color)] bg-[var(--bg-card)] hover:border-[var(--primary-gold)]/40',
                )}
              >
                <div className="flex items-center gap-2 mb-1">
                  <Clock className="w-4 h-4 text-[var(--primary-gold-dark)]" />
                  <span className="font-medium text-sm text-[var(--text-primary)]">{c.label}</span>
                </div>
                <p className="text-xs text-[var(--text-secondary)]">{c.helper}</p>
                <p className="text-[11px] text-[var(--text-secondary)]/80 font-mono mt-2">{c.cron}</p>
              </button>
            ))}
          </div>
        </Section>

        {/* Section 4 — Người nhận */}
        <Section step={4} title={t('templates48ReportAuto.section4Title')} description={t('templates48ReportAuto.section4Description')}>
          <div className="space-y-2">
            <label className="text-sm font-medium text-[var(--text-primary)]">{t('templates48ReportAuto.emailListLabel')}</label>
            <textarea
              value={recipients}
              onChange={(e) => setRecipients(e.target.value)}
              rows={3}
              placeholder="manager@acme.vn, ops@acme.vn"
              className="w-full px-3 py-2 bg-white border border-[var(--border-color)] rounded-md-custom text-sm text-[var(--text-primary)] placeholder:text-[var(--text-secondary)]/60 focus:outline-none focus:ring-2 focus:ring-[var(--primary-gold)]/30 focus:border-[var(--primary-gold)] transition-all resize-none"
            />
            {recipientList.length > 0 && (
              <p className="text-xs text-[var(--text-secondary)]">
                <Mail className="w-3.5 h-3.5 inline mr-1" />
                {t('templates48ReportAuto.recipientSummary', { count: recipientList.length, list: recipientList.join(', ') })}
              </p>
            )}
          </div>
        </Section>

        {/* Section 5 — Consent */}
        <Section
          step={5}
          title={t('templates48ReportAuto.section5Title')}
          description={t('templates48ReportAuto.section5Description')}
        >
          <label className="flex items-start gap-3 p-3 rounded-md-custom border border-[var(--border-color)] bg-[var(--bg-card)] cursor-pointer hover:border-[var(--primary-gold)]/40 transition-colors">
            <input
              type="checkbox"
              checked={allowExternal}
              onChange={(e) => setAllowExternal(e.target.checked)}
              className="mt-0.5 w-4 h-4 accent-[var(--primary-gold)]"
            />
            <div>
              <p className="text-sm font-medium text-[var(--text-primary)]">
                {t('templates48ReportAuto.consentCheckboxLabel')}
              </p>
              <p className="text-xs text-[var(--text-secondary)] mt-1 leading-relaxed">
                {t('templates48ReportAuto.consentDetailPart1')} <code>consent_external=true</code>. {t('templates48ReportAuto.consentDetailPart2')}
                {' '}<span className="font-mono">&lt;EMAIL_1&gt;</span> {t('templates48ReportAuto.consentDetailPart3')}
                {' '}<span className="font-mono">llm_router.py</span> {t('templates48ReportAuto.consentDetailPart4')}
              </p>
            </div>
          </label>
        </Section>

        {/* Action footer */}
        <div className="sticky bottom-0 bg-[var(--bg-card)]/95 backdrop-blur-sm border-t border-[var(--border-color)] -mx-6 lg:-mx-8 px-6 lg:px-8 py-4 flex items-center justify-between">
          <div className="flex items-center gap-2 text-xs text-[var(--text-secondary)]">
            <ShieldCheck className="w-4 h-4 text-[var(--primary-gold-dark)]" />
            {t('templates48ReportAuto.idempotencyNote')}
          </div>
          <div className="flex items-center gap-2">
            <Button
              variant="secondary"
              size="md"
              onClick={() => onSubmit('save')}
              disabled={!formValid || submitting}
              isLoading={submitting}
            >
              <Save className="w-4 h-4 mr-2" /> {t('templates48ReportAuto.saveConfigButton')}
            </Button>
            <Button
              variant="primary"
              size="md"
              onClick={() => onSubmit('run')}
              disabled={!formValid || submitting}
              isLoading={submitting}
            >
              <Play className="w-4 h-4 mr-2" /> {t('templates48ReportAuto.saveRunNowButton')}
            </Button>
          </div>
        </div>

        {/* Recent runs preview */}
        <RecentRunsPreview />
      </div>
    </>
  );
}

// ============================================================================
// Sub-components
// ============================================================================

function Section({
  step, title, description, children,
}: { step: number; title: string; description: string; children: React.ReactNode }) {
  return (
    <section className="bg-[var(--bg-card)] border border-[var(--border-color)] rounded-lg-custom p-5 lg:p-6 shadow-soft-sm">
      <div className="flex items-start gap-3 mb-4">
        <div className="w-7 h-7 rounded-full bg-[var(--primary-gold)]/15 border border-[var(--primary-gold)]/30 flex items-center justify-center shrink-0">
          <span className="text-xs font-semibold text-[var(--primary-gold-dark)]">{step}</span>
        </div>
        <div>
          <h3 className="font-serif text-lg text-[var(--text-primary)]">{title}</h3>
          <p className="text-xs text-[var(--text-secondary)] mt-0.5 leading-relaxed">{description}</p>
        </div>
      </div>
      <div>{children}</div>
    </section>
  );
}

function DatasetCard({
  dataset, selected, onSelect,
}: { dataset: GoldDataset; selected: boolean; onSelect: () => void }) {
  const t = useT();
  return (
    <button
      onClick={onSelect}
      className={cn(
        'text-left p-3 rounded-md-custom border transition-all',
        selected
          ? 'border-[var(--primary-gold)] bg-[var(--primary-gold)]/10'
          : 'border-[var(--border-color)] bg-[var(--bg-card)] hover:border-[var(--primary-gold)]/40',
      )}
    >
      <div className="flex items-start justify-between gap-2">
        <div>
          <p className="font-mono text-sm text-[var(--text-primary)]">{dataset.name}</p>
          <p className="text-xs text-[var(--text-secondary)] mt-1">
            {t('templates48ReportAuto.datasetRowsSummary', { domain: dataset.domain, rows: dataset.rows.toLocaleString('vi-VN') })}
          </p>
        </div>
        {selected && <CheckCircle2 className="w-4 h-4 text-[var(--primary-gold-dark)] shrink-0" />}
      </div>
    </button>
  );
}

function GoalCard({
  goal, selected, onSelect,
}: { goal: GoalMeta; selected: boolean; onSelect: () => void }) {
  const Icon = goal.icon;
  return (
    <button
      onClick={onSelect}
      className={cn(
        'text-left p-4 rounded-md-custom border transition-all shadow-soft-sm',
        selected
          ? 'border-[var(--primary-gold)] bg-[var(--primary-gold)]/10'
          : 'border-[var(--border-color)] bg-[var(--bg-card)] hover:border-[var(--primary-gold)]/40',
      )}
    >
      <div className="w-9 h-9 rounded-md-custom bg-[var(--primary-gold)]/15 flex items-center justify-center mb-3">
        <Icon className="w-4 h-4 text-[var(--primary-gold-dark)]" />
      </div>
      <p className="font-medium text-sm text-[var(--text-primary)]">{goal.label}</p>
      <p className="text-xs text-[var(--text-secondary)] mt-1 leading-relaxed">{goal.description}</p>
    </button>
  );
}

function RecentRunsPreview() {
  const t = useT();
  const RUNS = [
    { id: 'run_99', cadence: 'weekly', status: 'success', when: '2026-04-29 07:00', delivered: 4 },
    { id: 'run_98', cadence: 'weekly', status: 'success', when: '2026-04-22 07:00', delivered: 4 },
    { id: 'run_97', cadence: 'weekly', status: 'failed',  when: '2026-04-15 07:00', delivered: 0 },
  ];
  return (
    <section className="bg-[var(--bg-card)] border border-[var(--border-color)] rounded-lg-custom p-5 shadow-soft-sm">
      <div className="flex items-center gap-2 mb-3">
        <CalendarCheck className="w-4 h-4 text-[var(--primary-gold-dark)]" />
        <h3 className="font-serif text-base text-[var(--text-primary)]">{t('templates48ReportAuto.recentRunsTitle')}</h3>
        <Badge variant="default">{t('templates48ReportAuto.recentRunsCount', { count: RUNS.length })}</Badge>
      </div>
      <div className="divide-y divide-[var(--border-color)]/60">
        {RUNS.map((r) => (
          <div key={r.id} className="py-3 flex items-center justify-between gap-3">
            <div className="flex items-center gap-3 min-w-0">
              {r.status === 'success' ? (
                <CheckCircle2 className="w-4 h-4 text-[var(--state-success)] shrink-0" />
              ) : (
                <AlertTriangle className="w-4 h-4 text-[var(--state-error)] shrink-0" />
              )}
              <div className="min-w-0">
                <p className="text-sm text-[var(--text-primary)]">{r.when}</p>
                <p className="text-xs text-[var(--text-secondary)] mt-0.5">
                  {r.cadence === 'weekly' ? t('templates48ReportAuto.cadenceWeeklyLabel') : r.cadence}
                  {r.status === 'success' && ` · ${t('templates48ReportAuto.deliveredToCount', { count: r.delivered })}`}
                </p>
              </div>
            </div>
            <Badge variant={r.status === 'success' ? 'success' : 'error'}>
              {r.status === 'success' ? t('templates48ReportAuto.statusSuccess') : t('templates48ReportAuto.statusFailed')}
            </Badge>
          </div>
        ))}
      </div>
      <p className="text-xs text-[var(--text-secondary)] mt-3">
        <Sparkles className="w-3.5 h-3.5 inline mr-1 text-[var(--primary-gold-dark)]" />
        {t('templates48ReportAuto.auditLogNotePart1')} <span className="font-mono">decision_audit_log</span> {t('templates48ReportAuto.auditLogNotePart2')}
      </p>
    </section>
  );
}
