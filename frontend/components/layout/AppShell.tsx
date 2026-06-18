"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Sidebar from "./Sidebar";
import { Header } from "./Header";
import { useAuth } from "@/lib/auth-store";
import { ChatPanel } from "@/components/chat/ChatPanel";

export default function AppShell({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const { accessToken } = useAuth();
  const [ready, setReady] = useState(false);

  useEffect(() => {
    // Zustand persist hydrates async; give it one tick to load from storage.
    const token = accessToken ?? localStorage.getItem("kaori.access_token");
    if (!token) {
      router.replace("/login");
    } else {
      setReady(true);
    }
  }, [accessToken, router]);

  if (!ready) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-canvas">
        <div className="animate-spin rounded-full h-8 w-8 border-2 border-brand-200 border-t-brand-500" />
      </div>
    );
  }

  return (
    <div className="flex min-h-screen bg-canvas">
      <Sidebar />
      <div className="flex-1 flex flex-col min-w-0">
        <Header />
        <main className="flex-1 p-6 md:p-8 max-w-[1400px] w-full mx-auto">
          {children}
        </main>
      </div>
      {/* Sprint 8 — conversational layer. Drawer floats over the page. */}
      <ChatPanel scope="enterprise" />
    </div>
  );
}
