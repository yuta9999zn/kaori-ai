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
import { useT } from '@/lib/i18n/provider';

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

function buildActions(t: (key: string, params?: Record<string, string | number>) => string):
  { icon: React.ComponentType<any>; title: string; action: Action }[] {
  return [
    { icon: Heading2, title: t('dmsMdToolbar.h2Title'), action: { linePrefix: '## ', placeholder: t('dmsMdToolbar.h2Placeholder') } },
    { icon: Bold, title: t('dmsMdToolbar.boldTitle'), action: { wrap: ['**', '**'], placeholder: t('dmsMdToolbar.boldPlaceholder') } },
    { icon: Italic, title: t('dmsMdToolbar.italicTitle'), action: { wrap: ['*', '*'], placeholder: t('dmsMdToolbar.italicPlaceholder') } },
    { icon: CaseUpper, title: t('dmsMdToolbar.upperTitle'), action: { transform: (s) => (s || t('dmsMdToolbar.upperPlaceholder')).toLocaleUpperCase('vi-VN') } },
    { icon: Highlighter, title: t('dmsMdToolbar.highlightTitle'), action: { wrap: ['==', '=='], placeholder: t('dmsMdToolbar.highlightPlaceholder') } },
    { icon: List, title: t('dmsMdToolbar.bulletTitle'), action: { linePrefix: '- ', placeholder: t('dmsMdToolbar.bulletPlaceholder') } },
    { icon: ListChecks, title: t('dmsMdToolbar.checklistTitle'), action: { linePrefix: '- [ ] ', placeholder: t('dmsMdToolbar.checklistPlaceholder') } },
    { icon: Link2, title: t('dmsMdToolbar.linkTitle'), action: { wrap: ['[', '](https://)'], placeholder: t('dmsMdToolbar.linkPlaceholder') } },
    { icon: Hash, title: t('dmsMdToolbar.hashtagTitle'), action: { wrap: [' #', ''], placeholder: t('dmsMdToolbar.hashtagPlaceholder') } },
  ];
}

export function MdToolbar({ target, onChange, className }: {
  target: React.RefObject<HTMLTextAreaElement | null>;
  onChange: (v: string) => void;
  className?: string;
}) {
  const t = useT();
  const ACTIONS = buildActions(t);
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
