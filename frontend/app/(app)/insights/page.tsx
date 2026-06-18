"use client";

import { useState, useRef } from "react";
import { useQuery, useMutation } from "@tanstack/react-query";
import { Send, Loader2, AlertCircle, Lightbulb, Info, TrendingDown, TrendingUp } from "lucide-react";
import { api } from "@/lib/api";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge, type BadgeTone } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { useT } from "@/lib/i18n/provider";
import { fmtDateTime } from "@/lib/format";

// ── Types ──────────────────────────────────────────────────────────────────────

type FrameworkType = "five_why" | "fishbone" | "swot" | "five_w1h" | "mom_compare";
type InsightCategory = "trend" | "anomaly" | "opportunity" | "risk";

interface StrategyResult {
  framework: FrameworkType;
  problem?: string;
  chain?: string[];
  quadrants?: { S: string[]; W: string[]; O: string[]; T: string[] };
  categories?: Record<string, string[]>;
  pillars?: Record<string, string[]>;
  periods?: string[];
  metrics?: Array<{ name: string; before: number; after: number; delta: number }>;
  narrative: string;
  recommendations: string[];
}

// CR-0018 — matches ai-orchestrator /insights/feed: {insights:[{...}]}.
interface InsightFeedItem {
  id: string;
  title: string;
  body: string;
  category: InsightCategory;
  grounding_score?: number;     // |OR| share of claims grounded (0..1)
  flagged_claims?: number[];    // numbers not found in measured facts
  disclaimer?: string;          // BR-9
  analysis_run_id?: string;
}

const FRAMEWORK_LABELS: Record<FrameworkType, string> = {
  five_why:    "5 Whys",
  fishbone:    "Fishbone (Ishikawa)",
  swot:        "SWOT",
  five_w1h:    "5W1H",
  mom_compare: "So sánh tháng",
};

const CATEGORY_META: Record<InsightCategory, { icon: any; tone: BadgeTone; label: string }> = {
  trend:       { icon: TrendingUp,   tone: "info",    label: "Xu hướng" },
  anomaly:     { icon: AlertCircle,  tone: "warning", label: "Bất thường" },
  opportunity: { icon: TrendingUp,   tone: "success", label: "Cơ hội" },
  risk:        { icon: TrendingDown, tone: "danger",  label: "Rủi ro" },
};

// ── Page ───────────────────────────────────────────────────────────────────────

