'use client';
/**
 * Locale provider — holds the current locale in React context, persists
 * to localStorage (kaori.locale), and syncs with the enterprise settings
 * endpoint when the user is logged in.
 */
import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react';
import { LOCALES, translate, type Locale } from './dictionary';

interface Ctx {
  locale: Locale;
  setLocale: (l: Locale) => void;
  t: (key: string, params?: Record<string, string | number>) => string;
}

const LocaleContext = createContext<Ctx | null>(null);

const STORAGE_KEY = 'kaori.locale';

function detectInitialLocale(): Locale {
  if (typeof window === 'undefined') return 'vi';
  const stored = window.localStorage.getItem(STORAGE_KEY) as Locale | null;
  if (stored && (LOCALES as readonly string[]).includes(stored)) return stored;
  const nav = navigator.language?.toLowerCase() ?? '';
  for (const l of LOCALES) {
    if (nav.startsWith(l)) return l;
    if (nav.split('-')[0] === l) return l;
  }
  return 'vi';
}

export function LocaleProvider({ children }: { children: React.ReactNode }) {
  const [locale, setLocaleState] = useState<Locale>('vi');

  useEffect(() => {
    const detected = detectInitialLocale();
    if (detected !== locale) setLocaleState(detected);
    document.documentElement.lang = detected;
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const setLocale = useCallback((l: Locale) => {
    setLocaleState(l);
    if (typeof window !== 'undefined') {
      window.localStorage.setItem(STORAGE_KEY, l);
      document.documentElement.lang = l;
      const token = window.localStorage.getItem('kaori.access_token');
      if (token) {
        fetch('/api/v1/enterprises/me/settings', {
          method: 'PATCH',
          headers: {
            'Content-Type': 'application/json',
            Authorization: `Bearer ${token}`,
            'Accept-Language': l,
          },
          body: JSON.stringify({ output_lang: l }),
        }).catch(() => { /* best-effort */ });
      }
    }
  }, []);

  const t = useCallback(
    (key: string, params?: Record<string, string | number>) => translate(key, locale, params),
    [locale],
  );

  const value = useMemo<Ctx>(() => ({ locale, setLocale, t }), [locale, setLocale, t]);
  return <LocaleContext.Provider value={value}>{children}</LocaleContext.Provider>;
}

export function useLocale() {
  const ctx = useContext(LocaleContext);
  if (!ctx) throw new Error('useLocale must be used inside <LocaleProvider>');
  return ctx;
}

export function useT() {
  return useLocale().t;
}
