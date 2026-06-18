"use client";

/**
 * P15-S11 — Customer detail (mig 062/063).
 *
 * Two-column layout: left = profile + capability + titles; right = contract
 * list under this customer. GET /api/v1/customers/:id bundles both.
 */

import { useParams } from "next/navigation";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { ArrowLeft, Briefcase, FileSignature, Award, AlertCircle } from "lucide-react";

import { api } from "@/lib/api";
import { Badge, type BadgeTone } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { Button } from "@/components/ui/button";

interface Customer {
  customer_id:        string;
  code:               string;
  customer_name:      string;
  contact_person:     string | null;
  phone:              string | null;
  email:              string | null;
  tax_code:           string | null;
  address:            string | null;
  city:               string | null;
  customer_type:      string;
  industry:           string | null;
  years_in_business:  number | null;
  employees_count:    number | null;
  annual_revenue_vnd: string | null;
  credit_rating:      string | null;
  titles_awards:      string | null;
  certifications:     string | null;
  experience_summary: string | null;
  relationship_tier:  string | null;
  first_contact_date: string | null;
  assigned_account_manager: string | null;
  note:               string | null;
  status:             string;
  created_at:         string;
}

interface Contract {
  contract_id:        string;
  customer_id:        string;
  customer_code:      string | null;
  customer_name:      string | null;
  contract_no:        string;
  contract_type:      string;
  description:        string | null;
  signed_at:          string | null;
  start_at:           string | null;
  end_at:             string | null;
  value_vnd:          string | null;
  currency:           string;
  payment_terms_days: number | null;
  payment_schedule:   string | null;
  status:             string;
  signed_by_customer: string | null;
  signed_by_us:       string | null;
  attachment_uri:     string | null;
  renewal_type:       string | null;
  note:               string | null;
}

interface CustomerDetail {
  customer:  Customer;
  contracts: Contract[];
}

const CONTRACT_STATUS_TONE: Record<string, BadgeTone> = {
  active:       "success",
  draft:        "neutral",
  under_review: "warning",
  expired:      "neutral",
  closed:       "neutral",
  terminated:   "danger",
};

