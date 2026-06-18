"use client";

/**
 * P15-S11 — Vendor detail (mig 062/063). Mirrors /customers/[id] but with
 * vendor_type vocab + reliability_tier + the vendor-contract columns.
 */

import { useParams } from "next/navigation";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { ArrowLeft, Building2, FileSignature, Award, AlertCircle } from "lucide-react";

import { api } from "@/lib/api";
import { Badge, type BadgeTone } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { Button } from "@/components/ui/button";

interface Vendor {
  vendor_id:          string;
  code:               string;
  vendor_name:        string;
  contact_person:     string | null;
  phone:              string | null;
  email:              string | null;
  tax_code:           string | null;
  address:            string | null;
  city:               string | null;
  country:            string;
  vendor_type:        string;
  services_offered:   string | null;
  industries_served:  string | null;
  years_in_business:  number | null;
  employees_count:    number | null;
  annual_revenue_vnd: string | null;
  credit_rating:      string | null;
  certifications:     string | null;
  titles_awards:      string | null;
  experience_summary: string | null;
  reliability_tier:   string | null;
  first_contract_date: string | null;
  managed_by:         string | null;
  note:               string | null;
  status:             string;
  created_at:         string;
}

interface Contract {
  contract_id:        string;
  vendor_id:          string;
  vendor_code:        string | null;
  vendor_name:        string | null;
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
  signed_by_vendor:   string | null;
  signed_by_us:       string | null;
  attachment_uri:     string | null;
  renewal_type:       string | null;
  note:               string | null;
}

interface VendorDetail { vendor: Vendor; contracts: Contract[]; }

const CONTRACT_STATUS_TONE: Record<string, BadgeTone> = {
  active: "success", draft: "neutral", under_review: "warning",
  expired: "neutral", closed: "neutral", terminated: "danger",
};

const VENDOR_CONTRACT_TYPE_LABEL: Record<string, string> = {
  framework_msa:     "MSA",
  sow_under_msa:     "SOW (dưới MSA)",
  saas_subscription: "SaaS",
  api_subscription:  "API",
  consulting:        "Tư vấn",
  outsourcing:       "Outsourcing",
  banking_services:  "Ngân hàng",
  one_off_project:   "One-off",
  recurring_po:      "PO định kỳ",
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

export default function VendorDetailPage() {
  const params = useParams();
  const id = (params?.id as string) ?? "";

  const { data, isLoading, isError } = useQuery<VendorDetail>({
    queryKey: ["vendor", id],
    queryFn:  () => api(`/api/v1/vendors/${id}`),
    enabled:  !!id,
  });

  if (isLoading) return <div className="space-y-6"><Skeleton className="h-12 w-48" /><Skeleton className="h-64" /></div>;

  if (isError || !data) {
    return (
      <Card className="border-danger-200 bg-danger-50/30">
        <CardContent className="pt-6 text-small text-danger-700 flex items-center gap-2">
          <AlertCircle className="w-4 h-4" /> Không tải được nhà cung cấp.
        </CardContent>
      </Card>
    );
  }

  const v = data.vendor;

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-3">
        <Link href="/vendors"><Button variant="ghost"><ArrowLeft className="w-4 h-4 mr-1" /> Danh sách</Button></Link>
        <div>
          <h1 className="text-h1 font-serif text-ink flex items-center gap-2">
            <Building2 className="w-5 h-5 text-brand-500" />
            {v.vendor_name}
          </h1>
          <p className="text-tiny text-ink-muted font-mono mt-0.5">{v.code}</p>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-1 space-y-4">
          <Card>
            <CardContent className="pt-5 space-y-3">
              <h3 className="text-body-strong text-ink">Thông tin cơ bản</h3>
              <Field label="Người liên hệ" value={v.contact_person} />
              <Field label="Email" value={v.email} mono />
              <Field label="Điện thoại" value={v.phone} mono />
              <Field label="MST" value={v.tax_code} mono />
              <Field label="Địa chỉ" value={v.address} />
              <Field label="Thành phố" value={v.city} />
              <Field label="Quốc gia" value={v.country} mono />
            </CardContent>
          </Card>

          <Card>
            <CardContent className="pt-5 space-y-3">
              <h3 className="text-body-strong text-ink">Phân loại</h3>
              <Field label="Loại NCC" value={v.vendor_type} />
              <Field label="Dịch vụ cung cấp" value={v.services_offered} multiline />
              <Field label="Ngành phục vụ" value={v.industries_served} />
              <Field label="Tier tin cậy" value={v.reliability_tier} />
              <Field label="Quản lý bởi" value={v.managed_by} mono />
              <Field label="Hợp đồng đầu" value={fmtDate(v.first_contract_date)} />
            </CardContent>
          </Card>
        </div>

        <div className="lg:col-span-2 space-y-4">
          <Card>
            <CardContent className="pt-5 space-y-3">
              <h3 className="text-body-strong text-ink flex items-center gap-2">
                <Award className="w-4 h-4 text-brand-500" /> Năng lực + danh hiệu
              </h3>
              <div className="grid grid-cols-2 gap-3">
                <Field label="Số năm hoạt động" value={v.years_in_business?.toString() ?? null} />
                <Field label="Số nhân viên" value={v.employees_count?.toLocaleString("vi-VN") ?? null} />
                <Field label="Doanh thu/năm" value={fmtVnd(v.annual_revenue_vnd)} />
                <Field label="Tín dụng" value={v.credit_rating} />
              </div>
              <Field label="Danh hiệu / giải thưởng" value={v.titles_awards} multiline />
              <Field label="Chứng nhận" value={v.certifications} multiline />
              <Field label="Tổng quan kinh nghiệm" value={v.experience_summary} multiline />
              {v.note && <Field label="Ghi chú" value={v.note} multiline />}
            </CardContent>
          </Card>

          <Card>
            <CardContent className="pt-5 space-y-3">
              <h3 className="text-body-strong text-ink flex items-center gap-2">
                <FileSignature className="w-4 h-4 text-brand-500" /> Hợp đồng ({data.contracts.length})
              </h3>
              {data.contracts.length === 0 ? (
                <p className="text-tiny text-[#B0A698]">Chưa có hợp đồng với nhà cung cấp này.</p>
              ) : (
                <div className="space-y-2">
                  {data.contracts.map((ct) => (
                    <div key={ct.contract_id} className="rounded-xl border border-subtle p-3 hover:border-brand-200 transition-colors">
                      <div className="flex items-start justify-between gap-3">
                        <div className="min-w-0 flex-1">
                          <div className="flex items-center gap-2 flex-wrap">
                            <span className="text-tiny font-mono text-brand-600">{ct.contract_no}</span>
                            <Badge tone="neutral">{VENDOR_CONTRACT_TYPE_LABEL[ct.contract_type] ?? ct.contract_type}</Badge>
                            <Badge tone={CONTRACT_STATUS_TONE[ct.status] ?? "neutral"}>{ct.status}</Badge>
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
