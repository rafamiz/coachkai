'use client';

import { useEffect, useState } from 'react';
import { createClient } from '@/lib/supabase/client';

interface WeightEntry {
  id: string;
  weight_kg: number;
  note: string | null;
  logged_at: string;
}

export default function WeightPage() {
  const [entries, setEntries] = useState<WeightEntry[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    loadWeight();
  }, []);

  async function loadWeight() {
    const supabase = createClient();
    const { data } = await supabase
      .from('weight_log')
      .select('*')
      .order('logged_at', { ascending: true })
      .limit(90);

    setEntries(data || []);
    setLoading(false);
  }

  if (loading) {
    return <div className="text-center py-12 text-gray-400">Loading...</div>;
  }

  const latest = entries[entries.length - 1];
  const first = entries[0];
  const change = latest && first ? (latest.weight_kg - first.weight_kg).toFixed(1) : '0';
  const minW = Math.min(...entries.map((e) => e.weight_kg)) - 2;
  const maxW = Math.max(...entries.map((e) => e.weight_kg)) + 2;
  const range = maxW - minW || 1;

  return (
    <div className="space-y-6">
      <h2 className="text-2xl font-bold">Weight</h2>

      {/* Summary */}
      <div className="grid grid-cols-3 gap-3">
        <div className="bg-white rounded-xl p-3 shadow-sm text-center">
          <div className="text-xl font-bold">{latest?.weight_kg || '-'}</div>
          <div className="text-xs text-gray-500">Current (kg)</div>
        </div>
        <div className="bg-white rounded-xl p-3 shadow-sm text-center">
          <div className="text-xl font-bold">{first?.weight_kg || '-'}</div>
          <div className="text-xs text-gray-500">Start (kg)</div>
        </div>
        <div className="bg-white rounded-xl p-3 shadow-sm text-center">
          <div className={`text-xl font-bold ${parseFloat(change) <= 0 ? 'text-brand-600' : 'text-red-500'}`}>
            {parseFloat(change) >= 0 ? '+' : ''}{change}
          </div>
          <div className="text-xs text-gray-500">Change (kg)</div>
        </div>
      </div>

      {/* Weight Chart */}
      <div className="bg-white rounded-2xl p-4 shadow-sm">
        <h3 className="font-semibold mb-3">Weight Trend</h3>
        {entries.length < 2 ? (
          <p className="text-gray-400 text-center py-8 text-sm">
            Log at least 2 weigh-ins to see your trend.
            <br />Send &quot;I weigh 72kg&quot; on WhatsApp!
          </p>
        ) : (
          <div className="relative h-48">
            <svg className="w-full h-full" viewBox={`0 0 ${entries.length * 20} 200`} preserveAspectRatio="none">
              <polyline
                points={entries
                  .map((e, i) => `${i * 20 + 10},${200 - ((e.weight_kg - minW) / range) * 180}`)
                  .join(' ')}
                fill="none"
                stroke="#22c55e"
                strokeWidth="2"
              />
              {entries.map((e, i) => (
                <circle
                  key={e.id}
                  cx={i * 20 + 10}
                  cy={200 - ((e.weight_kg - minW) / range) * 180}
                  r="4"
                  fill="#22c55e"
                />
              ))}
            </svg>
            <div className="flex justify-between text-xs text-gray-400 mt-1">
              <span>{new Date(first.logged_at).toLocaleDateString('en-US', { month: 'short', day: 'numeric' })}</span>
              <span>{new Date(latest.logged_at).toLocaleDateString('en-US', { month: 'short', day: 'numeric' })}</span>
            </div>
          </div>
        )}
      </div>

      {/* History */}
      <div>
        <h3 className="font-semibold mb-3">Log</h3>
        <div className="space-y-2">
          {[...entries].reverse().slice(0, 20).map((entry) => (
            <div key={entry.id} className="bg-white rounded-xl px-4 py-3 shadow-sm flex justify-between items-center">
              <div>
                <span className="font-semibold">{entry.weight_kg} kg</span>
                {entry.note && <span className="text-sm text-gray-500 ml-2">{entry.note}</span>}
              </div>
              <span className="text-xs text-gray-400">
                {new Date(entry.logged_at).toLocaleDateString('en-US', { month: 'short', day: 'numeric' })}
              </span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
