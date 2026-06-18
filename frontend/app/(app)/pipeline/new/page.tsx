"use client";

import { useState } from "react";
import { Check } from "lucide-react";
import { cn } from "@/lib/cn";
import { useT } from "@/lib/i18n/provider";
import FileUploader from "@/components/pipeline/FileUploader";
import SchemaReview from "@/components/pipeline/SchemaReview";
import CleaningReview from "@/components/pipeline/CleaningReview";
import AnalysisConfig from "@/components/pipeline/AnalysisConfig";
import ResultsDashboard from "@/components/pipeline/ResultsDashboard";

type Step = "upload" | "schema" | "clean" | "analyze" | "results";

interface PipelineState {
  runId: string | null;
  step: Step;
  schemaData: unknown;
  cleaningRules: unknown[];
  analysisRunId: string | null;
}

const STEP_KEYS: Step[] = ["upload", "schema", "clean", "analyze", "results"];

export default function PipelineNewPage() {
  const t = useT();
  const [state, setState] = useState<PipelineState>({
    runId: null, step: "upload", schemaData: null,
    cleaningRules: [], analysisRunId: null,
  });

  const STEPS: { key: Step; label: string }[] = [
    { key: "upload",  label: t("pipeline.new.step.upload")  },
    { key: "schema",  label: t("pipeline.new.step.schema")  },
    { key: "clean",   label: t("pipeline.new.step.clean")   },
    { key: "analyze", label: t("pipeline.new.step.analyze") },
    { key: "results", label: t("pipeline.new.step.results") },
  ];

  const currentIdx = STEP_KEYS.indexOf(state.step);

  function advance(next: Step, updates?: Partial<PipelineState>) {
    setState((prev) => ({ ...prev, step: next, ...updates }));
  }

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-h1 font-serif text-ink">{t("pipeline.title")}</h1>
        <p className="text-small text-ink-muted mt-1">{t("pipeline.subtitle")}</p>
      </div>

      {/* Step indicator */}
      <div className="bg-surface rounded-2xl border border-subtle px-6 py-4">
        <ol className="flex items-center gap-0" aria-label="Pipeline steps">
          {STEPS.map((s, i) => {
            const done   = i < currentIdx;
            const active = i === currentIdx;
            return (
              <li key={s.key} className="flex items-center flex-1 last:flex-none">
                <div className="flex items-center gap-2.5 min-w-0">
                  <span
                    className={cn(
                      "w-7 h-7 rounded-full flex items-center justify-center text-small font-semibold shrink-0 transition-colors",
                      done   && "bg-brand-500 text-white",
                      active && "bg-brand-500 text-white ring-4 ring-brand-100",
                      !done && !active && "bg-muted text-[#B0A698] border border-subtle",
                    )}
                    aria-current={active ? "step" : undefined}
                  >
                    {done ? <Check className="w-3.5 h-3.5" strokeWidth={3} /> : i + 1}
                  </span>
                  <span
                    className={cn(
                      "text-small font-medium hidden sm:block truncate",
                      active && "text-brand-700",
                      done   && "text-ink-muted",
                      !done && !active && "text-[#B0A698]",
                    )}
                  >
                    {s.label}
                  </span>
                </div>
                {i < STEPS.length - 1 && (
                  <div
                    className={cn(
                      "flex-1 mx-3 h-0.5 rounded-full transition-colors",
                      i < currentIdx ? "bg-brand-300" : "bg-subtle",
                    )}
                  />
                )}
              </li>
            );
          })}
        </ol>
      </div>

      <div className="max-w-4xl">
        {state.step === "upload" && (
          <FileUploader onComplete={(runId) => advance("schema", { runId })} />
        )}
        {state.step === "schema" && state.runId && (
          <SchemaReview
            runId={state.runId}
            onComplete={(schemaData) => advance("clean", { schemaData })}
          />
        )}
        {state.step === "clean" && state.runId && (
          <CleaningReview
            runId={state.runId}
            onComplete={() => advance("analyze")}
          />
        )}
        {state.step === "analyze" && state.runId && (
          <AnalysisConfig
            runId={state.runId}
            onComplete={(analysisRunId) => advance("results", { analysisRunId })}
          />
        )}
        {state.step === "results" && state.analysisRunId && (
          <ResultsDashboard analysisRunId={state.analysisRunId} />
        )}
      </div>
    </div>
  );
}
