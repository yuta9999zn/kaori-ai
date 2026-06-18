'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { ShieldCheck } from 'lucide-react';

import { cn } from '@/components/platform/foundation';

const TABS = [
  { href: '/platform/security/mfa',      label: 'Xác thực 2 lớp' },
  { href: '/platform/security/sessions', label: 'Phiên đăng nhập' },
];

export default function PlatformSecurityLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const pathname = usePathname() ?? '';

  return (
    <>
      <header className="px-6 lg:px-8 py-5 border-b border-[var(--border-color)] bg-[var(--bg-card)]">
        <div className="flex items-start gap-4">
          <div className="w-12 h-12 rounded-md-custom bg-[var(--primary-gold)]/15 border border-[var(--primary-gold)]/30 flex items-center justify-center shrink-0">
            <ShieldCheck className="w-6 h-6 text-[var(--primary-gold-dark)]" strokeWidth={1.5} />
          </div>
          <div>
            <h1 className="font-serif text-2xl text-[var(--text-primary)]">Bảo mật tài khoản</h1>
            <p className="text-sm text-[var(--text-secondary)] mt-1">
              Quản lý xác thực 2 lớp (TOTP) và các phiên đăng nhập đang hoạt động.
            </p>
          </div>
        </div>
      </header>

      <nav className="px-6 lg:px-8 border-b border-[var(--border-color)] bg-[var(--bg-card)] overflow-x-auto">
        <div className="flex items-center gap-1">
          {TABS.map((tab) => {
            const active = pathname.startsWith(tab.href);
            return (
              <Link
                key={tab.href}
                href={tab.href}
                className={cn(
                  'px-3 py-2.5 text-sm font-medium border-b-2 -mb-px transition-colors whitespace-nowrap',
                  active
                    ? 'border-[var(--primary-gold)] text-[var(--text-primary)]'
                    : 'border-transparent text-[var(--text-secondary)] hover:text-[var(--text-primary)]',
                )}
              >
                {tab.label}
              </Link>
            );
          })}
        </div>
      </nav>

      <div className="px-6 lg:px-8 py-6">{children}</div>
    </>
  );
}