const CONTRACT_TYPE_LABEL: Record<string, string> = {
  license_enterprise: "License Enterprise",
  license_pilot:      "License Pilot",
  framework_msa:      "Khung MSA",
  addon_module:       "Add-on Module",
  custom_solution:    "Custom",
  consulting:         "Tư vấn",
  one_off:            "One-off",
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

export default function CustomerDetailPage() {
  const params = useParams();
  const id = (params?.id as string) ?? "";

  const { data, isLoading, isError } = useQuery<CustomerDetail>({
    queryKey: ["customer", id],
    queryFn:  () => api(`/api/v1/customers/${id}`),
    enabled:  !!id,
  });

  if (isLoading) {
    return (
      <div className="space-y-6">
        <Skeleton className="h-12 w-48" />
        <Skeleton className="h-64" />
      </div>
    );
  }

  if (isError || !data) {
    return (
      <Card className="border-danger-200 bg-danger-50/30">
        <CardContent className="pt-6 text-small text-danger-700 flex items-center gap-2">
          <AlertCircle className="w-4 h-4" /> Không tải được khách hàng. Có thể đã bị xoá hoặc cross-enterprise.
        </CardContent>
      </Card>
    );
  }

  const c = data.customer;

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-3">
        <Link href="/customers">
          <Button variant="ghost"><ArrowLeft className="w-4 h-4 mr-1" /> Danh sách</Button>
        </Link>
        <div>
          <h1 className="text-h1 font-serif text-ink flex items-center gap-2">
            <Briefcase className="w-5 h-5 text-brand-500" />
            {c.customer_name}
          </h1>
          <p className="text-tiny text-ink-muted font-mono mt-0.5">{c.code}</p>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Profile column */}
        <div className="lg:col-span-1 space-y-4">
          <Card>
            <CardContent className="pt-5 space-y-3">
              <h3 className="text-body-strong text-ink">Thông tin cơ bản</h3>
              <Field label="Người liên hệ" value={c.contact_person} />
              <Field label="Email" value={c.email} mono />
              <Field label="Điện thoại" value={c.phone} mono />
              <Field label="MST" value={c.tax_code} mono />
              <Field label="Địa chỉ" value={c.address} />
              <Field label="Thành phố" value={c.city} />
            </CardContent>
          </Card>

          <Card>
            <CardContent className="pt-5 space-y-3">
              <h3 className="text-body-strong text-ink">Phân loại</h3>
              <Field label="Loại KH" value={c.customer_type} />
              <Field label="Ngành" value={c.industry} />
              <Field label="Tier" value={c.relationship_tier} />
              <Field label="AM phụ trách" value={c.assigned_account_manager} mono />
              <Field label="Lần đầu liên hệ" value={fmtDate(c.first_contact_date)} />
            </CardContent>
          </Card>
        </div>

        {/* Capability + contracts column */}
        <div className="lg:col-span-2 space-y-4">
          <Card>
            <CardContent className="pt-5 space-y-3">
              <h3 className="text-body-strong text-ink flex items-center gap-2">
                <Award className="w-4 h-4 text-brand-500" /> Năng lực + danh hiệu
              </h3>
              <div className="grid grid-cols-2 gap-3">
                <Field label="Số năm hoạt động" value={c.years_in_business?.toString() ?? null} />
                <Field label="Số nhân viên" value={c.employees_count?.toLocaleString("vi-VN") ?? null} />
                <Field label="Doanh thu/năm" value={fmtVnd(c.annual_revenue_vnd)} />
                <Field label="Tín dụng" value={c.credit_rating} />
              </div>
              <Field label="Danh hiệu / giải thưởng" value={c.titles_awards} multiline />
              <Field label="Chứng nhận" value={c.certifications} multiline />
              <Field label="Tổng quan kinh nghiệm" value={c.experience_summary} multiline />
              {c.note && <Field label="Ghi chú" value={c.note} multiline />}
            </CardContent>
          </Card>

          <Card>
            <CardContent className="pt-5 space-y-3">
              <h3 className="text-body-strong text-ink flex items-center gap-2">
                <FileSignature className="w-4 h-4 text-brand-500" /> Hợp đồng ({data.contracts.length})
              </h3>
              {data.contracts.length === 0 ? (
                <p className="text-tiny text-[#B0A698]">Chưa có hợp đồng nào với khách hàng này.</p>
              ) : (
                <div className="space-y-2">
                  {data.contracts.map((ct) => (
                    <div key={ct.contract_id} className="rounded-xl border border-subtle p-3 hover:border-brand-200 transition-colors">
                      <div className="flex items-start justify-between gap-3">
                        <div className="min-w-0 flex-1">
                          <div className="flex items-center gap-2 flex-wrap">
                            <span className="text-tiny font-mono text-brand-600">{ct.contract_no}</span>
                            <Badge tone="neutral">{CONTRACT_TYPE_LABEL[ct.contract_type] ?? ct.contract_type}</Badge>
                            <Badge tone={CONTRACT_STATUS_TONE[ct.status] ?? "neutral"}>{ct.status}</Badge>
                            {ct.renewal_type === "auto_renew" && <Badge tone="info">auto-renew</Badge>}
                          </div>
                          {ct.description && <p className="text-small text-ink mt-1">{ct.description}</p>}
                          <div className="grid grid-cols-3 gap-x-4 gap-y-1 mt-2 text-tiny text-ink-muted">
                            <div><span className="text-[#B0A698]">Giá trị:</span> <span className="tabular-nums text-ink">{fmtVnd(ct.value_vnd, ct.currency)}</span></div>
                            <div><span className="text-[#B0A698]">Thanh toán:</span> {ct.payment_schedule ?? "—"}{ct.payment_terms_days ? ` (${ct.payment_terms_days}d)` : ""}</div>
                            <div><span className="text-[#B0A698]">Hiệu lực:</span> {fmtDate(ct.start_at)} → {fmtDate(ct.end_at)}</div>
                          </div>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}

function Field({ label, value, mono, multiline }: {
  label: string; value: string | null; mono?: boolean; multiline?: boolean;
}) {
  return (
    <div className="space-y-0.5">
      <p className="text-tiny text-[#B0A698] uppercase tracking-wider">{label}</p>
      <p className={`text-small text-ink ${mono ? "font-mono" : ""} ${multiline ? "whitespace-pre-line" : "truncate"}`}>
        {value || "—"}
      </p>
    </div>
  );
}
