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
import { useT } from "@/lib/i18n/provider";

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

const CONTRACT_TYPE_KEYS: Record<string, string> = {
  license_enterprise: "idPage.ctypeLicenseEnterprise",
  license_pilot:      "idPage.ctypeLicensePilot",
  framework_msa:      "idPage.ctypeFrameworkMsa",
  addon_module:       "idPage.ctypeAddonModule",
  custom_solution:    "idPage.ctypeCustomSolution",
  consulting:         "idPage.ctypeConsulting",
  one_off:            "idPage.ctypeOneOff",
};

function fmtVnd(s: string | null, currency: string, t: (key: string) => string): string {
  if (!s) return "—";
  const n = Number(s);
  if (!Number.isFinite(n)) return s;
  if (currency === "USD") return `$${n.toLocaleString("en-US")}`;
  if (n >= 1_000_000_000) return `${(n / 1_000_000_000).toFixed(1)} ${t("idPage.unitBillion")}`;
  if (n >= 1_000_000)     return `${(n / 1_000_000).toFixed(0)} ${t("idPage.unitMillion")}`;
  return `${n.toLocaleString("vi-VN")} ₫`;
}

function fmtDate(s: string | null): string {
  if (!s) return "—";
  return new Date(s).toLocaleDateString("vi-VN", { day: "2-digit", month: "2-digit", year: "numeric" });
}

export default function CustomerDetailPage() {
  const t = useT();
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
          <AlertCircle className="w-4 h-4" /> {t("idPage.errLoadFailed")}
        </CardContent>
      </Card>
    );
  }

  const c = data.customer;

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-3">
        <Link href="/customers">
          <Button variant="ghost"><ArrowLeft className="w-4 h-4 mr-1" /> {t("idPage.backToList")}</Button>
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
              <h3 className="text-body-strong text-ink">{t("idPage.sectionBasicInfo")}</h3>
              <Field label={t("idPage.lblContactPerson")} value={c.contact_person} />
              <Field label={t("idPage.lblEmail")} value={c.email} mono />
              <Field label={t("idPage.lblPhone")} value={c.phone} mono />
              <Field label={t("idPage.lblTaxCode")} value={c.tax_code} mono />
              <Field label={t("idPage.lblAddress")} value={c.address} />
              <Field label={t("idPage.lblCity")} value={c.city} />
            </CardContent>
          </Card>

          <Card>
            <CardContent className="pt-5 space-y-3">
              <h3 className="text-body-strong text-ink">{t("idPage.sectionClassification")}</h3>
              <Field label={t("idPage.lblCustomerType")} value={c.customer_type} />
              <Field label={t("idPage.lblIndustry")} value={c.industry} />
              <Field label={t("idPage.lblTier")} value={c.relationship_tier} />
              <Field label={t("idPage.lblAccountManager")} value={c.assigned_account_manager} mono />
              <Field label={t("idPage.lblFirstContact")} value={fmtDate(c.first_contact_date)} />
            </CardContent>
          </Card>
        </div>

        {/* Capability + contracts column */}
        <div className="lg:col-span-2 space-y-4">
          <Card>
            <CardContent className="pt-5 space-y-3">
              <h3 className="text-body-strong text-ink flex items-center gap-2">
                <Award className="w-4 h-4 text-brand-500" /> {t("idPage.sectionCapability")}
              </h3>
              <div className="grid grid-cols-2 gap-3">
                <Field label={t("idPage.lblYearsInBusiness")} value={c.years_in_business?.toString() ?? null} />
                <Field label={t("idPage.lblEmployeesCount")} value={c.employees_count?.toLocaleString("vi-VN") ?? null} />
                <Field label={t("idPage.lblAnnualRevenue")} value={fmtVnd(c.annual_revenue_vnd, "VND", t)} />
                <Field label={t("idPage.lblCreditRating")} value={c.credit_rating} />
              </div>
              <Field label={t("idPage.lblTitlesAwards")} value={c.titles_awards} multiline />
              <Field label={t("idPage.lblCertifications")} value={c.certifications} multiline />
              <Field label={t("idPage.lblExperienceSummary")} value={c.experience_summary} multiline />
              {c.note && <Field label={t("idPage.lblNote")} value={c.note} multiline />}
            </CardContent>
          </Card>

          <Card>
            <CardContent className="pt-5 space-y-3">
              <h3 className="text-body-strong text-ink flex items-center gap-2">
                <FileSignature className="w-4 h-4 text-brand-500" /> {t("idPage.sectionContracts", { count: data.contracts.length })}
              </h3>
              {data.contracts.length === 0 ? (
                <p className="text-tiny text-[#B0A698]">{t("idPage.noContracts")}</p>
              ) : (
                <div className="space-y-2">
                  {data.contracts.map((ct) => (
                    <div key={ct.contract_id} className="rounded-xl border border-subtle p-3 hover:border-brand-200 transition-colors">
                      <div className="flex items-start justify-between gap-3">
                        <div className="min-w-0 flex-1">
                          <div className="flex items-center gap-2 flex-wrap">
                            <span className="text-tiny font-mono text-brand-600">{ct.contract_no}</span>
                            <Badge tone="neutral">{CONTRACT_TYPE_KEYS[ct.contract_type] ? t(CONTRACT_TYPE_KEYS[ct.contract_type]) : ct.contract_type}</Badge>
                            <Badge tone={CONTRACT_STATUS_TONE[ct.status] ?? "neutral"}>{ct.status}</Badge>
                            {ct.renewal_type === "auto_renew" && <Badge tone="info">{t("idPage.autoRenew")}</Badge>}
                          </div>
                          {ct.description && <p className="text-small text-ink mt-1">{ct.description}</p>}
                          <div className="grid grid-cols-3 gap-x-4 gap-y-1 mt-2 text-tiny text-ink-muted">
                            <div><span className="text-[#B0A698]">{t("idPage.lblValue")}</span> <span className="tabular-nums text-ink">{fmtVnd(ct.value_vnd, ct.currency, t)}</span></div>
                            <div><span className="text-[#B0A698]">{t("idPage.lblPayment")}</span> {ct.payment_schedule ?? "—"}{ct.payment_terms_days ? ` (${ct.payment_terms_days}d)` : ""}</div>
                            <div><span className="text-[#B0A698]">{t("idPage.lblValidity")}</span> {fmtDate(ct.start_at)} → {fmtDate(ct.end_at)}</div>
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
