'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';

const ACTIVITY_LEVELS = [
  { id: 'sedentary', label: 'Sedentary', desc: 'Desk job, little exercise' },
  { id: 'light', label: 'Lightly Active', desc: '1-2 workouts/week' },
  { id: 'moderate', label: 'Moderately Active', desc: '3-5 workouts/week' },
  { id: 'active', label: 'Very Active', desc: '6-7 workouts/week' },
  { id: 'very_active', label: 'Extremely Active', desc: 'Athlete / physical job' },
];

export default function ProfilePage() {
  const router = useRouter();
  const [form, setForm] = useState({
    first_name: '',
    gender: '',
    date_of_birth: '',
    height_cm: '',
    weight_kg: '',
    activity_level: '',
  });

  const isValid = form.first_name && form.gender && form.date_of_birth &&
    form.height_cm && form.weight_kg && form.activity_level;

  const handleContinue = () => {
    if (!isValid) return;
    Object.entries(form).forEach(([key, val]) => {
      localStorage.setItem(`onboarding_${key}`, val);
    });
    router.push('/onboarding/dietary');
  };

  return (
    <div className="flex-1 flex flex-col space-y-6">
      <div>
        <h1 className="text-2xl font-bold">Tell us about yourself</h1>
        <p className="text-gray-500 mt-1">We&apos;ll use this to calculate your plan</p>
      </div>

      <div className="space-y-4 flex-1">
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">First Name</label>
          <input
            type="text"
            value={form.first_name}
            onChange={(e) => setForm({ ...form, first_name: e.target.value })}
            className="w-full px-4 py-3 rounded-xl border border-gray-300 focus:border-brand-500 focus:ring-1 focus:ring-brand-500 outline-none"
            placeholder="Your name"
          />
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Gender</label>
          <div className="flex gap-2">
            {['male', 'female', 'other'].map((g) => (
              <button
                key={g}
                onClick={() => setForm({ ...form, gender: g })}
                className={`flex-1 py-3 rounded-xl border-2 font-medium capitalize transition-all ${
                  form.gender === g ? 'border-brand-500 bg-brand-50 text-brand-700' : 'border-gray-200'
                }`}
              >
                {g}
              </button>
            ))}
          </div>
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Date of Birth</label>
          <input
            type="date"
            value={form.date_of_birth}
            onChange={(e) => setForm({ ...form, date_of_birth: e.target.value })}
            className="w-full px-4 py-3 rounded-xl border border-gray-300 focus:border-brand-500 focus:ring-1 focus:ring-brand-500 outline-none"
          />
        </div>

        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Height (cm)</label>
            <input
              type="number"
              value={form.height_cm}
              onChange={(e) => setForm({ ...form, height_cm: e.target.value })}
              className="w-full px-4 py-3 rounded-xl border border-gray-300 focus:border-brand-500 focus:ring-1 focus:ring-brand-500 outline-none"
              placeholder="170"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Weight (kg)</label>
            <input
              type="number"
              value={form.weight_kg}
              onChange={(e) => setForm({ ...form, weight_kg: e.target.value })}
              className="w-full px-4 py-3 rounded-xl border border-gray-300 focus:border-brand-500 focus:ring-1 focus:ring-brand-500 outline-none"
              placeholder="70"
            />
          </div>
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Activity Level</label>
          <div className="space-y-2">
            {ACTIVITY_LEVELS.map((level) => (
              <button
                key={level.id}
                onClick={() => setForm({ ...form, activity_level: level.id })}
                className={`w-full p-3 rounded-xl border-2 text-left transition-all ${
                  form.activity_level === level.id
                    ? 'border-brand-500 bg-brand-50'
                    : 'border-gray-200'
                }`}
              >
                <div className="font-medium text-sm">{level.label}</div>
                <div className="text-xs text-gray-500">{level.desc}</div>
              </button>
            ))}
          </div>
        </div>
      </div>

      <button
        onClick={handleContinue}
        disabled={!isValid}
        className="w-full py-4 bg-brand-500 hover:bg-brand-600 disabled:bg-gray-200 disabled:text-gray-400 text-white font-semibold rounded-xl transition-colors"
      >
        Continue
      </button>
    </div>
  );
}
