// Toolbar soạn thảo Markdown (ADR-0042) — thao tác trên textarea qua ref:
// tiêu đề / đậm / nghiêng / VIẾT HOA / ==highlight== / gạch đầu dòng /
// checklist / link / #hashtag. Không thêm dependency — chèn cú pháp tại
// con trỏ, bôi đen rồi bấm là bọc quanh vùng chọn.
'use client';

import React from 'react';
import {
  Heading2, Bold, Italic, CaseUpper, Highlighter, List, ListChecks,
  Link2, Hash,
} from 'lucide-react';
import { cn } from '@/components/p2/foundation';

type Action =
  | { wrap: [string, string]; placeholder: string }
  | { linePrefix: string; placeholder: string }
  | { transform: (s: string) => string; placeholder?: undefined };

function applyAction(el: HTMLTextAreaElement, a: Action, onChange: (v: string) => void) {
  const { selectionStart: s, selectionEnd: e, value } = el;
  const sel = value.slice(s, e);
  let next = value;
  let cursor = e;

  if ('wrap' in a) {
    const [pre, post] = a.wrap;
    const body = sel || a.placeholder;
    next = value.slice(0, s) + pre + body + post + value.slice(e);
    cursor = s + pre.length + body.length + post.length;
  } else if ('linePrefix' in a) {
    // prefix từng dòng trong vùng chọn (hoặc dòng hiện tại)
    const lineStart = value.lastIndexOf('\n', s - 1) + 1;
    const block = value.slice(lineStart, e || lineStart);
    const body = (sel || '') === '' ? a.linePrefix + a.placeholder
      : block.split('\n').map((l) => a.linePrefix + l).join('\n');
    next = value.slice(0, lineStart) + body + value.slice(Math.max(e, lineStart));
    cursor = lineStart + body.length;
  } else {
    const body = a.transform(sel);
    next = value.slice(0, s) + body + value.slice(e);
    cursor = s + body.length;
  }

  onChange(next);
  requestAnimationFrame(() => { el.focus(); el.setSelectionRange(cursor, cursor); });
}

const ACTIONS: { icon: React.ComponentType<any>; title: string; action: Action }[] = [
  { icon: Heading2, title: 'Tiêu đề phụ', action: { linePrefix: '## ', placeholder: 'Tiêu đề' } },
  { icon: Bold, title: 'Đậm', action: { wrap: ['**', '**'], placeholder: 'chữ đậm' } },
  { icon: Italic, title: 'Nghiêng', action: { wrap: ['*', '*'], placeholder: 'chữ nghiêng' } },
  { icon: CaseUpper, title: 'VIẾT HOA vùng chọn', action: { transform: (s) => (s || 'VIẾT HOA').toLocaleUpperCase('vi-VN') } },
  { icon: Highlighter, title: 'Đánh dấu quan trọng', action: { wrap: ['==', '=='], placeholder: 'nội dung quan trọng' } },
  { icon: List, title: 'Gạch đầu dòng', action: { linePrefix: '- ', placeholder: 'nội dung' } },
  { icon: ListChecks, title: 'Checklist', action: { linePrefix: '- [ ] ', placeholder: 'việc cần làm' } },
  { icon: Link2, title: 'Chèn link', action: { wrap: ['[', '](https://)'], placeholder: 'tên link' } },
  { icon: Hash, title: 'Hashtag', action: { wrap: [' #', ''], placeholder: 'tag' } },
];

export function MdToolbar({ target, onChange, className }: {
  target: React.RefObject<HTMLTextAreaElement | null>;
  onChange: (v: string) => void;
  className?: string;
}) {
  return (
    <div className={cn('flex items-center gap-0.5 flex-wrap rounded-t border border-b-0 border-[var(--border-color)] bg-[var(--bg-app)]/70 px-1.5 py-1', className)}>
      {ACTIONS.map(({ icon: Icon, title, action }) => (
        <button key={title} type="button" title={title}
          onMouseDown={(ev) => {
            ev.preventDefault(); // giữ selection trong textarea
            if (target.current) applyAction(target.current, action, onChange);
          }}
          className="p-1.5 rounded hover:bg-[var(--primary-gold)]/15 text-[var(--text-secondary)] hover:text-[var(--primary-gold-dark)]">
          <Icon className="w-3.5 h-3.5" />
        </button>
      ))}
    </div>
  );
}
