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
import { useT } from "@/lib/i18n/provider";

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

const VENDOR_TYPE_KEY: Record<VendorType, string> = {
  supplier:   "vendorsPage.typeSupplier",
  platform:   "vendorsPage.typePlatform",
  consultant: "vendorsPage.typeConsultant",
  agency:     "vendorsPage.typeAgency",
  contractor: "vendorsPage.typeContractor",
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
  const t = useT();
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
      header: t("vendorsPage.colCode"),
      render: (r) => (
        <Link href={`/vendors/${r.vendor_id}`} className="text-tiny font-mono text-brand-600 hover:underline">
          {r.code}
        </Link>
      ),
    },
    {
      key: "vendor_name",
      header: t("vendorsPage.colVendorName"),
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
      header: t("vendorsPage.colType"),
      render: (r) => <Badge tone="neutral">{r.vendor_type in VENDOR_TYPE_KEY ? t(VENDOR_TYPE_KEY[r.vendor_type]) : r.vendor_type}</Badge>,
    },
    {
      key: "services_offered",
      header: t("vendorsPage.colServices"),
      render: (r) => <span className="text-tiny text-ink-muted truncate block max-w-[200px]">{r.services_offered ?? "—"}</span>,
    },
    {
      key: "country",
      header: t("vendorsPage.colCountry"),
      render: (r) => <span className="text-tiny tabular-nums">{r.country}</span>,
    },
    {
      key: "credit_rating",
      header: t("vendorsPage.colCredit"),
      render: (r) => r.credit_rating
        ? <Badge tone={r.credit_rating.startsWith("A") ? "success" : r.credit_rating.startsWith("B") ? "warning" : "neutral"}>{r.credit_rating}</Badge>
        : <span className="text-tiny text-[#B0A698]">—</span>,
    },
    {
      key: "reliability_tier",
      header: t("vendorsPage.colTier"),
      render: (r) => r.reliability_tier
        ? <Badge tone={TIER_TONE[r.reliability_tier]}>{r.reliability_tier}</Badge>
        : <span className="text-tiny text-[#B0A698]">—</span>,
    },
    {
      key: "managed_by",
      header: t("vendorsPage.colManagedBy"),
      render: (r) => <span className="text-tiny text-ink-muted">{r.managed_by ?? "—"}</span>,
    },
  ], [t]);

  return (
    <div className="space-y-6">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h1 className="text-h1 font-serif text-ink flex items-center gap-3">
            <Building2 className="w-6 h-6 text-brand-500" />
            {t("vendorsPage.title")}
          </h1>
          <p className="text-small text-ink-muted mt-1">
            {t("vendorsPage.subtitle")}
          </p>
        </div>
      </div>

      <Card>
        <CardContent className="pt-4 pb-4">
          <div className="flex items-center gap-4 flex-wrap">
            <FilterSelect label={t("vendorsPage.filterStatus")} value={statusFilter} onChange={setStatusFilter}
              options={[
                { value: "", label: t("vendorsPage.optAll") },
                { value: "active", label: t("vendorsPage.optActive") },
                { value: "inactive", label: t("vendorsPage.optInactive") },
                { value: "archived", label: t("vendorsPage.optArchived") },
              ]} />
            <FilterSelect label={t("vendorsPage.filterType")} value={typeFilter} onChange={setTypeFilter}
              options={[
                { value: "", label: t("vendorsPage.optAll") },
                { value: "supplier", label: t("vendorsPage.typeSupplier") },
                { value: "platform", label: t("vendorsPage.typePlatform") },
                { value: "consultant", label: t("vendorsPage.typeConsultant") },
                { value: "agency", label: t("vendorsPage.typeAgency") },
                { value: "contractor", label: t("vendorsPage.typeContractor") },
              ]} />
            <FilterSelect label={t("vendorsPage.filterTier")} value={tierFilter} onChange={setTierFilter}
              options={[
                { value: "", label: t("vendorsPage.optAll") },
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
            <AlertCircle className="w-4 h-4" /> {t("vendorsPage.errLoad")}
          </CardContent>
        </Card>
      )}

      {!isLoading && !isError && (data ?? []).length === 0 && (
        <EmptyState icon={ShieldQuestion} title={t("vendorsPage.emptyTitle")} description={t("vendorsPage.emptyDesc")} />
      )}

      {!isLoading && !isError && (data ?? []).length > 0 && (
        <DataTable<Vendor> columns={COLUMNS} rows={data ?? []} emptyMessage={t("vendorsPage.emptyFiltered")} />
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
