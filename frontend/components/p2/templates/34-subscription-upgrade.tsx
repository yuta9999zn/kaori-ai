// @ts-nocheck — template import; tighten types when wiring to real API
'use client';

// ============================================================================
// 34. /p2/subscription/upgrade — Plan Comparison + Upgrade (F-030)
// ----------------------------------------------------------------------------
// 5 plans (CLAUDE.md §10):
//   PILOT      1.000.000₫ / tháng · 500 KH max  · không overage
//   ENT BASIC  2.000.000₫ / tháng · 1.000 KH    · +500K mỗi 1.000 thêm
//   ENT MID    5.000.000₫ / tháng · 4.000 KH    · +400K mỗi 1.000 thêm
//   ENT MAX    8.000.000₫ / tháng · 10.000 KH   · +250K mỗi 1.000 thêm
//   ENT ROI    8M + 1.5% revenue saved (cap 20M) · 10.000+ KH
//                Opt-in: chỉ mở khi đã ở ENT MAX ≥ 3 tháng liên tiếp
//
// Endpoints:
//   GET  /api/v1/subscription/upgrade-eligibility   → { roi_eligible, max_months_count }
//   POST /api/v1/subscription/upgrade { target_plan } → returns 202 + email manual workflow
//
// Phase 1 = manual-upgrade workflow (PR #75): we open a request that ops fulfils.
// Phase 2 will wire Stripe / VietQR direct charge.
// ============================================================================

import React, { useState, useEffect } from 'react';
import {
  ChevronLeft, CreditCard, Sparkles, CheckCircle2, Lock,
  ArrowUpRight, ArrowDownRight, ShieldCheck, AlertTriangle, Star,
  Calendar,
} from 'lucide-react';

import {
  Button, Badge, ErrorBanner, SuccessBanner, cn,
  api, formatVND, formatVNDLong, PRICING,
  type ProblemDetails,
} from '@/components/p2/foundation';
import { PageHeader } from '@/components/p2/shell';
type PlanCode = 'PILOT' | 'BASIC' | 'MID' | 'MAX' | 'ROI';

interface Plan {
  code:         PlanCode;
  name:         string;
  tagline:      string;
  monthly_vnd:  number;
  monthly_label: string;
  unique_kh:    string;
  overage:      string;
  features:     Array<{ ok: boolean; label: string }>;
  highlight?:   boolean;
}

