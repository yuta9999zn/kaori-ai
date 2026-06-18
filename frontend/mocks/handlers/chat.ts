/**
 * Sprint 8 — MSW handlers for the chat SSE endpoint.
 *
 * Two routes (one per scope) emit a deterministic 4-event sequence:
 *   thinking → tool_call → tool_result → message → done
 * so the FE can be developed without spinning up Ollama / the gateway.
 *
 * MSW supports streaming via ReadableStream — we hand-roll the SSE wire
 * format the same way ``pipeline.ts`` does, but emit multiple frames
 * instead of one, with a small delay between them so the FE renders
 * the typing indicator + tool card before the final answer.
 */
import { http, HttpResponse } from "msw";

const BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8080";

// One frame = ``data: <json>\n\n``.
function frame(payload: object): string {
  return `data: ${JSON.stringify(payload)}\n\n`;
}

function sseStream(events: object[], gapMs = 80): ReadableStream<Uint8Array> {
  const enc = new TextEncoder();
  return new ReadableStream({
    async start(controller) {
      for (const ev of events) {
        controller.enqueue(enc.encode(frame(ev)));
        await new Promise((r) => setTimeout(r, gapMs));
      }
      controller.close();
    },
  });
}

interface ChatBody {
  message: string;
  history?: Array<{ role: string; content: string }>;
}

export const chatHandlers = [
  // ── /chat/enterprise/stream ──────────────────────────────────────────────
  http.post(`${BASE}/api/v1/chat/enterprise/stream`, async ({ request }) => {
    const body = (await request.json()) as ChatBody;
    const userMsg = (body.message || "").toLowerCase();

    // Pretend the model decided to call a tool when the user asked
    // about a domain we have a fixture for. Otherwise just chat.
    let events: object[];
    if (userMsg.includes("rủi ro") || userMsg.includes("churn")) {
      events = [
        { type: "thinking" },
        {
          type: "tool_call",
          tool: "get_top_at_risk_customers",
          args: { limit: 3 },
        },
        {
          type: "tool_result",
          tool: "get_top_at_risk_customers",
          ok: true,
          preview:
            '{"count":3,"customers":[{"customer_external_id":"C001","revenue_at_risk":12500000.0}]}',
        },
        {
          type: "message",
          text:
            "Top 3 khách hàng đang rủi ro: C001 (12.5M), C047 (8.9M), C112 (5.4M). " +
            "Có thể bắt đầu campaign giữ chân ngay tuần này.",
        },
        { type: "done" },
      ];
    } else if (userMsg.includes("hạn mức") || userMsg.includes("quota") || userMsg.includes("billing")) {
      events = [
        { type: "thinking" },
        { type: "tool_call", tool: "get_billing_quota_status", args: {} },
        {
          type: "tool_result",
          tool: "get_billing_quota_status",
          ok: true,
          preview:
            '{"plan_code":"BUSINESS","quota":2000,"current_month_usage":1700,"usage_pct":85.0,"alert_80_fired":true}',
        },
        {
          type: "message",
          text:
            "Bạn đang ở plan BUSINESS, dùng 1.700 / 2.000 khách (85%). Đã chạm cảnh báo 80%. " +
            "Còn ~300 khách trước khi cần upgrade.",
        },
        { type: "done" },
      ];
    } else {
      events = [
        { type: "thinking" },
        {
          type: "message",
          text:
            "Xin chào! Mình có thể giúp tóm tắt quyết định AI gần đây, " +
            "tìm khách hàng rủi ro cao, hoặc kiểm tra hạn mức. Bạn cần gì?",
        },
        { type: "done" },
      ];
    }

    return new HttpResponse(sseStream(events), {
      headers: {
        "Content-Type":  "text/event-stream",
        "Cache-Control": "no-cache, no-transform",
      },
    });
  }),

  // ── /chat/platform/stream ────────────────────────────────────────────────
  http.post(`${BASE}/api/v1/chat/platform/stream`, async ({ request }) => {
    const body = (await request.json()) as ChatBody;
    const userMsg = (body.message || "").toLowerCase();

    let events: object[];
    if (userMsg.includes("vượt") || userMsg.includes("alert") || userMsg.includes("quota")) {
      events = [
        { type: "thinking" },
        {
          type: "tool_call",
          tool: "find_workspaces_in_alert",
          args: { threshold: "any" },
        },
        {
          type: "tool_result",
          tool: "find_workspaces_in_alert",
          ok: true,
          preview:
            '{"count":2,"workspaces":[{"enterprise_name":"Acme VN","usage_pct":97.0}]}',
        },
        {
          type: "message",
          text:
            "Có 2 tenant đang trong vùng cảnh báo: Acme VN (97% — sắp hết quota), " +
            "BlueRiver (82%). Acme nên được liên hệ ưu tiên cho upgrade.",
        },
        { type: "done" },
      ];
    } else {
      events = [
        { type: "thinking" },
        { type: "tool_call", tool: "get_platform_summary", args: {} },
        {
          type: "tool_result",
          tool: "get_platform_summary",
          ok: true,
          preview:
            '{"workspaces_active":12,"enterprises_active":18,"users_active":74,"pipeline_runs_total":340,"pipeline_runs_last_7d":22}',
        },
        {
          type: "message",
          text:
            "Hiện có 12 workspace / 18 enterprise / 74 user đang hoạt động. " +
            "Tuần qua 22 pipeline runs (tổng 340).",
        },
        { type: "done" },
      ];
    }

    return new HttpResponse(sseStream(events), {
      headers: {
        "Content-Type":  "text/event-stream",
        "Cache-Control": "no-cache, no-transform",
      },
    });
  }),
];
