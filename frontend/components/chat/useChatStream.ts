"use client";

/**
 * Sprint 8 — chat SSE stream consumer.
 *
 * The chat endpoint is POST + text/event-stream, which native EventSource
 * cannot do (EventSource is GET-only). We use ``fetch`` with a streaming
 * body reader instead. The wire format is identical to standard SSE so
 * the parser is straightforward: split on the blank-line frame separator,
 * extract ``data: <json>`` lines, dispatch to the caller.
 *
 * The hook exposes:
 *   - ``messages``     turn-by-turn conversation (user + assistant + tools)
 *   - ``status``       'idle' | 'streaming' | 'error'
 *   - ``send``         submit a new user turn (kicks off the stream)
 *   - ``abort``        cancel the in-flight stream (used on unmount or
 *                      when the user starts another turn)
 *
 * History is kept in component memory only (Sprint 8 plan §10 Q3
 * "Stateless"); the session lives until the panel unmounts.
 */
import { useCallback, useEffect, useRef, useState } from "react";
import { safeRandomUUID } from "@/lib/uuid";

const BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8080";

export type ChatScope = "enterprise" | "platform";

export type ChatMessage =
  | { id: string; role: "user";      content: string }
  | { id: string; role: "assistant"; content: string; toolCalls: ToolCallRecord[] }
  | { id: string; role: "error";     title: string;  detail?: string };

export interface ToolCallRecord {
  tool: string;
  args: Record<string, unknown>;
  ok?: boolean;
  preview?: string;
}

interface SSEEvent {
  type: "thinking" | "tool_call" | "tool_result" | "message" | "error" | "done";
  tool?: string;
  args?: Record<string, unknown>;
  ok?: boolean;
  preview?: string;
  text?: string;
  title?: string;
  detail?: string;
}

type Status = "idle" | "streaming" | "error";

export function useChatStream(scope: ChatScope) {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [status, setStatus]     = useState<Status>("idle");
  const abortRef                = useRef<AbortController | null>(null);

  // Cancel any in-flight stream on unmount — otherwise the reader keeps
  // running after the panel closes and dispatches setState to a dead
  // component (React 19 logs a warning).
  useEffect(() => {
    return () => abortRef.current?.abort();
  }, []);

  const abort = useCallback(() => {
    abortRef.current?.abort();
    abortRef.current = null;
    setStatus("idle");
  }, []);

  const send = useCallback(
    async (userText: string) => {
      const trimmed = userText.trim();
      if (!trimmed || status === "streaming") return;

      // Cancel any prior stream before kicking off a new one.
      abortRef.current?.abort();
      const ac = new AbortController();
      abortRef.current = ac;

      const userMsg: ChatMessage = {
        id: safeRandomUUID(), role: "user", content: trimmed,
      };
      const assistantId = safeRandomUUID();

      // Snapshot history BEFORE appending the new user turn so the BE
      // gets the visible history (matches CLAUDE.md §10 Q3 stateless model).
      const historyForBe = messages
        .filter((m): m is Extract<ChatMessage, { role: "user" | "assistant" }> =>
          m.role === "user" || m.role === "assistant",
        )
        .map((m) => ({ role: m.role, content: m.content }));

      setMessages((prev) => [
        ...prev,
        userMsg,
        // Placeholder so the FE can render a typing bubble immediately.
        { id: assistantId, role: "assistant", content: "", toolCalls: [] },
      ]);
      setStatus("streaming");

      const token =
        typeof window !== "undefined"
          ? localStorage.getItem("kaori.access_token")
          : null;

      let resp: Response;
      try {
        resp = await fetch(`${BASE}/api/v1/chat/${scope}/stream`, {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            Accept: "text/event-stream",
            ...(token ? { Authorization: `Bearer ${token}` } : {}),
          },
          body: JSON.stringify({ message: trimmed, history: historyForBe }),
          signal: ac.signal,
        });
      } catch (err) {
        if ((err as Error).name === "AbortError") return;
        appendError(setMessages, assistantId, "Không gọi được chat.", String(err));
        setStatus("error");
        return;
      }

      if (!resp.ok || !resp.body) {
        const detail =
          resp.status === 403
            ? "Tài khoản không có quyền truy cập chat."
            : `HTTP ${resp.status}`;
        appendError(setMessages, assistantId, "Lỗi khi mở stream.", detail);
        setStatus("error");
        return;
      }

      const reader = resp.body
        .pipeThrough(new TextDecoderStream())
        .getReader();
      let buffer = "";

      try {
        while (true) {
          const { value, done } = await reader.read();
          if (done) break;
          if (value) buffer += value;

          // Frames are separated by a blank line (``\n\n``). Pop full
          // frames; keep the trailing partial in the buffer.
          let idx;
          while ((idx = buffer.indexOf("\n\n")) >= 0) {
            const frame = buffer.slice(0, idx);
            buffer = buffer.slice(idx + 2);

            const dataLine = frame
              .split("\n")
              .find((l) => l.startsWith("data: "));
            if (!dataLine) continue;

            try {
              const event = JSON.parse(dataLine.slice("data: ".length)) as SSEEvent;
              applyEvent(event, assistantId, setMessages);
              if (event.type === "done") break;
            } catch {
              // Ignore malformed frame; keep stream open.
            }
          }
        }
      } catch (err) {
        if ((err as Error).name === "AbortError") return;
        appendError(setMessages, assistantId, "Stream gián đoạn.", String(err));
        setStatus("error");
        return;
      }

      setStatus("idle");
    },
    // ``messages`` is intentionally NOT in the dep array — we read it
    // inside but only as a snapshot at send time. Putting it in would
    // re-create ``send`` on every turn and stop the abort handle from
    // matching the outer scope's controller.
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [scope, status],
  );

  const reset = useCallback(() => {
    abort();
    setMessages([]);
  }, [abort]);

  return { messages, status, send, abort, reset };
}


