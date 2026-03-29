'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';

const ALLERGIES = [
  'Peanuts', 'Tree Nuts', 'Dairy', 'Eggs', 'Wheat/Gluten',
  'Soy', 'Fish', 'Shellfish', 'Sesame',
];

export default function AllergiesPage() {
  const router = useRouter();
  const [selected, setSelected] = useState<string[]>([]);
  const [custom, setCustom] = useState('');

  const toggle = (allergy: string) => {
    setSelected((prev) =>
      prev.includes(allergy) ? prev.filter((a) => a !== allergy) : [...prev, allergy],
    );
  };

  const handleContinue = () => {
    const all = [...selected];
    if (custom.trim()) {
      all.push(...custom.split(',').map((s) => s.trim()).filter(Boolean));
    }
    localStorage.setItem('onboarding_allergies', JSON.stringify(all));

    const goal = localStorage.getItem('onboarding_goal');
    if (goal === 'lose_weight' || goal === 'gain_muscle') {
      router.push('/onboarding/target');
    } else {
      router.push('/onboarding/macros');
    }
  };

  return (
    <div className="flex-1 flex flex-col space-y-6">
      <div>
        <h1 className="text-2xl font-bold">Any food allergies?</h1>
        <p className="text-gray-500 mt-1">Select all that apply, or skip if none</p>
      </div>

      <div className="flex flex-wrap gap-2 flex-1">
        {ALLERGIES.map((allergy) => (
          <button
            key={allergy}
            onClick={() => toggle(allergy)}
            className={`px-4 py-2 rounded-full border-2 text-sm font-medium transition-all ${
              selected.includes(allergy)
                ? 'border-brand-500 bg-brand-50 text-brand-700'
                : 'border-gray-200 text-gray-600 hover:border-gray-300'
            }`}
          >
            {allergy}
          </button>
        ))}

        <div className="w-full mt-4">
          <input
            type="text"
            value={custom}
            onChange={(e) => setCustom(e.target.value)}
            placeholder="Other allergies (comma separated)"
            className="w-full px-4 py-3 rounded-xl border border-gray-300 focus:border-brand-500 focus:ring-1 focus:ring-brand-500 outline-none text-sm"
          />
        </div>
      </div>

      <button
        onClick={handleContinue}
        className="w-full py-4 bg-brand-500 hover:bg-brand-600 text-white font-semibold rounded-xl transition-colors"
      >
        {selected.length > 0 ? 'Continue' : 'Skip — No Allergies'}
      </button>
    </div>
  );
}