const PLANS: Plan[] = [
  {
    code:         'PILOT',
    name:         'Pilot',
    tagline:      'Thử nghiệm với 1 use case',
    monthly_vnd:  PRICING.PILOT,
    monthly_label: '1 triệu VNĐ',
    unique_kh:    '500 khách hàng / tháng',
    overage:      'Không có overage — phải nâng cấp khi đầy',
    features: [
      { ok: true,  label: 'Toàn bộ template phân tích Phase 1' },
      { ok: true,  label: 'Qwen 2.5 nội bộ' },
      { ok: true,  label: '1 workspace · 3 user' },
      { ok: false, label: 'API integration' },
      { ok: false, label: 'Custom branding (F-026)' },
    ],
  },
  {
    code:         'BASIC',
    name:         'Enterprise Basic',
    tagline:      'Doanh nghiệp nhỏ · 1.000 khách / tháng',
    monthly_vnd:  PRICING.BASIC,
    monthly_label: '2 triệu VNĐ',
    unique_kh:    '1.000 khách hàng / tháng',
    overage:      '+500K mỗi 1.000 khách hàng vượt mức',
    features: [
      { ok: true,  label: 'Mọi tính năng Pilot' },
      { ok: true,  label: '1 workspace · 10 user' },
      { ok: true,  label: 'Email alerts + scheduled reports (F-038)' },
      { ok: true,  label: 'API integration cơ bản' },
      { ok: false, label: 'Custom AI fine-tune (Phase 2)' },
    ],
  },
  {
    code:         'MID',
    name:         'Enterprise Mid',
    tagline:      'Đang scale · 4.000 khách / tháng',
    monthly_vnd:  PRICING.MID,
    monthly_label: '5 triệu VNĐ',
    unique_kh:    '4.000 khách hàng / tháng',
    overage:      '+400K mỗi 1.000 khách hàng vượt mức',
    highlight:    true,
    features: [
      { ok: true, label: 'Mọi tính năng Basic' },
      { ok: true, label: '3 workspace · 25 user' },
      { ok: true, label: 'Custom branding email + login (F-026)' },
      { ok: true, label: 'AI bên ngoài (Claude / GPT-4o) opt-in K-4' },
      { ok: true, label: 'Priority support trong giờ hành chính' },
    ],
  },
  {
    code:         'MAX',
    name:         'Enterprise Max',
    tagline:      'Doanh nghiệp lớn · 10.000 khách / tháng',
    monthly_vnd:  PRICING.MAX,
    monthly_label: '8 triệu VNĐ',
    unique_kh:    '10.000 khách hàng / tháng',
    overage:      '+250K mỗi 1.000 khách hàng vượt mức',
    features: [
      { ok: true, label: 'Mọi tính năng Mid' },
      { ok: true, label: 'Workspace + user không giới hạn' },
      { ok: true, label: 'SSO + MFA bắt buộc' },
      { ok: true, label: 'Premium support 24/7' },
      { ok: true, label: 'Mở khoá ENT ROI sau 3 tháng MAX' },
    ],
  },
  {
    code:         'ROI',
    name:         'Enterprise ROI',
    tagline:      '10.000+ khách · ăn chia theo doanh thu cứu được',
    monthly_vnd:  PRICING.ROI_BASE,
    monthly_label: '8 triệu VNĐ + 1.5% doanh thu cứu được',
    unique_kh:    '10.000+ khách hàng / tháng',
    overage:      `Tổng tối đa ${formatVND(PRICING.ROI_CAP)} / tháng`,
    features: [
      { ok: true, label: 'Mọi tính năng Max' },
      { ok: true, label: '8M cố định + 1.5% revenue cứu được (cap 20M)' },
      { ok: true, label: 'Quarterly North-Star ROI review meeting' },
      { ok: true, label: 'Solution architect cá nhân' },
      { ok: true, label: 'Yêu cầu: ≥3 tháng MAX liên tiếp' },
    ],
  },
];

interface CurrentSubscription {
  plan: PlanCode;
  is_roi: boolean;
}
interface UpgradeEligibility {
  roi_eligible:      boolean;
  max_months_count:  number;
  current_plan:      PlanCode;
}

