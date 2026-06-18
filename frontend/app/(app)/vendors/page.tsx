"use client";

/**
 * P15-S11 — Vendor list (mig 062/063). Mirrors /customers shape with
 * vendor_type vocab (supplier/platform/consultant/agency/contractor) +
 * reliability_tier instead of relationship_tier.
 */

import { useMemo, useState } from "react";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { Building2, AlertCircle, ShieldQuestion } from "lucide-react";

import { api } from "@/lib/api";
import { DataTable, type Column } from "@/components/ui/data-table";
import { Badge, type BadgeTone } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { EmptyState } from "@/components/ui/empty-state";

type VendorType      = "supplier" | "platform" | "consultant" | "agency" | "contractor";
type ReliabilityTier = "platinum" | "gold" | "silver" | "bronze";

interface Vendor {
  vendor_id:          string;
  code:               string;
  vendor_name:        string;
  contact_person:     string | null;
  email:              string | null;
  phone:              string | null;
  country:            string;
  vendor_type:        VendorType;
  services_offered:   string | null;
  industries_served:  string | null;
  annual_revenue_vnd: string | null;
  credit_rating:      string | null;
  reliability_tier:   ReliabilityTier | null;
  managed_by:         string | null;
  status:             string;
  created_at:         string;
}

const VENDOR_TYPE_LABEL: Record<VendorType, string> = {
  supplier:   "Cung ứng",
  platform:   "Nền tảng",
  consultant: "Tư vấn",
  agency:     "Agency",
  contractor: "Nhà thầu",
};

const TIER_TONE: Record<ReliabilityTier, BadgeTone> = {
  platinum: "brand",
  gold:     "warning",
  silver:   "info",
  bronze:   "neutral",
};

function fmtVnd(s: string | null): string {
  if (!s) return "—";
  const n = Number(s);
  if (!Number.isFinite(n)) return s;
  if (n >= 1_000_000_000) return `${(n / 1_000_000_000).toFixed(1)} tỷ ₫`;
  if (n >= 1_000_000)     return `${(n / 1_000_000).toFixed(0)} triệu ₫`;
  return `${n.toLocaleString("vi-VN")} ₫`;
}

