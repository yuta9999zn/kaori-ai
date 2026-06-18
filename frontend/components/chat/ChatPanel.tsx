"use client";

/**
 * Right-side drawer chatbot — Sprint 8 PR2.
 *
 * Mounted once at the layout level (one instance for the P2 enterprise
 * shell, one for the P1 platform shell). The toggle button floats at the
 * bottom-right when closed; the drawer slides in from the right when open.
 *
 * Why a drawer, not a /chat page: the user is usually mid-task on a
 * dashboard or list view when they want to ask something. Keeping the
 * page context behind the drawer (instead of navigating away) matches
 * the Linear / GitHub Copilot UX the plan §10 Q6 chose.
 */
import { useEffect, useRef, useState } from "react";
import { MessageSquare, X, RotateCcw, Send, Bot, User as UserIcon, AlertTriangle } from "lucide-react";
import { cn } from "@/lib/cn";
import { useChatStream, type ChatMessage, type ChatScope } from "./useChatStream";
import { ToolCallCard } from "./ToolCallCard";

interface Props {
  scope: ChatScope;
  /** Override the floating-button label. Defaults to "Hỏi Kaori". */
  buttonLabel?: string;
}

const SCOPE_INTROS: Record<ChatScope, { greeting: string; suggestions: string[] }> = {
  enterprise: {
    greeting:
      "Chào anh chị 👋 — Kaori đây. Có thể hỏi về tồn kho dữ liệu, " +
      "decisions gần đây, top khách hàng rủi ro, hạn mức billing.",
    suggestions: [
      "Tóm tắt quyết định AI tuần này",
      "Top 5 khách hàng đang rủi ro",
      "Hạn mức tháng này còn bao nhiêu?",
    ],
  },
  platform: {
    greeting:
      "Chào admin 👋 — Kaori Ops đây. Có thể hỏi tổng quan platform, " +
      "tenant đang vượt quota, signup gần đây.",
    suggestions: [
      "Tổng quan platform hiện tại",
      "Workspace nào đang vượt 95% quota?",
      "Số signup mới 30 ngày qua",
    ],
  },
};

export function ChatPanel({ scope, buttonLabel = "Hỏi Kaori" }: Props) {
  const [open, setOpen] = useState(false);
  const [draft, setDraft] = useState("");
  const { messages, status, send, reset } = useChatStream(scope);

  const intro = SCOPE_INTROS[scope];
  const scrollRef = useRef<HTMLDivElement | null>(null);

  // Auto-scroll to the bottom on new messages or streaming updates.
  useEffect(() => {
    if (!open) return;
    const el = scrollRef.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [messages, open, status]);

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!draft.trim() || status === "streaming") return;
    send(draft);
    setDraft("");
  }

  function handleSuggestion(s: string) {
    if (status === "streaming") return;
    send(s);
  }

  return (
    <>
      {/* Floating toggle button (visible when drawer is closed). */}
      {!open && (
        <button
          type="button"
          onClick={() => setOpen(true)}
          aria-label={buttonLabel}
          className={cn(
            "fixed bottom-6 right-6 z-40",
            "h-12 px-4 rounded-full",
            "bg-[var(--color-brand-500)] text-white shadow-soft-md",
            "hover:bg-[var(--color-brand-600)] transition-colors",
            "flex items-center gap-2 text-sm font-medium",
          )}
        >
          <MessageSquare className="w-4 h-4" />
          {buttonLabel}
        </button>
      )}

      {/* Drawer (visible when open). Backdrop is intentionally absent —
          we don't want to block the dashboard the user is looking at. */}
      <aside
        aria-hidden={!open}
        className={cn(
          "fixed top-0 right-0 z-40 h-screen w-[400px] max-w-[100vw]",
          "bg-white border-l border-[var(--color-subtle)] shadow-soft-md",
          "flex flex-col",
          "transition-transform duration-200",
          open ? "translate-x-0" : "translate-x-full pointer-events-none",
        )}
      >
        {/* Header ─────────────────────────────────────────────── */}
        <div className="flex items-center gap-3 px-4 h-14 border-b border-[var(--color-subtle)] shrink-0">
          <div className="w-8 h-8 rounded-md bg-[var(--color-brand-500)]/10 flex items-center justify-center">
            <Bot className="w-4 h-4 text-[var(--color-brand-500)]" />
          </div>
          <div className="flex-1 min-w-0">
            <p className="text-sm font-semibold text-[var(--color-ink)]">Kaori</p>
            <p className="text-[11px] text-[var(--color-ink-muted)]">
              {scope === "platform" ? "Platform Ops" : "Trợ lý doanh nghiệp"}
            </p>
          </div>
          {messages.length > 0 && (
            <button
              type="button"
              aria-label="Xoá hội thoại"
              onClick={reset}
              className="p-1.5 rounded-md text-[var(--color-ink-muted)] hover:bg-canvas hover:text-[var(--color-ink)] transition-colors"
            >
              <RotateCcw className="w-4 h-4" />
            </button>
          )}
          <button
            type="button"
            aria-label="Đóng chat"
            onClick={() => setOpen(false)}
            className="p-1.5 rounded-md text-[var(--color-ink-muted)] hover:bg-canvas hover:text-[var(--color-ink)] transition-colors"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Body ───────────────────────────────────────────────── */}
        <div
          ref={scrollRef}
          className="flex-1 overflow-y-auto px-4 py-4 space-y-3"
        >
          {messages.length === 0 ? (
            <Empty intro={intro} onSuggestion={handleSuggestion} />
          ) : (
            messages.map((m) => <Bubble key={m.id} message={m} />)
          )}
          {status === "streaming" && (() => {
            const last = messages.at(-1);
            return last?.role === "assistant" && !last.content;
          })() && (
            <Typing />
          )}
        </div>

        {/* Composer ───────────────────────────────────────────── */}
        <form
          onSubmit={handleSubmit}
          className="border-t border-[var(--color-subtle)] px-3 py-3 shrink-0 flex items-end gap-2 bg-white"
        >
          <textarea
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                handleSubmit(e);
              }
            }}
            placeholder={status === "streaming" ? "Đang trả lời…" : "Hỏi Kaori bất kỳ điều gì…"}
            rows={1}
            disabled={status === "streaming"}
            className={cn(
              "flex-1 resize-none rounded-md-custom border border-[var(--color-subtle)]",
              "px-3 py-2 text-sm",
              "focus:outline-none focus:border-[var(--color-brand-500)] focus:ring-1 focus:ring-[var(--color-brand-500)]/30",
              "disabled:bg-canvas disabled:text-[var(--color-ink-muted)]",
              "max-h-32",
            )}
          />
          <button
            type="submit"
            aria-label="Gửi"
            disabled={!draft.trim() || status === "streaming"}
            className={cn(
              "h-9 w-9 rounded-md-custom flex items-center justify-center shrink-0",
              "bg-[var(--color-brand-500)] text-white",
              "hover:bg-[var(--color-brand-600)] transition-colors",
              "disabled:bg-[var(--color-subtle)] disabled:text-[var(--color-ink-muted)] disabled:cursor-not-allowed",
            )}
          >
            <Send className="w-4 h-4" />
          </button>
        </form>
      </aside>
    </>
  );
}


