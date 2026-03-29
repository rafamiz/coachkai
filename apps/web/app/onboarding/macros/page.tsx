'use client';

import { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';

// Inline TDEE calculation to avoid SSR issues with core package
function calcAge(dob: string): number {
  const d = new Date(dob);
  const today = new Date();
  let age = today.getFullYear() - d.getFullYear();
  if (today.getMonth() < d.getMonth() || (today.getMonth() === d.getMonth() && today.getDate() < d.getDate())) age--;
  return age;
}

const ACTIVITY_MULT: Record<string, number> = {
  sedentary: 1.2, light: 1.375, moderate: 1.55, active: 1.725, very_active: 1.9,
};

const MACRO_RATIOS: Record<string, { p: number; c: number; f: number }> = {
  lose_weight: { p: 0.40, c: 0.30, f: 0.30 },
  gain_muscle: { p: 0.35, c: 0.40, f: 0.25 },
  maintain: { p: 0.30, c: 0.40, f: 0.30 },
  eat_healthier: { p: 0.30, c: 0.40, f: 0.30 },
};

export default function MacrosPage() {
  const router = useRouter();
  const [plan, setPlan] = useState({ calories: 0, protein: 0, carbs: 0, fat: 0 });

  useEffect(() => {
    const gender = localStorage.getItem('onboarding_gender') || 'male';
    const weight = parseFloat(localStorage.getItem('onboarding_weight_kg') || '70');
    const height = parseFloat(localStorage.getItem('onboarding_height_cm') || '170');
    const dob = localStorage.getItem('onboarding_date_of_birth') || '1990-01-01';
    const activity = localStorage.getItem('onboarding_activity_level') || 'moderate';
    const goal = localStorage.getItem('onboarding_goal') || 'maintain';
    const weeklyGoal = parseFloat(localStorage.getItem('onboarding_weekly_goal_kg') || '0.5');

    const age = calcAge(dob);
    const base = 10 * weight + 6.25 * height - 5 * age;
    const bmr = gender === 'female' ? base - 161 : base + 5;
    const tdee = Math.round(bmr * (ACTIVITY_MULT[activity] || 1.55));

    let cal = tdee;
    if (goal === 'lose_weight') cal = Math.max(1200, Math.round(tdee - weeklyGoal * 1100));
    if (goal === 'gain_muscle') cal = Math.round(tdee + 300);

    const ratios = MACRO_RATIOS[goal] || MACRO_RATIOS.maintain;
    setPlan({
      calories: cal,
      protein: Math.round((cal * ratios.p) / 4),
      carbs: Math.round((cal * ratios.c) / 4),
      fat: Math.round((cal * ratios.f) / 9),
    });
  }, []);

  const handleContinue = () => {
    localStorage.setItem('onboarding_daily_calories', String(plan.calories));
    localStorage.setItem('onboarding_protein_g', String(plan.protein));
    localStorage.setItem('onboarding_carbs_g', String(plan.carbs));
    localStorage.setItem('onboarding_fat_g', String(plan.fat));
    router.push('/onboarding/whatsapp');
  };

  const total = plan.protein * 4 + plan.carbs * 4 + plan.fat * 9;
  const protPct = total > 0 ? Math.round((plan.protein * 4 / total) * 100) : 0;
  const carbPct = total > 0 ? Math.round((plan.carbs * 4 / total) * 100) : 0;
  const fatPct = total > 0 ? Math.round((plan.fat * 9 / total) * 100) : 0;

  return (
    <div className="flex-1 flex flex-col space-y-6">
      <div>
        <h1 className="text-2xl font-bold">Your Personalized Plan</h1>
        <p className="text-gray-500 mt-1">Based on your profile and goals</p>
      </div>

      <div className="flex-1 space-y-6">
        <div className="text-center py-6 bg-brand-50 rounded-2xl">
          <div className="text-5xl font-bold text-brand-700">{plan.calories}</div>
          <div className="text-gray-500 mt-1">calories per day</div>
        </div>

        <div className="space-y-3">
          <MacroBar label="Protein" grams={plan.protein} pct={protPct} color="bg-blue-500" />
          <MacroBar label="Carbs" grams={plan.carbs} pct={carbPct} color="bg-amber-500" />
          <MacroBar label="Fat" grams={plan.fat} pct={fatPct} color="bg-rose-500" />
        </div>

        <p className="text-sm text-gray-500 text-center">
          These targets are calculated using the Mifflin-St Jeor equation based on your profile.
          You can adjust them later in settings.
        </p>
      </div>

      <button
        onClick={handleContinue}
        className="w-full py-4 bg-brand-500 hover:bg-brand-600 text-white font-semibold rounded-xl transition-colors"
      >
        Looks Good!
      </button>
    </div>
  );
}

function MacroBar({ label, grams, pct, color }: { label: string; grams: number; pct: number; color: string }) {
  return (
    <div className="space-y-1">
      <div className="flex justify-between text-sm">
        <span className="font-medium">{label}</span>
        <span className="text-gray-500">{grams}g ({pct}%)</span>
      </div>
      <div className="h-3 bg-gray-100 rounded-full overflow-hidden">
        <div className={`h-full ${color} rounded-full transition-all duration-700`} style={{ width: `${pct}%` }} />
      </div>
    </div>
  );
}