export default function VendorsPage() {
  const [statusFilter, setStatusFilter] = useState<string>("active");
  const [typeFilter,   setTypeFilter]   = useState<string>("");
  const [tierFilter,   setTierFilter]   = useState<string>("");

  const { data, isLoading, isError } = useQuery<Vendor[]>({
    queryKey: ["vendors", statusFilter, typeFilter, tierFilter],
    queryFn: () => {
      const params = new URLSearchParams();
      if (statusFilter) params.set("status", statusFilter);
      if (typeFilter)   params.set("vendor_type", typeFilter);
      if (tierFilter)   params.set("reliability_tier", tierFilter);
      return api(`/api/v1/vendors?${params}`);
    },
    staleTime: 60_000,
  });

  const COLUMNS: Column<Vendor>[] = useMemo(() => [
    {
      key: "code",
      header: "Mã NCC",
      render: (r) => (
        <Link href={`/vendors/${r.vendor_id}`} className="text-tiny font-mono text-brand-600 hover:underline">
          {r.code}
        </Link>
      ),
    },
    {
      key: "vendor_name",
      header: "Nhà cung cấp",
      render: (r) => (
        <div className="min-w-0">
          <Link href={`/vendors/${r.vendor_id}`} className="text-body-strong text-ink hover:text-brand-500 truncate block">
            {r.vendor_name}
          </Link>
          <p className="text-tiny text-[#B0A698] truncate">
            {r.contact_person ?? "—"}{r.email ? ` · ${r.email}` : ""}
          </p>
        </div>
      ),
    },
    {
      key: "vendor_type",
      header: "Loại",
      render: (r) => <Badge tone="neutral">{VENDOR_TYPE_LABEL[r.vendor_type] ?? r.vendor_type}</Badge>,
    },
    {
      key: "services_offered",
      header: "Dịch vụ",
      render: (r) => <span className="text-tiny text-ink-muted truncate block max-w-[200px]">{r.services_offered ?? "—"}</span>,
    },
    {
      key: "country",
      header: "Quốc gia",
      render: (r) => <span className="text-tiny tabular-nums">{r.country}</span>,
    },
    {
      key: "credit_rating",
      header: "Tín dụng",
      render: (r) => r.credit_rating
        ? <Badge tone={r.credit_rating.startsWith("A") ? "success" : r.credit_rating.startsWith("B") ? "warning" : "neutral"}>{r.credit_rating}</Badge>
        : <span className="text-tiny text-[#B0A698]">—</span>,
    },
    {
      key: "reliability_tier",
      header: "Tier",
      render: (r) => r.reliability_tier
        ? <Badge tone={TIER_TONE[r.reliability_tier]}>{r.reliability_tier}</Badge>
        : <span className="text-tiny text-[#B0A698]">—</span>,
    },
    {
      key: "managed_by",
      header: "Phụ trách",
      render: (r) => <span className="text-tiny text-ink-muted">{r.managed_by ?? "—"}</span>,
    },
  ], []);

  return (
    <div className="space-y-6">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h1 className="text-h1 font-serif text-ink flex items-center gap-3">
            <Building2 className="w-6 h-6 text-brand-500" />
            Nhà cung cấp
          </h1>
          <p className="text-small text-ink-muted mt-1">
            Danh sách vendor + dịch vụ, chứng nhận, độ tin cậy. Mig 062 — pilot Vingroup demo.
          </p>
        </div>
      </div>

      <Card>
        <CardContent className="pt-4 pb-4">
          <div className="flex items-center gap-4 flex-wrap">
            <FilterSelect label="Trạng thái" value={statusFilter} onChange={setStatusFilter}
              options={[
                { value: "", label: "Tất cả" },
                { value: "active", label: "Đang hoạt động" },
                { value: "inactive", label: "Tạm ngưng" },
                { value: "archived", label: "Đã lưu trữ" },
              ]} />
            <FilterSelect label="Loại NCC" value={typeFilter} onChange={setTypeFilter}
              options={[
                { value: "", label: "Tất cả" },
                { value: "supplier", label: "Cung ứng" },
                { value: "platform", label: "Nền tảng" },
                { value: "consultant", label: "Tư vấn" },
                { value: "agency", label: "Agency" },
                { value: "contractor", label: "Nhà thầu" },
              ]} />
            <FilterSelect label="Tier" value={tierFilter} onChange={setTierFilter}
              options={[
                { value: "", label: "Tất cả" },
                { value: "platinum", label: "Platinum" },
                { value: "gold", label: "Gold" },
                { value: "silver", label: "Silver" },
                { value: "bronze", label: "Bronze" },
              ]} />
          </div>
        </CardContent>
      </Card>

      {isLoading && <div className="space-y-3">{Array.from({ length: 6 }).map((_, i) => <Skeleton key={i} className="h-14" />)}</div>}

      {isError && (
        <Card className="border-danger-200 bg-danger-50/30">
          <CardContent className="pt-6 text-small text-danger-700 flex items-center gap-2">
            <AlertCircle className="w-4 h-4" /> Lỗi khi tải vendor.
          </CardContent>
        </Card>
      )}

      {!isLoading && !isError && (data ?? []).length === 0 && (
        <EmptyState icon={ShieldQuestion} title="Chưa có nhà cung cấp" description="Đổi bộ lọc hoặc thêm vendor mới." />
      )}

      {!isLoading && !isError && (data ?? []).length > 0 && (
        <DataTable<Vendor> columns={COLUMNS} rows={data ?? []} emptyMessage="Không có vendor nào khớp bộ lọc." />
      )}
    </div>
  );
}

function FilterSelect({ label, value, onChange, options }: {
  label: string; value: string; onChange: (v: string) => void;
  options: Array<{ value: string; label: string }>;
}) {
  return (
    <label className="flex items-center gap-2 text-tiny text-ink-muted">
      {label}:
      <select value={value} onChange={(e) => onChange(e.target.value)}
        className="px-2 py-1 rounded-md border border-subtle bg-surface text-tiny focus:outline-none focus:ring-2 focus:ring-brand-300">
        {options.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
      </select>
    </label>
  );
}
