"use client";

import { useEffect, useState } from "react";
import { analyticsApi } from "@/lib/api/client";
import FlexibleChart from "@/components/charts/FlexibleChart";
import { ChartBlock } from "@/components/charts/chart-registry";

// ── Types matching ai-orchestrator GET /analytics/runs/{id} ───────────────────

interface TemplateResult {
  template_id: string;
  status: "done" | "error" | "running";
  results_payload: { template_id: string; blocks: ChartBlock[] } | null;
  error_message: string | null;
}

interface AnalysisRun {
  id: string;
  run_id: string;
  templates: string[];
  status: "queued" | "running" | "done" | "error";
  overview: { narrative?: string; templates_run?: string[]; row_count?: number; col_count?: number } | null;
  template_results: TemplateResult[];
}

const TEMPLATE_LABELS: Record<string, string> = {
  summary_stats:  "Thống kê tổng quan",
  time_series:    "Chuỗi thời gian",
  distribution:   "Phân phối",
  correlation:    "Tương quan",
  clustering:     "Phân nhóm",
  cohort:         "Cohort",
  churn:          "Nguy cơ rời bỏ",
  anomaly:        "Bất thường",
  regression:     "Hồi quy",
  bank_classify:  "Phân loại giao dịch",
};

// ── Component ─────────────────────────────────────────────────────────────────

