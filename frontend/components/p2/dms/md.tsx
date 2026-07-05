// Mini Markdown renderer cho body_md của nghiệp vụ page (ADR-0042).
// Chỉ subset an toàn: heading / bold / italic / list / checklist / hr / paragraph.
// Không thêm dependency, không dangerouslySetInnerHTML — render bằng React nodes.
'use client';

import React from 'react';

function inline(text: string, keyPrefix: string): React.ReactNode[] {
  // **bold** và *italic* — tách tuần tự, không lồng nhau (đủ cho mô tả nghiệp vụ).
  const parts: React.ReactNode[] = [];
  let rest = text;
  let i = 0;
  const re = /(\*\*[^*]+\*\*|==[^=]+==|\*[^*]+\*|`[^`]+`|\[[^\]]+\]\((https?:\/\/[^)\s]+)\)|(?:^|(?<=\s))#[\p{L}0-9][\p{L}0-9_-]*)/u;
  while (rest) {
    const m = rest.match(re);
    if (!m || m.index === undefined) { parts.push(rest); break; }
    if (m.index > 0) parts.push(rest.slice(0, m.index));
    const tok = m[0];
    const key = `${keyPrefix}-${i++}`;
    if (tok.startsWith('**')) parts.push(<strong key={key}>{tok.slice(2, -2)}</strong>);
    else if (tok.startsWith('==')) parts.push(
      // ==highlight== — đánh dấu quan trọng (màu hệ Kaori, không hardcode hex)
      <mark key={key} className="bg-[var(--primary-gold)]/25 text-[var(--text-primary)] px-0.5 rounded">{tok.slice(2, -2)}</mark>);
    else if (tok.startsWith('`')) parts.push(
      <code key={key} className="px-1 py-0.5 bg-[var(--bg-app)] rounded text-[0.85em] font-mono">{tok.slice(1, -1)}</code>);
    else if (tok.startsWith('[')) {
      // [tên](https://…) — chỉ nhận http(s)
      const lm = tok.match(/^\[([^\]]+)\]\((https?:\/\/[^)\s]+)\)$/);
      if (lm) parts.push(
        <a key={key} href={lm[2]} target="_blank" rel="noreferrer"
          className="text-[var(--primary-gold-dark)] underline underline-offset-2 hover:opacity-80">{lm[1]}</a>);
      else parts.push(tok);
    } else if (tok.startsWith('#')) parts.push(
      // #hashtag — chip nhãn trong dòng văn bản
      <span key={key} className="inline-block px-1 py-0 rounded bg-[var(--bg-app)] border border-[var(--border-color)] text-[0.8em] font-mono text-[var(--text-secondary)] align-middle">{tok}</span>);
    else parts.push(<em key={key}>{tok.slice(1, -1)}</em>);
    rest = rest.slice(m.index + tok.length);
  }
  return parts;
}

export function Markdown({ text, className }: { text: string; className?: string }) {
  const lines = (text || '').split('\n');
  const out: React.ReactNode[] = [];
  let list: { items: React.ReactNode[]; kind: 'ul' | 'todo' } | null = null;
  let para: string[] = [];

  const flushPara = (k: string) => {
    if (para.length) {
      out.push(<p key={k} className="text-sm leading-relaxed mb-2">{inline(para.join(' '), k)}</p>);
      para = [];
    }
  };
  const flushList = (k: string) => {
    if (list) {
      out.push(<ul key={k} className="mb-2 space-y-1">{list.items}</ul>);
      list = null;
    }
  };

  lines.forEach((raw, n) => {
    const line = raw.trimEnd();
    const k = `l${n}`;
    const h = line.match(/^(#{1,4})\s+(.*)/);
    const todo = line.match(/^[-*]\s+\[([ xX])\]\s+(.*)/);
    const li = line.match(/^[-*]\s+(.*)/);

    if (!line.trim()) { flushPara(k); flushList(k + 'f'); return; }
    if (h) {
      flushPara(k); flushList(k + 'f');
      const level = h[1].length;
      const cls = level === 1 ? 'text-xl font-bold mt-4 mb-2'
        : level === 2 ? 'text-lg font-semibold mt-4 mb-1.5'
        : 'text-sm font-semibold mt-3 mb-1';
      out.push(React.createElement(`h${Math.min(level + 1, 6)}`, { key: k, className: cls }, inline(h[2], k)));
      return;
    }
    if (line === '---') { flushPara(k); flushList(k + 'f'); out.push(<hr key={k} className="my-3 border-[var(--border-color)]" />); return; }
    if (todo) {
      flushPara(k);
      if (!list || list.kind !== 'todo') { flushList(k + 'f'); list = { items: [], kind: 'todo' }; }
      list.items.push(
        <li key={k} className="text-sm flex items-start gap-2">
          <input type="checkbox" checked={todo[1] !== ' '} readOnly className="mt-0.5 accent-[var(--primary-gold-dark)]" />
          <span>{inline(todo[2], k)}</span>
        </li>);
      return;
    }
    if (li) {
      flushPara(k);
      if (!list || list.kind !== 'ul') { flushList(k + 'f'); list = { items: [], kind: 'ul' }; }
      list.items.push(<li key={k} className="text-sm list-disc ml-5">{inline(li[1], k)}</li>);
      return;
    }
    flushList(k + 'f');
    para.push(line);
  });
  flushPara('end'); flushList('endf');

  return <div className={className}>{out}</div>;
}
