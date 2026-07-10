"use client";

import { useState } from "react";
import { BarChart2, TrendingUp, Layers, ScatterChart, PieChart, Users, Activity, Brain, GitBranch, Banknote, ShieldAlert } from "lucide-react";
import { analyticsApi } from "@/lib/api/client";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/cn";
import { useT } from "@/lib/i18n/provider";

const TEMPLATES = [
  { id: "summary_stats", icon: BarChart2,    labelKey: "pipelineAnalysisconfig.tplSummaryStatsLabel", descKey: "pipelineAnalysisconfig.tplSummaryStatsDesc" },
  { id: "time_series",   icon: TrendingUp,   labelKey: "pipelineAnalysisconfig.tplTimeSeriesLabel",   descKey: "pipelineAnalysisconfig.tplTimeSeriesDesc" },
  { id: "distribution",  icon: Layers,       labelKey: "pipelineAnalysisconfig.tplDistributionLabel", descKey: "pipelineAnalysisconfig.tplDistributionDesc" },
  { id: "correlation",   icon: ScatterChart, labelKey: "pipelineAnalysisconfig.tplCorrelationLabel",  descKey: "pipelineAnalysisconfig.tplCorrelationDesc" },
  { id: "clustering",    icon: PieChart,     labelKey: "pipelineAnalysisconfig.tplClusteringLabel",   descKey: "pipelineAnalysisconfig.tplClusteringDesc" },
  { id: "cohort",        icon: Users,        labelKey: "pipelineAnalysisconfig.tplCohortLabel",       descKey: "pipelineAnalysisconfig.tplCohortDesc" },
  { id: "churn",         icon: Activity,     labelKey: "pipelineAnalysisconfig.tplChurnLabel",        descKey: "pipelineAnalysisconfig.tplChurnDesc" },
  { id: "anomaly",       icon: Brain,        labelKey: "pipelineAnalysisconfig.tplAnomalyLabel",      descKey: "pipelineAnalysisconfig.tplAnomalyDesc" },
  { id: "regression",    icon: GitBranch,    labelKey: "pipelineAnalysisconfig.tplRegressionLabel",   descKey: "pipelineAnalysisconfig.tplRegressionDesc" },
  { id: "bank_classify", icon: Banknote,     labelKey: "pipelineAnalysisconfig.tplBankClassifyLabel", descKey: "pipelineAnalysisconfig.tplBankClassifyDesc" },
];

export default function AnalysisConfig({
  runId,
  onComplete,
}: {
  runId: string;
  onComplete: (analysisRunId: string) => void;
}) {
  const t = useT();
  const [selected,        setSelected]        = useState<Set<string>>(new Set(["summary_stats"]));
  const [consentExternal, setConsentExternal] = useState(false);
  const [triggering,      setTriggering]      = useState(false);
  const [error,           setError]           = useState("");

  function toggle(id: string) {
    setSelected((prev) => { const s = new Set(prev); s.has(id) ? s.delete(id) : s.add(id); return s; });
  }

  async function handleStart() {
    if (selected.size === 0) return;
    setTriggering(true);
    setError("");
    try {
      const { data } = await analyticsApi.createRun(runId, [...selected], { consent_external: consentExternal });
      onComplete(data.analysis_run_id);
    } catch {
      setError(t("pipelineAnalysisconfig.errStart"));
    } finally {
      setTriggering(false);
    }
  }

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-h2 font-serif text-[#2E2A24]">{t("pipelineAnalysisconfig.title")}</h2>
        <p className="text-small text-[#7A7266] mt-1">
          {t("pipelineAnalysisconfig.subtitle")}
        </p>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
        {TEMPLATES.map((tpl) => {
          const Icon   = tpl.icon;
          const active = selected.has(tpl.id);
          return (
            <label
              key={tpl.id}
              className={cn(
                "flex items-start gap-4 p-4 rounded-2xl border-2 cursor-pointer transition-all",
                active
                  ? "border-brand-400 bg-brand-50"
                  : "border-subtle bg-surface hover:border-brand-300 hover:bg-brand-50/30",
              )}
            >
              <input
                type="checkbox"
                checked={active}
                onChange={() => toggle(tpl.id)}
                className="mt-0.5 w-4 h-4 rounded border-subtle text-brand-600 focus:ring-brand-300"
              />
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 mb-0.5">
                  <Icon className={cn("w-4 h-4 shrink-0", active ? "text-brand-600" : "text-[#A89F90]")} strokeWidth={1.75} />
                  <span className={cn("text-body-strong", active ? "text-brand-800" : "text-[#2E2A24]")}>{t(tpl.labelKey)}</span>
                </div>
                <p className="text-small text-[#7A7266]">{t(tpl.descKey)}</p>
              </div>
            </label>
          );
        })}
      </div>

      {/* External AI consent */}
      <Card className="border-warning-200 bg-warning-50/30">
        <CardContent className="pt-4 pb-4">
          <label className="flex items-start gap-3 cursor-pointer">
            <input
              type="checkbox"
              checked={consentExternal}
              onChange={(e) => setConsentExternal(e.target.checked)}
              className="mt-0.5 w-4 h-4 rounded border-warning-300 text-warning-600 focus:ring-warning-300"
            />
            <div>
              <div className="flex items-center gap-2">
                <ShieldAlert className="w-4 h-4 text-warning-600 shrink-0" />
                <p className="text-body-strong text-warning-800">{t("pipelineAnalysisconfig.consentTitle")}</p>
              </div>
              <p className="text-small text-warning-700 mt-0.5">
                {t("pipelineAnalysisconfig.consentDesc")}
              </p>
            </div>
          </label>
        </CardContent>
      </Card>

      {error && (
        <div className="bg-danger-50 border border-danger-100 rounded-xl px-4 py-3">
          <p className="text-small text-danger-700">{error}</p>
        </div>
      )}

      <div className="flex items-center justify-between">
        <p className="text-small text-[#7A7266]">{t("pipelineAnalysisconfig.selectedCount", { count: selected.size })}</p>
        <Button onClick={handleStart} loading={triggering} disabled={selected.size === 0}>
          {triggering ? t("pipelineAnalysisconfig.starting") : t("pipelineAnalysisconfig.startCta")}
        </Button>
      </div>
    </div>
  );
}
