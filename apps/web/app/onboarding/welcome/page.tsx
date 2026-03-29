'use client';

import { useRouter } from 'next/navigation';

export default function WelcomePage() {
  const router = useRouter();

  return (
    <div className="flex-1 flex flex-col justify-center text-center space-y-8">
      <div className="space-y-4">
        <div className="text-7xl">{'\u{1F966}'}</div>
        <h1 className="text-3xl font-bold">Welcome to NutriCoach</h1>
        <p className="text-gray-600 text-lg">
          Let&apos;s set up your personalized nutrition plan in just a few steps.
        </p>
      </div>

      <div className="space-y-3 text-left">
        <Step num={1} text="Set your health goals" />
        <Step num={2} text="Tell us about yourself" />
        <Step num={3} text="Get your personalized plan" />
        <Step num={4} text="Connect WhatsApp" />
      </div>

      <button
        onClick={() => router.push('/onboarding/goals')}
        className="w-full py-4 bg-brand-500 hover:bg-brand-600 text-white font-semibold rounded-xl transition-colors"
      >
        Let&apos;s Go
      </button>
    </div>
  );
}

function Step({ num, text }: { num: number; text: string }) {
  return (
    <div className="flex items-center gap-3">
      <div className="w-8 h-8 rounded-full bg-brand-100 text-brand-700 flex items-center justify-center text-sm font-bold">
        {num}
      </div>
      <span className="text-gray-700">{text}</span>
    </div>
  );
}
