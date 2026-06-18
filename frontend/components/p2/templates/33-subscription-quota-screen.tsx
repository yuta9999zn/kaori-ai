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
        title="Gói cước & Hạn mức"
        description="Theo dõi mức sử dụng tháng + so sánh kế hoạch + lịch sử thanh toán."
        actions={
          <>
            <Button variant="secondary" onClick={load}>
              <RefreshCw className="w-4 h-4 mr-2" />
              Làm mới
            </Button>
            <Button onClick={() => (window.location.href = '/p2/subscription/upgrade')}>
              <ArrowUpRight className="w-4 h-4 mr-2" />
              Nâng cấp gói
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
                <p className="font-serif text-base text-[#9B5050]">Sắp chạm giới hạn ({pct(quota)}%)</p>
                <p className="text-sm text-[var(--text-primary)] mt-1">
                  Đã dùng {quota.current_unique_customers.toLocaleString('vi-VN')} / {quota.plan_limit_unique_customers.toLocaleString('vi-VN')} khách hàng tháng này.
                  Vượt hạn mức sẽ bị tính phí overage hoặc gián đoạn — nâng cấp ngay để tránh.
                </p>
              </div>
              <Button variant="destructive" size="sm" onClick={() => (window.location.href = '/p2/subscription/upgrade')}>
                Nâng cấp ngay
              </Button>
            </div>
          </div>
        )}

        {/* Warning (80% — 94%) */}
        {quota && quota.alert_level === 'warning' && (
          <div className="bg-[var(--state-warning)]/10 border border-[var(--state-warning)]/30 rounded-md-custom p-3 flex items-start gap-3">
            <AlertTriangle className="w-4 h-4 text-[var(--state-warning)] shrink-0 mt-0.5" />
            <p className="text-sm text-[#9E814D]">
              Đã dùng {pct(quota)}% hạn mức tháng này. Cân nhắc nâng cấp trước khi chạm 95% để tránh overage.
            </p>
          </div>
        )}

        {/* Tabs */}
        <div className="bg-[var(--bg-card)] rounded-lg-custom border border-[var(--border-color)] p-1.5 shadow-soft-sm flex flex-wrap gap-1">
          <TabButton active={tab === 'quota'}   onClick={() => setTab('quota')}   icon={Activity} label="Hạn mức tháng này" />
          <TabButton active={tab === 'plan'}    onClick={() => setTab('plan')}    icon={CreditCard} label="Gói hiện tại" />
          <TabButton active={tab === 'history'} onClick={() => setTab('history')} icon={History}    label="Lịch sử thanh toán" />
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
            <span className="font-medium text-[var(--text-primary)]">K-11 — Đơn vị tính:</span> mỗi khách hàng (
            <span className="font-mono">customer_external_id</span>) chỉ đếm 1 lần / tháng / workspace dù xuất hiện trong nhiều file. Bản ghi
            <span className="font-mono"> enterprise_monthly_billing</span> là immutable (UPSERT, không xóa).
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
  if (!quota || !sub) return null;

  return (
    <div className="space-y-4">
      <div className="bg-[var(--bg-card)] rounded-lg-custom border border-[var(--border-color)] p-5 shadow-soft-sm">
        <div className="flex items-start justify-between gap-3 flex-wrap mb-4">
          <div>
            <p className="text-[11px] uppercase tracking-wider text-[var(--text-secondary)]">Số khách hàng xử lý trong tháng (K-11)</p>
            <p className="font-serif text-3xl text-[var(--text-primary)] mt-1">
              {quota.current_unique_customers.toLocaleString('vi-VN')}
              <span className="text-base text-[var(--text-secondary)] font-normal"> / {quota.plan_limit_unique_customers.toLocaleString('vi-VN')}</span>
            </p>
            <p className="text-xs text-[var(--text-secondary)] mt-1">
              Chu kỳ: {quota.cycle_start} → {quota.cycle_end}
            </p>
          </div>
          <Badge variant="current">
            <CreditCard className="w-3 h-3 mr-1 inline" />
            Gói {PLAN_NAMES[sub.plan]}
          </Badge>
        </div>

        <QuotaBar
          current={quota.current_unique_customers}
          limit={quota.plan_limit_unique_customers}
          unit="khách hàng"
        />

        <p className="text-xs text-[var(--text-secondary)] mt-3 leading-relaxed">
          Đơn vị tính = <span className="font-mono">COUNT(DISTINCT customer_external_id)</span> / workspace / tháng — chống split-batch gaming.
          Vượt hạn mức trên các gói có overage (Basic / Mid / Max) sẽ tự động tính phí; gói Pilot bắt buộc nâng cấp trước khi vượt.
        </p>
      </div>
    </div>
  );
}

