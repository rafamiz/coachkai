'use client';

import { useEffect, useState } from 'react';
import { createClient } from '@/lib/supabase/client';

interface TodayData {
  calories: number;
  protein_g: number;
  carbs_g: number;
  fat_g: number;
  water_ml: number;
  meal_count: number;
  meals: Array<{
    id: string;
    meal_type: string;
    calories: number;
    protein_g: number;
    ai_summary: string;
    photo_url: string | null;
    logged_at: string;
  }>;
  targets: { calories: number; protein_g: number; carbs_g: number; fat_g: number };
  streak: number;
}

export default function DashboardPage() {
  const [data, setData] = useState<TodayData | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    loadTodayData();
  }, []);

  async function loadTodayData() {
    const supabase = createClient();
    const { data: { user } } = await supabase.auth.getUser();
    if (!user) {
      setLoading(false);
      return;
    }

    const today = new Date().toISOString().split('T')[0];

    const [mealsRes, waterRes, profileRes, summaryRes] = await Promise.all([
      supabase.from('meals').select('*').gte('logged_at', `${today}T00:00:00`).order('logged_at'),
      supabase.from('water_intake').select('amount_ml').gte('logged_at', `${today}T00:00:00`),
      supabase.from('users').select('daily_calories, protein_g, carbs_g, fat_g').eq('auth_id', user.id).single(),
      supabase.from('daily_summaries').select('streak_days').eq('date', today).single(),
    ]);

    const meals = mealsRes.data || [];
    const water = (waterRes.data || []).reduce((s, w) => s + w.amount_ml, 0);
    const targets = profileRes.data || { daily_calories: 2000, protein_g: 150, carbs_g: 200, fat_g: 65 };

    setData({
      calories: meals.reduce((s, m) => s + (m.calories || 0), 0),
      protein_g: meals.reduce((s, m) => s + (m.protein_g || 0), 0),
      carbs_g: meals.reduce((s, m) => s + (m.carbs_g || 0), 0),
      fat_g: meals.reduce((s, m) => s + (m.fat_g || 0), 0),
      water_ml: water,
      meal_count: meals.length,
      meals,
      targets: {
        calories: targets.daily_calories || 2000,
        protein_g: targets.protein_g || 150,
        carbs_g: targets.carbs_g || 200,
        fat_g: targets.fat_g || 65,
      },
      streak: summaryRes.data?.streak_days || 0,
    });
    setLoading(false);
  }

  if (loading) {
    return <div className="text-center py-12 text-gray-400">Loading...</div>;
  }

  if (!data) {
    return (
      <div className="text-center py-12">
        <p className="text-gray-500">Please log in to view your dashboard.</p>
      </div>
    );
  }

  const calPct = Math.min(100, Math.round((data.calories / data.targets.calories) * 100));
  const remaining = Math.max(0, data.targets.calories - data.calories);

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h2 className="text-2xl font-bold">Today</h2>
        {data.streak > 1 && (
          <span className="bg-orange-100 text-orange-700 px-3 py-1 rounded-full text-sm font-medium">
            {'\u{1F525}'} {data.streak} day streak
          </span>
        )}
      </div>

      {/* Calorie Ring */}
      <div className="bg-white rounded-2xl p-6 shadow-sm text-center">
        <div className="relative w-40 h-40 mx-auto">
          <svg className="w-full h-full -rotate-90" viewBox="0 0 120 120">
            <circle cx="60" cy="60" r="52" fill="none" stroke="#f3f4f6" strokeWidth="12" />
            <circle
              cx="60" cy="60" r="52" fill="none" stroke="#22c55e"
              strokeWidth="12" strokeLinecap="round"
              strokeDasharray={`${calPct * 3.27} 327`}
            />
          </svg>
          <div className="absolute inset-0 flex flex-col items-center justify-center">
            <div className="text-3xl font-bold">{data.calories}</div>
            <div className="text-xs text-gray-500">of {data.targets.calories} kcal</div>
          </div>
        </div>
        <p className="mt-2 text-sm text-gray-500">{remaining} kcal remaining</p>
      </div>

      {/* Macro Bars */}
      <div className="bg-white rounded-2xl p-4 shadow-sm space-y-3">
        <MacroRow label="Protein" current={data.protein_g} target={data.targets.protein_g} color="bg-blue-500" />
        <MacroRow label="Carbs" current={data.carbs_g} target={data.targets.carbs_g} color="bg-amber-500" />
        <MacroRow label="Fat" current={data.fat_g} target={data.targets.fat_g} color="bg-rose-500" />
        <MacroRow label="Water" current={data.water_ml} target={2000} color="bg-cyan-500" unit="ml" />
      </div>

      {/* Today's Meals */}
      <div>
        <h3 className="font-semibold mb-3">Meals ({data.meal_count})</h3>
        {data.meals.length === 0 ? (
          <div className="bg-white rounded-2xl p-6 shadow-sm text-center text-gray-400">
            <p>No meals logged yet today.</p>
            <p className="text-sm mt-1">Send a photo to NutriCoach on WhatsApp!</p>
          </div>
        ) : (
          <div className="space-y-2">
            {data.meals.map((meal) => (
              <div key={meal.id} className="bg-white rounded-xl p-4 shadow-sm flex gap-3">
                {meal.photo_url && (
                  <img src={meal.photo_url} alt="" className="w-16 h-16 rounded-lg object-cover" />
                )}
                <div className="flex-1 min-w-0">
                  <div className="flex justify-between items-start">
                    <span className="text-xs font-medium uppercase text-gray-400">{meal.meal_type}</span>
                    <span className="text-sm font-semibold">{meal.calories} kcal</span>
                  </div>
                  <p className="text-sm text-gray-600 mt-1 line-clamp-2">{meal.ai_summary}</p>
                  <p className="text-xs text-gray-400 mt-1">
                    P: {meal.protein_g}g | {new Date(meal.logged_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                  </p>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

function MacroRow({ label, current, target, color, unit = 'g' }: {
  label: string; current: number; target: number; color: string; unit?: string;
}) {
  const pct = Math.min(100, Math.round((current / target) * 100));
  return (
    <div>
      <div className="flex justify-between text-sm mb-1">
        <span className="text-gray-600">{label}</span>
        <span className="font-medium">{Math.round(current)}/{target}{unit}</span>
      </div>
      <div className="h-2 bg-gray-100 rounded-full overflow-hidden">
        <div className={`h-full ${color} rounded-full transition-all`} style={{ width: `${pct}%` }} />
      </div>
    </div>
  );
}
