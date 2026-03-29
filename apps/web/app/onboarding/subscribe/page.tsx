'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';

export default function SubscribePage() {
  const router = useRouter();
  const [plan, setPlan] = useState<'monthly' | 'yearly'>('yearly');
  const [loading, setLoading] = useState(false);

  const completeOnboarding = async () => {
    setLoading(true);
    try {
      // Gather all onboarding data
      const data = {
        phone: localStorage.getItem('onboarding_phone'),
        first_name: localStorage.getItem('onboarding_first_name'),
        gender: localStorage.getItem('onboarding_gender'),
        date_of_birth: localStorage.getItem('onboarding_date_of_birth'),
        height_cm: parseFloat(localStorage.getItem('onboarding_height_cm') || '170'),
        weight_kg: parseFloat(localStorage.getItem('onboarding_weight_kg') || '70'),
        activity_level: localStorage.getItem('onboarding_activity_level'),
        goal: localStorage.getItem('onboarding_goal'),
        target_weight_kg: localStorage.getItem('onboarding_target_weight_kg')
          ? parseFloat(localStorage.getItem('onboarding_target_weight_kg')!)
          : undefined,
        weekly_goal_kg: localStorage.getItem('onboarding_weekly_goal_kg')
          ? parseFloat(localStorage.getItem('onboarding_weekly_goal_kg')!)
          : undefined,
        dietary_preference: localStorage.getItem('onboarding_dietary_preference') || 'none',
        allergies: JSON.parse(localStorage.getItem('onboarding_allergies') || '[]'),
        unit_system: 'metric',
        timezone: Intl.DateTimeFormat().resolvedOptions().timeZone,
      };

      const res = await fetch('/api/onboarding/complete', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(data),
      });

      if (res.ok) {
        // Clear onboarding data
        Object.keys(localStorage).forEach((key) => {
          if (key.startsWith('onboarding_')) localStorage.removeItem(key);
        });
        router.push('/onboarding/success');
      }
    } catch (err) {
      console.error('Onboarding error:', err);
    }
    setLoading(false);
  };

  return (
    <div className="flex-1 flex flex-col space-y-6">
      <div>
        <h1 className="text-2xl font-bold">Start Your Free Trial</h1>
        <p className="text-gray-500 mt-1">7 days free, then choose your plan</p>
      </div>

      <div className="space-y-3 flex-1">
        <button
          onClick={() => setPlan('yearly')}
          className={`w-full p-4 rounded-xl border-2 text-left transition-all relative ${
            plan === 'yearly' ? 'border-brand-500 bg-brand-50' : 'border-gray-200'
          }`}
        >
          <span className="absolute -top-2 right-3 bg-brand-500 text-white text-xs px-2 py-0.5 rounded-full">
            Save 33%
          </span>
          <div className="font-semibold">Yearly</div>
          <div className="text-2xl font-bold mt-1">$79.99<span className="text-sm font-normal text-gray-500">/year</span></div>
          <div className="text-sm text-gray-500">$6.67/month</div>
        </button>

        <button
          onClick={() => setPlan('monthly')}
          className={`w-full p-4 rounded-xl border-2 text-left transition-all ${
            plan === 'monthly' ? 'border-brand-500 bg-brand-50' : 'border-gray-200'
          }`}
        >
          <div className="font-semibold">Monthly</div>
          <div className="text-2xl font-bold mt-1">$9.99<span className="text-sm font-normal text-gray-500">/month</span></div>
        </button>

        <div className="bg-gray-50 rounded-xl p-4 space-y-2 mt-4">
          <p className="font-medium text-sm">What you get:</p>
          <Feature text="Unlimited meal analysis with AI" />
          <Feature text="Personalized macro & calorie tracking" />
          <Feature text="Daily & weekly progress reports" />
          <Feature text="Recipe suggestions tailored to you" />
          <Feature text="Grocery list generation" />
          <Feature text="Water & exercise tracking" />
        </div>
      </div>

      <div className="space-y-2">
        <button
          onClick={completeOnboarding}
          disabled={loading}
          className="w-full py-4 bg-brand-500 hover:bg-brand-600 disabled:bg-gray-300 text-white font-semibold rounded-xl transition-colors"
        >
          {loading ? 'Setting up...' : 'Start 7-Day Free Trial'}
        </button>
        <p className="text-xs text-gray-400 text-center">
          Cancel anytime. No charge during trial period.
        </p>
      </div>
    </div>
  );
}

function Feature({ text }: { text: string }) {
  return (
    <div className="flex items-center gap-2 text-sm text-gray-600">
      <span className="text-brand-500">{'\u{2713}'}</span>
      {text}
    </div>
  );
}
