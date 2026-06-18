"use client";

/**
 * F-030 — Enterprise Subscription & Quota.
 *
 * Three-tab layout (Quota | Plan | Upgrade) over GET
 * /api/v1/enterprises/me/subscription. The in-app banner at the top is
 * the F-031 alert delivery surface — it appears whenever
 * `alert_80_fired || alert_95_fired` is set on the current month's
 * enterprise_monthly_billing row.
 */

import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Gauge, CreditCard, ArrowUpCircle, AlertTriangle, AlertOctagon,
  CheckCircle2, Clock, Sparkles,
} from "lucide-react";
import { api } from "@/lib/api";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge, type BadgeTone } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { useT } from "@/lib/i18n/provider";
import { fmtDateTime } from "@/lib/format";

// ── Types ──────────────────────────────────────────────────────────────────

interface PendingUpgrade {
  request_id:     string;
  requested_plan: string;
  requested_at:   string;
}

interface SubscriptionState {
  enterprise_id:           string;
  enterprise_name:         string;
  current_plan:            string;
  plan_display_name:       string;
  plan_quota:              number;
  plan_price_vnd:          number;
  usage_count:             number;
  quota:                   number;
  usage_pct:               number;
  overage_units:           number;
  forecast_eom:            number;
  alert_80_fired:          boolean;
  alert_95_fired:          boolean;
  billing_month:           string;
  days_in_billing_month:   number;
  days_remaining:          number;
  last_aggregated_at:      string | null;
  pending_upgrade:         PendingUpgrade | null;
}

// ── Plan catalogue (read from BE response would be cleaner — Phase 2) ──────

const PLAN_CATALOGUE: Array<{ code: string; label: string; quota: number; priceVnd: number }> = [
  { code: "PILOT",      label: "Pilot",         quota:    500, priceVnd:  1_000_000 },
  { code: "ENT_BASIC",  label: "Enterprise Basic",  quota:  1_000, priceVnd:  2_000_000 },
  { code: "ENT_MID",    label: "Enterprise Mid",    quota:  4_000, priceVnd:  5_000_000 },
  { code: "ENT_MAX",    label: "Enterprise Max",    quota: 10_000, priceVnd:  8_000_000 },
];

const TABS = [
  { id: "quota",   label: "Hạn mức",  icon: Gauge },
  { id: "plan",    label: "Gói",       icon: CreditCard },
  { id: "upgrade", label: "Nâng cấp",  icon: ArrowUpCircle },
] as const;

type TabId = (typeof TABS)[number]["id"];

function fmtVnd(v: number): string {
  return new Intl.NumberFormat("vi-VN").format(v) + " ₫";
}

function pctTone(pct: number): BadgeTone {
  if (pct >= 95) return "danger";
  if (pct >= 80) return "warning";
  return "success";
}

// ── Page ───────────────────────────────────────────────────────────────────

