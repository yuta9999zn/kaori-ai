// crypto.randomUUID (và crypto.subtle) chỉ tồn tại trong secure context
// (HTTPS hoặc localhost). Bản demo/pilot chạy HTTP qua IP không có chúng —
// mọi call sinh id phía client phải đi qua helper này thay vì gọi trần.
export function safeRandomUUID(): string {
  const c: Crypto | undefined = typeof crypto !== 'undefined' ? crypto : undefined;
  if (typeof (c as any)?.randomUUID === 'function') return (c as any).randomUUID();
  if (typeof c?.getRandomValues === 'function') {
    // UUIDv4 từ getRandomValues — API này có cả trong insecure context.
    const b = c.getRandomValues(new Uint8Array(16));
    b[6] = (b[6] & 0x0f) | 0x40;
    b[8] = (b[8] & 0x3f) | 0x80;
    const h = Array.from(b, (x) => x.toString(16).padStart(2, '0')).join('');
    return `${h.slice(0, 8)}-${h.slice(8, 12)}-${h.slice(12, 16)}-${h.slice(16, 20)}-${h.slice(20)}`;
  }
  return `id-${Date.now()}-${Math.random().toString(36).slice(2, 10)}`;
}
