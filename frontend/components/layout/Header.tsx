'use client';
import Link from 'next/link';
import { Bell, User, LogOut } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { LocalePicker } from '@/components/i18n/locale-picker';
import { useT } from '@/lib/i18n/provider';
import { useAuth } from '@/lib/auth-store';
import { useRouter } from 'next/navigation';

export function Header() {
  const t = useT();
  const { user, clear } = useAuth();
  const router = useRouter();

  function handleLogout() {
    clear();
    router.push('/login');
  }

  return (
    <header className="border-b border-subtle bg-surface px-6 py-3 flex items-center justify-between">
      <div className="text-small text-[#7A7266]">
        <Link href="/dashboard" className="hover:text-[#2E2A24]">
          {user?.enterprise_name ?? t('nav.workspace')}
        </Link>
      </div>
      <div className="flex items-center gap-2">
        <LocalePicker />
        <Button variant="ghost" size="sm" aria-label="Thông báo">
          <Bell className="w-[18px] h-[18px]" strokeWidth={1.5} />
        </Button>
        <Button variant="ghost" size="sm" aria-label={t('auth.logout')} onClick={handleLogout}>
          <LogOut className="w-[18px] h-[18px]" strokeWidth={1.5} />
        </Button>
      </div>
    </header>
  );
}
