"use client";

/**
 * P15-S11 — Combined contracts list (mig 062/063). Tabs split customer
 * vs vendor contracts; filters per tab. Click rows → respective parent
 * detail page (customer or vendor).
 */

import { useMemo, useState } from "react";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { FileSignature, AlertCircle, FileBox } from "lucide-react";

import { api } from "@/lib/api";
import { DataTable, type Column } from "@/components/ui/data-table";
import { Badge, type BadgeTone } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { EmptyState } from "@/components/ui/empty-state";
import { useT } from "@/lib/i18n/provider";

interface CustomerContract {
  contract_id:   string;
  customer_id:   string;
  customer_code: string | null;
  customer_name: string | null;
  contract_no:   string;
  contract_type: string;
  description:   string | null;
  signed_at:     string | null;
  start_at:      string | null;
  end_at:        string | null;
  value_vnd:     string | null;
  currency:      string;
  payment_terms_days: number | null;
  status:        string;
  renewal_type:  string | null;
}

interface VendorContract {
  contract_id:   string;
  vendor_id:     string;
  vendor_code:   string | null;
  vendor_name:   string | null;
  contract_no:   string;
  contract_type: string;
  description:   string | null;
  signed_at:     string | null;
  start_at:      string | null;
  end_at:        string | null;
  value_vnd:     string | null;
  currency:      string;
  payment_terms_days: number | null;
  status:        string;
  renewal_type:  string | null;
}

const CONTRACT_STATUS_TONE: Record<string, BadgeTone> = {
  active: "success", draft: "neutral", under_review: "warning",
  expired: "neutral", closed: "neutral", terminated: "danger",
};

function fmtVnd(s: string | null, currency: string = "VND"): string {
  if (!s) return "—";
  const n = Number(s);
  if (!Number.isFinite(n)) return s;
  if (currency === "USD") return `$${n.toLocaleString("en-US")}`;
  if (n >= 1_000_000_000) return `${(n / 1_000_000_000).toFixed(1)} tỷ ₫`;
  if (n >= 1_000_000)     return `${(n / 1_000_000).toFixed(0)} triệu ₫`;
  return `${n.toLocaleString("vi-VN")} ₫`;
}

function fmtDate(s: string | null): string {
  if (!s) return "—";
  return new Date(s).toLocaleDateString("vi-VN", { day: "2-digit", month: "2-digit", year: "numeric" });
}

export default function ContractsPage() {
  const t = useT();
  const [tab, setTab] = useState<"customer" | "vendor">("customer");
  const [statusFilter, setStatusFilter] = useState<string>("active");

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-h1 font-serif text-ink flex items-center gap-3">
          <FileSignature className="w-6 h-6 text-brand-500" />
          {t('contractsPage.title')}
        </h1>
        <p className="text-small text-ink-muted mt-1">
          {t('contractsPage.subtitle')}
        </p>
      </div>

      <div className="flex items-center gap-1 border-b border-subtle">
        <button
          onClick={() => setTab("customer")}
          className={`px-4 py-2 text-small font-medium border-b-2 -mb-px transition-colors ${
            tab === "customer" ? "border-brand-500 text-ink" : "border-transparent text-ink-muted hover:text-ink"
          }`}
        >
          {t('contractsPage.tabCustomer')}
        </button>
        <button
          onClick={() => setTab("vendor")}
          className={`px-4 py-2 text-small font-medium border-b-2 -mb-px transition-colors ${
            tab === "vendor" ? "border-brand-500 text-ink" : "border-transparent text-ink-muted hover:text-ink"
          }`}
        >
          {t('contractsPage.tabVendor')}
        </button>
      </div>

      <Card>
        <CardContent className="pt-4 pb-4">
          <label className="flex items-center gap-2 text-tiny text-ink-muted">
            {t('contractsPage.statusLabel')}
            <select value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)}
              className="px-2 py-1 rounded-md border border-subtle bg-surface text-tiny focus:outline-none focus:ring-2 focus:ring-brand-300">
              <option value="">{t('contractsPage.statusAll')}</option>
              <option value="active">{t('contractsPage.statusActive')}</option>
              <option value="draft">{t('contractsPage.statusDraft')}</option>
              <option value="under_review">{t('contractsPage.statusUnderReview')}</option>
              <option value="expired">{t('contractsPage.statusExpired')}</option>
              <option value="closed">{t('contractsPage.statusClosed')}</option>
              <option value="terminated">{t('contractsPage.statusTerminated')}</option>
            </select>
          </label>
        </CardContent>
      </Card>

      {tab === "customer" ? <CustomerContractsList statusFilter={statusFilter} /> : <VendorContractsList statusFilter={statusFilter} />}
    </div>
  );
}


