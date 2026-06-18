import type { Metadata } from "next";
import { Inter, Playfair_Display, JetBrains_Mono } from "next/font/google";
import "./globals.css";
import { QueryProvider } from "@/lib/query-client";
import { LocaleProvider } from "@/lib/i18n/provider";
import { MockProvider } from "@/components/dev/MockProvider";

// Fonts per anh's reference templates (D:\Kaori Document\frontend template):
// Inter (body) + Playfair Display (headings via .font-serif). JetBrains Mono
// kept for code/numeric tabular cells.
const sans = Inter({
  subsets: ["latin", "vietnamese"],
  variable: "--font-sans",
  weight: ["400", "500", "600", "700"],
  display: "swap",
});

const serif = Playfair_Display({
  subsets: ["latin", "vietnamese"],
  variable: "--font-serif",
  weight: ["400", "500", "600"],
  style: ["normal", "italic"],
  display: "swap",
});

const mono = JetBrains_Mono({
  subsets: ["latin"],
  variable: "--font-mono",
  weight: ["400", "500", "600"],
  display: "swap",
});

export const metadata: Metadata = {
  title: "Kaori — AI Data Analytics",
  description: "Upload, clean, and analyse any business data with AI-powered insights.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  const cls = `${sans.variable} ${serif.variable} ${mono.variable}`;
  return (
    <html lang="vi" className={cls}>
      <body
        className="font-sans bg-canvas text-ink antialiased"
        style={{ fontFamily: "var(--font-sans, 'Inter', system-ui, sans-serif)" }}
      >
        <QueryProvider>
          <LocaleProvider>
            <MockProvider>
              {children}
            </MockProvider>
          </LocaleProvider>
        </QueryProvider>
      </body>
    </html>
  );
}
