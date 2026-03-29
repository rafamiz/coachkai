'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';

const NAV_ITEMS = [
  { href: '/dashboard', icon: '\u{1F3E0}', label: 'Today' },
  { href: '/dashboard/meals', icon: '\u{1F37D}\u{FE0F}', label: 'Meals' },
  { href: '/dashboard/progress', icon: '\u{1F4CA}', label: 'Progress' },
  { href: '/dashboard/weight', icon: '\u{2696}\u{FE0F}', label: 'Weight' },
  { href: '/dashboard/settings', icon: '\u{2699}\u{FE0F}', label: 'Settings' },
];

export default function DashboardLayout({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();

  return (
    <div className="min-h-screen bg-gray-50 pb-20">
      <header className="bg-white border-b border-gray-200 px-6 py-4">
        <h1 className="text-xl font-bold text-brand-600">{'\u{1F966}'} NutriCoach</h1>
      </header>

      <main className="max-w-lg mx-auto px-4 py-6">
        {children}
      </main>

      <nav className="fixed bottom-0 left-0 right-0 bg-white border-t border-gray-200 safe-bottom">
        <div className="max-w-lg mx-auto flex justify-around py-2">
          {NAV_ITEMS.map((item) => {
            const isActive = pathname === item.href;
            return (
              <Link
                key={item.href}
                href={item.href}
                className={`flex flex-col items-center py-1 px-3 text-xs ${
                  isActive ? 'text-brand-600' : 'text-gray-400'
                }`}
              >
                <span className="text-xl">{item.icon}</span>
                <span className="mt-0.5">{item.label}</span>
              </Link>
            );
          })}
        </div>
      </nav>
    </div>
  );
}
