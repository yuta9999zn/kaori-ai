// Insight nhóm/folder (ADR-0042) — POST 202 rồi poll; stats deterministic
// hiển thị trước, summary/findings từ Qwen (grounded) khi job xong.
'use client';

import React, { useEffect, useRef, useState } from 'react';
import { Loader2, Sparkles, X, AlertTriangle } from 'lucide-react';
import { Badge, cn, api } from '@/components/p2/foundation';
import { InsightData } from './types';

const POLL_MS = 3000;
const POLL_MAX = 150; // ~7.5 phút — Qwen trên máy pilot có thể cần ~5 phút; job bounded phía BE

// React StrictMode (dev) mount effect 2 lần → chặn POST đúp cùng scope
// trong cửa sổ ngắn (module-level vì ref không sống qua re-mount).
const _recentPosts = new Map<string, Promise<{ insight_id: string }>>();
function postInsightOnce(scopeKind: string, scope: Record<string, unknown>) {
  const key = scopeKind + JSON.stringify(scope);
  const existing = _recentPosts.get(key);
  if (existing) return existing;
  const p = api<{ insight_id: string }>('/api/v1/document-repository/insights', {
    method: 'POST',
    body: JSON.stringify({ scope_kind: scopeKind, scope }),
  });
  _recentPosts.set(key, p);
  setTimeout(() => _recentPosts.delete(key), 5000);
  return p;
}

export function InsightPanel({ scope, onClose }: {
  scope: { scope_kind: 'group' | 'folder'; scope: Record<string, unknown>; title: string };
  onClose: () => void;
}) {
  const [insight, setInsight] = useState<InsightData | null>(null);
  const [error, setError] = useState<string | null>(null);
  const polls = useRef(0);

  useEffect(() => {
    let timer: ReturnType<typeof setTimeout> | null = null;
    let cancelled = false;

    async function poll(id: string) {
      if (cancelled) return;
      try {
        const r = await api<InsightData>(`/api/v1/document-repository/insights/${id}`);
        if (cancelled) return;
        setInsight(r);
        if ((r.status === 'pending' || r.status === 'running') && polls.current++ < POLL_MAX) {
          timer = setTimeout(() => poll(id), POLL_MS);
        }
      } catch (e: any) {
        if (!cancelled) setError(e?.title || 'Không tải được kết quả phân tích');
      }
    }

    postInsightOnce(scope.scope_kind, scope.scope)
      .then((r) => poll(r.insight_id))
      .catch((e: any) => setError(e?.title || 'Không tạo được phân tích'));

    return () => { cancelled = true; if (timer) clearTimeout(timer); };
  }, []); // one shot per mount — panel remounts per request

  const running = !insight || insight.status === 'pending' || insight.status === 'running';
  const stats = insight?.stats || {};

  return (
    <div className="bg-[var(--bg-card)] border border-[var(--primary-gold)]/40 rounded-lg-custom p-4 space-y-3">
      <div className="flex items-center gap-2">
        <Sparkles className="w-4 h-4 text-[var(--primary-gold-dark)]" />
        <h3 className="text-sm font-semibold flex-1">Phân tích: {scope.title}</h3>
        {insight?.model === 'qwen2.5-local' && <Badge variant="default" className="text-[10px]">AI tạo — Qwen nội bộ</Badge>}
        <button onClick={onClose} className="text-[var(--text-secondary)] hover:text-[var(--state-error)]"><X className="w-4 h-4" /></button>
      </div>

      {error && <p className="text-sm text-[var(--state-error)]">{error}</p>}

      {running && !error && (
        <div className="text-sm text-[var(--text-secondary)] flex items-center gap-2">
          <Loader2 className="w-4 h-4 animate-spin" />
          Đang phân tích {insight?.status === 'running' ? '(đang chạy)' : '(đang chờ)'}…
          {insight && polls.current >= POLL_MAX && (
            <button
              onClick={() => {
                polls.current = 0;
                api<InsightData>(`/api/v1/document-repository/insights/${insight.insight_id}`)
                  .then(setInsight).catch(() => {});
              }}
              className="text-[var(--primary-gold-dark)] hover:underline text-xs">
              Kiểm tra lại
            </button>
          )}
        </div>
      )}

      {insight?.status === 'failed' && (
        <p className="text-sm text-[var(--state-error)] flex items-center gap-1.5">
          <AlertTriangle className="w-4 h-4" /> Phân tích thất bại: {insight.error || 'lỗi không rõ'}
        </p>
      )}

      {insight?.status === 'complete' && (
        <div className="space-y-3">
          {/* stats deterministic */}
          <div className="flex flex-wrap gap-2 text-[11px]">
            <span className="px-2 py-1 rounded bg-[var(--bg-app)]/70 border border-[var(--border-color)]">
              <b className="tabular-nums">{insight.doc_count}</b> tài liệu
            </span>
            {stats.completeness && (
              <span className="px-2 py-1 rounded bg-[var(--bg-app)]/70 border border-[var(--border-color)]">
                <b className="tabular-nums">{stats.completeness.incomplete_count}</b> thiếu thông tin
              </span>
            )}
            {Object.entries(stats.past_date_counts || {}).map(([k, v]) => (
              <span key={k} className="px-2 py-1 rounded bg-amber-50 border border-amber-200 text-amber-700">
                <b className="tabular-nums">{v as number}</b> quá «{k}»
              </span>
            ))}
            {Object.entries(stats.status_counts || {}).flatMap(([field, counts]) =>
              Object.entries(counts as Record<string, number>).map(([val, n]) => (
                <span key={`${field}:${val}`} className="px-2 py-1 rounded bg-[var(--bg-app)]/70 border border-[var(--border-color)]">
                  {field}: {val.replace(/_/g, ' ')} <b className="tabular-nums">{n}</b>
                </span>
              )))}
          </div>

          {insight.summary && (
            <p className="text-sm leading-relaxed border-l-2 border-[var(--primary-gold)] pl-3">{insight.summary}</p>
          )}

          {insight.findings.length > 0 && (
            <ul className="space-y-1.5">
              {insight.findings.map((f, i) => (
                <li key={i} className="text-sm">
                  <span className="font-medium">• {f.title}</span>
                  {f.detail && <span className="text-[var(--text-secondary)]"> — {f.detail}</span>}
                </li>
              ))}
            </ul>
          )}

          {stats.truncated && (
            <p className="text-[11px] text-amber-700 flex items-center gap-1">
              <AlertTriangle className="w-3 h-3" /> Lát cắt vượt giới hạn — kết quả tính trên một phần tài liệu.
            </p>
          )}
        </div>
      )}
    </div>
  );
}
