'use client';

// BPMN tab for the workflow detail page. Loads/saves the diagram via the BE
// (mig 115 GET/PUT /workflows/{id}/bpmn) and projects it onto nodes/edges
// (POST /bpmn/sync). The actual editor is bpmn-js — a browser-only library —
// so it is loaded with next/dynamic { ssr:false } (per Next 16 lazy-loading
// guide: ssr:false is only allowed inside a Client Component).

import dynamic from 'next/dynamic';
import { useCallback, useEffect, useRef, useState } from 'react';
import { api, type ApiError } from '@/lib/api';

const BpmnEditor = dynamic(() => import('./BpmnEditor'), {
  ssr: false,
  loading: () => (
    <div className="flex h-[640px] items-center justify-center rounded-md-custom border border-[var(--border-color)] text-sm text-[var(--text-secondary)]">
      Đang tải trình thiết kế BPMN…
    </div>
  ),
});

interface BpmnDoc {
  workflow_id: string;
  bpmn_xml: string | null;
  last_modified_at: string;
  design_summary: BpmnSummary | null;
}
interface BpmnSummary {
  node_count: number;
  edge_count: number;
  executable_count: number;
  trigger_count: number;
  message_flow_count?: number;
  boundary_count?: number;
  pools?: { name: string; lanes: string[] }[];
  design_only?: { id: string; title: string; bpmn_type: string }[];
  warnings?: string[];
}
interface BpmnSyncResult {
  nodes_created: number;
  edges_created: number;
  design_summary: BpmnSummary;
  dangling_branches: { title: string; expected_edges: number; actual_edges: number }[];
}

