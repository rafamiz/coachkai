'use client';

import { useEffect, useState } from 'react';
import { createClient } from '@/lib/supabase/client';

interface Summary {
  date: string;
  total_calories: number;
  total_protein_g: number;
  total_carbs_g: number;
  total_fat_g: number;
  meal_count: number;
  adherence_pct: number | null;
  streak_days: number;
  calorie_target: number;
}

export default function ProgressPage() {
  const [summaries, setSummaries] = useState<Summary[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    loadProgress();
  }, []);

  async function loadProgress() {
    const supabase = createClient();
    const thirtyDaysAgo = new Date();
    thirtyDaysAgo.setDate(thirtyDaysAgo.getDate() - 30);

    const { data } = await supabase
      .from('daily_summaries')
      .select('*')
      .gte('date', thirtyDaysAgo.toISOString().split('T')[0])
      .order('date', { ascending: true });

    setSummaries(data || []);
    setLoading(false);
  }

  if (loading) {
    return <div className="text-center py-12 text-gray-400">Loading...</div>;
  }

  const activeDays = summaries.filter((s) => s.meal_count > 0).length;
  const avgCal = summaries.length > 0
    ? Math.round(summaries.reduce((s, d) => s + d.total_calories, 0) / summaries.length)
    : 0;
  const avgAdherence = summaries.length > 0
    ? Math.round(summaries.reduce((s, d) => s + (d.adherence_pct || 0), 0) / summaries.length)
    : 0;
  const currentStreak = summaries.length > 0 ? summaries[summaries.length - 1].streak_days : 0;
  const maxCal = Math.max(...summaries.map((s) => s.total_calories), 1);

  return (
    <div className="space-y-6">
      <h2 className="text-2xl font-bold">Progress</h2>

      {/* Stats Grid */}
      <div className="grid grid-cols-2 gap-3">
        <StatCard label="Avg Calories" value={`${avgCal}`} sub="kcal/day" />
        <StatCard label="Days Tracked" value={`${activeDays}`} sub="of last 30" />
        <StatCard label="Avg Adherence" value={`${avgAdherence}%`} sub="to calorie target" />
        <StatCard label="Current Streak" value={`${currentStreak}`} sub="days" />
      </div>

      {/* Calorie Bar Chart */}
      <div className="bg-white rounded-2xl p-4 shadow-sm">
        <h3 className="font-semibold mb-3">Daily Calories (Last 30 Days)</h3>
        <div className="flex items-end gap-0.5 h-32">
          {summaries.map((s) => {
            const height = (s.total_calories / maxCal) * 100;
            const target = s.calorie_target || 2000;
            const isOver = s.total_calories > target * 1.1;
            const isUnder = s.total_calories < target * 0.8;
            return (
              <div key={s.date} className="flex-1 flex flex-col items-center justify-end h-full">
                <div
                  className={`w-full rounded-t ${
                    isOver ? 'bg-red-400' : isUnder ? 'bg-amber-300' : 'bg-brand-400'
                  }`}
                  style={{ height: `${Math.max(2, height)}%` }}
                  title={`${s.date}: ${s.total_calories} kcal`}
                />
              </div>
            );
          })}
        </div>
        <div className="flex justify-between text-xs text-gray-400 mt-2">
          <span>{summaries[0]?.date.slice(5) || ''}</span>
          <span>{summaries[summaries.length - 1]?.date.slice(5) || ''}</span>
        </div>
        <div className="flex gap-4 justify-center mt-3 text-xs">
          <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-full bg-brand-400" /> On target</span>
          <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-full bg-amber-300" /> Under</span>
          <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-full bg-red-400" /> Over</span>
        </div>
      </div>

      {/* Weekly Breakdown */}
      <div className="bg-white rounded-2xl p-4 shadow-sm">
        <h3 className="font-semibold mb-3">Macro Averages</h3>
        <div className="space-y-3">
          {[
            { label: 'Protein', value: Math.round(summaries.reduce((s, d) => s + d.total_protein_g, 0) / Math.max(1, summaries.length)), color: 'text-blue-600' },
            { label: 'Carbs', value: Math.round(summaries.reduce((s, d) => s + d.total_carbs_g, 0) / Math.max(1, summaries.length)), color: 'text-amber-600' },
            { label: 'Fat', value: Math.round(summaries.reduce((s, d) => s + d.total_fat_g, 0) / Math.max(1, summaries.length)), color: 'text-rose-600' },
          ].map((m) => (
            <div key={m.label} className="flex justify-between items-center">
              <span className="text-gray-600">{m.label}</span>
              <span className={`font-semibold ${m.color}`}>{m.value}g avg/day</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

function StatCard({ label, value, sub }: { label: string; value: string; sub: string }) {
  return (
    <div className="bg-white rounded-xl p-4 shadow-sm text-center">
      <div className="text-2xl font-bold">{value}</div>
      <div className="text-xs text-gray-500">{sub}</div>
      <div className="text-xs font-medium text-gray-400 mt-1">{label}</div>
    </div>
  );
}
