"use client";

import { useState } from "react";
import { BarChart2, TrendingUp, Layers, ScatterChart, PieChart, Users, Activity, Brain, GitBranch, Banknote, ShieldAlert } from "lucide-react";
import { analyticsApi } from "@/lib/api/client";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/cn";

const TEMPLATES = [
  { id: "summary_stats", icon: BarChart2,    label: "Thống kê tổng quan",    desc: "Mean, median, std, quartiles cho tất cả cột số" },
  { id: "time_series",   icon: TrendingUp,   label: "Chuỗi thời gian",       desc: "Xu hướng, mùa vụ, dự báo — cần cột ngày + số" },
  { id: "distribution",  icon: Layers,       label: "Phân phối",             desc: "Histogram, outlier, skewness" },
  { id: "correlation",   icon: ScatterChart, label: "Tương quan",            desc: "Ma trận tương quan — cần ≥2 cột số" },
  { id: "clustering",    icon: PieChart,     label: "Phân nhóm",             desc: "K-means segmentation — cần ≥3 cột số" },
  { id: "cohort",        icon: Users,        label: "Cohort retention",      desc: "Bảng giữ chân khách hàng theo tháng" },
  { id: "churn",         icon: Activity,     label: "Nguy cơ rời bỏ",       desc: "RFM + dự đoán churn — cần customer_id + date" },
  { id: "anomaly",       icon: Brain,        label: "Phát hiện bất thường",  desc: "Outlier + time anomaly detection" },
  { id: "regression",    icon: GitBranch,    label: "Hồi quy dự đoán",      desc: "Dự đoán biến target từ các features" },
  { id: "bank_classify", icon: Banknote,     label: "Phân loại giao dịch",   desc: "Phân loại sao kê ngân hàng theo danh mục" },
];

export default function AnalysisConfig({
  runId,
  onComplete,
}: {
  runId: string;
  onComplete: (analysisRunId: string) => void;
}) {
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
      setError("Lỗi khi bắt đầu phân tích. Vui lòng thử lại.");
    } finally {
      setTriggering(false);
    }
  }

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-h2 font-serif text-[#2E2A24]">Chọn phân tích</h2>
        <p className="text-small text-[#7A7266] mt-1">
          Chọn một hoặc nhiều loại phân tích. Tất cả chạy đồng thời trên dữ liệu đã làm sạch.
        </p>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
        {TEMPLATES.map((t) => {
          const Icon   = t.icon;
          const active = selected.has(t.id);
          return (
            <label
              key={t.id}
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
                onChange={() => toggle(t.id)}
                className="mt-0.5 w-4 h-4 rounded border-subtle text-brand-600 focus:ring-brand-300"
              />
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 mb-0.5">
                  <Icon className={cn("w-4 h-4 shrink-0", active ? "text-brand-600" : "text-[#A89F90]")} strokeWidth={1.75} />
                  <span className={cn("text-body-strong", active ? "text-brand-800" : "text-[#2E2A24]")}>{t.label}</span>
                </div>
                <p className="text-small text-[#7A7266]">{t.desc}</p>
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
                <p className="text-body-strong text-warning-800">Cho phép AI bên ngoài (Claude / GPT-4o)</p>
              </div>
              <p className="text-small text-warning-700 mt-0.5">
                Dữ liệu sẽ được ẩn danh (xoá email, SĐT) trước khi gửi. Mặc định: Qwen2.5 nội bộ.
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
        <p className="text-small text-[#7A7266]">Đã chọn {selected.size} loại phân tích</p>
        <Button onClick={handleStart} loading={triggering} disabled={selected.size === 0}>
          {triggering ? "Đang bắt đầu…" : "Bắt đầu phân tích →"}
        </Button>
      </div>
    </div>
  );
}