// ────────────────────────────────────────────────────────────────────────────
// Sub-components
// ────────────────────────────────────────────────────────────────────────────

function Empty({
  intro,
  onSuggestion,
}: {
  intro: { greeting: string; suggestions: string[] };
  onSuggestion: (s: string) => void;
}) {
  return (
    <div className="text-sm text-[var(--color-ink-muted)] space-y-3">
      <p>{intro.greeting}</p>
      <div className="space-y-1.5">
        {intro.suggestions.map((s) => (
          <button
            key={s}
            type="button"
            onClick={() => onSuggestion(s)}
            className={cn(
              "w-full text-left px-3 py-2 rounded-md border border-[var(--color-subtle)]",
              "hover:border-[var(--color-brand-500)]/50 hover:bg-canvas/60",
              "transition-colors text-sm text-[var(--color-ink)]",
            )}
          >
            {s}
          </button>
        ))}
      </div>
    </div>
  );
}

function Bubble({ message }: { message: ChatMessage }) {
  if (message.role === "user") {
    return (
      <div className="flex items-start gap-2 justify-end">
        <div className="rounded-md-custom bg-[var(--color-brand-500)]/10 px-3 py-2 text-sm text-[var(--color-ink)] max-w-[280px] whitespace-pre-wrap break-words">
          {message.content}
        </div>
        <div className="w-7 h-7 shrink-0 rounded-full bg-canvas border border-[var(--color-subtle)] flex items-center justify-center">
          <UserIcon className="w-3.5 h-3.5 text-[var(--color-ink-muted)]" />
        </div>
      </div>
    );
  }

  if (message.role === "error") {
    return (
      <div className="flex items-start gap-2">
        <div className="w-7 h-7 shrink-0 rounded-full bg-[var(--color-danger-50)] flex items-center justify-center">
          <AlertTriangle className="w-3.5 h-3.5 text-[var(--color-danger-700)]" />
        </div>
        <div className="rounded-md-custom border border-[var(--color-danger-200)] bg-[var(--color-danger-50)] px-3 py-2 text-sm text-[var(--color-danger-700)] max-w-[280px]">
          <p className="font-medium">{message.title}</p>
          {message.detail && (
            <p className="text-xs mt-0.5 opacity-80">{message.detail}</p>
          )}
        </div>
      </div>
    );
  }

  // assistant
  return (
    <div className="flex items-start gap-2">
      <div className="w-7 h-7 shrink-0 rounded-full bg-[var(--color-brand-500)]/10 flex items-center justify-center">
        <Bot className="w-3.5 h-3.5 text-[var(--color-brand-500)]" />
      </div>
      <div className="flex-1 min-w-0 space-y-1">
        {message.toolCalls.map((tc, i) => (
          <ToolCallCard key={i} call={tc} />
        ))}
        {message.content && (
          <div className="rounded-md-custom bg-canvas border border-[var(--color-subtle)] px-3 py-2 text-sm text-[var(--color-ink)] whitespace-pre-wrap break-words">
            {message.content}
          </div>
        )}
      </div>
    </div>
  );
}

function Typing() {
  return (
    <div className="flex items-start gap-2">
      <div className="w-7 h-7 shrink-0 rounded-full bg-[var(--color-brand-500)]/10 flex items-center justify-center">
        <Bot className="w-3.5 h-3.5 text-[var(--color-brand-500)]" />
      </div>
      <div className="rounded-md-custom bg-canvas border border-[var(--color-subtle)] px-3 py-2 text-sm flex items-center gap-1">
        <span className="w-1.5 h-1.5 rounded-full bg-[var(--color-ink-muted)] animate-pulse" />
        <span className="w-1.5 h-1.5 rounded-full bg-[var(--color-ink-muted)] animate-pulse [animation-delay:120ms]" />
        <span className="w-1.5 h-1.5 rounded-full bg-[var(--color-ink-muted)] animate-pulse [animation-delay:240ms]" />
      </div>
    </div>
  );
}
