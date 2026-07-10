// @ts-nocheck — template import; tighten types when wiring to real API
'use client';

// ============================================================================
// 33. /p2/subscription — Subscription & Quota (F-030)
// ----------------------------------------------------------------------------
// 3-tab page (PR #75 / Sprint 3):
//   1. Hạn mức (Quota)        — current month usage + alert banner 80%/95%
//   2. Gói cước (Plan)         — current plan VND + features
//   3. Lịch sử (History)      — last 12 months billing rows
//
// CRITICAL invariants (CLAUDE.md):
//   K-9   — money columns are NUMERIC(14,4); display VND with dot grouping
//   K-11  — billing unit = COUNT(DISTINCT customer_external_id) per month
//   §10   — pricing PILOT 1M / BASIC 2M / MID 5M / MAX 8M / ROI 8M+1.5%
//
// Endpoints:
//   GET /api/v1/subscription/current   → { plan, started_at, renews_at }
//   GET /api/v1/subscription/quota     → { current_unique_customers, plan_limit_unique_customers, alert_level }
//   GET /api/v1/subscription/history?limit=12
//
// Quota alert level:
//   - none      < 80%
//   - warning   80% — 94% (email already sent if F-NEW1 tone-aware)
//   - critical  ≥ 95% (email + suggest upgrade banner)
// ============================================================================

import React, { useState, useEffect } from 'react';
import {
  CreditCard, AlertTriangle, TrendingUp, ArrowUpRight, ShieldCheck,
  CheckCircle2, Sparkles, Calendar, Download, RefreshCw, Lock,
  History, Users, Activity,
} from 'lucide-react';

import {
  Button, Badge, ErrorBanner, QuotaBar, cn,
  api, formatVND, formatVNDLong, PRICING,
  type ProblemDetails,
} from '@/components/p2/foundation';
import { PageHeader } from '@/components/p2/shell';
import { useT } from '@/lib/i18n/provider';
type PlanCode = 'PILOT' | 'BASIC' | 'MID' | 'MAX' | 'ROI';
type AlertLvl = 'none' | 'warning' | 'critical';

interface CurrentSubscription {
  plan:        PlanCode;
  plan_name:   string;
  monthly_vnd: number;
  started_at:  string;
  renews_at:   string;
  cancellable: boolean;
  is_roi:      boolean;
  roi_revenue_saved_pct?: number;
}

interface QuotaSnapshot {
  /** K-11: COUNT(DISTINCT customer_external_id) per current month */
  current_unique_customers:    number;
  plan_limit_unique_customers: number;
  alert_level:                 AlertLvl;
  cycle_start:                 string;
  cycle_end:                   string;
}

interface HistoryRow {
  billing_month:        string;
  unique_customers:     number;
  plan_at_month:        PlanCode;
  base_vnd:             number;
  overage_vnd:          number;
  total_vnd:            number;
  invoice_id:           string;
}

const PLAN_NAMES: Record<PlanCode, string> = {
  PILOT: 'Pilot',
  BASIC: 'Enterprise Basic',
  MID:   'Enterprise Mid',
  MAX:   'Enterprise Max',
  ROI:   'Enterprise ROI',
};

