'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';

const DIETS = [
  { id: 'none', icon: '\u{2705}', label: 'No Preference' },
  { id: 'vegetarian', icon: '\u{1F96C}', label: 'Vegetarian' },
  { id: 'vegan', icon: '\u{1F331}', label: 'Vegan' },
  { id: 'pescatarian', icon: '\u{1F41F}', label: 'Pescatarian' },
  { id: 'keto', icon: '\u{1F951}', label: 'Keto' },
  { id: 'paleo', icon: '\u{1F356}', label: 'Paleo' },
  { id: 'gluten_free', icon: '\u{1F33E}', label: 'Gluten-Free' },
  { id: 'mediterranean', icon: '\u{1F347}', label: 'Mediterranean' },
];

export default function DietaryPage() {
  const router = useRouter();
  const [selected, setSelected] = useState('none');

  const handleContinue = () => {
    localStorage.setItem('onboarding_dietary_preference', selected);
    router.push('/onboarding/allergies');
  };

  return (
    <div className="flex-1 flex flex-col space-y-6">
      <div>
        <h1 className="text-2xl font-bold">Any dietary preferences?</h1>
        <p className="text-gray-500 mt-1">We&apos;ll tailor recipes and advice</p>
      </div>

      <div className="grid grid-cols-2 gap-3 flex-1">
        {DIETS.map((diet) => (
          <button
            key={diet.id}
            onClick={() => setSelected(diet.id)}
            className={`p-4 rounded-xl border-2 text-center transition-all ${
              selected === diet.id
                ? 'border-brand-500 bg-brand-50'
                : 'border-gray-200 hover:border-gray-300'
            }`}
          >
            <div className="text-2xl mb-1">{diet.icon}</div>
            <div className="text-sm font-medium">{diet.label}</div>
          </button>
        ))}
      </div>

      <button
        onClick={handleContinue}
        className="w-full py-4 bg-brand-500 hover:bg-brand-600 text-white font-semibold rounded-xl transition-colors"
      >
        Continue
      </button>
    </div>
  );
}
