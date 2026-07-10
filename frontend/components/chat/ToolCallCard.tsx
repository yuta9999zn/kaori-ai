"use client";

/**
 * Collapsible card showing a single tool invocation —
 * ``🛠️ tool_name(args)`` header + ✔/✖ status badge + click-to-expand
 * preview of the JSON result. Mirrors the audit row we want users (and
 * platform admins reviewing chats) to see without clicking through.
 */
import { useState } from "react";
import { ChevronDown, ChevronRight, Wrench, Check, X, Loader2 } from "lucide-react";
import { cn } from "@/lib/cn";
import { useT } from "@/lib/i18n/provider";
import type { ToolCallRecord } from "./useChatStream";

interface Props {
  call: ToolCallRecord;
}

export function ToolCallCard({ call }: Props) {
  const t = useT();
  const [open, setOpen] = useState(false);
  const pending = call.ok === undefined;
  const ok      = call.ok === true;
  const failed  = call.ok === false;

  return (
    <div
      className={cn(
        "border rounded-md text-xs my-1.5",
        "border-[var(--color-subtle)] bg-canvas/60",
      )}
    >
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        className="w-full flex items-center gap-2 px-2.5 py-2 text-left hover:bg-canvas transition-colors rounded-md"
      >
        {open ? (
          <ChevronDown className="w-3 h-3 shrink-0 text-[var(--color-ink-muted)]" />
        ) : (
          <ChevronRight className="w-3 h-3 shrink-0 text-[var(--color-ink-muted)]" />
        )}
        <Wrench className="w-3 h-3 shrink-0 text-[var(--color-brand-500)]" />
        <span className="font-mono text-[11px] text-[var(--color-ink)] truncate flex-1">
          {call.tool}
        </span>
        {pending && (
          <Loader2 className="w-3 h-3 animate-spin text-[var(--color-ink-muted)] shrink-0" />
        )}
        {ok && (
          <Check className="w-3 h-3 text-[var(--color-success-700)] shrink-0" />
        )}
        {failed && (
          <X className="w-3 h-3 text-[var(--color-danger-700)] shrink-0" />
        )}
      </button>

      {open && (
        <div className="px-2.5 pb-2 pt-0.5 border-t border-[var(--color-subtle)]/60 space-y-1.5">
          {Object.keys(call.args).length > 0 && (
            <div>
              <div className="text-[10px] uppercase tracking-wider text-[var(--color-ink-muted)] mb-0.5">
                {t('chatToolcallcard.paramsLabel')}
              </div>
              <pre className="font-mono text-[11px] text-[var(--color-ink)] whitespace-pre-wrap break-words">
                {JSON.stringify(call.args, null, 2)}
              </pre>
            </div>
          )}
          {call.preview && (
            <div>
              <div className="text-[10px] uppercase tracking-wider text-[var(--color-ink-muted)] mb-0.5">
                {t('chatToolcallcard.resultLabel')}
              </div>
              <pre className="font-mono text-[11px] text-[var(--color-ink)] whitespace-pre-wrap break-words">
                {call.preview}
              </pre>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
