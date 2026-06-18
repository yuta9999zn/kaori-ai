'use client';

// Client-only BPMN editor — wraps bpmn-js (Camunda's bpmn.io modeler) + a
// Vietnamese Kaori properties panel that assigns a KAORI_ACTION to the
// selected element via the `kaori:nodeType` extension attribute.
//
// MUST be loaded with next/dynamic { ssr:false } (see BpmnPanel) — bpmn-js
// touches `window`/DOM at import time and cannot be server-rendered.
//
// License: bpmn-js keeps the "bpmn.io" watermark (anh chốt giữ 2026-05-29).

import { useCallback, useEffect, useRef, useState } from 'react';
import BpmnModeler from 'bpmn-js/lib/Modeler';
import { layoutProcess } from 'bpmn-auto-layout';
import 'bpmn-js/dist/assets/diagram-js.css';
import 'bpmn-js/dist/assets/bpmn-js.css';
import 'bpmn-js/dist/assets/bpmn-font/css/bpmn.css';

import { kaoriModdle } from '@/lib/bpmn/kaori-moddle';
import {
  ACTION_GROUP_LABEL,
  KAORI_ACTION_BY_KEY,
  KAORI_NODETYPE_ATTR,
  actionsForBpmnType,
  isExecutable,
  type KaoriAction,
} from '@/lib/bpmn/bpmn-elements';

const KAORI_ATTR = KAORI_NODETYPE_ATTR; // 'kaori:nodeType'

// Minimal valid diagram for a brand-new workflow (one start event + DI).
const EMPTY_DIAGRAM = `<?xml version="1.0" encoding="UTF-8"?>
<bpmn:definitions xmlns:bpmn="http://www.omg.org/spec/BPMN/20100524/MODEL"
  xmlns:bpmndi="http://www.omg.org/spec/BPMN/20100524/DI"
  xmlns:dc="http://www.omg.org/spec/DD/20100524/DC"
  xmlns:kaori="http://kaori.ai/bpmn"
  id="Definitions_kaori" targetNamespace="http://kaori.ai/bpmn">
  <bpmn:process id="Process_1" isExecutable="true">
    <bpmn:startEvent id="StartEvent_1" name="Bắt đầu" />
  </bpmn:process>
  <bpmndi:BPMNDiagram id="BPMNDiagram_1">
    <bpmndi:BPMNPlane id="BPMNPlane_1" bpmnElement="Process_1">
      <bpmndi:BPMNShape id="StartEvent_1_di" bpmnElement="StartEvent_1">
        <dc:Bounds x="180" y="160" width="36" height="36" />
      </bpmndi:BPMNShape>
    </bpmndi:BPMNPlane>
  </bpmndi:BPMNDiagram>
</bpmn:definitions>`;

export interface BpmnEditorProps {
  initialXml: string | null;
  /** Fires (debounced) with the current BPMN XML on every diagram change. */
  onChange?: (xml: string) => void;
}

function readNodeType(bo: any): string | null {
  if (!bo) return null;
  // moddle stores the extension attr both as a typed prop and in $attrs.
  return bo.get?.(KAORI_ATTR) ?? bo.nodeType ?? bo.$attrs?.[KAORI_ATTR] ?? null;
}