export default function SubscriptionPage() {
  const t = useT();
  const [tab, setTab] = useState<'quota' | 'plan' | 'history'>('quota');

  const [sub,     setSub]     = useState<CurrentSubscription | null>(null);
  const [quota,   setQuota]   = useState<QuotaSnapshot | null>(null);
  const [history, setHistory] = useState<HistoryRow[]>([]);

  const [loading, setLoading] = useState(true);
  const [problem, setProblem] = useState<ProblemDetails | null>(null);

  async function load() {
    setLoading(true);
    setProblem(null);
    try {
      const [s, q, h] = await Promise.all([
        api<CurrentSubscription>('/api/v1/subscription/current'),
        api<QuotaSnapshot>('/api/v1/subscription/quota'),
        api<{ items: HistoryRow[] }>('/api/v1/subscription/history?limit=12'),
      ]);
      setSub(s);
      setQuota(q);
      setHistory(h.items);
    } catch (err: any) {
      setProblem(err);
    } finally {
      setLoading(false);
    }
  }
  useEffect(() => { load(); }, []);

  return (
    <>
      <PageHeader
        title={t('templates33SubscriptionQuotaScreen.pageTitle')}
        description={t('templates33SubscriptionQuotaScreen.pageDescription')}
        actions={
          <>
            <Button variant="secondary" onClick={load}>
              <RefreshCw className="w-4 h-4 mr-2" />
              {t('templates33SubscriptionQuotaScreen.refresh')}
            </Button>
            <Button onClick={() => (window.location.href = '/p2/subscription/upgrade')}>
              <ArrowUpRight className="w-4 h-4 mr-2" />
              {t('templates33SubscriptionQuotaScreen.upgradePlan')}
            </Button>
          </>
        }
      />

      <div className="px-6 lg:px-8 py-6 max-w-[1100px] mx-auto space-y-5">
        <ErrorBanner problem={problem} />

        {/* Critical quota alert (≥ 95%) */}
        {quota && quota.alert_level === 'critical' && (
          <div className="bg-[var(--state-error)]/10 border border-[var(--state-error)]/30 rounded-lg-custom p-4 shadow-soft-sm">
            <div className="flex items-start gap-3">
              <AlertTriangle className="w-5 h-5 text-[var(--state-error)] shrink-0 mt-0.5" />
              <div className="flex-1">
                <p className="font-serif text-base text-[#9B5050]">{t('templates33SubscriptionQuotaScreen.criticalTitle', { pct: pct(quota) })}</p>
                <p className="text-sm text-[var(--text-primary)] mt-1">
                  {t('templates33SubscriptionQuotaScreen.criticalBody', {
                    current: quota.current_unique_customers.toLocaleString('vi-VN'),
                    limit: quota.plan_limit_unique_customers.toLocaleString('vi-VN'),
                  })}
                </p>
              </div>
              <Button variant="destructive" size="sm" onClick={() => (window.location.href = '/p2/subscription/upgrade')}>
                {t('templates33SubscriptionQuotaScreen.upgradeNow')}
              </Button>
            </div>
          </div>
        )}

        {/* Warning (80% — 94%) */}
        {quota && quota.alert_level === 'warning' && (
          <div className="bg-[var(--state-warning)]/10 border border-[var(--state-warning)]/30 rounded-md-custom p-3 flex items-start gap-3">
            <AlertTriangle className="w-4 h-4 text-[var(--state-warning)] shrink-0 mt-0.5" />
            <p className="text-sm text-[#9E814D]">
              {t('templates33SubscriptionQuotaScreen.warningBody', { pct: pct(quota) })}
            </p>
          </div>
        )}

        {/* Tabs */}
        <div className="bg-[var(--bg-card)] rounded-lg-custom border border-[var(--border-color)] p-1.5 shadow-soft-sm flex flex-wrap gap-1">
          <TabButton active={tab === 'quota'}   onClick={() => setTab('quota')}   icon={Activity} label={t('templates33SubscriptionQuotaScreen.tabQuota')} />
          <TabButton active={tab === 'plan'}    onClick={() => setTab('plan')}    icon={CreditCard} label={t('templates33SubscriptionQuotaScreen.tabPlan')} />
          <TabButton active={tab === 'history'} onClick={() => setTab('history')} icon={History}    label={t('templates33SubscriptionQuotaScreen.tabHistory')} />
        </div>

        {loading && !sub ? (
          <div className="h-64 rounded-lg-custom bg-[var(--bg-card)] border border-[var(--border-color)] animate-pulse" />
        ) : tab === 'quota' ? (
          <QuotaTab quota={quota} sub={sub} />
        ) : tab === 'plan' ? (
          <PlanTab sub={sub} />
        ) : (
          <HistoryTab rows={history} />
        )}

        {/* K-11 + privacy footer */}
        <div className="flex items-start gap-2 p-3 rounded-md-custom bg-[var(--bg-app)]/40 border border-[var(--border-color)] text-xs text-[var(--text-secondary)]">
          <ShieldCheck className="w-4 h-4 text-[var(--primary-gold-dark)] shrink-0 mt-0.5" />
          <p>
            <span className="font-medium text-[var(--text-primary)]">{t('templates33SubscriptionQuotaScreen.k11Label')}</span> {t('templates33SubscriptionQuotaScreen.k11Part1')} (
            <span className="font-mono">customer_external_id</span>) {t('templates33SubscriptionQuotaScreen.k11Part2')}
            <span className="font-mono"> enterprise_monthly_billing</span> {t('templates33SubscriptionQuotaScreen.k11Part3')}
          </p>
        </div>
      </div>
    </>
  );
}