function CustomerContractsList({ statusFilter }: { statusFilter: string }) {
  const t = useT();
  const { data, isLoading, isError } = useQuery<CustomerContract[]>({
    queryKey: ["customer-contracts", statusFilter],
    queryFn: () => {
      const params = new URLSearchParams();
      if (statusFilter) params.set("status", statusFilter);
      return api(`/api/v1/customer-contracts?${params}`);
    },
    staleTime: 60_000,
  });

  const COLUMNS: Column<CustomerContract>[] = useMemo(() => [
    {
      key: "contract_no",
      header: t('contractsPage.colContractNo'),
      render: (r) => <span className="text-tiny font-mono text-brand-600">{r.contract_no}</span>,
    },
    {
      key: "customer_name",
      header: t('contractsPage.colCustomer'),
      render: (r) => (
        <Link href={`/customers/${r.customer_id}`} className="text-tiny text-ink hover:text-brand-500 truncate block">
          {r.customer_name ?? "—"}
        </Link>
      ),
    },
    { key: "contract_type", header: t('contractsPage.colType'), render: (r) => <Badge tone="neutral">{r.contract_type}</Badge> },
    { key: "value_vnd",  header: t('contractsPage.colValue'), render: (r) => <span className="text-tiny tabular-nums">{fmtVnd(r.value_vnd, r.currency)}</span> },
    { key: "start_at",   header: t('contractsPage.colStart'), render: (r) => <span className="text-tiny tabular-nums">{fmtDate(r.start_at)}</span> },
    { key: "end_at",     header: t('contractsPage.colEnd'), render: (r) => <span className="text-tiny tabular-nums">{fmtDate(r.end_at)}</span> },
    { key: "status",     header: t('contractsPage.colStatus'), render: (r) => <Badge tone={CONTRACT_STATUS_TONE[r.status] ?? "neutral"}>{r.status}</Badge> },
    { key: "renewal_type", header: t('contractsPage.colRenewal'), render: (r) => <span className="text-tiny text-ink-muted">{r.renewal_type ?? "—"}</span> },
  ], [t]);

  return <ContractTable data={data} isLoading={isLoading} isError={isError} columns={COLUMNS} />;
}


function VendorContractsList({ statusFilter }: { statusFilter: string }) {
  const t = useT();
  const { data, isLoading, isError } = useQuery<VendorContract[]>({
    queryKey: ["vendor-contracts", statusFilter],
    queryFn: () => {
      const params = new URLSearchParams();
      if (statusFilter) params.set("status", statusFilter);
      return api(`/api/v1/vendor-contracts?${params}`);
    },
    staleTime: 60_000,
  });

  const COLUMNS: Column<VendorContract>[] = useMemo(() => [
    {
      key: "contract_no",
      header: t('contractsPage.colContractNo'),
      render: (r) => <span className="text-tiny font-mono text-brand-600">{r.contract_no}</span>,
    },
    {
      key: "vendor_name",
      header: t('contractsPage.colVendor'),
      render: (r) => (
        <Link href={`/vendors/${r.vendor_id}`} className="text-tiny text-ink hover:text-brand-500 truncate block">
          {r.vendor_name ?? "—"}
        </Link>
      ),
    },
    { key: "contract_type", header: t('contractsPage.colType'), render: (r) => <Badge tone="neutral">{r.contract_type}</Badge> },
    { key: "value_vnd",  header: t('contractsPage.colValue'), render: (r) => <span className="text-tiny tabular-nums">{fmtVnd(r.value_vnd, r.currency)}</span> },
    { key: "start_at",   header: t('contractsPage.colStart'), render: (r) => <span className="text-tiny tabular-nums">{fmtDate(r.start_at)}</span> },
    { key: "end_at",     header: t('contractsPage.colEnd'), render: (r) => <span className="text-tiny tabular-nums">{fmtDate(r.end_at)}</span> },
    { key: "status",     header: t('contractsPage.colStatus'), render: (r) => <Badge tone={CONTRACT_STATUS_TONE[r.status] ?? "neutral"}>{r.status}</Badge> },
    { key: "renewal_type", header: t('contractsPage.colRenewal'), render: (r) => <span className="text-tiny text-ink-muted">{r.renewal_type ?? "—"}</span> },
  ], [t]);

  return <ContractTable data={data} isLoading={isLoading} isError={isError} columns={COLUMNS} />;
}


function ContractTable<T extends { contract_id: string }>({
  data, isLoading, isError, columns,
}: {
  data: T[] | undefined; isLoading: boolean; isError: boolean; columns: Column<T>[];
}) {
  const t = useT();
  if (isLoading) return <div className="space-y-3">{Array.from({ length: 6 }).map((_, i) => <Skeleton key={i} className="h-14" />)}</div>;
  if (isError) return (
    <Card className="border-danger-200 bg-danger-50/30">
      <CardContent className="pt-6 text-small text-danger-700 flex items-center gap-2">
        <AlertCircle className="w-4 h-4" /> {t('contractsPage.errLoad')}
      </CardContent>
    </Card>
  );
  if ((data ?? []).length === 0) return <EmptyState icon={FileBox} title={t('contractsPage.emptyTitle')} description={t('contractsPage.emptyDesc')} />;
  return <DataTable<T> columns={columns} rows={data ?? []} emptyMessage={t('contractsPage.emptyMessage')} />;
}
