'use client';

import { usePathname } from 'next/navigation';

const STEPS = ['welcome', 'goals', 'profile', 'dietary', 'allergies', 'target', 'macros', 'whatsapp', 'subscribe'];

export default function OnboardingLayout({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const currentStep = STEPS.findIndex((s) => pathname.includes(s));
  const progress = currentStep >= 0 ? ((currentStep + 1) / STEPS.length) * 100 : 0;

  return (
    <div className="min-h-screen bg-white flex flex-col">
      {currentStep > 0 && (
        <div className="w-full h-1 bg-gray-100">
          <div
            className="h-full bg-brand-500 transition-all duration-500"
            style={{ width: `${progress}%` }}
          />
        </div>
      )}
      <div className="flex-1 flex flex-col items-center px-6 py-8 max-w-md mx-auto w-full">
        {children}
      </div>
    </div>
  );
}
