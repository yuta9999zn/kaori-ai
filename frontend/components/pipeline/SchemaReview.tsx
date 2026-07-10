"use client";

import { useEffect, useState } from "react";
import { AlertTriangle, CheckCircle2, Loader2 } from "lucide-react";
import { pipelineApi } from "@/lib/api/client";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { useT } from "@/lib/i18n/provider";

interface ColumnMapping {
  source_column: string;
  canonical_name: string;
  data_type: string;
  confidence: number;
  method: string;
  uncertainty_flags: string[];
}

interface Sheet {
  file_id: string;
  sheet_name: string | null;
  detected_purpose: string | null;
  mappings: ColumnMapping[];
}

function getFlagMeta(t: ReturnType<typeof useT>): Record<string, { label: string; tone: "warning" | "danger" | "info" | "neutral" }> {
  return {
    LOW_CONFIDENCE:    { label: t("pipelineSchemareview.flagLowConfidence"), tone: "warning" },
    AMBIGUOUS_TOP2:    { label: t("pipelineSchemareview.flagAmbiguous"),     tone: "warning" },
    LANG_MISMATCH:     { label: t("pipelineSchemareview.flagLangMismatch"), tone: "info"    },
    LLM_FALLBACK_USED: { label: t("pipelineSchemareview.flagLlmFallback"),  tone: "info"    },
    NO_CANONICAL_MATCH:{ label: t("pipelineSchemareview.flagNoMatch"),      tone: "danger"  },
  };
}

// CR-0016 — short hint for key canonical names so the user sees what each maps
// to, especially the unit_price vs amount distinction that drives whether the
// line total gets derived (đơn giá × số lượng).
function getCanonHint(t: ReturnType<typeof useT>): Record<string, string> {
  return {
    unit_price:           t("pipelineSchemareview.hintUnitPrice"),
    amount:               t("pipelineSchemareview.hintAmount"),
    revenue:              t("pipelineSchemareview.hintRevenue"),
    quantity:             t("pipelineSchemareview.hintQuantity"),
    customer_external_id: t("pipelineSchemareview.hintCustomerId"),
    date:                 t("pipelineSchemareview.hintDate"),
  };
}