function pct(q: QuotaSnapshot): number {
  return Math.min(100, Math.round((q.current_unique_customers / Math.max(1, q.plan_limit_unique_customers)) * 100));
}

// ----------------------------------------------------------------------------
// Tabs
// ----------------------------------------------------------------------------

function TabButton({
  active, onClick, icon: Icon, label,
}: { active: boolean; onClick: () => void; icon: any; label: string }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={cn(
        'flex-1 min-w-[160px] inline-flex items-center justify-center gap-2 px-4 py-2 text-sm font-medium rounded-md-custom transition-colors',
        active
          ? 'bg-[var(--primary-gold)]/10 text-[var(--primary-gold-dark)] border border-[var(--primary-gold)]/30'
          : 'text-[var(--text-secondary)] hover:text-[var(--text-primary)] hover:bg-[var(--bg-app)] border border-transparent',
      )}
    >
      <Icon className="w-4 h-4" />
      {label}
    </button>
  );
}

function QuotaTab({
  quota, sub,
}: { quota: QuotaSnapshot | null; sub: CurrentSubscription | null }) {
  const t = useT();
  if (!quota || !sub) return null;

  return (
    <div className="space-y-4">
      <div className="bg-[var(--bg-card)] rounded-lg-custom border border-[var(--border-color)] p-5 shadow-soft-sm">
        <div className="flex items-start justify-between gap-3 flex-wrap mb-4">
          <div>
            <p className="text-[11px] uppercase tracking-wider text-[var(--text-secondary)]">{t('templates33SubscriptionQuotaScreen.monthlyCustomers')}</p>
            <p className="font-serif text-3xl text-[var(--text-primary)] mt-1">
              {quota.current_unique_customers.toLocaleString('vi-VN')}
              <span className="text-base text-[var(--text-secondary)] font-normal"> / {quota.plan_limit_unique_customers.toLocaleString('vi-VN')}</span>
            </p>
            <p className="text-xs text-[var(--text-secondary)] mt-1">
              {t('templates33SubscriptionQuotaScreen.cycleRange', { start: quota.cycle_start, end: quota.cycle_end })}
            </p>
          </div>
          <Badge variant="current">
            <CreditCard className="w-3 h-3 mr-1 inline" />
            {t('templates33SubscriptionQuotaScreen.planBadge', { plan: PLAN_NAMES[sub.plan] })}
          </Badge>
        </div>

        <QuotaBar
          current={quota.current_unique_customers}
          limit={quota.plan_limit_unique_customers}
          unit={t('templates33SubscriptionQuotaScreen.unitCustomer')}
        />

        <p className="text-xs text-[var(--text-secondary)] mt-3 leading-relaxed">
          {t('templates33SubscriptionQuotaScreen.quotaUnitPrefix')} <span className="font-mono">COUNT(DISTINCT customer_external_id)</span> {t('templates33SubscriptionQuotaScreen.quotaUnitSuffix')}
        </p>
      </div>
    </div>
  );
}

