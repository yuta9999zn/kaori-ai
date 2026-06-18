"use client";

import { useEffect } from "react";

export function MockProvider({ children }: { children: React.ReactNode }) {
  useEffect(() => {
    if (typeof window === "undefined") return;

    // Set NEXT_PUBLIC_DISABLE_MSW=1 in .env.local when you want `npm run dev`
    // to talk to the real Docker stack (8080 gateway) instead of the mock
    // handlers — the prod build (FE container) never loads MSW so it's
    // already real-backend by default.
    const mockEnabled =
      process.env.NODE_ENV === "development" &&
      process.env.NEXT_PUBLIC_DISABLE_MSW !== "1";

    if (!mockEnabled) {
      // Real-backend mode. A `mockServiceWorker.js` registered by a PREVIOUS
      // `npm run dev` session persists in the browser at this origin and keeps
      // intercepting fetches even though we never call worker.start() here —
      // surfacing as phantom 401 "missing bearer" / CORS failures on real API
      // calls (e.g. file upload) while curl works. Proactively unregister it so
      // switching from dev → real backend self-heals (effective next reload).
      navigator.serviceWorker
        ?.getRegistrations?.()
        .then((regs) => {
          for (const r of regs) {
            if (r.active?.scriptURL?.includes("mockServiceWorker")) r.unregister();
          }
        })
        .catch(() => {});
      return;
    }

    // Lazy-load MSW so it's tree-shaken out of production builds.
    import("@/mocks/browser").then(({ worker }) => {
      worker.start({ onUnhandledRequest: "bypass" }).catch(console.error);
    });
  }, []);

  return <>{children}</>;
}
