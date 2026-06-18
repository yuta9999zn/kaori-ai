'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { cn } from '@/lib/cn';

export interface TabItem {
  href: string;
  label: string;
}

export function TabNav({ tabs, className }: { tabs: TabItem[]; className?: string }) {
  const path = usePathname() ?? '';
  return (
    <div className={cn('border-b border-subtle', className)}>
      <nav className="flex gap-1 -mb-px">
        {tabs.map((t) => {
          const active = path === t.href || (t.href !== tabs[0].href && path.startsWith(t.href + '/'));
          return (
            <Link
              key={t.href}
              href={t.href}
              className={cn(
                'px-4 py-2.5 text-small border-b-2 transition-colors',
                active
                  ? 'border-brand-500 text-brand-700 font-medium'
                  : 'border-transparent text-[#7A7266] hover:text-[#2E2A24] hover:border-[#E9E2D5]',
              )}
            >
              {t.label}
            </Link>
          );
        })}
      </nav>
    </div>
  );
}