export default function SubscriptionPage() {
  const t  = useT();
  const qc = useQueryClient();
  const [tab, setTab] = useState<TabId>("quota");

  const { data, isLoading, isError } = useQuery<{ data: SubscriptionState }>({
    queryKey: ["subscription"],
    queryFn:  () => api(`/api/v1/enterprises/me/subscription`),
    staleTime: 30_000,
  });

  const upgradeMutation = useMutation({
    mutationFn: (target: string) =>
      api(`/api/v1/enterprises/me/subscription/upgrade`, {
        method: "POST",
        body:   JSON.stringify({ target_plan: target }),
      }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["subscription"] }),
  });

  const s = data?.data;
  const upgradeOptions = useMemo(
    () => PLAN_CATALOGUE.filter((p) => p.code !== s?.current_plan),
    [s?.current_plan],
  );

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-h1 font-serif text-ink">Gói dịch vụ & Hạn mức</h1>
        <p className="text-small text-ink-muted mt-1">
          Theo dõi hạn mức tháng và yêu cầu nâng cấp gói khi cần.
        </p>
      </div>

      {/* F-031 alert delivery surface */}
      {s?.alert_95_fired && (
        <Card className="border-danger-200 bg-danger-50/30">
          <CardContent className="pt-6 flex items-start gap-3">
            <AlertOctagon className="w-5 h-5 text-danger-600 mt-0.5" />
            <div className="space-y-1">
              <p className="text-body-strong text-danger-700">Đã đạt 95% hạn mức tháng</p>
              <p className="text-small text-danger-600">
                Yêu cầu nâng cấp ngay để tránh ngừng dịch vụ. Liên hệ hỗ trợ nếu cần xử lý gấp.
              </p>
            </div>
          </CardContent>
        </Card>
      )}
      {s?.alert_80_fired && !s?.alert_95_fired && (
        <Card className="border-warning-200 bg-warning-50/30">
          <CardContent className="pt-6 flex items-start gap-3">
            <AlertTriangle className="w-5 h-5 text-warning-600 mt-0.5" />
            <div className="space-y-1">
              <p className="text-body-strong text-warning-700">Đã đạt 80% hạn mức tháng</p>
              <p className="text-small text-warning-600">
                Tốc độ sử dụng hiện tại có thể vượt hạn mức trước cuối tháng. Cân nhắc nâng cấp gói.
              </p>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Tab switcher */}
      <div className="border-b border-subtle">
        <nav className="flex gap-1 -mb-px">
          {TABS.map((tDef) => {
            const Icon   = tDef.icon;
            const active = tab === tDef.id;
            return (
              <button
                key={tDef.id}
                onClick={() => setTab(tDef.id)}
                className={`px-4 py-2.5 text-small border-b-2 transition-colors flex items-center gap-2 ${
                  active
                    ? "border-brand-500 text-brand-700 font-medium"
                    : "border-transparent text-ink-muted hover:text-ink hover:border-[#E9E2D5]"
                }`}
              >
                <Icon className="w-4 h-4" />
                {tDef.label}
              </button>
            );
          })}
        </nav>
      </div>

      {isLoading && (
        <div className="space-y-3">
          {Array.from({ length: 4 }).map((_, i) => <Skeleton key={i} className="h-24" />)}
        </div>
      )}

      {isError && (
        <Card className="border-danger-200 bg-danger-50/30">
          <CardContent className="pt-6 text-small text-danger-700">{t("error.generic")}</CardContent>
        </Card>
      )}

      {!isLoading && !isError && s && (
        <>
          {tab === "quota"   && <QuotaTab   s={s} />}
          {tab === "plan"    && <PlanTab    s={s} />}
          {tab === "upgrade" && (
            <UpgradeTab
              s={s}
              options={upgradeOptions}
              isPending={upgradeMutation.isPending}
              isError={upgradeMutation.isError}
              errorMessage={(upgradeMutation.error as { message?: string } | null)?.message}
              onSubmit={upgradeMutation.mutate}
            />
          )}
        </>
      )}
    </div>
  );
}

// ── Tabs ───────────────────────────────────────────────────────────────────

function QuotaTab({ s }: { s: SubscriptionState }) {
  return (
    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="flex items-center gap-2">
            <Gauge className="w-4 h-4 text-brand-500" /> Sử dụng tháng này
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-3 pb-5">
          <div className="flex items-baseline gap-2">
            <span className="text-h2 font-serif text-ink tabular-nums">
              {s.usage_count.toLocaleString("vi-VN")}
            </span>
            <span className="text-small text-ink-muted">/ {s.quota.toLocaleString("vi-VN")} khách hàng</span>
            <Badge tone={pctTone(s.usage_pct)}>{s.usage_pct}%</Badge>
          </div>
          <div className="h-2 bg-[#F5EFE5] rounded-full overflow-hidden">
            <div
              className={`h-full ${s.usage_pct >= 95 ? "bg-danger-500" : s.usage_pct >= 80 ? "bg-warning-500" : "bg-brand-500"}`}
              style={{ width: `${Math.min(100, s.usage_pct)}%` }}
            />
          </div>
          <p className="text-tiny text-[#B0A698]">
            Còn {s.days_remaining} ngày trong chu kỳ {s.billing_month} ({s.days_in_billing_month} ngày).
          </p>
        </CardContent>
      </Card>

      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="flex items-center gap-2">
            <Sparkles className="w-4 h-4 text-brand-500" /> Dự báo cuối kỳ
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-2 pb-5">
          <div className="flex items-baseline gap-2">
            <span className="text-h2 font-serif text-ink tabular-nums">
              {s.forecast_eom.toLocaleString("vi-VN")}
            </span>
            <span className="text-small text-ink-muted">khách hàng (ước tính)</span>
          </div>
          <p className="text-tiny text-[#B0A698]">
            Dự báo tuyến tính dựa trên tốc độ {s.usage_count} khách trong {s.days_in_billing_month - s.days_remaining} ngày đầu kỳ.
          </p>
          {s.last_aggregated_at && (
            <p className="text-tiny text-[#B0A698]">
              Cập nhật lần cuối: {fmtDateTime(s.last_aggregated_at)}
            </p>
          )}
        </CardContent>
      </Card>

      {s.overage_units > 0 && (
        <Card className="md:col-span-2 border-warning-200 bg-warning-50/30">
          <CardContent className="pt-6">
            <p className="text-body-strong text-warning-700">
              Đã vượt {s.overage_units.toLocaleString("vi-VN")} khách hàng
            </p>
            <p className="text-small text-warning-600">
              Phí vượt sẽ được tính theo định mức gói ({s.current_plan}).
            </p>
          </CardContent>
        </Card>
      )}
    </div>
  );
}

