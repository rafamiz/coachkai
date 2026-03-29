'use client';

import { useEffect, useState } from 'react';
import { createClient } from '@/lib/supabase/client';

interface Meal {
  id: string;
  meal_type: string;
  description: string | null;
  calories: number;
  protein_g: number;
  carbs_g: number;
  fat_g: number;
  goal_score: number;
  ai_summary: string;
  photo_url: string | null;
  logged_at: string;
}

export default function MealsPage() {
  const [meals, setMeals] = useState<Meal[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    loadMeals();
  }, []);

  async function loadMeals() {
    const supabase = createClient();
    const sevenDaysAgo = new Date();
    sevenDaysAgo.setDate(sevenDaysAgo.getDate() - 7);

    const { data } = await supabase
      .from('meals')
      .select('*')
      .gte('logged_at', sevenDaysAgo.toISOString())
      .order('logged_at', { ascending: false });

    setMeals(data || []);
    setLoading(false);
  }

  if (loading) {
    return <div className="text-center py-12 text-gray-400">Loading...</div>;
  }

  // Group by date
  const grouped = meals.reduce<Record<string, Meal[]>>((acc, meal) => {
    const date = new Date(meal.logged_at).toLocaleDateString('en-US', {
      weekday: 'long', month: 'short', day: 'numeric',
    });
    if (!acc[date]) acc[date] = [];
    acc[date].push(meal);
    return acc;
  }, {});

  return (
    <div className="space-y-6">
      <h2 className="text-2xl font-bold">Meal History</h2>

      {Object.entries(grouped).map(([date, dateMeals]) => {
        const dayCal = dateMeals.reduce((s, m) => s + m.calories, 0);
        return (
          <div key={date}>
            <div className="flex justify-between items-center mb-2">
              <h3 className="font-semibold text-gray-700">{date}</h3>
              <span className="text-sm text-gray-500">{dayCal} kcal</span>
            </div>
            <div className="space-y-2">
              {dateMeals.map((meal) => (
                <div key={meal.id} className="bg-white rounded-xl p-4 shadow-sm">
                  <div className="flex gap-3">
                    {meal.photo_url && (
                      <img src={meal.photo_url} alt="" className="w-20 h-20 rounded-lg object-cover" />
                    )}
                    <div className="flex-1">
                      <div className="flex justify-between">
                        <span className="text-xs font-medium uppercase text-gray-400">{meal.meal_type}</span>
                        <div className="flex items-center gap-1">
                          {Array.from({ length: 5 }, (_, i) => (
                            <span key={i} className={`text-xs ${i < meal.goal_score ? 'text-yellow-400' : 'text-gray-200'}`}>
                              {'\u{2B50}'}
                            </span>
                          ))}
                        </div>
                      </div>
                      <p className="text-sm text-gray-700 mt-1">{meal.ai_summary || meal.description}</p>
                      <div className="flex gap-3 mt-2 text-xs text-gray-500">
                        <span>{meal.calories} kcal</span>
                        <span>P: {meal.protein_g}g</span>
                        <span>C: {meal.carbs_g}g</span>
                        <span>F: {meal.fat_g}g</span>
                      </div>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        );
      })}

      {meals.length === 0 && (
        <div className="text-center py-12 text-gray-400">
          No meals logged yet. Start tracking via WhatsApp!
        </div>
      )}
    </div>
  );
}