function applyEvent(
  event: SSEEvent,
  assistantId: string,
  setMessages: React.Dispatch<React.SetStateAction<ChatMessage[]>>,
) {
  switch (event.type) {
    case "thinking":
      // No state change — UI keys off ``status='streaming'`` for the
      // typing indicator, and the placeholder bubble is already there.
      return;

    case "tool_call":
      setMessages((prev) =>
        prev.map((m) =>
          m.id === assistantId && m.role === "assistant"
            ? {
                ...m,
                toolCalls: [
                  ...m.toolCalls,
                  {
                    tool: event.tool ?? "",
                    args: event.args ?? {},
                  },
                ],
              }
            : m,
        ),
      );
      return;

    case "tool_result":
      setMessages((prev) =>
        prev.map((m) => {
          if (m.id !== assistantId || m.role !== "assistant") return m;
          // Match the most recent tool_call for this tool name without
          // a result yet — guard against the model invoking the same
          // tool twice in one hop.
          const idx = [...m.toolCalls]
            .reverse()
            .findIndex(
              (tc) => tc.tool === event.tool && tc.ok === undefined,
            );
          if (idx < 0) return m;
          const realIdx = m.toolCalls.length - 1 - idx;
          const next = [...m.toolCalls];
          next[realIdx] = {
            ...next[realIdx],
            ok:      event.ok,
            preview: event.preview,
          };
          return { ...m, toolCalls: next };
        }),
      );
      return;

    case "message":
      setMessages((prev) =>
        prev.map((m) =>
          m.id === assistantId && m.role === "assistant"
            ? { ...m, content: event.text ?? "" }
            : m,
        ),
      );
      return;

    case "error":
      appendError(
        setMessages,
        assistantId,
        event.title ?? "Lỗi",
        event.detail,
      );
      return;

    case "done":
    default:
      return;
  }
}


function appendError(
  setMessages: React.Dispatch<React.SetStateAction<ChatMessage[]>>,
  assistantId: string,
  title: string,
  detail?: string,
) {
  setMessages((prev) => {
    // Replace the placeholder assistant bubble with an error one so the
    // UI doesn't show an empty assistant turn alongside the error.
    const next = prev.filter(
      (m) => !(m.id === assistantId && m.role === "assistant" && !m.content),
    );
    return [
      ...next,
      { id: assistantId, role: "error", title, detail },
    ];
  });
}
