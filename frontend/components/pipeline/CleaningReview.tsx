"use client";

import { useEffect, useState } from "react";
import { AlertTriangle, Loader2 } from "lucide-react";
import { pipelineApi } from "@/lib/api/client";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";

interface CleaningRule {
  rule_id: string;
  name: string;
  description: string;
  category: string;
  safe: boolean;
  target_columns?: string[];
  // CR-0016 — measured recommendation for DERIVE_LINE_TOTAL (no forced default).
  suggested?: boolean | null;
  rationale?: string;
  amount_signals?: Record<string, any>;
}

const CATEGORY_LABELS: Record<string, string> = {
  UNIVERSAL:   "Cơ bản (áp dụng cho mọi dataset)",
  BY_TYPE:     "Theo kiểu dữ liệu",
  BY_PURPOSE:  "Theo mục đích",
  AI_DETECTED: "AI phát hiện",
};

export default function CleaningReview({
  runId,
  onComplete,
}: {
  runId: string;
  onComplete: () => void;
}) {
  const [loading,  setLoading]  = useState(true);
  const [rules,    setRules]    = useState<CleaningRule[]>([]);
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [applying, setApplying] = useState(false);
  const [error,    setError]    = useState("");

  useEffect(() => {
    pipelineApi.getCleaningSuggestions(runId)
      .then(({ data }) => {
        setRules(data.rules);
        // Pre-select safe rules + any rule the evidence recommends (CR-0016).
        setSelected(new Set(
          data.rules
            .filter((r: CleaningRule) => r.safe || r.suggested === true)
            .map((r: CleaningRule) => r.rule_id)
        ));
        setLoading(false);
      })
      .catch(() => { setError("Không thể lấy gợi ý làm sạch"); setLoading(false); });
  }, [runId]);

  function toggle(ruleId: string) {
    setSelected((prev) => { const s = new Set(prev); s.has(ruleId) ? s.delete(ruleId) : s.add(ruleId); return s; });
  }

  async function handleApply() {
    setApplying(true);
    try {
      // Correct endpoint: POST /api/v1/clean/apply (not /analyze)
      await pipelineApi.applyCleaningRules(runId, [...selected]);
      onComplete();
    } catch {
      setError("Lỗi khi áp dụng quy tắc làm sạch");
    } finally {
      setApplying(false);
    }
  }

  const grouped = rules.reduce<Record<string, CleaningRule[]>>((acc, r) => {
    (acc[r.category] ??= []).push(r);
    return acc;
  }, {});

  if (loading) return (
    <div className="flex items-center justify-center py-24">
      <div className="text-center space-y-3">
        <Loader2 className="w-9 h-9 text-brand-400 animate-spin mx-auto" />
        <p className="text-small text-[#7A7266]">Đang phân tích dữ liệu…</p>
      </div>
    </div>
  );

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-h2 font-serif text-[#2E2A24]">Làm sạch dữ liệu</h2>
        <p className="text-small text-[#7A7266] mt-1">
          Chọn quy tắc để áp dụng. Dữ liệu gốc (Bronze) không bị thay đổi.
        </p>
      </div>

      {Object.entries(grouped).map(([cat, catRules]) => (
        <Card key={cat}>
          <CardHeader className="pb-0">
            <CardTitle>{CATEGORY_LABELS[cat] ?? cat}</CardTitle>
          </CardHeader>
          <CardContent className="pt-3 pb-2 divide-y divide-subtle">
            {catRules.map((rule) => (
              <label
                key={rule.rule_id}
                className="flex items-start gap-4 py-4 cursor-pointer hover:bg-muted/60 transition-colors -mx-6 px-6"
              >
                <input
                  type="checkbox"
                  checked={selected.has(rule.rule_id)}
                  onChange={() => toggle(rule.rule_id)}
                  className="mt-0.5 w-4 h-4 rounded border-subtle text-brand-600 focus:ring-brand-300"
                />
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 flex-wrap">
                    <span className="text-body-strong text-[#2E2A24]">{rule.name}</span>
                    <Badge tone={rule.safe ? "success" : "warning"}>
                      {rule.safe ? "An toàn" : "Cần xác nhận"}
                    </Badge>
                    {rule.suggested === true && <Badge tone="info">Gợi ý nên áp dụng</Badge>}
                  </div>
                  <p className="text-small text-[#7A7266] mt-0.5">{rule.description}</p>
                  {/* CR-0016 — measured evidence behind the line-total suggestion */}
                  {rule.rationale && (
                    <div className="mt-2 rounded-lg bg-brand-50/60 border border-brand-100 px-3 py-2">
                      <p className="text-small text-[#2E2A24]">{rule.rationale}</p>
                      {rule.amount_signals && (
                        <div className="text-tiny text-[#7A7266] mt-1 flex flex-wrap gap-x-4 gap-y-0.5">
                          {rule.amount_signals.unit_price_median != null && (
                            <span>Đơn giá (median): {rule.amount_signals.unit_price_median}</span>
                          )}
                          {rule.amount_signals.quantity_median != null && (
                            <span>Số lượng (median): {rule.amount_signals.quantity_median}</span>
                          )}
                          {rule.amount_signals.implied_line_total_median != null && (
                            <span>Thành tiền ước: {rule.amount_signals.implied_line_total_median}</span>
                          )}
                          <span>Có cột thành tiền: {rule.amount_signals.has_explicit_total ? "có" : "chưa"}</span>
                          {rule.amount_signals.total_matches_unit_times_qty != null && (
                            <span>Khớp đơn giá×SL: {Math.round(rule.amount_signals.total_matches_unit_times_qty * 100)}%</span>
                          )}
                        </div>
                      )}
                    </div>
                  )}
                  {rule.target_columns && rule.target_columns.length > 0 && (
                    <p className="text-tiny text-[#A89F90] mt-1 font-mono">
                      → {rule.target_columns.join(", ")}
                    </p>
                  )}
                </div>
              </label>
            ))}
          </CardContent>
        </Card>
      ))}

      {error && (
        <div className="flex items-center gap-2 bg-danger-50 border border-danger-100 rounded-xl px-4 py-3">
          <AlertTriangle className="w-4 h-4 text-danger-500 shrink-0" />
          <p className="text-small text-danger-700">{error}</p>
        </div>
      )}

      <div className="flex items-center justify-between">
        <p className="text-small text-[#7A7266]">Đã chọn {selected.size} / {rules.length} quy tắc</p>
        <Button onClick={handleApply} loading={applying} disabled={selected.size === 0}>
          {applying ? "Đang áp dụng…" : "Áp dụng và tiếp tục →"}
        </Button>
      </div>
    </div>
  );
}
