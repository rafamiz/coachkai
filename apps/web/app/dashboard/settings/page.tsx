'use client';

import { useEffect, useState } from 'react';
import { createClient } from '@/lib/supabase/client';

export default function SettingsPage() {
  const [profile, setProfile] = useState<Record<string, unknown> | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    loadProfile();
  }, []);

  async function loadProfile() {
    const supabase = createClient();
    const { data: { user } } = await supabase.auth.getUser();
    if (user) {
      const { data } = await supabase.from('users').select('*').eq('auth_id', user.id).single();
      setProfile(data);
    }
    setLoading(false);
  }

  async function saveProfile() {
    if (!profile) return;
    setSaving(true);
    const supabase = createClient();
    await supabase.from('users').update({
      first_name: profile.first_name,
      daily_calories: profile.daily_calories,
      protein_g: profile.protein_g,
      carbs_g: profile.carbs_g,
      fat_g: profile.fat_g,
      dietary_preference: profile.dietary_preference,
      timezone: profile.timezone,
    }).eq('id', profile.id);
    setSaving(false);
  }

  if (loading) return <div className="text-center py-12 text-gray-400">Loading...</div>;
  if (!profile) return <div className="text-center py-12 text-gray-500">Please log in.</div>;

  return (
    <div className="space-y-6">
      <h2 className="text-2xl font-bold">Settings</h2>

      <div className="bg-white rounded-2xl p-4 shadow-sm space-y-4">
        <h3 className="font-semibold">Profile</h3>
        <Field label="Name" value={String(profile.first_name || '')} onChange={(v) => setProfile({ ...profile, first_name: v })} />
        <Field label="Phone" value={String(profile.phone || '')} disabled />
        <Field label="Timezone" value={String(profile.timezone || '')} onChange={(v) => setProfile({ ...profile, timezone: v })} />
      </div>

      <div className="bg-white rounded-2xl p-4 shadow-sm space-y-4">
        <h3 className="font-semibold">Daily Targets</h3>
        <Field label="Calories" value={String(profile.daily_calories || '')} type="number" onChange={(v) => setProfile({ ...profile, daily_calories: parseInt(v) })} />
        <Field label="Protein (g)" value={String(profile.protein_g || '')} type="number" onChange={(v) => setProfile({ ...profile, protein_g: parseInt(v) })} />
        <Field label="Carbs (g)" value={String(profile.carbs_g || '')} type="number" onChange={(v) => setProfile({ ...profile, carbs_g: parseInt(v) })} />
        <Field label="Fat (g)" value={String(profile.fat_g || '')} type="number" onChange={(v) => setProfile({ ...profile, fat_g: parseInt(v) })} />
      </div>

      <button
        onClick={saveProfile}
        disabled={saving}
        className="w-full py-3 bg-brand-500 hover:bg-brand-600 text-white font-semibold rounded-xl transition-colors"
      >
        {saving ? 'Saving...' : 'Save Changes'}
      </button>

      <div className="bg-white rounded-2xl p-4 shadow-sm">
        <h3 className="font-semibold mb-2">Subscription</h3>
        <p className="text-sm text-gray-500">
          Manage your subscription and billing through your account settings.
        </p>
      </div>
    </div>
  );
}

function Field({ label, value, onChange, type = 'text', disabled = false }: {
  label: string; value: string; onChange?: (v: string) => void; type?: string; disabled?: boolean;
}) {
  return (
    <div>
      <label className="block text-sm text-gray-500 mb-1">{label}</label>
      <input
        type={type}
        value={value}
        onChange={onChange ? (e) => onChange(e.target.value) : undefined}
        disabled={disabled}
        className="w-full px-3 py-2 rounded-lg border border-gray-200 focus:border-brand-500 focus:ring-1 focus:ring-brand-500 outline-none disabled:bg-gray-50 disabled:text-gray-400"
      />
    </div>
  );
}