export default function BpmnPanel({ workflowId }: { workflowId: string }) {
  const [loaded, setLoaded] = useState(false);
  const [initialXml, setInitialXml] = useState<string | null>(null);
  const [summary, setSummary] = useState<BpmnSummary | null>(null);
  const [reloadKey, setReloadKey] = useState(0);
  const [busy, setBusy] = useState<null | 'save' | 'sync' | 'fromsteps'>(null);
  const [toast, setToast] = useState<{ kind: 'ok' | 'err'; msg: string } | null>(null);
  const [syncResult, setSyncResult] = useState<BpmnSyncResult | null>(null);
  const currentXml = useRef<string | null>(null);

  const flash = (kind: 'ok' | 'err', msg: string) => {
    setToast({ kind, msg });
    window.setTimeout(() => setToast(null), 4000);
  };

  const load = useCallback(async () => {
    setLoaded(false);
    try {
      let doc = await api<BpmnDoc>(`/api/v1/workflows/${workflowId}/bpmn`);
      // Always re-project from the Builder steps on open so the diagram reflects
      // the LATEST structure — anh: adding switch branches didn't refresh the
      // BPMN (the old auto-sync only fired when blank). The Linear builder is the
      // source of truth today; free-form BPMN authoring + pools is a #9 concern.
      try {
        doc = await api<BpmnDoc>(`/api/v1/workflows/${workflowId}/bpmn/from-steps`, { method: 'POST' });
      } catch { /* 422 = workflow has no steps yet → keep the stored/blank diagram */ }
      setInitialXml(doc.bpmn_xml);
      currentXml.current = doc.bpmn_xml;
      setSummary(doc.design_summary);
      setReloadKey((k) => k + 1); // remount editor with fresh XML
    } catch (e) {
      flash('err', (e as ApiError)?.message ?? 'Không tải được BPMN');
    } finally {
      setLoaded(true);
    }
  }, [workflowId]);

  useEffect(() => {
    void load();
  }, [load]);

  const save = async () => {
    if (!currentXml.current) {
      flash('err', 'Chưa có sơ đồ để lưu');
      return;
    }
    setBusy('save');
    try {
      const doc = await api<BpmnDoc>(`/api/v1/workflows/${workflowId}/bpmn`, {
        method: 'PUT',
        body: JSON.stringify({ bpmn_xml: currentXml.current }),
      });
      setSummary(doc.design_summary);
      flash('ok', 'Đã lưu sơ đồ BPMN');
    } catch (e) {
      flash('err', (e as ApiError)?.message ?? 'Lưu thất bại (BPMN không hợp lệ?)');
    } finally {
      setBusy(null);
    }
  };

  // Reverse projection — render the linear-Builder steps as a BPMN diagram.
  // Read-only on the steps, so it's the safe way to populate an empty canvas.
  const fromSteps = async () => {
    setBusy('fromsteps');
    try {
      const doc = await api<BpmnDoc>(
        `/api/v1/workflows/${workflowId}/bpmn/from-steps`,
        { method: 'POST' },
      );
      setInitialXml(doc.bpmn_xml);
      currentXml.current = doc.bpmn_xml;
      setSummary(doc.design_summary);
      setReloadKey((k) => k + 1);
      flash('ok', 'Đã dựng sơ đồ BPMN từ các bước trong Builder');
    } catch (e) {
      flash('err', (e as ApiError)?.message ?? 'Không dựng được sơ đồ từ bước');
    } finally {
      setBusy(null);
    }
  };

  const sync = async () => {
    // BPMN→nodes is a REPLACE (Model A). Warn before overwriting builder steps.
    if (!window.confirm(
      'Đồng bộ sẽ GHI ĐÈ toàn bộ các bước trong Builder bằng sơ đồ BPMN hiện tại. '
      + 'Nếu bạn vừa dựng bước trong Builder mà sơ đồ này chưa phản ánh, hãy bấm '
      + '“Tạo sơ đồ từ bước” trước. Tiếp tục đồng bộ?')) {
      return;
    }
    setBusy('sync');
    try {
      // Save first so the sync reads the latest diagram.
      if (currentXml.current) {
        await api(`/api/v1/workflows/${workflowId}/bpmn`, {
          method: 'PUT',
          body: JSON.stringify({ bpmn_xml: currentXml.current }),
        });
      }
      const res = await api<BpmnSyncResult>(
        `/api/v1/workflows/${workflowId}/bpmn/sync`,
        { method: 'POST' },
      );
      setSyncResult(res);
      setSummary(res.design_summary);
      flash('ok', `Đã đồng bộ: ${res.nodes_created} bước, ${res.edges_created} luồng`);
    } catch (e) {
      flash('err', (e as ApiError)?.message ?? 'Đồng bộ thất bại');
    } finally {
      setBusy(null);
    }
  };

  return (
    <div className="space-y-3">
      {/* Toolbar */}
      <div className="flex flex-wrap items-center gap-2">
        <span className="inline-flex items-center gap-1 rounded bg-amber-50 px-2 py-1 text-[11px] font-medium text-amber-700">
          ⚙ Thiết kế — chưa thực thi
        </span>
        <div className="flex-1" />
        <button
          onClick={() => void load()}
          disabled={busy !== null}
          className="rounded-md-custom border border-[var(--border-color)] px-3 py-1.5 text-sm hover:bg-black/5 disabled:opacity-50"
        >
          Tải lại
        </button>
        <button
          onClick={() => void fromSteps()}
          disabled={busy !== null}
          title="Dựng sơ đồ BPMN từ các bước đã tạo trong Builder (không ghi đè bước)"
          className="rounded-md-custom border border-[var(--border-color)] px-3 py-1.5 text-sm hover:bg-black/5 disabled:opacity-50"
        >
          {busy === 'fromsteps' ? 'Đang dựng…' : 'Tạo sơ đồ từ bước'}
        </button>
        <button
          onClick={() => void save()}
          disabled={busy !== null}
          className="rounded-md-custom border border-[var(--border-color)] px-3 py-1.5 text-sm hover:bg-black/5 disabled:opacity-50"
        >
          {busy === 'save' ? 'Đang lưu…' : 'Lưu sơ đồ'}
        </button>
        <button
          onClick={() => void sync()}
          disabled={busy !== null}
          className="rounded-md-custom bg-[var(--primary-gold)] px-3 py-1.5 text-sm font-medium text-white hover:opacity-90 disabled:opacity-50"
        >
          {busy === 'sync' ? 'Đang đồng bộ…' : 'Lưu & Đồng bộ bước'}
        </button>
      </div>

      {/* Editor (client-only) */}
      {loaded && <BpmnEditor key={reloadKey} initialXml={initialXml} onChange={(xml) => (currentXml.current = xml)} />}

      {/* Design summary */}
      {summary && (
        <div className="rounded-md-custom border border-[var(--border-color)] bg-white p-3 text-xs">
          <div className="flex flex-wrap gap-x-4 gap-y-1 text-[var(--text-secondary)]">
            {/* "Phần tử" not "Bước": the BPMN diagram count includes synthetic
                start/end events + gateways, so it legitimately exceeds the
                workflow's authored step count (shown on the Builder/Báo cáo
                tabs). Labelling it "Bước" made the 3 tabs look contradictory. */}
            <span title="Tổng phần tử sơ đồ BPMN — gồm cả sự kiện bắt đầu/kết thúc và cổng (gateway), nên nhiều hơn số bước nghiệp vụ.">Phần tử: <b className="text-[var(--text-primary)]">{summary.node_count}</b></span>
            <span>Luồng: <b className="text-[var(--text-primary)]">{summary.edge_count}</b></span>
            <span>Thực thi được: <b className="text-emerald-700">{summary.executable_count}</b></span>
            <span>Trigger: <b className="text-[var(--text-primary)]">{summary.trigger_count}</b></span>
            {!!summary.message_flow_count && <span>Message flow: <b>{summary.message_flow_count}</b></span>}
            {!!summary.pools?.length && <span>Pool: <b>{summary.pools.length}</b></span>}
          </div>
          {!!summary.pools?.length && (
            <div className="mt-2 text-[var(--text-secondary)]">
              {summary.pools.map((p) => (
                <div key={p.name}>
                  <b className="text-[var(--text-primary)]">{p.name}</b>
                  {p.lanes.length ? ` — lane: ${p.lanes.join(', ')}` : ''}
                </div>
              ))}
            </div>
          )}
          {!!summary.warnings?.length && (
            <ul className="mt-2 list-disc pl-4 text-amber-700">
              {summary.warnings.slice(0, 8).map((w, i) => <li key={i}>{w}</li>)}
            </ul>
          )}
        </div>
      )}

      {/* Sync result — dangling branches block activation */}
      {syncResult?.dangling_branches?.length ? (
        <div className="rounded-md-custom border border-rose-200 bg-rose-50 p-3 text-xs text-rose-700">
          <b>Nhánh chưa nối đủ (cần xử lý trước khi chạy):</b>
          <ul className="mt-1 list-disc pl-4">
            {syncResult.dangling_branches.map((d, i) => (
              <li key={i}>{d.title}: có {d.actual_edges}/{d.expected_edges} nhánh</li>
            ))}
          </ul>
        </div>
      ) : null}

      {/* Toast */}
      {toast && (
        <div
          className={
            'fixed bottom-4 right-4 z-50 rounded-md-custom px-4 py-2 text-sm shadow-lg ' +
            (toast.kind === 'ok' ? 'bg-emerald-600 text-white' : 'bg-rose-600 text-white')
          }
        >
          {toast.msg}
        </div>
      )}
    </div>
  );
}
