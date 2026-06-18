"use client";

/**
 * F-NEW2 — Pipeline status stream consumer.
 *
 * Subscribes to ``GET /api/v1/pipelines/:run_id/events`` (text/event-stream)
 * and calls ``onStatus`` for every status transition. Falls back to 5-second
 * polling on ``GET /api/v1/upload/:run_id/status`` if EventSource cannot open
 * (older browsers, corporate proxies that strip SSE) or after a stream error.
 *
 * Headless on purpose — the wizard / list rows pass their own renderers
 * via ``onStatus``. This component just owns the connection lifecycle.
 */

import { useEffect, useRef } from "react";

const BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8080";

export interface StatusEvent {
  run_id: string;
  status: string;
  updated_at?: string;
  row_count_bronze?: number;
  row_count_silver?: number;
  error_message?: string;
  // Server emits {replay: true} on the initial-state frame after a
  // Last-Event-ID reconnect. Components can choose to render or ignore.
  replay?: boolean;
  [k: string]: unknown;
}

const TERMINAL_STATUSES = new Set([
  "analysis_complete", "failed", "cancelled",
]);

const POLL_INTERVAL_MS = 5_000;

interface Props {
  runId: string;
  onStatus: (event: StatusEvent) => void;
  /** Disable to test polling fallback in dev. Defaults to true. */
  preferSse?: boolean;
}

export function StatusStream({ runId, onStatus, preferSse = true }: Props) {
  // Refs hold the live connection objects so the cleanup function on
  // unmount can close them deterministically.
  const sseRef  = useRef<EventSource | null>(null);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const stoppedRef = useRef(false);

  useEffect(() => {
    stoppedRef.current = false;

    const startPolling = () => {
      if (pollRef.current || stoppedRef.current) return;
      const tick = async () => {
        try {
          const res = await fetch(`${BASE}/api/v1/upload/${runId}/status`, {
            headers: getAuthHeader(),
          });
          if (!res.ok) return;
          const json = await res.json() as StatusEvent;
          onStatus(json);
          if (TERMINAL_STATUSES.has(json.status)) stop();
        } catch {
          // Swallow transient errors — next tick retries.
        }
      };
      void tick();
      pollRef.current = setInterval(tick, POLL_INTERVAL_MS);
    };

    const startSse = () => {
      // EventSource doesn't support custom headers (no Authorization), so
      // we pass the bearer token as a query string. The gateway accepts
      // both shapes; the SSE handler ignores the param.
      const token = typeof window !== "undefined"
                    ? localStorage.getItem("kaori.access_token")
                    : null;
      const url = `${BASE}/api/v1/pipelines/${runId}/events`
                + (token ? `?access_token=${encodeURIComponent(token)}` : "");

      const es = new EventSource(url, { withCredentials: false });
      sseRef.current = es;

      es.addEventListener("status", (ev) => {
        try {
          const data = JSON.parse((ev as MessageEvent).data) as StatusEvent;
          onStatus(data);
          if (TERMINAL_STATUSES.has(data.status)) stop();
        } catch {
          // Malformed payload — ignore single event, keep stream open.
        }
      });

      es.onerror = () => {
        // Browser already auto-retries; if we never opened (readyState !== OPEN)
        // give up SSE and fall back to polling so the user still gets updates.
        if (es.readyState === EventSource.CLOSED || es.readyState === EventSource.CONNECTING) {
          es.close();
          sseRef.current = null;
          startPolling();
        }
      };
    };

    if (preferSse && typeof window !== "undefined" && "EventSource" in window) {
      startSse();
    } else {
      startPolling();
    }

    function stop() {
      stoppedRef.current = true;
      if (sseRef.current) { sseRef.current.close(); sseRef.current = null; }
      if (pollRef.current) { clearInterval(pollRef.current); pollRef.current = null; }
    }

    return stop;
  }, [runId, onStatus, preferSse]);

  return null;
}

function getAuthHeader(): HeadersInit {
  const token = typeof window !== "undefined"
                ? localStorage.getItem("kaori.access_token")
                : null;
  return token ? { Authorization: `Bearer ${token}` } : {};
}
