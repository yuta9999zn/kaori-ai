"use client";

/**
 * Shared brand panel for the auth flow (login / forgot / reset / MFA).
 * Mirrors the left half of template `1KaoriLogin.jsx`.
 */

import { KaoriLogo } from "@/components/brand/KaoriLogo";
import { useT } from "@/lib/i18n/provider";

interface Props {
  /** Headline shown in serif italic. Override per page if needed. */
  headline?:    string;
  italicTail?:  string;
  subhead?:     string;
}

export function AuthBrandPanel({
  headline,
  italicTail,
  subhead,
}: Props) {
  const t = useT();
  const headlineText   = headline    ?? t("componentsBrandpanel.headline");
  const italicTailText = italicTail  ?? t("componentsBrandpanel.italicTail");
  const subheadText    = subhead     ?? t("componentsBrandpanel.subhead");
  return (
    <div className="relative hidden lg:flex w-1/2 flex-col justify-between p-12 overflow-hidden bg-gradient-to-br from-[#FAF7F2] via-[#F4EFE6] to-[#E9E7E2]">
      <div className="absolute inset-0 bg-pattern z-0" />
      <div className="absolute -top-32 -left-32 w-96 h-96 bg-[#D9C6C6] rounded-full mix-blend-multiply filter blur-3xl opacity-20 animate-pulse" />
      <div className="absolute bottom-10 -right-20 w-[30rem] h-[30rem] bg-[#AFC3B1] rounded-full mix-blend-multiply filter blur-[100px] opacity-20" />

      <div className="relative z-10 flex items-center gap-3">
        <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-white shadow-sm border border-[var(--color-subtle)]">
          <KaoriLogo size={24} detailed className="text-[var(--color-brand-500)]" />
        </div>
        <span className="font-serif text-xl font-semibold text-[var(--color-ink)] tracking-wide">
          Kaori
        </span>
      </div>

      <div className="relative z-10 flex flex-col max-w-lg mb-20 animate-fade-in">
        <h1 className="font-serif text-5xl leading-[1.15] text-[var(--color-ink)] font-medium mb-6">
          {headlineText}
          <br />
          <span className="text-[var(--color-ink-muted)] italic">{italicTailText}</span>
        </h1>
        <p className="text-[var(--color-ink-muted)] text-lg leading-relaxed">{subheadText}</p>
      </div>

      <div className="relative z-10 flex items-center gap-4 text-sm text-[var(--color-ink-muted)]">
        <span>{t("componentsBrandpanel.copyright")}</span>
        <span className="w-1 h-1 rounded-full bg-[var(--color-brand-500)]" />
        <a href="#" className="hover:text-[var(--color-ink)] transition-colors">
          {t("componentsBrandpanel.privacyPolicy")}
        </a>
      </div>
    </div>
  );
}

/** Mobile-only Kaori logo + wordmark anchored to top-left of the form panel. */
export function MobileLogo() {
  return (
    <div className="absolute top-8 left-8 flex items-center gap-2 lg:hidden">
      <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-white shadow-sm border border-[var(--color-subtle)]">
        <KaoriLogo size={20} />
      </div>
      <span className="font-serif text-lg font-medium text-[var(--color-ink)]">Kaori</span>
    </div>
  );
}