function PlanTab({ s }: { s: SubscriptionState }) {
  return (
    <Card>
      <CardHeader className="pb-3">
        <CardTitle className="flex items-center gap-2">
          <CreditCard className="w-4 h-4 text-brand-500" /> Gói hiện tại
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-3 pb-5">
        <div className="flex items-baseline justify-between">
          <div>
            <p className="text-h2 font-serif text-ink">{s.plan_display_name}</p>
            <p className="text-tiny text-[#B0A698]">Mã: {s.current_plan}</p>
          </div>
          <p className="text-h3 font-serif text-ink tabular-nums">{fmtVnd(s.plan_price_vnd)}</p>
        </div>
        <p className="text-small text-ink-muted">
          Hạn mức cơ bản: {s.plan_quota.toLocaleString("vi-VN")} khách hàng/tháng.
        </p>
      </CardContent>
    </Card>
  );
}

interface UpgradeTabProps {
  s:            SubscriptionState;
  options:      Array<{ code: string; label: string; quota: number; priceVnd: number }>;
  isPending:    boolean;
  isError:      boolean;
  errorMessage?: string;
  onSubmit:     (target: string) => void;
}

function UpgradeTab({ s, options, isPending, isError, errorMessage, onSubmit }: UpgradeTabProps) {
  const [target, setTarget] = useState<string>(options[0]?.code ?? "");

  if (s.pending_upgrade) {
    return (
      <Card className="border-info-200 bg-info-50/30">
        <CardContent className="pt-6 flex items-start gap-3">
          <Clock className="w-5 h-5 text-info-600 mt-0.5" />
          <div className="space-y-1">
            <p className="text-body-strong text-info-700">
              Đang chờ xử lý nâng cấp lên {s.pending_upgrade.requested_plan}
            </p>
            <p className="text-small text-info-600">
              Yêu cầu gửi lúc {fmtDateTime(s.pending_upgrade.requested_at)}.
              Đội ngũ Kaori sẽ liên hệ xác nhận trong 1 ngày làm việc.
            </p>
          </div>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card>
      <CardHeader className="pb-3">
        <CardTitle className="flex items-center gap-2">
          <ArrowUpCircle className="w-4 h-4 text-brand-500" /> Yêu cầu nâng cấp gói
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-4 pb-5">
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          {options.map((opt) => (
            <button
              key={opt.code}
              onClick={() => setTarget(opt.code)}
              className={`text-left p-4 rounded-xl border transition-colors ${
                target === opt.code
                  ? "border-brand-500 bg-brand-50/30"
                  : "border-subtle bg-surface hover:border-brand-300"
              }`}
            >
              <div className="flex items-baseline justify-between">
                <p className="text-body-strong text-ink">{opt.label}</p>
                {target === opt.code && <CheckCircle2 className="w-4 h-4 text-brand-500" />}
              </div>
              <p className="text-tiny text-[#B0A698] mt-1">
                {opt.quota.toLocaleString("vi-VN")} khách hàng • {fmtVnd(opt.priceVnd)}
              </p>
            </button>
          ))}
        </div>
        {isError && (
          <p className="text-small text-danger-600">{errorMessage ?? "Không thể gửi yêu cầu."}</p>
        )}
        <div className="flex justify-end">
          <Button onClick={() => onSubmit(target)} loading={isPending} disabled={!target}>
            Gửi yêu cầu nâng cấp
          </Button>
        </div>
        <p className="text-tiny text-[#B0A698]">
          Yêu cầu sẽ được Kaori xử lý thủ công trong giai đoạn pilot.
        </p>
      </CardContent>
    </Card>
  );
}