function PlanTab({ sub }: { sub: CurrentSubscription | null }) {
  const t = useT();
  if (!sub) return null;
  const customerLimit = sub.plan === 'PILOT' ? '500' : sub.plan === 'BASIC' ? '1.000' : sub.plan === 'MID' ? '4.000' : '10.000+';
  return (
    <div className="bg-[var(--bg-card)] rounded-lg-custom border border-[var(--border-color)] shadow-soft-sm overflow-hidden">
      <div className="px-5 py-4 border-b border-[var(--border-color)]/60 bg-[var(--primary-gold)]/4 flex items-center justify-between gap-3 flex-wrap">
        <div className="flex items-center gap-3">
          <div className="w-12 h-12 rounded-md-custom bg-[var(--primary-gold)]/20 flex items-center justify-center">
            <CreditCard className="w-5 h-5 text-[var(--primary-gold-dark)]" />
          </div>
          <div>
            <h3 className="font-serif text-lg text-[var(--text-primary)]">{PLAN_NAMES[sub.plan]}</h3>
            <p className="text-xs text-[var(--text-secondary)]">{t('templates33SubscriptionQuotaScreen.planStartedRenews', { started: sub.started_at, renews: sub.renews_at })}</p>
          </div>
        </div>
        <div className="text-right">
          <p className="font-serif text-2xl text-[var(--text-primary)]">{formatVND(sub.monthly_vnd)}</p>
          <p className="text-xs text-[var(--text-secondary)]">{t('templates33SubscriptionQuotaScreen.perMonth', { amount: formatVNDLong(sub.monthly_vnd) })}</p>
        </div>
      </div>

      <div className="p-5 space-y-3">
        {sub.is_roi && (
          <div className="flex items-start gap-2 p-3 rounded-md-custom bg-[var(--primary-gold)]/8 border border-[var(--primary-gold)]/30">
            <Sparkles className="w-4 h-4 text-[var(--primary-gold-dark)] shrink-0 mt-0.5" />
            <div className="text-sm">
              <p className="font-medium text-[var(--text-primary)]">ENT ROI tier</p>
              <p className="text-xs text-[var(--text-secondary)] mt-0.5">
                {t('templates33SubscriptionQuotaScreen.roiFeeLead', { base: formatVND(PRICING.ROI_BASE) })} (
                {sub.roi_revenue_saved_pct != null && <>{t('templates33SubscriptionQuotaScreen.roiContribution', { pct: sub.roi_revenue_saved_pct.toFixed(1) })}</>}
                {t('templates33SubscriptionQuotaScreen.roiCapLead', { cap: formatVND(PRICING.ROI_CAP) })}).
              </p>
            </div>
          </div>
        )}

        <Feature ok title={t('templates33SubscriptionQuotaScreen.featureAllTemplates')} />
        <Feature ok title={t('templates33SubscriptionQuotaScreen.featureQuotaLimit', { limit: customerLimit })} />
        <Feature ok title={t('templates33SubscriptionQuotaScreen.featureQwenLocal')} />
        <Feature ok title="Audit log K-6 + RLS NOBYPASSRLS" />
        <Feature ok={sub.plan !== 'PILOT'} title={t('templates33SubscriptionQuotaScreen.featureOverage')} />
        <Feature ok={sub.plan === 'MAX' || sub.plan === 'ROI'} title={t('templates33SubscriptionQuotaScreen.featureRoiOption')} />
      </div>

      <div className="px-5 py-4 border-t border-[var(--border-color)]/60 bg-[var(--bg-app)]/30 flex items-center justify-between gap-3 flex-wrap">
        <p className="text-xs text-[var(--text-secondary)]">
          {t('templates33SubscriptionQuotaScreen.billingLedgerPrefix')} <span className="font-mono">enterprise_monthly_billing</span> {t('templates33SubscriptionQuotaScreen.billingLedgerSuffix')}
        </p>
        <Button onClick={() => (window.location.href = '/p2/subscription/upgrade')}>
          <ArrowUpRight className="w-4 h-4 mr-2" />
          {t('templates33SubscriptionQuotaScreen.compareUpgrade')}
        </Button>
      </div>
    </div>
  );
}