export default function InsightsPage() {
  const t = useT();
  const [question, setQuestion] = useState("");
  const [result,   setResult]   = useState<StrategyResult | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  const { data: feedData, isLoading: feedLoading } = useQuery<{ insights: InsightFeedItem[] }>({
    queryKey: ["insights-feed"],
    queryFn:  () => api("/api/v1/insights/feed?limit=10"),
    staleTime: 60_000,
  });

  const { mutate: ask, isPending: asking, isError: askError } = useMutation({
    mutationFn: (q: string) =>
      api<StrategyResult>("/api/v1/strategy/ask", {
        method: "POST",
        body: JSON.stringify({ question: q }),
      }),
    onSuccess: (data) => setResult(data),
  });

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    const q = question.trim();
    if (!q) return;
    setResult(null);
    ask(q);
  }

  return (
    <div className="space-y-8">
      {/* Header */}
      <div>
        <h1 className="text-h1 font-serif text-ink">{t("insights.title")}</h1>
        <p className="text-small text-ink-muted mt-1">{t("insights.subtitle")}</p>
      </div>

      {/* Ask AI */}
      <Card>
        <CardContent className="pt-6 space-y-4">
          <form onSubmit={handleSubmit} className="flex gap-3">
            <input
              ref={inputRef}
              type="text"
              value={question}
              onChange={(e) => setQuestion(e.target.value)}
              placeholder={t("insights.ask.placeholder")}
              className="flex-1 h-10 rounded-xl border border-subtle bg-muted px-3 text-body text-ink placeholder:text-[#B0A698] focus:outline-none focus:ring-2 focus:ring-brand-300"
            />
            <Button type="submit" loading={asking}>
              {asking ? (
                t("insights.ask.button.busy")
              ) : (
                <>
                  <Send className="w-4 h-4 mr-1.5" />
                  {t("insights.ask.button")}
                </>
              )}
            </Button>
          </form>

          {askError && (
            <div className="flex items-center gap-2 text-danger-600 text-small">
              <AlertCircle className="w-4 h-4" />
              {t("error.generic")}
            </div>
          )}
        </CardContent>
      </Card>

      {/* Framework result */}
      {result && <FrameworkResult result={result} />}

      {/* Insight feed */}
      <div className="space-y-4">
        <h2 className="text-h2 font-serif text-ink">Insights gần đây</h2>
        {feedLoading ? (
          <div className="space-y-3">
            {Array.from({ length: 4 }).map((_, i) => <Skeleton key={i} className="h-24" />)}
          </div>
        ) : (feedData?.insights ?? []).length === 0 ? (
          <Card>
            <CardContent className="py-8 text-center text-small text-ink-muted">
              <Lightbulb className="w-7 h-7 text-brand-300 mx-auto mb-2" strokeWidth={1.5} />
              Chưa có insights. Chạy phân tích để tạo insight.
            </CardContent>
          </Card>
        ) : (
          <div className="space-y-3">
            {(feedData?.insights ?? []).map((item) => (
              <InsightCard key={item.id} item={item} />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

// ── Framework result renderer ──────────────────────────────────────────────────

function FrameworkResult({ result }: { result: StrategyResult }) {
  const fwLabel = FRAMEWORK_LABELS[result.framework] ?? result.framework;
  return (
    <div className="space-y-4">
      <div className="flex items-center gap-2">
        <h2 className="text-h2 font-serif text-ink">Kết quả phân tích</h2>
        <Badge tone="brand">{fwLabel}</Badge>
      </div>

      {/* 5 Whys */}
      {result.framework === "five_why" && result.chain && (
        <Card>
          <CardHeader><CardTitle>Chuỗi nguyên nhân</CardTitle></CardHeader>
          <CardContent className="pb-6">
            <ol className="space-y-3">
              {result.chain.map((step, i) => (
                <li key={i} className="flex gap-3">
                  <span className="w-6 h-6 rounded-full bg-brand-100 text-brand-700 text-tiny font-semibold flex items-center justify-center shrink-0 mt-0.5">
                    {i + 1}
                  </span>
                  <p className="text-body text-ink">{step}</p>
                </li>
              ))}
            </ol>
          </CardContent>
        </Card>
      )}

      {/* SWOT */}
      {result.framework === "swot" && result.quadrants && (
        <div className="grid grid-cols-2 gap-4">
          {(["S", "W", "O", "T"] as const).map((q) => {
            const tone: BadgeTone = q === "S" || q === "O" ? "success" : "danger";
            const label = { S: "Strengths", W: "Weaknesses", O: "Opportunities", T: "Threats" }[q];
            return (
              <Card key={q}>
                <CardHeader className="pb-2">
                  <div className="flex items-center gap-2">
                    <Badge tone={tone}>{q}</Badge>
                    <CardTitle>{label}</CardTitle>
                  </div>
                </CardHeader>
                <CardContent className="pb-5">
                  <ul className="space-y-1.5">
                    {(result.quadrants![q] ?? []).map((item, i) => (
                      <li key={i} className="text-small text-ink flex gap-2">
                        <span className="text-[#B0A698] mt-0.5">·</span>{item}
                      </li>
                    ))}
                  </ul>
                </CardContent>
              </Card>
            );
          })}
        </div>
      )}

      {/* Fishbone / 5W1H — category groups */}
      {(result.framework === "fishbone" || result.framework === "five_w1h") &&
        (result.categories || result.pillars) && (
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          {Object.entries(result.categories ?? result.pillars ?? {}).map(([cat, items]) => (
            <Card key={cat}>
              <CardHeader className="pb-2"><CardTitle>{cat}</CardTitle></CardHeader>
              <CardContent className="pb-5">
                <ul className="space-y-1.5">
                  {items.map((item, i) => (
                    <li key={i} className="text-small text-ink flex gap-2">
                      <span className="text-[#B0A698] mt-0.5">·</span>{item}
                    </li>
                  ))}
                </ul>
              </CardContent>
            </Card>
          ))}
        </div>
      )}

      {/* MoM Compare */}
      {result.framework === "mom_compare" && result.metrics && (
        <Card>
          <CardHeader><CardTitle>So sánh kỳ</CardTitle></CardHeader>
          <CardContent className="pb-6 space-y-2">
            {result.metrics.map((m, i) => (
              <div key={i} className="flex items-center justify-between py-2 border-b border-subtle last:border-0">
                <span className="text-small text-ink-muted">{m.name}</span>
                <div className="flex items-center gap-3 tabular-nums">
                  <span className="text-small text-[#B0A698]">{m.before}</span>
                  <span className="text-small text-[#C0B8A8]">→</span>
                  <span className="text-body-strong text-ink">{m.after}</span>
                  <Badge tone={m.delta >= 0 ? "success" : "danger"}>
                    {m.delta >= 0 ? "+" : ""}{m.delta.toFixed(1)}%
                  </Badge>
                </div>
              </div>
            ))}
          </CardContent>
        </Card>
      )}

      {/* Narrative */}
      {result.narrative && (
        <Card>
          <CardHeader><CardTitle>Nhận xét</CardTitle></CardHeader>
          <CardContent className="pb-6">
            <p className="text-body text-ink leading-relaxed whitespace-pre-wrap">
              {result.narrative}
            </p>
          </CardContent>
        </Card>
      )}

      {/* Recommendations */}
      {result.recommendations?.length > 0 && (
        <Card>
          <CardHeader><CardTitle>Đề xuất</CardTitle></CardHeader>
          <CardContent className="pb-6">
            <ul className="space-y-2">
              {result.recommendations.map((rec, i) => (
                <li key={i} className="flex gap-3 text-small text-ink">
                  <span className="w-5 h-5 rounded-full bg-brand-50 text-brand-600 text-tiny font-semibold flex items-center justify-center shrink-0 mt-0.5">
                    {i + 1}
                  </span>
                  {rec}
                </li>
              ))}
            </ul>
          </CardContent>
        </Card>
      )}
    </div>
  );
}

// ── Insight card ───────────────────────────────────────────────────────────────

function InsightCard({ item }: { item: InsightFeedItem }) {
  const meta = CATEGORY_META[item.category] ?? CATEGORY_META.trend;
  const Icon = meta.icon;
  const pct = item.grounding_score != null ? Math.round(item.grounding_score * 100) : null;
  const flagged = item.flagged_claims ?? [];

  return (
    <Card>
      <CardContent className="pt-5 flex gap-4">
        <div className={`rounded-xl p-2.5 shrink-0 ${
          item.category === "risk"        ? "bg-danger-50  text-danger-600"  :
          item.category === "opportunity" ? "bg-success-50 text-success-600" :
          item.category === "anomaly"     ? "bg-warning-50 text-warning-600" :
                                            "bg-info-50    text-info-600"
        }`}>
          <Icon className="w-5 h-5" strokeWidth={1.75} />
        </div>
        <div className="flex-1 min-w-0 space-y-1.5">
          <div className="flex items-center gap-2 flex-wrap">
            <p className="text-body-strong text-ink">{item.title}</p>
            <Badge tone={meta.tone}>{meta.label}</Badge>
            {/* CR-0018 — grounding self-verify: how well the claimed numbers match the data */}
            {pct != null && (
              <Badge tone={flagged.length ? "warning" : "success"}>Khớp dữ liệu {pct}%</Badge>
            )}
          </div>
          {item.body && <p className="text-small text-ink-muted">{item.body}</p>}
          {flagged.length > 0 && (
            <p className="text-small text-warning-700">
              ⚠ Số chưa khớp dữ liệu đo được: {flagged.join(", ")}
            </p>
          )}
          {item.disclaimer && <p className="text-tiny text-[#C0B8A8]">{item.disclaimer}</p>}
        </div>
      </CardContent>
    </Card>
  );
}