export default function SubscriptionUpgradePage() {
  const [sub,         setSub]         = useState<CurrentSubscription | null>(null);
  const [eligibility, setEligibility] = useState<UpgradeEligibility | null>(null);
  const [loading,     setLoading]     = useState(true);
  const [problem,     setProblem]     = useState<ProblemDetails | null>(null);
  const [success,     setSuccess]     = useState<string | null>(null);

  const [target,    setTarget]    = useState<PlanCode | null>(null);
  const [confirming, setConfirming] = useState(false);

  async function load() {
    setLoading(true);
    try {
      const [s, e] = await Promise.all([
        api<CurrentSubscription>('/api/v1/subscription/current'),
        api<UpgradeEligibility>('/api/v1/subscription/upgrade-eligibility'),
      ]);
      setSub(s);
      setEligibility(e);
    } catch (err: any) {
      setProblem(err);
    } finally {
      setLoading(false);
    }
  }
  useEffect(() => { load(); }, []);

  async function submitUpgrade(targetPlan: PlanCode) {
    setConfirming(true);
    setProblem(null);
    try {
      await api('/api/v1/subscription/upgrade', {
        method: 'POST',
        body:   JSON.stringify({ target_plan: targetPlan }),
      });
      setSuccess(`Đã gửi yêu cầu nâng cấp lên ${PLANS.find((p) => p.code === targetPlan)?.name ?? targetPlan}. Ops sẽ liên hệ trong 1 ngày làm việc.`);
      setTarget(null);
    } catch (err: any) {
      setProblem(err);
    } finally {
      setConfirming(false);
    }
  }

  const currentIdx = PLANS.findIndex((p) => p.code === sub?.plan);

  return (
    <>
      <PageHeader
        title="Nâng cấp gói cước"
        description="So sánh 5 gói. Quy đổi đơn vị: 1 khách hàng (DISTINCT customer_external_id) / tháng (K-11)."
        actions={
          <Button variant="tertiary" onClick={() => (window.location.href = '/p2/subscription')}>
            <ChevronLeft className="w-4 h-4 mr-1" />
            Quay lại
          </Button>
        }
      />

      <div className="px-6 lg:px-8 py-6 max-w-[1400px] mx-auto space-y-5">
        <ErrorBanner problem={problem} />
        {success && <SuccessBanner message={success} />}

        {/* ROI eligibility banner */}
        {eligibility && !eligibility.roi_eligible && (
          <div className="bg-[var(--bg-card)] rounded-md-custom border border-[var(--border-color)] p-3 flex items-start gap-3">
            <Calendar className="w-4 h-4 text-[var(--text-secondary)] shrink-0 mt-0.5" />
            <p className="text-xs text-[var(--text-secondary)]">
              <span className="font-medium text-[var(--text-primary)]">ENT ROI</span> mở khoá khi bạn ở
              <span className="font-medium text-[var(--text-primary)]"> Enterprise Max ≥ 3 tháng liên tiếp</span>.
              Hiện tại: {eligibility.current_plan === 'MAX' ? `${eligibility.max_months_count} / 3 tháng MAX` : 'chưa ở gói MAX'}.
            </p>
          </div>
        )}

        {/* Plan grid */}
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-5 gap-4 items-stretch">
          {PLANS.map((p, idx) => {
            const isCurrent = sub?.plan === p.code;
            const isUpgrade = currentIdx >= 0 && idx > currentIdx;
            const isDowngrade = currentIdx >= 0 && idx < currentIdx;
            const roiLocked = p.code === 'ROI' && eligibility && !eligibility.roi_eligible && !isCurrent;

            return (
              <PlanCard
                key={p.code}
                plan={p}
                isCurrent={isCurrent}
                isUpgrade={isUpgrade}
                isDowngrade={isDowngrade}
                locked={!!roiLocked}
                onSelect={() => setTarget(p.code)}
              />
            );
          })}
        </div>

        {/* K-11 footer */}
        <div className="flex items-start gap-2 p-3 rounded-md-custom bg-[var(--bg-app)]/40 border border-[var(--border-color)] text-xs text-[var(--text-secondary)]">
          <ShieldCheck className="w-4 h-4 text-[var(--primary-gold-dark)] shrink-0 mt-0.5" />
          <p>
            Mọi giao dịch nâng cấp Phase 1 đi qua workflow thủ công (PR #75 / Sprint 3) — ops sẽ chuyển khoản VietQR và xác nhận trong vòng 1 ngày làm việc.
            Phase 2 sẽ tự động hoá thanh toán + invoice. Đơn vị tính giữ nguyên: <span className="font-medium text-[var(--text-primary)]">DISTINCT customer_external_id</span> / tháng / workspace (K-11).
          </p>
        </div>
      </div>

      {/* Confirmation modal */}
      {target && sub && (
        <ConfirmUpgradeModal
          target={target}
          current={sub.plan}
          confirming={confirming}
          onCancel={() => setTarget(null)}
          onConfirm={() => submitUpgrade(target)}
        />
      )}
    </>
  );
}

// ----------------------------------------------------------------------------
// PlanCard
// ----------------------------------------------------------------------------

function PlanCard({
  plan: p, isCurrent, isUpgrade, isDowngrade, locked, onSelect,
}: {
  plan: Plan;
  isCurrent: boolean;
  isUpgrade: boolean;
  isDowngrade: boolean;
  locked: boolean;
  onSelect: () => void;
}) {
  return (
    <div className={cn(
      'flex flex-col rounded-lg-custom border shadow-soft-sm overflow-hidden',
      isCurrent
        ? 'border-[var(--primary-gold)] bg-[var(--primary-gold)]/5 ring-2 ring-[var(--primary-gold)]/30'
        : p.highlight
          ? 'border-[var(--primary-gold)]/40 bg-[var(--bg-card)]'
          : 'border-[var(--border-color)] bg-[var(--bg-card)]',
      locked && 'opacity-70',
    )}>
      <div className="px-4 py-4 border-b border-[var(--border-color)]/60 relative">
        {p.highlight && !isCurrent && (
          <Badge variant="current" className="absolute right-3 top-3">
            <Star className="w-3 h-3 mr-1 inline" />
            Phổ biến
          </Badge>
        )}
        {isCurrent && (
          <Badge variant="success" className="absolute right-3 top-3">
            <CheckCircle2 className="w-3 h-3 mr-1 inline" />
            Đang dùng
          </Badge>
        )}

        <h3 className="font-serif text-lg text-[var(--text-primary)]">{p.name}</h3>
        <p className="text-xs text-[var(--text-secondary)] mt-0.5 leading-snug">{p.tagline}</p>

        <p className="font-serif text-2xl text-[var(--text-primary)] mt-3">
          {p.code === 'ROI' ? formatVND(PRICING.ROI_BASE) : formatVND(p.monthly_vnd)}
        </p>
        <p className="text-[11px] text-[var(--text-secondary)] mt-0.5">{p.monthly_label} / tháng</p>
      </div>

      <div className="px-4 py-4 space-y-3 flex-1">
        <div className="rounded-md-custom bg-[var(--bg-app)]/40 border border-[var(--border-color)]/40 p-2.5">
          <p className="text-[10px] uppercase tracking-wider text-[var(--text-secondary)]">Hạn mức</p>
          <p className="text-xs font-medium text-[var(--text-primary)] mt-0.5">{p.unique_kh}</p>
        </div>
        <div className="rounded-md-custom bg-[var(--bg-app)]/40 border border-[var(--border-color)]/40 p-2.5">
          <p className="text-[10px] uppercase tracking-wider text-[var(--text-secondary)]">Overage</p>
          <p className="text-xs text-[var(--text-primary)] mt-0.5 leading-snug">{p.overage}</p>
        </div>

        <ul className="space-y-1.5 pt-1">
          {p.features.map((f, i) => (
            <li key={i} className="flex items-start gap-2 text-xs">
              {f.ok
                ? <CheckCircle2 className="w-3.5 h-3.5 text-[var(--state-success)] shrink-0 mt-0.5" />
                : <Lock className="w-3.5 h-3.5 text-[var(--text-secondary)]/50 shrink-0 mt-0.5" />}
              <span className={f.ok ? 'text-[var(--text-primary)]' : 'text-[var(--text-secondary)]'}>{f.label}</span>
            </li>
          ))}
        </ul>
      </div>

      <div className="px-4 py-3 border-t border-[var(--border-color)]/60 bg-[var(--bg-app)]/30">
        {isCurrent ? (
          <Button variant="secondary" disabled className="w-full">
            Đang dùng gói này
          </Button>
        ) : locked ? (
          <Button variant="secondary" disabled className="w-full">
            <Lock className="w-3.5 h-3.5 mr-1.5" />
            Cần ≥ 3 tháng MAX
          </Button>
        ) : isUpgrade ? (
          <Button onClick={onSelect} className="w-full">
            <ArrowUpRight className="w-3.5 h-3.5 mr-1.5" />
            Nâng cấp
          </Button>
        ) : isDowngrade ? (
          <Button variant="secondary" onClick={onSelect} className="w-full">
            <ArrowDownRight className="w-3.5 h-3.5 mr-1.5" />
            Hạ cấp
          </Button>
        ) : (
          <Button onClick={onSelect} className="w-full">
            Chọn gói
          </Button>
        )}
      </div>
    </div>
  );
}

// ----------------------------------------------------------------------------
// Confirm modal
// ----------------------------------------------------------------------------

function ConfirmUpgradeModal({
  target, current, confirming, onCancel, onConfirm,
}: {
  target: PlanCode;
  current: PlanCode;
  confirming: boolean;
  onCancel: () => void;
  onConfirm: () => void;
}) {
  const targetPlan  = PLANS.find((p) => p.code === target);
  const currentPlan = PLANS.find((p) => p.code === current);
  if (!targetPlan || !currentPlan) return null;

  const isUpgrade = PLANS.findIndex((p) => p.code === target) > PLANS.findIndex((p) => p.code === current);

  return (
    <div className="fixed inset-0 z-50 bg-[var(--text-primary)]/40 backdrop-blur-sm flex items-center justify-center p-4">
      <div className="bg-[var(--bg-card)] rounded-lg-custom border border-[var(--border-color)] shadow-soft-lg w-full max-w-md p-5 animate-slide-up-fade">
        <h3 className="font-serif text-lg text-[var(--text-primary)]">
          Xác nhận {isUpgrade ? 'nâng cấp' : 'thay đổi gói'}
        </h3>
        <p className="text-sm text-[var(--text-secondary)] mt-1">
          Yêu cầu sẽ được gửi tới ops để xác nhận thanh toán bằng VietQR (Phase 1 — manual workflow).
        </p>

        <div className="mt-4 space-y-2">
          <div className="rounded-md-custom border border-[var(--border-color)] bg-[var(--bg-app)]/30 p-3">
            <p className="text-[11px] uppercase tracking-wider text-[var(--text-secondary)]">Hiện tại</p>
            <p className="font-serif text-sm text-[var(--text-primary)] mt-0.5">{currentPlan.name}</p>
            <p className="text-xs text-[var(--text-secondary)]">{formatVND(currentPlan.monthly_vnd)} / tháng</p>
          </div>
          <div className="flex justify-center text-[var(--primary-gold-dark)]">
            {isUpgrade ? <ArrowUpRight className="w-5 h-5" /> : <ArrowDownRight className="w-5 h-5" />}
          </div>
          <div className="rounded-md-custom border border-[var(--primary-gold)]/40 bg-[var(--primary-gold)]/8 p-3">
            <p className="text-[11px] uppercase tracking-wider text-[var(--primary-gold-dark)]">Sau khi đổi</p>
            <p className="font-serif text-sm text-[var(--text-primary)] mt-0.5">{targetPlan.name}</p>
            <p className="text-xs text-[var(--text-secondary)]">{targetPlan.monthly_label} / tháng</p>
          </div>
        </div>

        {!isUpgrade && (
          <div className="mt-3 flex items-start gap-2 p-3 rounded-md-custom bg-[var(--state-warning)]/10 border border-[var(--state-warning)]/30 text-xs text-[#9E814D]">
            <AlertTriangle className="w-4 h-4 shrink-0 mt-0.5" />
            <p>
              Hạ cấp sẽ áp dụng từ chu kỳ tháng kế tiếp. Hạn mức tháng hiện tại giữ nguyên cho đến khi gia hạn.
            </p>
          </div>
        )}

        <div className="mt-4 flex items-center gap-2 justify-end">
          <Button variant="tertiary" onClick={onCancel} disabled={confirming}>Huỷ</Button>
          <Button onClick={onConfirm} isLoading={confirming}>
            {isUpgrade ? <Sparkles className="w-4 h-4 mr-2" /> : null}
            Xác nhận
          </Button>
        </div>
      </div>
    </div>
  );
}
