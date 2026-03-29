'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';

const GOALS = [
  { id: 'lose_weight', icon: '\u{1F3AF}', label: 'Lose Weight', desc: 'Reduce body fat while maintaining muscle' },
  { id: 'gain_muscle', icon: '\u{1F4AA}', label: 'Build Muscle', desc: 'Increase strength and muscle mass' },
  { id: 'maintain', icon: '\u{2696}\u{FE0F}', label: 'Maintain Weight', desc: 'Keep your current weight stable' },
  { id: 'eat_healthier', icon: '\u{1F49A}', label: 'Eat Healthier', desc: 'Improve overall nutrition quality' },
];

export default function GoalsPage() {
  const router = useRouter();
  const [selected, setSelected] = useState<string | null>(null);

  const handleContinue = () => {
    if (!selected) return;
    localStorage.setItem('onboarding_goal', selected);
    router.push('/onboarding/profile');
  };

  return (
    <div className="flex-1 flex flex-col space-y-6">
      <div>
        <h1 className="text-2xl font-bold">What&apos;s your main goal?</h1>
        <p className="text-gray-500 mt-1">This helps us personalize your plan</p>
      </div>

      <div className="space-y-3 flex-1">
        {GOALS.map((goal) => (
          <button
            key={goal.id}
            onClick={() => setSelected(goal.id)}
            className={`w-full p-4 rounded-xl border-2 text-left transition-all ${
              selected === goal.id
                ? 'border-brand-500 bg-brand-50'
                : 'border-gray-200 hover:border-gray-300'
            }`}
          >
            <div className="flex items-center gap-3">
              <span className="text-2xl">{goal.icon}</span>
              <div>
                <div className="font-semibold">{goal.label}</div>
                <div className="text-sm text-gray-500">{goal.desc}</div>
              </div>
            </div>
          </button>
        ))}
      </div>

      <button
        onClick={handleContinue}
        disabled={!selected}
        className="w-full py-4 bg-brand-500 hover:bg-brand-600 disabled:bg-gray-200 disabled:text-gray-400 text-white font-semibold rounded-xl transition-colors"
      >
        Continue
      </button>
    </div>
  );
}