export default function BpmnEditor({ initialXml, onChange }: BpmnEditorProps) {
  const canvasRef = useRef<HTMLDivElement | null>(null);
  const modelerRef = useRef<any>(null);
  const readyRef = useRef(false);
  const [selected, setSelected] = useState<any | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [, force] = useState(0);

  const safeZoom = useCallback(() => {
    try {
      (modelerRef.current?.get('canvas') as any)?.zoom('fit-viewport');
    } catch {
      /* empty/rootless canvas — ignore */
    }
  }, []);

  // bpmn-auto-layout can place a disconnected ("treo") node at a tiny/negative
  // coordinate → it ends up hidden behind the palette. Shift the whole diagram
  // so its top-left clears the palette before zooming.
  const nudgeIntoView = useCallback(() => {
    const m = modelerRef.current;
    if (!m) return;
    try {
      const er = m.get('elementRegistry') as any;
      const root = (m.get('canvas') as any).getRootElement();
      // top-level shapes only (pools move their children with them)
      const top = er.filter(
        (el: any) => el.parent === root && typeof el.x === 'number' && !el.waypoints,
      );
      if (!top.length) return;
      const MARGIN_X = 180, MARGIN_Y = 80;
      const minX = Math.min(...top.map((s: any) => s.x));
      const minY = Math.min(...top.map((s: any) => s.y));
      const dx = minX < MARGIN_X ? MARGIN_X - minX : 0;
      const dy = minY < MARGIN_Y ? MARGIN_Y - minY : 0;
      if (dx || dy) (m.get('modeling') as any).moveElements(top, { x: dx, y: dy });
    } catch {
      /* best-effort layout nudge */
    }
    safeZoom();
  }, [safeZoom]);

  // Import that NEVER crashes the editor. If the stored diagram fails to
  // render (the classic bpmn-js "reading 'root-0'" — missing/broken layout
  // info, common with pools), regenerate the layout from the semantics via
  // auto-layout; if even that fails, fall back to a blank canvas so the user
  // can keep working instead of staring at a dead error.
  const robustImport = useCallback(async (xml: string | null) => {
    const modeler = modelerRef.current;
    if (!modeler) return;
    let source = xml && xml.trim() ? xml : EMPTY_DIAGRAM;
    // A generated/projected diagram (nodes→BPMN) ships WITHOUT layout info
    // (no BPMNDiagram) so gateways fork into a proper tree here rather than
    // stacking at the origin. Lay it out first, then persist the computed XML.
    let autoLaidOut = false;
    if (!/BPMNDiagram/.test(source)) {
      try { source = await layoutProcess(source); autoLaidOut = true; } catch { /* import as-is */ }
    }
    try {
      await modeler.importXML(source);
      safeZoom();
      if (autoLaidOut) onChange?.(source);   // keep the freshly computed layout
      return;
    } catch {
      /* fall through to auto-layout recovery */
    }
    try {
      const laidOut = await layoutProcess(source);
      await modeler.importXML(laidOut);
      nudgeIntoView();
      setNotice('Sơ đồ đã lưu thiếu thông tin bố cục — Kaori đã tự sắp xếp lại. '
        + 'Kiểm tra lại vị trí rồi bấm "Lưu sơ đồ".');
      onChange?.(laidOut);
      return;
    } catch {
      /* fall through to blank */
    }
    try {
      await modeler.importXML(EMPTY_DIAGRAM);
      safeZoom();
      setNotice('Không mở được sơ đồ đã lưu (lỗi định dạng/bố cục). '
        + 'Đã mở canvas trống — vẽ lại, hoặc bấm "Tải .bpmn" để lấy bản XML cũ.');
    } catch {
      setNotice('Không khởi tạo được trình thiết kế BPMN.');
    }
  }, [onChange, safeZoom, nudgeIntoView]);

  useEffect(() => {
    if (!canvasRef.current) return;
    const modeler = new BpmnModeler({
      container: canvasRef.current,
      moddleExtensions: { kaori: kaoriModdle },
    });
    modelerRef.current = modeler;

    const onSel = (e: any) => setSelected(e.newSelection?.[0] ?? null);
    modeler.on('selection.changed', onSel);

    const onChanged = async () => {
      if (!readyRef.current) return; // ignore the import's own command
      try {
        const { xml } = await modeler.saveXML({ format: true });
        if (xml) onChange?.(xml);
        force((n) => n + 1);
      } catch {
        /* transient export error — ignored, next change retries */
      }
    };
    modeler.on('commandStack.changed', onChanged);

    (async () => {
      await robustImport(initialXml);
      readyRef.current = true;
    })();

    return () => {
      readyRef.current = false;
      modeler.destroy();
    };
    // Mount once. Re-loading a different diagram is done by remounting with a
    // new React key (BpmnPanel bumps it on Load).
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const setName = useCallback((name: string) => {
    const m = modelerRef.current;
    if (!m || !selected) return;
    m.get('modeling').updateProperties(selected, { name });
    force((n) => n + 1);
  }, [selected]);

  const setAction = useCallback((key: string) => {
    const m = modelerRef.current;
    if (!m || !selected) return;
    m.get('modeling').updateProperties(selected, { [KAORI_ATTR]: key || undefined });
    force((n) => n + 1);
  }, [selected]);

  // "Sắp xếp lại bố cục" — regenerate clean positions/waypoints/labels from the
  // diagram semantics. Fixes overlapping labels, mis-placed gateway names and
  // crooked flows (anh's #2/#3/#6). Note: keeps Kaori actions on tasks.
  const relayout = useCallback(async () => {
    const m = modelerRef.current;
    if (!m || busy) return;
    setBusy(true);
    setNotice(null);
    try {
      const { xml } = await m.saveXML({ format: true });
      const laidOut = await layoutProcess(xml);
      await m.importXML(laidOut);
      nudgeIntoView();
      // saveXML again after the nudge so the persisted XML matches what's shown.
      const after = await m.saveXML({ format: true });
      onChange?.(after.xml ?? laidOut);
      setNotice('Đã sắp xếp lại bố cục. Bấm "Lưu sơ đồ" để giữ.');
    } catch {
      setNotice('Không sắp xếp lại được (sơ đồ có thể chứa pool/lane phức tạp).');
    } finally {
      setBusy(false);
    }
  }, [busy, onChange, nudgeIntoView]);

  const exportBpmn = useCallback(async () => {
    const m = modelerRef.current;
    if (!m) return;
    try {
      const { xml } = await m.saveXML({ format: true });
      const blob = new Blob([xml ?? ''], { type: 'application/bpmn+xml' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = 'workflow.bpmn';
      a.click();
      URL.revokeObjectURL(url);
    } catch {
      setNotice('Không xuất được .bpmn.');
    }
  }, []);

  const bo = selected?.businessObject;
  const bpmnType: string | undefined = bo?.$type;
  const currentKey = readNodeType(bo);
  const actions: KaoriAction[] = bpmnType ? actionsForBpmnType(bpmnType) : [];
  const grouped = actions.reduce<Record<string, KaoriAction[]>>((acc, a) => {
    (acc[a.group] = acc[a.group] || []).push(a);
    return acc;
  }, {});
  const execOk = bpmnType ? isExecutable(bpmnType, currentKey) : false;
  const isTaskCarrier =
    !!bpmnType && (bpmnType.endsWith('Task') || bpmnType === 'bpmn:CallActivity');

  return (
    <div className="flex h-[640px] flex-col rounded-md-custom border border-[var(--border-color)] overflow-hidden bg-white">
      {/* Editor toolbar */}
      <div className="flex items-center gap-2 border-b border-[var(--border-color)] px-2 py-1.5 text-xs">
        <button
          onClick={() => void relayout()}
          disabled={busy}
          className="rounded border border-[var(--border-color)] px-2 py-1 hover:bg-black/5 disabled:opacity-50"
          title="Tự dựng lại vị trí/đường nối/nhãn từ cấu trúc sơ đồ"
        >
          {busy ? 'Đang sắp xếp…' : '↹ Sắp xếp lại bố cục'}
        </button>
        <button
          onClick={() => void exportBpmn()}
          className="rounded border border-[var(--border-color)] px-2 py-1 hover:bg-black/5"
        >
          ↓ Tải .bpmn
        </button>
        {notice && <span className="ml-2 text-[11px] text-amber-700">{notice}</span>}
      </div>

      <div className="flex flex-1 min-h-0">
        {/* Canvas */}
        <div className="relative flex-1 min-w-0">
          <div ref={canvasRef} className="absolute inset-0" />
        </div>

        {/* Kaori properties panel (VN) */}
        <aside className="w-72 shrink-0 border-l border-[var(--border-color)] bg-[var(--bg-subtle,#fafafa)] overflow-y-auto p-3 text-sm">
          <h3 className="font-semibold text-[var(--text-primary)] mb-2">Thuộc tính</h3>
          {!selected ? (
            <div className="text-xs text-[var(--text-secondary)] space-y-2">
              <p>Chọn một phần tử để cấu hình. Kéo-thả từ bảng công cụ bên trái
                để thêm bước / cổng / sự kiện.</p>
              <p><b>Nối 2 phần tử:</b> rê chuột vào phần tử nguồn → bảng nút nhỏ
                hiện bên phải nó → <b>kéo nút mũi tên</b> (Kết nối) thả vào phần
                tử đích. Hoặc bấm công cụ <b>mũi tên</b> ở palette trái rồi bấm
                nguồn → bấm đích.</p>
            </div>
          ) : (
            <div className="space-y-3">
              <div>
                <label className="block text-[11px] uppercase tracking-wide text-[var(--text-secondary)] mb-1">
                  Loại BPMN
                </label>
                <div className="text-xs font-mono text-[var(--text-primary)]">{bpmnType}</div>
              </div>

              <div>
                <label className="block text-[11px] uppercase tracking-wide text-[var(--text-secondary)] mb-1">
                  Tên hiển thị
                </label>
                <input
                  value={bo?.name ?? ''}
                  onChange={(e) => setName(e.target.value)}
                  placeholder="Đặt tên bước…"
                  className="w-full rounded border border-[var(--border-color)] px-2 py-1 text-sm"
                />
              </div>

              {/* Kaori action — only for task carriers (events/gateways map
                  structurally; assigning an action is meaningless for them). */}
              {isTaskCarrier && (
                <div>
                  <label className="block text-[11px] uppercase tracking-wide text-[var(--text-secondary)] mb-1">
                    Hành động Kaori
                  </label>
                  <select
                    value={currentKey ?? ''}
                    onChange={(e) => setAction(e.target.value)}
                    className="w-full rounded border border-[var(--border-color)] px-2 py-1 text-sm bg-white"
                  >
                    <option value="">— Chưa gán (chỉ thiết kế) —</option>
                    {Object.entries(grouped).map(([group, items]) => (
                      <optgroup key={group} label={ACTION_GROUP_LABEL[group as keyof typeof ACTION_GROUP_LABEL] ?? group}>
                        {items.map((a) => (
                          <option key={a.key} value={a.key}>{a.vi}</option>
                        ))}
                      </optgroup>
                    ))}
                  </select>
                  {currentKey && KAORI_ACTION_BY_KEY[currentKey]?.desc && (
                    <p className="mt-1 text-[11px] text-[var(--text-secondary)]">
                      {KAORI_ACTION_BY_KEY[currentKey].desc}
                    </p>
                  )}
                </div>
              )}

              {/* Gateway condition hint */}
              {bpmnType?.endsWith('Gateway') && (
                <p className="text-[11px] text-[var(--text-secondary)]">
                  Điều kiện nhánh đặt trên <b>đường nối ra</b> của cổng: chọn
                  mũi tên → ô "Tên" gõ điều kiện (vd <code>{'${score >= 80}'}</code>).
                  Nhánh mặc định (else) để trống tên + đặt làm Default.
                </p>
              )}

              {/* Executable badge */}
              <div
                className={
                  'inline-flex items-center gap-1 rounded px-2 py-1 text-[11px] font-medium ' +
                  (execOk ? 'bg-emerald-50 text-emerald-700' : 'bg-amber-50 text-amber-700')
                }
              >
                {execOk ? '✓ Thực thi được' : '⚙ Thiết kế — chưa thực thi'}
              </div>
            </div>
          )}
        </aside>
      </div>
    </div>
  );
}