function PlanTab({ sub }: { sub: CurrentSubscription | null }) {
  if (!sub) return null;
  return (
    <div className="bg-[var(--bg-card)] rounded-lg-custom border border-[var(--border-color)] shadow-soft-sm overflow-hidden">
      <div className="px-5 py-4 border-b border-[var(--border-color)]/60 bg-[var(--primary-gold)]/4 flex items-center justify-between gap-3 flex-wrap">
        <div className="flex items-center gap-3">
          <div className="w-12 h-12 rounded-md-custom bg-[var(--primary-gold)]/20 flex items-center justify-center">
            <CreditCard className="w-5 h-5 text-[var(--primary-gold-dark)]" />
          </div>
          <div>
            <h3 className="font-serif text-lg text-[var(--text-primary)]">{PLAN_NAMES[sub.plan]}</h3>
            <p className="text-xs text-[var(--text-secondary)]">Bắt đầu {sub.started_at} · Gia hạn {sub.renews_at}</p>
          </div>
        </div>
        <div className="text-right">
          <p className="font-serif text-2xl text-[var(--text-primary)]">{formatVND(sub.monthly_vnd)}</p>
          <p className="text-xs text-[var(--text-secondary)]">{formatVNDLong(sub.monthly_vnd)} / tháng</p>
        </div>
      </div>

      <div className="p-5 space-y-3">
        {sub.is_roi && (
          <div className="flex items-start gap-2 p-3 rounded-md-custom bg-[var(--primary-gold)]/8 border border-[var(--primary-gold)]/30">
            <Sparkles className="w-4 h-4 text-[var(--primary-gold-dark)] shrink-0 mt-0.5" />
            <div className="text-sm">
              <p className="font-medium text-[var(--text-primary)]">ENT ROI tier</p>
              <p className="text-xs text-[var(--text-secondary)] mt-0.5">
                Phí cố định {formatVND(PRICING.ROI_BASE)} + 1.5% doanh thu cứu được (
                {sub.roi_revenue_saved_pct != null && <>tháng này đã đóng góp {sub.roi_revenue_saved_pct.toFixed(1)}%, </>}
                tối đa {formatVND(PRICING.ROI_CAP)}).
              </p>
            </div>
          </div>
        )}

        <Feature ok title="Toàn bộ template phân tích Phase 1" />
        <Feature ok title={`Hạn mức ${sub.plan === 'PILOT' ? '500' : sub.plan === 'BASIC' ? '1.000' : sub.plan === 'MID' ? '4.000' : '10.000+'} khách hàng / tháng`} />
        <Feature ok title="Qwen 2.5 nội bộ — không tốn quota AI bên ngoài" />
        <Feature ok title="Audit log K-6 + RLS NOBYPASSRLS" />
        <Feature ok={sub.plan !== 'PILOT'} title="Overage VND theo gói (PILOT bắt buộc nâng cấp khi đầy)" />
        <Feature ok={sub.plan === 'MAX' || sub.plan === 'ROI'} title="Tuỳ chọn ENT ROI 8M + 1.5% doanh thu cứu được (cap 20M)" />
      </div>

      <div className="px-5 py-4 border-t border-[var(--border-color)]/60 bg-[var(--bg-app)]/30 flex items-center justify-between gap-3 flex-wrap">
        <p className="text-xs text-[var(--text-secondary)]">
          Mọi giao dịch ghi vào <span className="font-mono">enterprise_monthly_billing</span> (immutable, UPSERT).
        </p>
        <Button onClick={() => (window.location.href = '/p2/subscription/upgrade')}>
          <ArrowUpRight className="w-4 h-4 mr-2" />
          So sánh & nâng cấp
        </Button>
      </div>
    </div>
  );
}

function HistoryTab({ rows }: { rows: HistoryRow[] }) {
  return (
    <div className="bg-[var(--bg-card)] rounded-lg-custom border border-[var(--border-color)] shadow-soft-sm overflow-hidden">
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead className="bg-[var(--bg-app)]/50 border-b border-[var(--border-color)]/60">
            <tr>
              <th className="px-4 py-3 text-left text-[11px] font-semibold uppercase tracking-wider text-[var(--text-secondary)]">Tháng</th>
              <th className="px-4 py-3 text-left text-[11px] font-semibold uppercase tracking-wider text-[var(--text-secondary)]">Gói</th>
              <th className="px-4 py-3 text-right text-[11px] font-semibold uppercase tracking-wider text-[var(--text-secondary)]">Khách hàng</th>
              <th className="px-4 py-3 text-right text-[11px] font-semibold uppercase tracking-wider text-[var(--text-secondary)]">Phí cơ bản</th>
              <th className="px-4 py-3 text-right text-[11px] font-semibold uppercase tracking-wider text-[var(--text-secondary)]">Overage</th>
              <th className="px-4 py-3 text-right text-[11px] font-semibold uppercase tracking-wider text-[var(--text-secondary)]">Tổng cộng</th>
              <th className="px-4 py-3 text-right text-[11px] font-semibold uppercase tracking-wider text-[var(--text-secondary)]">Hoá đơn</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-[var(--border-color)]/60">
            {rows.length === 0 ? (
              <tr>
                <td colSpan={7} className="px-4 py-12 text-center text-[var(--text-secondary)] text-sm">
                  <Calendar className="w-8 h-8 mx-auto mb-2 text-[var(--text-secondary)]/40" />
                  Chưa có lịch sử thanh toán.
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