export default function SchemaReview({
  runId,
  onComplete,
}: {
  runId: string;
  onComplete: (schemaData: unknown) => void;
}) {
  const t = useT();
  const [loading,    setLoading]    = useState(true);
  const [sheets,     setSheets]     = useState<Sheet[]>([]);
  const [overrides,  setOverrides]  = useState<Record<string, { canonical: string; dtype: string }>>({});
  const [confirming, setConfirming] = useState(false);
  const [error,      setError]      = useState("");

  useEffect(() => {
    pipelineApi.getSchema(runId)
      .then(({ data }) => { setSheets(data.sheets); setLoading(false); })
      .catch((e) => { setError(e.response?.data?.detail || t("pipelineSchemareview.errFetchSchema")); setLoading(false); });
  }, [runId]);

  function setOverride(col: string, canonical: string, dtype: string) {
    setOverrides((prev) => ({ ...prev, [col]: { canonical, dtype } }));
  }

  async function handleConfirm() {
    setConfirming(true);
    const overrideList = Object.entries(overrides).map(([src, v]) => ({
      source_column: src, canonical_name: v.canonical, data_type: v.dtype,
    }));
    try {
      const { data } = await pipelineApi.confirmSchema(runId, overrideList);
      onComplete(data);
    } catch {
      setError(t("pipelineSchemareview.errConfirm"));
    } finally {
      setConfirming(false);
    }
  }

  if (loading) return (
    <div className="flex items-center justify-center py-24">
      <div className="text-center space-y-3">
        <Loader2 className="w-9 h-9 text-brand-400 animate-spin mx-auto" />
        <p className="text-small text-[#7A7266]">{t("pipelineSchemareview.analyzing")}</p>
      </div>
    </div>
  );

  if (error) return (
    <div className="flex items-center gap-3 bg-danger-50 border border-danger-100 rounded-xl px-5 py-4">
      <AlertTriangle className="w-5 h-5 text-danger-500 shrink-0" />
      <p className="text-small text-danger-700">{error}</p>
    </div>
  );

  const totalWarnings = sheets.flatMap((s) => s.mappings.filter((m) => m.uncertainty_flags.length > 0)).length;
  const flagMeta = getFlagMeta(t);
  const canonHint = getCanonHint(t);
  const tableHeaders = [
    t("pipelineSchemareview.colSource"),
    t("pipelineSchemareview.colCanonical"),
    t("pipelineSchemareview.colDtype"),
    t("pipelineSchemareview.colConfidence"),
    t("pipelineSchemareview.colWarning"),
  ];

  return (
    <div className="space-y-6">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h2 className="text-h2 font-serif text-[#2E2A24]">{t("pipelineSchemareview.title")}</h2>
          <p className="text-small text-[#7A7266] mt-1">
            {t("pipelineSchemareview.desc")}
          </p>
        </div>
        {totalWarnings > 0 && (
          <Badge tone="warning" className="shrink-0 mt-1">
            {t("pipelineSchemareview.warningBadge", { count: totalWarnings })}
          </Badge>
        )}
      </div>

      {sheets.map((sheet, si) => (
        <Card key={si}>
          <CardHeader className="pb-0">
            <div className="flex items-center gap-3">
              <CardTitle>{sheet.sheet_name || t("pipelineSchemareview.sheetDefault")}</CardTitle>
              {sheet.detected_purpose && (
                <Badge tone="info">{sheet.detected_purpose}</Badge>
              )}
            </div>
          </CardHeader>
          <CardContent className="pt-4 pb-2 overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-subtle">
                  {tableHeaders.map((h) => (
                    <th key={h} className="px-3 py-2.5 text-left text-label text-[#A89F90] font-medium">{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-subtle">
                {sheet.mappings.map((m, mi) => {
                  const override       = overrides[m.source_column];
                  const displayCanon   = override?.canonical ?? m.canonical_name;
                  const displayDtype   = override?.dtype     ?? m.data_type;
                  const hasWarning     = m.uncertainty_flags.length > 0;
                  const confidencePct  = Math.round(m.confidence * 100);

                  return (
                    <tr key={mi} className={hasWarning ? "bg-warning-50/30" : ""}>
                      <td className="px-3 py-3 font-mono text-tiny text-[#7A7266]">{m.source_column}</td>
                      <td className="px-3 py-3">
                        <input
                          value={displayCanon}
                          onChange={(e) => setOverride(m.source_column, e.target.value, displayDtype)}
                          className="border border-subtle rounded-lg px-2 py-1 text-small w-full focus:outline-none focus:ring-2 focus:ring-brand-300 bg-surface"
                        />
                        {canonHint[displayCanon] && (
                          <p className="text-tiny text-[#A89F90] mt-1">{canonHint[displayCanon]}</p>
                        )}
                      </td>
                      <td className="px-3 py-3">
                        <select
                          value={displayDtype}
                          onChange={(e) => setOverride(m.source_column, displayCanon, e.target.value)}
                          className="border border-subtle rounded-lg px-2 py-1 text-small focus:outline-none focus:ring-2 focus:ring-brand-300 bg-surface"
                        >
                          {["text","integer","decimal","date","boolean","phone","currency","id"].map((dt) => (
                            <option key={dt} value={dt}>{dt}</option>
                          ))}
                        </select>
                      </td>
                      <td className="px-3 py-3">
                        <div className="flex items-center gap-2">
                          <div className="w-14 bg-subtle rounded-full h-1.5 shrink-0">
                            <div
                              className={`h-1.5 rounded-full ${confidencePct >= 90 ? "bg-success-500" : confidencePct >= 65 ? "bg-warning-500" : "bg-danger-400"}`}
                              style={{ width: `${confidencePct}%` }}
                            />
                          </div>
                          <span className="text-tiny text-[#A89F90] tabular-nums">{confidencePct}%</span>
                        </div>
                      </td>
                      <td className="px-3 py-3">
                        <div className="flex flex-wrap gap-1">
                          {m.uncertainty_flags.map((f) => {
                            const meta = flagMeta[f];
                            return (
                              <Badge key={f} tone={meta?.tone ?? "neutral"}>
                                {meta?.label ?? f}
                              </Badge>
                            );
                          })}
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </CardContent>
        </Card>
      ))}

      {error && (
        <div className="flex items-center gap-2 bg-danger-50 border border-danger-100 rounded-xl px-4 py-3">
          <AlertTriangle className="w-4 h-4 text-danger-500 shrink-0" />
          <p className="text-small text-danger-700">{error}</p>
        </div>
      )}

      <div className="flex justify-end">
        <Button onClick={handleConfirm} loading={confirming}>
          {confirming ? t("pipelineSchemareview.confirming") : t("pipelineSchemareview.confirmBtn")}
        </Button>
      </div>
    </div>
  );
}