export default function ResultsDashboard({
  analysisRunId,
}: {
  analysisRunId: string;
}) {
  const [run, setRun] = useState<AnalysisRun | null>(null);
  const [activeTab, setActiveTab] = useState("overview");
  const [polling, setPolling] = useState(true);

  useEffect(() => {
    let alive = true;

    async function fetchRun() {
      try {
        const { data } = await analyticsApi.getRun(analysisRunId);
        if (!alive) return;
        setRun(data);
        if (data.status === "done" || data.status === "error") setPolling(false);
      } catch {
        // keep polling on transient errors
      }
    }

    fetchRun();
    if (!polling) return;
    const id = setInterval(fetchRun, 3000);
    return () => { alive = false; clearInterval(id); };
  }, [analysisRunId, polling]);

  if (!run) {
    return (
      <div className="flex items-center justify-center py-20">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600" />
      </div>
    );
  }

  const tabs = [
    { key: "overview", label: "Tổng quan" },
    ...run.template_results.map((r) => ({
      key: r.template_id,
      label: TEMPLATE_LABELS[r.template_id] ?? r.template_id,
      status: r.status,
    })),
  ];

  const done  = run.template_results.filter((r) => r.status === "done").length;
  const total = run.template_results.length;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold text-gray-900">Kết quả phân tích</h2>
          <p className="text-gray-500 mt-1 text-sm">
            {polling
              ? `Đang phân tích... (${done}/${total} hoàn tất)`
              : `${done}/${total} phân tích hoàn tất`}
          </p>
        </div>
        {polling && (
          <div className="flex items-center gap-2 text-blue-600 text-sm">
            <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-blue-600" />
            Đang cập nhật...
          </div>
        )}
      </div>

      {/* Tab bar */}
      <div className="flex gap-1 border-b border-gray-200 overflow-x-auto">
        {tabs.map((tab) => (
          <button
            key={tab.key}
            onClick={() => setActiveTab(tab.key)}
            className={`px-4 py-2.5 text-sm font-medium border-b-2 transition-colors whitespace-nowrap flex items-center gap-1.5
              ${activeTab === tab.key
                ? "border-blue-500 text-blue-600"
                : "border-transparent text-gray-500 hover:text-gray-700"}`}
          >
            {tab.label}
            {"status" in tab && (
              <span className={`w-1.5 h-1.5 rounded-full ${
                tab.status === "done" ? "bg-green-500" :
                tab.status === "error" ? "bg-red-500" : "bg-blue-400 animate-pulse"
              }`} />
            )}
          </button>
        ))}
      </div>

      {/* Overview tab */}
      {activeTab === "overview" && (
        <div className="space-y-6">
          {/* AI narrative */}
          {run.overview?.narrative && (
            <div className="bg-blue-50 border border-blue-100 rounded-xl p-5">
              <p className="text-blue-800 text-sm leading-relaxed">
                {run.overview.narrative}
              </p>
              <p className="text-blue-400 text-xs mt-2">Qwen2.5 · Tổng quan</p>
            </div>
          )}

          {/* Template cards */}
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
            {run.template_results.map((r) => (
              <button
                key={r.template_id}
                onClick={() => setActiveTab(r.template_id)}
                className="text-left bg-white border border-gray-200 rounded-xl p-5
                           hover:border-blue-300 hover:shadow-sm transition-all"
              >
                <div className="flex items-center justify-between mb-3">
                  <h3 className="font-semibold text-gray-800 text-sm">
                    {TEMPLATE_LABELS[r.template_id] ?? r.template_id}
                  </h3>
                  <StatusBadge status={r.status} />
                </div>
                <p className="text-gray-400 text-xs">
                  {r.results_payload?.blocks?.length ?? 0} biểu đồ
                </p>
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Per-template tabs */}
      {run.template_results.map((r) =>
        activeTab !== r.template_id ? null : (
          <div key={r.template_id} className="space-y-6">
            {r.status === "running" && (
              <div className="flex items-center justify-center py-16">
                <div className="text-center">
                  <div className="animate-spin rounded-full h-10 w-10 border-b-2 border-blue-600 mx-auto mb-4" />
                  <p className="text-gray-600">
                    Đang phân tích {TEMPLATE_LABELS[r.template_id]}...
                  </p>
                </div>
              </div>
            )}

            {r.status === "error" && (
              <div className="bg-red-50 border border-red-200 rounded-xl p-6">
                <p className="text-red-700 font-medium">Phân tích thất bại</p>
                {r.error_message && (
                  <p className="text-red-500 text-sm mt-1">{r.error_message}</p>
                )}
              </div>
            )}

            {r.status === "done" && r.results_payload?.blocks && (
              <div className="space-y-6">
                {r.results_payload.blocks.map((block) => (
                  <BlockRenderer key={block.id} block={block} />
                ))}
              </div>
            )}
          </div>
        )
      )}
    </div>
  );
}

// ── Block renderer ────────────────────────────────────────────────────────────

function BlockRenderer({ block }: { block: ChartBlock }) {
  if (block.type === "narrative") {
    return (
      <div className="bg-blue-50 border border-blue-100 rounded-xl p-5">
        <p className="text-blue-800 text-sm leading-relaxed">{block.text}</p>
        {block.provider && (
          <p className="text-blue-400 text-xs mt-2 capitalize">
            {block.provider} · AI nhận xét
          </p>
        )}
      </div>
    );
  }

  if (block.type === "stats_card") {
    const data = block.data as Record<string, unknown>[] | undefined;
    const single = Array.isArray(data) ? data[0] : (block as unknown as Record<string, unknown>);
    const entries = Object.entries(single ?? {}).filter(([k]) =>
      !["id", "type", "title"].includes(k)
    );
    return (
      <div className="bg-white border border-gray-200 rounded-xl p-5">
        {block.title && (
          <h4 className="font-semibold text-gray-700 text-sm mb-4">{block.title}</h4>
        )}
        <div className="grid grid-cols-2 sm:grid-cols-3 gap-4">
          {entries.map(([k, v]) => (
            <div key={k}>
              <p className="text-xs text-gray-400 uppercase tracking-wide">{k}</p>
              <p className="text-base font-semibold text-gray-800 mt-0.5">
                {v === null || v === undefined ? "—" : String(v)}
              </p>
            </div>
          ))}
        </div>
      </div>
    );
  }

  // type === "chart"
  return (
    <div className="bg-white border border-gray-200 rounded-xl p-5">
      {block.title && (
        <h4 className="font-semibold text-gray-700 text-sm mb-4">{block.title}</h4>
      )}
      <FlexibleChart block={block} />
    </div>
  );
}

// ── Helpers ───────────────────────────────────────────────────────────────────

function StatusBadge({ status }: { status: string }) {
  const map: Record<string, string> = {
    done:    "bg-green-100 text-green-700",
    error:   "bg-red-100 text-red-700",
    running: "bg-blue-100 text-blue-700",
    queued:  "bg-gray-100 text-gray-600",
  };
  const labels: Record<string, string> = {
    done: "Hoàn tất", error: "Lỗi", running: "Đang chạy", queued: "Chờ",
  };
  return (
    <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${map[status] ?? map.queued}`}>
      {labels[status] ?? status}
    </span>
  );
}