function HistoryTab({ rows }: { rows: HistoryRow[] }) {
  const t = useT();
  return (
    <div className="bg-[var(--bg-card)] rounded-lg-custom border border-[var(--border-color)] shadow-soft-sm overflow-hidden">
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead className="bg-[var(--bg-app)]/50 border-b border-[var(--border-color)]/60">
            <tr>
              <th className="px-4 py-3 text-left text-[11px] font-semibold uppercase tracking-wider text-[var(--text-secondary)]">{t('templates33SubscriptionQuotaScreen.colMonth')}</th>
              <th className="px-4 py-3 text-left text-[11px] font-semibold uppercase tracking-wider text-[var(--text-secondary)]">{t('templates33SubscriptionQuotaScreen.colPlan')}</th>
              <th className="px-4 py-3 text-right text-[11px] font-semibold uppercase tracking-wider text-[var(--text-secondary)]">{t('templates33SubscriptionQuotaScreen.colCustomers')}</th>
              <th className="px-4 py-3 text-right text-[11px] font-semibold uppercase tracking-wider text-[var(--text-secondary)]">{t('templates33SubscriptionQuotaScreen.colBaseFee')}</th>
              <th className="px-4 py-3 text-right text-[11px] font-semibold uppercase tracking-wider text-[var(--text-secondary)]">Overage</th>
              <th className="px-4 py-3 text-right text-[11px] font-semibold uppercase tracking-wider text-[var(--text-secondary)]">{t('templates33SubscriptionQuotaScreen.colTotal')}</th>
              <th className="px-4 py-3 text-right text-[11px] font-semibold uppercase tracking-wider text-[var(--text-secondary)]">{t('templates33SubscriptionQuotaScreen.colInvoice')}</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-[var(--border-color)]/60">
            {rows.length === 0 ? (
              <tr>
                <td colSpan={7} className="px-4 py-12 text-center text-[var(--text-secondary)] text-sm">
                  <Calendar className="w-8 h-8 mx-auto mb-2 text-[var(--text-secondary)]/40" />
                  {t('templates33SubscriptionQuotaScreen.noHistory')}
                </td>
              </tr>
            ) : rows.map((r) => (
              <tr key={r.billing_month} className="hover:bg-[var(--bg-app)]/30">
                <td className="px-4 py-3 text-sm text-[var(--text-primary)] whitespace-nowrap">{r.billing_month}</td>
                <td className="px-4 py-3"><Badge variant="default">{PLAN_NAMES[r.plan_at_month]}</Badge></td>
                <td className="px-4 py-3 text-right font-mono text-xs text-[var(--text-primary)]">
                  {r.unique_customers.toLocaleString('vi-VN')}
                </td>
                <td className="px-4 py-3 text-right font-mono text-xs text-[var(--text-primary)]">{formatVND(r.base_vnd)}</td>
                <td className="px-4 py-3 text-right font-mono text-xs text-[var(--text-primary)]">
                  {r.overage_vnd > 0 ? formatVND(r.overage_vnd) : '—'}
                </td>
                <td className="px-4 py-3 text-right font-mono text-sm font-semibold text-[var(--text-primary)]">
                  {formatVND(r.total_vnd)}
                </td>
                <td className="px-4 py-3 text-right">
                  <a
                    href={`/api/v1/subscription/invoices/${r.invoice_id}`}
                    className="inline-flex items-center text-xs text-[var(--primary-gold-dark)] hover:underline"
                  >
                    <Download className="w-3 h-3 mr-1" />
                    PDF
                  </a>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function Feature({ ok, title }: { ok: boolean; title: string }) {
  return (
    <div className="flex items-center gap-2 text-sm">
      {ok
        ? <CheckCircle2 className="w-4 h-4 text-[var(--state-success)] shrink-0" />
        : <Lock className="w-4 h-4 text-[var(--text-secondary)]/50 shrink-0" />}
      <span className={ok ? 'text-[var(--text-primary)]' : 'text-[var(--text-secondary)]'}>{title}</span>
    </div>
  );
}
