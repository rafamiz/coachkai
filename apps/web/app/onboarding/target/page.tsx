'use client';

import { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';

export default function TargetPage() {
  const router = useRouter();
  const [targetWeight, setTargetWeight] = useState('');
  const [pace, setPace] = useState('0.5');
  const [currentWeight, setCurrentWeight] = useState(0);
  const [goal, setGoal] = useState('');

  useEffect(() => {
    setCurrentWeight(parseFloat(localStorage.getItem('onboarding_weight_kg') || '70'));
    setGoal(localStorage.getItem('onboarding_goal') || '');
  }, []);

  const diff = targetWeight ? Math.abs(parseFloat(targetWeight) - currentWeight) : 0;
  const weeksToGoal = diff > 0 ? Math.ceil(diff / parseFloat(pace)) : 0;
  const targetDate = new Date();
  targetDate.setDate(targetDate.getDate() + weeksToGoal * 7);

  const handleContinue = () => {
    localStorage.setItem('onboarding_target_weight_kg', targetWeight);
    localStorage.setItem('onboarding_weekly_goal_kg', pace);
    router.push('/onboarding/macros');
  };

  return (
    <div className="flex-1 flex flex-col space-y-6">
      <div>
        <h1 className="text-2xl font-bold">
          {goal === 'lose_weight' ? "What's your target weight?" : "What's your target weight?"}
        </h1>
        <p className="text-gray-500 mt-1">Current weight: {currentWeight} kg</p>
      </div>

      <div className="space-y-6 flex-1">
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Target Weight (kg)</label>
          <input
            type="number"
            value={targetWeight}
            onChange={(e) => setTargetWeight(e.target.value)}
            className="w-full px-4 py-3 rounded-xl border border-gray-300 focus:border-brand-500 focus:ring-1 focus:ring-brand-500 outline-none text-lg text-center"
            placeholder="65"
          />
          {targetWeight && (
            <p className="text-sm text-gray-500 mt-2 text-center">
              That&apos;s {diff.toFixed(1)} kg to {goal === 'lose_weight' ? 'lose' : 'gain'}
            </p>
          )}
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-700 mb-2">How fast?</label>
          <div className="space-y-2">
            {[
              { kg: '0.25', label: 'Steady', desc: '0.25 kg/week', rec: true },
              { kg: '0.5', label: 'Moderate', desc: '0.5 kg/week', rec: false },
              { kg: '0.75', label: 'Aggressive', desc: '0.75 kg/week', rec: false },
            ].map((opt) => (
              <button
                key={opt.kg}
                onClick={() => setPace(opt.kg)}
                className={`w-full p-3 rounded-xl border-2 text-left transition-all ${
                  pace === opt.kg ? 'border-brand-500 bg-brand-50' : 'border-gray-200'
                }`}
              >
                <div className="flex justify-between items-center">
                  <div>
                    <span className="font-medium">{opt.label}</span>
                    <span className="text-sm text-gray-500 ml-2">{opt.desc}</span>
                  </div>
                  {opt.rec && <span className="text-xs bg-brand-100 text-brand-700 px-2 py-0.5 rounded-full">Recommended</span>}
                </div>
              </button>
            ))}
          </div>
        </div>

        {targetWeight && (
          <div className="bg-brand-50 rounded-xl p-4 text-center">
            <p className="text-sm text-gray-600">Estimated timeline</p>
            <p className="text-lg font-bold text-brand-700">
              ~{weeksToGoal} weeks ({targetDate.toLocaleDateString('en-US', { month: 'long', year: 'numeric' })})
            </p>
          </div>
        )}
      </div>

      <button
        onClick={handleContinue}
        disabled={!targetWeight}
        className="w-full py-4 bg-brand-500 hover:bg-brand-600 disabled:bg-gray-200 disabled:text-gray-400 text-white font-semibold rounded-xl transition-colors"
      >
        Continue
      </button>
    </div>
  );
}
