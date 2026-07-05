// Ghi chú tài liệu (mig 141) — dải bình luận kiểu Confluence page comments:
// ai viết, lúc nào, nội dung Markdown; xoá mềm. Dùng cho cả tài liệu soạn
// trong Kaori lẫn file upload.
'use client';

import React, { useCallback, useEffect, useRef, useState } from 'react';
import { Loader2, MessageSquarePlus, Trash2, MessageSquare } from 'lucide-react';
import { Button, api, type ProblemDetails } from '@/components/p2/foundation';
import { Markdown } from './md';
import { MdToolbar } from './md-toolbar';
import { DocNote } from './types';

function fmtTime(iso: string | null): string {
  if (!iso) return '';
  try {
    return new Date(iso).toLocaleString('vi-VN', { day: '2-digit', month: '2-digit', year: 'numeric', hour: '2-digit', minute: '2-digit' });
  } catch { return iso; }
}

export function NotesPanel({ docId }: { docId: string }) {
  const [notes, setNotes] = useState<DocNote[] | null>(null);
  const [draft, setDraft] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const taRef = useRef<HTMLTextAreaElement>(null);

  const load = useCallback(() => {
    api<{ items: DocNote[] }>(`/api/v1/document-repository/${docId}/notes`)
      .then((r) => setNotes(r.items || []))
      .catch((e: ProblemDetails) => setError(e?.title || 'Không tải được ghi chú'));
  }, [docId]);

  useEffect(() => { setNotes(null); setDraft(''); load(); }, [load]);

  async function add() {
    if (!draft.trim()) return;
    setBusy(true);
    try {
      await api(`/api/v1/document-repository/${docId}/notes`, {
        method: 'POST', body: JSON.stringify({ body_md: draft.trim() }),
      });
      setDraft('');
      load();
    } catch (e: any) { setError(e?.title || 'Không lưu được ghi chú'); }
    finally { setBusy(false); }
  }

  async function remove(noteId: string) {
    try {
      await api(`/api/v1/document-repository/${docId}/notes/${noteId}`, { method: 'DELETE' });
      load();
    } catch (e: any) { setError(e?.title || 'Không xoá được'); }
  }

  return (
    <div className="bg-[var(--bg-card)] border border-[var(--border-color)] rounded-lg-custom px-4 py-3 space-y-3">
      <h2 className="text-sm font-semibold flex items-center gap-1.5">
        <MessageSquare className="w-4 h-4 text-[var(--primary-gold-dark)]" />
        Ghi chú ({notes?.length ?? '…'})
      </h2>
      {error && <p className="text-xs text-[var(--state-error)]">{error}</p>}

      {notes === null ? (
        <div className="py-3 text-center"><Loader2 className="w-4 h-4 animate-spin inline text-[var(--text-secondary)]" /></div>
      ) : notes.length === 0 ? (
        <p className="text-xs italic text-[var(--text-secondary)]">Chưa có ghi chú nào.</p>
      ) : (
        <div className="space-y-2.5">
          {notes.map((n) => (
            <div key={n.note_id} className="group border-l-2 border-[var(--primary-gold)]/40 pl-3">
              <div className="flex items-center gap-2">
                <span className="text-[10px] text-[var(--text-secondary)]">{fmtTime(n.created_at)}</span>
                <button onClick={() => remove(n.note_id)} title="Xoá ghi chú"
                  className="opacity-0 group-hover:opacity-100 text-[var(--text-secondary)] hover:text-[var(--state-error)]">
                  <Trash2 className="w-3 h-3" />
                </button>
              </div>
              <Markdown text={n.body_md} className="[&_p]:mb-0.5 text-sm" />
            </div>
          ))}
        </div>
      )}

      <div>
        <MdToolbar target={taRef} onChange={setDraft} />
        <textarea ref={taRef} rows={2} value={draft} onChange={(e) => setDraft(e.target.value)}
          placeholder="Viết ghi chú… (**đậm**, ==đánh dấu==, [tên](https://link), #hashtag)"
          className="w-full px-2 py-1.5 bg-white border border-[var(--border-color)] rounded-b rounded-t-none text-sm focus:outline-none focus:ring-2 focus:ring-[var(--primary-gold)]/30" />
        <div className="flex justify-end mt-1.5">
          <Button onClick={add} disabled={busy || !draft.trim()}>
            {busy ? <Loader2 className="w-3.5 h-3.5 mr-1.5 animate-spin" /> : <MessageSquarePlus className="w-3.5 h-3.5 mr-1.5" />}
            Thêm ghi chú
          </Button>
        </div>
      </div>
    </div>
  );
}
