"use client";

/**
 * P15-S11 — Customer list (mig 062/063).
 *
 * Read-only list with filters (status / customer_type / relationship_tier).
 * Click row → /customers/[id] detail with contract list.
 *
 * Endpoints:
 *   GET /api/v1/customers
 *   GET /api/v1/customers/:id  (used on detail page)
 *
 * No CRUD on this page yet — pilot validates the data shape first; create/
 * edit/archive land in a follow-up commit when the FE templates exist.
 */

import { useMemo, useState } from "react";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { Briefcase, Award, AlertCircle } from "lucide-react";

import { api } from "@/lib/api";
import { DataTable, type Column } from "@/components/ui/data-table";
import { Badge, type BadgeTone } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { EmptyState } from "@/components/ui/empty-state";

type CustomerType     = "individual" | "SMB" | "enterprise" | "strategic";
type RelationshipTier = "platinum" | "gold" | "silver" | "bronze";

interface Customer {
  customer_id:        string;
  code:               string;
  customer_name:      string;
  contact_person:     string | null;
  email:              string | null;
  phone:              string | null;
  customer_type:      CustomerType;
  industry:           string | null;
  annual_revenue_vnd: string | null;   // Decimal serialised
  credit_rating:      string | null;
  relationship_tier:  RelationshipTier | null;
  assigned_account_manager: string | null;
  status:             string;
  created_at:         string;
}

const TYPE_LABEL: Record<CustomerType, string> = {
  individual: "Cá nhân",
  SMB:        "SMB",
  enterprise: "Enterprise",
  strategic:  "Chiến lược",
};

const TIER_TONE: Record<RelationshipTier, BadgeTone> = {
  platinum: "brand",
  gold:     "warning",
  silver:   "info",
  bronze:   "neutral",
};

const TIER_LABEL: Record<RelationshipTier, string> = {
  platinum: "Platinum",
  gold:     "Gold",
  silver:   "Silver",
  bronze:   "Bronze",
};

function fmtVnd(s: string | null): string {
  if (!s) return "—";
  const n = Number(s);
  if (!Number.isFinite(n)) return s;
  if (n >= 1_000_000_000) return `${(n / 1_000_000_000).toFixed(1)} tỷ ₫`;
  if (n >= 1_000_000)     return `${(n / 1_000_000).toFixed(0)} triệu ₫`;
  return `${n.toLocaleString("vi-VN")} ₫`;
}

export default function CustomersPage() {
  const [statusFilter, setStatusFilter] = useState<string>("active");
  const [typeFilter,   setTypeFilter]   = useState<string>("");
  const [tierFilter,   setTierFilter]   = useState<string>("");

  const { data, isLoading, isError } = useQuery<Customer[]>({
    queryKey: ["customers", statusFilter, typeFilter, tierFilter],
    queryFn: () => {
      const params = new URLSearchParams();
      if (statusFilter) params.set("status", statusFilter);
      if (typeFilter)   params.set("customer_type", typeFilter);
      if (tierFilter)   params.set("relationship_tier", tierFilter);
      return api(`/api/v1/customers?${params}`);
    },
    staleTime: 60_000,
  });

  const COLUMNS: Column<Customer>[] = useMemo(() => [
    {
      key: "code",
      header: "Mã KH",
      render: (r) => (
        <Link href={`/customers/${r.customer_id}`} className="text-tiny font-mono text-brand-600 hover:underline">
          {r.code}
        </Link>
      ),
    },
    {
      key: "customer_name",
      header: "Khách hàng",
      render: (r) => (
        <div className="min-w-0">
          <Link href={`/customers/${r.customer_id}`} className="text-body-strong text-ink hover:text-brand-500 truncate block">
            {r.customer_name}
          </Link>
          <p className="text-tiny text-[#B0A698] truncate">
            {r.contact_person ?? "—"}{r.email ? ` · ${r.email}` : ""}
          </p>
        </div>
      ),
    },
    {
      key: "customer_type",
      header: "Loại",
      render: (r) => <Badge tone="neutral">{TYPE_LABEL[r.customer_type] ?? r.customer_type}</Badge>,
    },
    {
      key: "industry",
      header: "Ngành",
      render: (r) => <span className="text-tiny text-ink-muted">{r.industry ?? "—"}</span>,
    },
    {
      key: "annual_revenue_vnd",
      header: "Doanh thu/năm",
      render: (r) => <span className="text-tiny tabular-nums">{fmtVnd(r.annual_revenue_vnd)}</span>,
    },
    {
      key: "credit_rating",
      header: "Tín dụng",
      render: (r) => r.credit_rating
        ? <Badge tone={r.credit_rating.startsWith("A") ? "success" : r.credit_rating.startsWith("B") ? "warning" : "neutral"}>{r.credit_rating}</Badge>
        : <span className="text-tiny text-[#B0A698]">—</span>,
    },
    {
      key: "relationship_tier",
      header: "Tier",
      render: (r) => r.relationship_tier
        ? <Badge tone={TIER_TONE[r.relationship_tier]}>{TIER_LABEL[r.relationship_tier]}</Badge>
        : <span className="text-tiny text-[#B0A698]">—</span>,
    },
    {
      key: "assigned_account_manager",
      header: "AM",
      render: (r) => <span className="text-tiny text-ink-muted">{r.assigned_account_manager ?? "—"}</span>,
    },
  ], []);

  return (
    <div className="space-y-6">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h1 className="text-h1 font-serif text-ink flex items-center gap-3">
            <Briefcase className="w-6 h-6 text-brand-500" />
            Khách hàng
          </h1>
          <p className="text-small text-ink-muted mt-1">
            Danh sách khách hàng + thông tin doanh thu, tín dụng, danh hiệu. Mig 062 — pilot Vingroup demo.
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
                { value: "blacklisted", label: "Blacklist" },
              ]} />
            <FilterSelect label="Loại KH" value={typeFilter} onChange={setTypeFilter}
              options={[
                { value: "", label: "Tất cả" },
                { value: "strategic", label: "Chiến lược" },
                { value: "enterprise", label: "Enterprise" },
                { value: "SMB", label: "SMB" },
                { value: "individual", label: "Cá nhân" },
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

      {isLoading && (
        <div className="space-y-3">
          {Array.from({ length: 6 }).map((_, i) => <Skeleton key={i} className="h-14" />)}
        </div>
      )}

      {isError && (
        <Card className="border-danger-200 bg-danger-50/30">
          <CardContent className="pt-6 text-small text-danger-700 flex items-center gap-2">
            <AlertCircle className="w-4 h-4" /> Lỗi khi tải khách hàng. Reload trang để thử lại.
          </CardContent>
        </Card>
      )}

      {!isLoading && !isError && (data ?? []).length === 0 && (
        <EmptyState
          icon={Award}
          title="Chưa có khách hàng nào"
          description="Đổi bộ lọc hoặc thêm khách hàng mới."
        />
      )}

      {!isLoading && !isError && (data ?? []).length > 0 && (
        <DataTable<Customer>
          columns={COLUMNS}
          rows={data ?? []}
          emptyMessage="Không có khách hàng nào khớp bộ lọc."
        />
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
      <select
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="px-2 py-1 rounded-md border border-subtle bg-surface text-tiny focus:outline-none focus:ring-2 focus:ring-brand-300"
      >
        {options.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
      </select>
    </label>
  );
}
