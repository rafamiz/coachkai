'use client';

import { useState, useEffect, useCallback } from 'react';

// ─── Types (mirror packages/core/src/types/user.ts) ─────────────────────────
type Goal = 'lose_weight' | 'gain_muscle' | 'maintain' | 'eat_healthier';
type Gender = 'male' | 'female' | 'other';
type ActivityLevel = 'sedentary' | 'light' | 'moderate' | 'active' | 'very_active';
type DietaryPreference =
  | 'none'
  | 'vegan'
  | 'vegetarian'
  | 'pescatarian'
  | 'keto'
  | 'paleo'
  | 'gluten_free'
  | 'mediterranean';
type Plan = 'free' | 'monthly' | 'yearly';

type StepId =
  | 'welcome'
  | 'goal'
  | 'gender'
  | 'age'
  | 'body'
  | 'target'
  | 'activity'
  | 'diet'
  | 'struggles'
  | 'analyzing'
  | 'results'
  | 'paywall';

interface OnboardingData {
  firstName: string;
  goal?: Goal;
  gender?: Gender;
  dateOfBirth?: string; // YYYY-MM-DD
  heightCm?: number;
  weightKg?: number;
  targetWeightKg?: number;
  weeklyGoalKg?: number;
  activityLevel?: ActivityLevel;
  dietaryPreference?: DietaryPreference;
  struggles: string[];
}

interface NutritionResults {
  tdee: number;
  calories: number;
  protein: number;
  carbs: number;
  fat: number;
}

// ─── Inline nutrition calculations (mirror packages/core/src/nutrition) ───────
const ACTIVITY_MULT: Record<ActivityLevel, number> = {
  sedentary: 1.2,
  light: 1.375,
  moderate: 1.55,
  active: 1.725,
  very_active: 1.9,
};

function calcAge(dob: string): number {
  const d = new Date(dob);
  const today = new Date();
  let age = today.getFullYear() - d.getFullYear();
  const m = today.getMonth() - d.getMonth();
  if (m < 0 || (m === 0 && today.getDate() < d.getDate())) age--;
  return age;
}

function calcTDEE(g: Gender, kg: number, cm: number, age: number, level: ActivityLevel): number {
  const base = 10 * kg + 6.25 * cm - 5 * age;
  const bmr = g === 'female' ? base - 161 : base + 5;
  return Math.round(bmr * ACTIVITY_MULT[level]);
}

function calcDailyCal(tdee: number, goal: Goal, weeklyKg?: number): number {
  let calories: number;
  if (goal === 'lose_weight') {
    const deficit = (weeklyKg ?? 0.5) * 1100;
    calories = Math.max(1200, Math.round(tdee - deficit));
  } else if (goal === 'gain_muscle') {
    calories = Math.round(tdee + 300);
  } else {
    calories = Math.round(tdee);
  }
  // Safety cap: no human requires >4 500 kcal/day on a coaching plan
  return Math.min(calories, 4500);
}

function calcMacros(cal: number, goal: Goal) {
  const r: Record<Goal, [number, number, number]> = {
    lose_weight: [0.4, 0.3, 0.3],
    gain_muscle: [0.35, 0.4, 0.25],
    maintain: [0.3, 0.4, 0.3],
    eat_healthier: [0.3, 0.4, 0.3],
  };
  const [p, c, f] = r[goal];
  return {
    protein: Math.round((cal * p) / 4),
    carbs: Math.round((cal * c) / 4),
    fat: Math.round((cal * f) / 9),
  };
}

function computeResults(data: OnboardingData): NutritionResults | null {
  if (!data.gender || !data.dateOfBirth || !data.heightCm || !data.weightKg || !data.activityLevel || !data.goal) {
    return null;
  }
  const age = calcAge(data.dateOfBirth);
  const tdee = calcTDEE(data.gender, data.weightKg, data.heightCm, age, data.activityLevel);
  const calories = calcDailyCal(tdee, data.goal, data.weeklyGoalKg);
  const { protein, carbs, fat } = calcMacros(calories, data.goal);
  return { tdee, calories, protein, carbs, fat };
}

// ─── Step ordering ───────────────────────────────────────────────────────────
const BASE_STEPS: StepId[] = [
  'welcome', 'goal', 'gender', 'age', 'body',
  'target', 'activity', 'diet', 'struggles',
  'analyzing', 'results', 'paywall',
];

const STEP_LABELS: Partial<Record<StepId, string>> = {
  goal: 'Paso 1 — Tu objetivo',
  gender: 'Paso 2 — Tu género',
  age: 'Paso 3 — Tu edad',
  body: 'Paso 4 — Tu cuerpo',
  target: 'Paso 5 — Tu meta',
  activity: 'Paso 6 — Tu actividad',
  diet: 'Paso 7 — Tu dieta',
  struggles: 'Paso 8 — Tus desafíos',
};

function getSteps(goal?: Goal): StepId[] {
  if (goal === 'maintain' || goal === 'eat_healthier') {
    return BASE_STEPS.filter(s => s !== 'target');
  }
  return BASE_STEPS;
}

function getProgress(stepId: StepId, goal?: Goal): number {
  const steps = getSteps(goal);
  const idx = steps.indexOf(stepId);
  if (idx <= 0) return 8; // endowed progress effect
  return Math.round(8 + (idx / (steps.length - 1)) * 92);
}

// ─── Shared UI primitives ─────────────────────────────────────────────────────
const ACCENT = '#ff6b35';

function OptionCard({
  selected,
  onClick,
  children,
  className = '',
}: {
  selected: boolean;
  onClick: () => void;
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <button
      onClick={onClick}
      className={`w-full text-left rounded-2xl border-2 p-4 transition-all duration-150 active:scale-[0.98] ${
        selected
          ? 'border-[#ff6b35] bg-[#ff6b35]/10'
          : 'border-gray-700 bg-gray-900 hover:border-gray-500'
      } ${className}`}
    >
      {children}
    </button>
  );
}

function PrimaryButton({
  onClick,
  disabled = false,
  loading = false,
  children,
  className = '',
}: {
  onClick?: () => void;
  disabled?: boolean;
  loading?: boolean;
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <button
      onClick={onClick}
      disabled={disabled || loading}
      className={`w-full rounded-2xl py-4 px-6 text-base font-bold transition-all duration-150 active:scale-[0.98] disabled:opacity-50 disabled:cursor-not-allowed ${className}`}
      style={disabled || loading ? {} : { backgroundColor: ACCENT, color: '#fff' }}
    >
      {loading ? (
        <span className="flex items-center justify-center gap-2">
          <span className="h-4 w-4 animate-spin rounded-full border-2 border-white/40 border-t-white" />
          Guardando...
        </span>
      ) : (
        children
      )}
    </button>
  );
}

function NumberInput({
  value,
  onChange,
  placeholder,
  unit,
  min,
  max,
}: {
  value: string;
  onChange: (v: string) => void;
  placeholder: string;
  unit: string;
  min?: number;
  max?: number;
}) {
  return (
    <div className="relative flex items-center">
      <input
        type="number"
        inputMode="numeric"
        value={value}
        onChange={e => onChange(e.target.value)}
        placeholder={placeholder}
        min={min}
        max={max}
        className="w-full rounded-2xl border-2 border-gray-700 bg-gray-900 px-5 py-4 text-xl font-semibold text-white placeholder-gray-600 focus:border-[#ff6b35] focus:outline-none pr-16"
      />
      <span className="absolute right-5 text-sm font-medium text-gray-400">{unit}</span>
    </div>
  );
}

// ─── Main Component ───────────────────────────────────────────────────────────
export default function OnboardingPage() {
  const [data, setData] = useState<OnboardingData>({ firstName: '', struggles: [] });
  const [stepId, setStepId] = useState<StepId>('welcome');
  const [analysisProgress, setAnalysisProgress] = useState(0);
  const [analysisMsg, setAnalysisMsg] = useState('Analizando tus objetivos...');
  const [results, setResults] = useState<NutritionResults | null>(null);
  const [selectedPlan, setSelectedPlan] = useState<Plan>('yearly');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [trialVisible, setTrialVisible] = useState(false);

  // Temp field state for steps that need individual inputs
  const [heightInput, setHeightInput] = useState('');
  const [weightInput, setWeightInput] = useState('');
  const [targetWeightInput, setTargetWeightInput] = useState('');
  const [dobDay, setDobDay] = useState('');
  const [dobMonth, setDobMonth] = useState('');
  const [dobYear, setDobYear] = useState('');

  const steps = getSteps(data.goal);
  const progress = getProgress(stepId, data.goal);

  const goNext = useCallback(() => {
    const idx = steps.indexOf(stepId);
    if (idx < steps.length - 1) setStepId(steps[idx + 1]);
  }, [stepId, steps]);

  const goBack = useCallback(() => {
    const idx = steps.indexOf(stepId);
    if (idx > 0) setStepId(steps[idx - 1]);
  }, [stepId, steps]);

  // Analysis animation
  useEffect(() => {
    if (stepId !== 'analyzing') return;
    setAnalysisProgress(0);

    const messages = [
      'Analizando tus objetivos...',
      'Calculando tu metabolismo basal...',
      'Ajustando según tu nivel de actividad...',
      'Personalizando tu plan nutricional...',
      'Listo. Tu plan está preparado ✓',
    ];

    let pct = 0;
    let msgIdx = 0;
    const interval = setInterval(() => {
      pct += 2;
      setAnalysisProgress(pct);
      const newMsgIdx = Math.floor((pct / 100) * (messages.length - 1));
      if (newMsgIdx !== msgIdx) {
        msgIdx = newMsgIdx;
        setAnalysisMsg(messages[Math.min(msgIdx, messages.length - 1)]);
      }
      if (pct >= 100) {
        clearInterval(interval);
        const computed = computeResults(data);
        setResults(computed);
        setTimeout(() => goNext(), 600);
      }
    }, 30);

    return () => clearInterval(interval);
  }, [stepId]); // eslint-disable-line react-hooks/exhaustive-deps

  // Paywall trial badge delayed animation
  useEffect(() => {
    if (stepId !== 'paywall') return;
    const t = setTimeout(() => setTrialVisible(true), 800);
    return () => clearTimeout(t);
  }, [stepId]);

  // Sync numeric inputs → data on step navigation
  const commitBodyInputs = () => {
    const h = parseFloat(heightInput);
    const w = parseFloat(weightInput);
    setData(d => ({
      ...d,
      ...(isFinite(h) && h > 0 ? { heightCm: h } : {}),
      ...(isFinite(w) && w > 0 ? { weightKg: w } : {}),
    }));
  };

  const commitTargetInput = () => {
    const t = parseFloat(targetWeightInput);
    setData(d => ({
      ...d,
      ...(isFinite(t) && t > 0 ? { targetWeightKg: t } : {}),
    }));
  };

  const commitDob = () => {
    const d = parseInt(dobDay);
    const m = parseInt(dobMonth);
    const y = parseInt(dobYear);
    if (d >= 1 && d <= 31 && m >= 1 && m <= 12 && y >= 1920 && y <= new Date().getFullYear() - 10) {
      const mm = String(m).padStart(2, '0');
      const dd = String(d).padStart(2, '0');
      setData(prev => ({ ...prev, dateOfBirth: `${y}-${mm}-${dd}` }));
      return true;
    }
    return false;
  };

  // Submit on paywall CTA
  const handleSubmit = async () => {
    setIsSubmitting(true);
    try {
      const payload = {
        first_name: data.firstName || 'Usuario',
        gender: data.gender ?? 'other',
        date_of_birth: data.dateOfBirth ?? '1990-01-01',
        height_cm: data.heightCm ?? 170,
        weight_kg: data.weightKg ?? 70,
        activity_level: data.activityLevel ?? 'moderate',
        goal: data.goal ?? 'eat_healthier',
        target_weight_kg: data.targetWeightKg ?? null,
        weekly_goal_kg: data.weeklyGoalKg ?? 0.5,
        dietary_preference: data.dietaryPreference ?? 'none',
        allergies: [],
        unit_system: 'metric',
        timezone: Intl.DateTimeFormat().resolvedOptions().timeZone,
        plan: selectedPlan,
        // phone is optional — omitted, handled server-side
      };

      const res = await fetch('/api/onboarding', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });

      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        console.error('Save failed:', err);
      }

      // Redirect to dashboard regardless (demo-friendly)
      window.location.href = '/dashboard';
    } catch (err) {
      console.error(err);
      window.location.href = '/dashboard';
    } finally {
      setIsSubmitting(false);
    }
  };

  // ─── Render helpers ──────────────────────────────────────────────────────────
  const renderStep = () => {
    switch (stepId) {
      // ── Welcome ────────────────────────────────────────────────────────────
      case 'welcome':
        return (
          <div className="flex flex-col gap-6">
            {/* Hero */}
            <div className="flex flex-col items-center gap-3 py-4">
              <div className="text-5xl">🔥</div>
              <h1 className="text-3xl font-extrabold text-white text-center leading-tight">
                Tu coach de<br />
                <span style={{ color: ACCENT }}>nutrición con IA</span>
              </h1>
              <p className="text-gray-400 text-center text-sm leading-relaxed">
                Planes 100&nbsp;% personalizados. Resultados reales.
              </p>
            </div>

            {/* Social proof badge */}
            <div className="flex items-center justify-center gap-2 rounded-2xl bg-gray-900 border border-gray-700 py-3 px-4">
              <span className="text-lg">🔥</span>
              <span className="text-sm text-gray-300">
                <span className="font-bold text-white">2,847&nbsp;</span>
                personas se sumaron esta semana
              </span>
            </div>

            {/* Features */}
            <div className="flex flex-col gap-3">
              {[
                ['⚡', 'Plan calórico calculado para vos'],
                ['🥗', 'Recetas según tus preferencias'],
                ['📊', 'Seguimiento diario inteligente'],
                ['💬', 'Soporte por WhatsApp 24/7'],
              ].map(([icon, text]) => (
                <div key={text} className="flex items-center gap-3">
                  <span className="text-xl w-7 text-center">{icon}</span>
                  <span className="text-gray-300 text-sm">{text}</span>
                </div>
              ))}
            </div>

            {/* Name input */}
            <div className="flex flex-col gap-2">
              <label className="text-sm font-medium text-gray-400">¿Cómo te llamás?</label>
              <input
                type="text"
                value={data.firstName}
                onChange={e => setData(d => ({ ...d, firstName: e.target.value }))}
                placeholder="Tu nombre"
                className="rounded-2xl border-2 border-gray-700 bg-gray-900 px-5 py-4 text-base text-white placeholder-gray-600 focus:border-[#ff6b35] focus:outline-none"
              />
            </div>

            <PrimaryButton onClick={goNext} disabled={data.firstName.trim().length < 2}>
              ¡Empecemos! →
            </PrimaryButton>
          </div>
        );

      // ── Goal ───────────────────────────────────────────────────────────────
      case 'goal': {
        const goals: { value: Goal; icon: string; label: string; desc: string }[] = [
          { value: 'lose_weight', icon: '🔥', label: 'Bajar de peso', desc: 'Quemá grasa y definite' },
          { value: 'gain_muscle', icon: '💪', label: 'Ganar músculo', desc: 'Aumentá masa y fuerza' },
          { value: 'maintain', icon: '⚡', label: 'Mantener mi peso', desc: 'Sostené tus resultados' },
          { value: 'eat_healthier', icon: '🥗', label: 'Comer más sano', desc: 'Mejorá tu calidad de vida' },
        ];
        return (
          <div className="flex flex-col gap-4">
            <div className="flex flex-col gap-1 mb-2">
              <h2 className="text-2xl font-extrabold text-white">¿Cuál es tu objetivo,<br />{data.firstName}?</h2>
              <p className="text-sm text-gray-400">Elegí el que mejor te representa</p>
            </div>
            {goals.map(g => (
              <OptionCard key={g.value} selected={data.goal === g.value} onClick={() => setData(d => ({ ...d, goal: g.value }))}>
                <div className="flex items-center gap-4">
                  <span className="text-3xl">{g.icon}</span>
                  <div>
                    <div className="font-bold text-white">{g.label}</div>
                    <div className="text-xs text-gray-400">{g.desc}</div>
                  </div>
                  {data.goal === g.value && (
                    <span className="ml-auto text-[#ff6b35] text-xl">✓</span>
                  )}
                </div>
              </OptionCard>
            ))}
            <PrimaryButton onClick={goNext} disabled={!data.goal} className="mt-2">
              Continuar →
            </PrimaryButton>
          </div>
        );
      }

      // ── Gender ─────────────────────────────────────────────────────────────
      case 'gender': {
        const genders: { value: Gender; icon: string; label: string }[] = [
          { value: 'male', icon: '♂️', label: 'Masculino' },
          { value: 'female', icon: '♀️', label: 'Femenino' },
          { value: 'other', icon: '⚧', label: 'Otro / Prefiero no decir' },
        ];
        return (
          <div className="flex flex-col gap-4">
            <div className="flex flex-col gap-1 mb-2">
              <h2 className="text-2xl font-extrabold text-white">¿Con qué género<br />te identificás?</h2>
              <p className="text-xs text-gray-500">Usamos esto para calcular tu metabolismo</p>
            </div>
            {genders.map(g => (
              <OptionCard key={g.value} selected={data.gender === g.value} onClick={() => setData(d => ({ ...d, gender: g.value }))}>
                <div className="flex items-center gap-4">
                  <span className="text-2xl">{g.icon}</span>
                  <span className="font-semibold text-white">{g.label}</span>
                  {data.gender === g.value && (
                    <span className="ml-auto text-[#ff6b35] text-xl">✓</span>
                  )}
                </div>
              </OptionCard>
            ))}
            <PrimaryButton onClick={goNext} disabled={!data.gender} className="mt-2">
              Continuar →
            </PrimaryButton>
          </div>
        );
      }

      // ── Age ────────────────────────────────────────────────────────────────
      case 'age':
        return (
          <div className="flex flex-col gap-6">
            <div className="flex flex-col gap-1">
              <h2 className="text-2xl font-extrabold text-white">¿Cuántos años tenés?</h2>
              <p className="text-sm text-gray-400">Tu edad afecta directamente tus calorías diarias</p>
            </div>
            <div className="grid grid-cols-3 gap-3">
              <div className="flex flex-col gap-1">
                <label className="text-xs text-gray-500 font-medium">Día</label>
                <input
                  type="number"
                  inputMode="numeric"
                  value={dobDay}
                  onChange={e => setDobDay(e.target.value)}
                  placeholder="DD"
                  min={1} max={31}
                  className="rounded-2xl border-2 border-gray-700 bg-gray-900 px-4 py-4 text-xl font-bold text-white text-center placeholder-gray-600 focus:border-[#ff6b35] focus:outline-none"
                />
              </div>
              <div className="flex flex-col gap-1">
                <label className="text-xs text-gray-500 font-medium">Mes</label>
                <input
                  type="number"
                  inputMode="numeric"
                  value={dobMonth}
                  onChange={e => setDobMonth(e.target.value)}
                  placeholder="MM"
                  min={1} max={12}
                  className="rounded-2xl border-2 border-gray-700 bg-gray-900 px-4 py-4 text-xl font-bold text-white text-center placeholder-gray-600 focus:border-[#ff6b35] focus:outline-none"
                />
              </div>
              <div className="flex flex-col gap-1">
                <label className="text-xs text-gray-500 font-medium">Año</label>
                <input
                  type="number"
                  inputMode="numeric"
                  value={dobYear}
                  onChange={e => setDobYear(e.target.value)}
                  placeholder="AAAA"
                  min={1920} max={new Date().getFullYear() - 10}
                  className="rounded-2xl border-2 border-gray-700 bg-gray-900 px-4 py-4 text-lg font-bold text-white text-center placeholder-gray-600 focus:border-[#ff6b35] focus:outline-none"
                />
              </div>
            </div>
            {data.dateOfBirth && (
              <p className="text-xs text-gray-500 text-center">
                Edad: <span className="text-white font-semibold">{calcAge(data.dateOfBirth)} años</span>
              </p>
            )}
            <PrimaryButton
              onClick={() => {
                const ok = commitDob();
                if (ok) goNext();
              }}
              disabled={
                !dobDay || !dobMonth || !dobYear ||
                parseInt(dobYear) < 1920 ||
                parseInt(dobYear) > new Date().getFullYear() - 10
              }
            >
              Continuar →
            </PrimaryButton>
          </div>
        );

      // ── Body measurements ──────────────────────────────────────────────────
      case 'body':
        return (
          <div className="flex flex-col gap-6">
            <div className="flex flex-col gap-1">
              <h2 className="text-2xl font-extrabold text-white">Tu talla y peso actual</h2>
              <p className="text-sm text-gray-400">Para calcular tu gasto calórico exacto</p>
            </div>
            <div className="flex flex-col gap-4">
              <div className="flex flex-col gap-2">
                <label className="text-sm font-medium text-gray-400">Altura</label>
                <NumberInput
                  value={heightInput}
                  onChange={setHeightInput}
                  placeholder="170"
                  unit="cm"
                  min={100}
                  max={250}
                />
              </div>
              <div className="flex flex-col gap-2">
                <label className="text-sm font-medium text-gray-400">Peso actual</label>
                <NumberInput
                  value={weightInput}
                  onChange={setWeightInput}
                  placeholder="70"
                  unit="kg"
                  min={30}
                  max={200}
                />
              </div>
            </div>
            <PrimaryButton
              onClick={() => {
                commitBodyInputs();
                goNext();
              }}
              disabled={
                !heightInput || !weightInput ||
                parseFloat(heightInput) < 100 || parseFloat(heightInput) > 250 ||
                parseFloat(weightInput) < 30 || parseFloat(weightInput) > 200
              }
            >
              Continuar →
            </PrimaryButton>
          </div>
        );

      // ── Target weight ──────────────────────────────────────────────────────
      case 'target': {
        const paces: { value: number; label: string; desc: string; badge?: string }[] = [
          { value: 0.25, label: 'Gradual', desc: '0.25 kg por semana', badge: 'Recomendado' },
          { value: 0.5, label: 'Moderado', desc: '0.5 kg por semana' },
          { value: 0.75, label: 'Acelerado', desc: '0.75 kg por semana' },
        ];
        return (
          <div className="flex flex-col gap-6">
            <div className="flex flex-col gap-1">
              <h2 className="text-2xl font-extrabold text-white">¿Cuál es tu peso objetivo?</h2>
              <p className="text-sm text-gray-400">
                Peso actual: <span className="text-white font-semibold">{weightInput} kg</span>
              </p>
            </div>
            <div className="flex flex-col gap-2">
              <label className="text-sm font-medium text-gray-400">Peso meta</label>
              <NumberInput
                value={targetWeightInput}
                onChange={setTargetWeightInput}
                placeholder={data.goal === 'gain_muscle' ? '80' : '65'}
                unit="kg"
                min={30}
                max={250}
              />
            </div>
            <div className="flex flex-col gap-2">
              <label className="text-sm font-medium text-gray-400">Ritmo de cambio</label>
              {paces.map(p => (
                <OptionCard
                  key={p.value}
                  selected={data.weeklyGoalKg === p.value}
                  onClick={() => setData(d => ({ ...d, weeklyGoalKg: p.value }))}
                >
                  <div className="flex items-center justify-between">
                    <div>
                      <span className="font-semibold text-white">{p.label}</span>
                      <span className="text-xs text-gray-400 ml-2">{p.desc}</span>
                    </div>
                    <div className="flex items-center gap-2">
                      {p.badge && (
                        <span className="rounded-full px-2 py-0.5 text-xs font-semibold" style={{ backgroundColor: `${ACCENT}22`, color: ACCENT }}>
                          {p.badge}
                        </span>
                      )}
                      {data.weeklyGoalKg === p.value && (
                        <span className="text-[#ff6b35] text-lg">✓</span>
                      )}
                    </div>
                  </div>
                </OptionCard>
              ))}
            </div>
            <PrimaryButton
              onClick={() => {
                commitTargetInput();
                goNext();
              }}
              disabled={
                !targetWeightInput ||
                parseFloat(targetWeightInput) < 30 ||
                !data.weeklyGoalKg
              }
            >
              Continuar →
            </PrimaryButton>
          </div>
        );
      }

      // ── Activity level ─────────────────────────────────────────────────────
      case 'activity': {
        const levels: { value: ActivityLevel; icon: string; label: string; desc: string }[] = [
          { value: 'sedentary', icon: '🪑', label: 'Sedentario', desc: 'Trabajo de oficina, muy poco movimiento' },
          { value: 'light', icon: '🚶', label: 'Poco activo', desc: '1-2 entrenamientos por semana' },
          { value: 'moderate', icon: '🏃', label: 'Moderado', desc: '3-4 entrenamientos por semana' },
          { value: 'active', icon: '💪', label: 'Activo', desc: '5-6 entrenamientos por semana' },
          { value: 'very_active', icon: '🔥', label: 'Muy activo', desc: 'Entrenamiento intenso diario' },
        ];
        return (
          <div className="flex flex-col gap-4">
            <div className="flex flex-col gap-1 mb-2">
              <h2 className="text-2xl font-extrabold text-white">¿Qué tan activo/a sos<br />en tu día a día?</h2>
              <p className="text-xs text-gray-500">Incluí trabajo físico y ejercicio</p>
            </div>
            {levels.map(l => (
              <OptionCard key={l.value} selected={data.activityLevel === l.value} onClick={() => setData(d => ({ ...d, activityLevel: l.value }))}>
                <div className="flex items-center gap-4">
                  <span className="text-2xl">{l.icon}</span>
                  <div className="flex-1 min-w-0">
                    <div className="font-semibold text-white">{l.label}</div>
                    <div className="text-xs text-gray-400 truncate">{l.desc}</div>
                  </div>
                  {data.activityLevel === l.value && (
                    <span className="text-[#ff6b35] text-lg flex-shrink-0">✓</span>
                  )}
                </div>
              </OptionCard>
            ))}
            <PrimaryButton onClick={goNext} disabled={!data.activityLevel} className="mt-1">
              Continuar →
            </PrimaryButton>
          </div>
        );
      }

      // ── Diet preferences ───────────────────────────────────────────────────
      case 'diet': {
        const diets: { value: DietaryPreference; icon: string; label: string }[] = [
          { value: 'none', icon: '🍽️', label: 'Sin restricciones' },
          { value: 'vegan', icon: '🌱', label: 'Vegano/a' },
          { value: 'vegetarian', icon: '🥦', label: 'Vegetariano/a' },
          { value: 'pescatarian', icon: '🐟', label: 'Pescetariano/a' },
          { value: 'keto', icon: '🥑', label: 'Keto / Low-Carb' },
          { value: 'paleo', icon: '🥩', label: 'Paleo' },
          { value: 'gluten_free', icon: '🌾', label: 'Sin gluten' },
          { value: 'mediterranean', icon: '🫒', label: 'Mediterránea' },
        ];
        return (
          <div className="flex flex-col gap-3">
            <div className="flex flex-col gap-1 mb-2">
              <h2 className="text-2xl font-extrabold text-white">¿Tenés alguna preferencia<br />alimentaria?</h2>
              <p className="text-xs text-gray-500">Tus recetas se adaptarán a esto</p>
            </div>
            <div className="grid grid-cols-2 gap-3">
              {diets.map(d => (
                <OptionCard
                  key={d.value}
                  selected={data.dietaryPreference === d.value}
                  onClick={() => setData(prev => ({ ...prev, dietaryPreference: d.value }))}
                  className="py-3"
                >
                  <div className="flex flex-col items-center gap-1 text-center">
                    <span className="text-2xl">{d.icon}</span>
                    <span className="text-xs font-semibold text-white leading-tight">{d.label}</span>
                    {data.dietaryPreference === d.value && (
                      <span className="text-[#ff6b35] text-xs">✓</span>
                    )}
                  </div>
                </OptionCard>
              ))}
            </div>
            <PrimaryButton onClick={goNext} disabled={!data.dietaryPreference} className="mt-2">
              Continuar →
            </PrimaryButton>
          </div>
        );
      }

      // ── Struggles ──────────────────────────────────────────────────────────
      case 'struggles': {
        const options = [
          { id: 'consistency', icon: '📅', label: 'Mantener la constancia' },
          { id: 'portions', icon: '⚖️', label: 'Controlar las porciones' },
          { id: 'junk_food', icon: '🍕', label: 'Resistir la comida chatarra' },
          { id: 'motivation', icon: '😓', label: 'Mantenerme motivado/a' },
          { id: 'time', icon: '⏱️', label: 'Falta de tiempo para cocinar' },
          { id: 'knowledge', icon: '🤔', label: 'No sé qué comer' },
        ];
        const toggle = (id: string) =>
          setData(d => ({
            ...d,
            struggles: d.struggles.includes(id)
              ? d.struggles.filter(s => s !== id)
              : [...d.struggles, id],
          }));
        return (
          <div className="flex flex-col gap-4">
            <div className="flex flex-col gap-1 mb-2">
              <h2 className="text-2xl font-extrabold text-white">¿Qué te cuesta más<br />con la nutrición?</h2>
              <p className="text-sm text-gray-400">Elegí todo lo que aplique</p>
            </div>
            <div className="flex flex-col gap-3">
              {options.map(o => (
                <OptionCard key={o.id} selected={data.struggles.includes(o.id)} onClick={() => toggle(o.id)}>
                  <div className="flex items-center gap-4">
                    <span className="text-xl">{o.icon}</span>
                    <span className="font-medium text-white flex-1">{o.label}</span>
                    <div
                      className="w-5 h-5 rounded-md border-2 flex items-center justify-center flex-shrink-0 transition-colors"
                      style={{
                        borderColor: data.struggles.includes(o.id) ? ACCENT : '#4b5563',
                        backgroundColor: data.struggles.includes(o.id) ? ACCENT : 'transparent',
                      }}
                    >
                      {data.struggles.includes(o.id) && <span className="text-white text-xs font-bold">✓</span>}
                    </div>
                  </div>
                </OptionCard>
              ))}
            </div>
            <PrimaryButton onClick={goNext} disabled={data.struggles.length === 0} className="mt-1">
              Continuar →
            </PrimaryButton>
          </div>
        );
      }

      // ── Analyzing animation ────────────────────────────────────────────────
      case 'analyzing':
        return (
          <div className="flex flex-col items-center justify-center gap-8 py-8 min-h-[60vh]">
            {/* Pulsing orb */}
            <div className="relative flex items-center justify-center">
              <div
                className="absolute h-32 w-32 rounded-full opacity-20 animate-ping"
                style={{ backgroundColor: ACCENT }}
              />
              <div
                className="absolute h-24 w-24 rounded-full opacity-30 animate-pulse"
                style={{ backgroundColor: ACCENT }}
              />
              <div
                className="relative z-10 h-20 w-20 rounded-full flex items-center justify-center text-4xl"
                style={{ backgroundColor: ACCENT }}
              >
                🧠
              </div>
            </div>

            <div className="flex flex-col items-center gap-2 w-full">
              <p className="text-white font-semibold text-center transition-all duration-500">
                {analysisMsg}
              </p>
              <div className="w-full h-2 bg-gray-800 rounded-full overflow-hidden mt-2">
                <div
                  className="h-full rounded-full transition-all duration-100"
                  style={{ width: `${analysisProgress}%`, backgroundColor: ACCENT }}
                />
              </div>
              <p className="text-gray-500 text-xs">{analysisProgress}%</p>
            </div>

            <p className="text-xs text-gray-600 text-center px-4">
              Analizando {data.firstName ? `el perfil de ${data.firstName}` : 'tu perfil'}...
            </p>
          </div>
        );

      // ── Results preview ────────────────────────────────────────────────────
      case 'results': {
        if (!results) return null;

        const goalLabels: Record<Goal, string> = {
          lose_weight: 'Bajar de peso 🔥',
          gain_muscle: 'Ganar músculo 💪',
          maintain: 'Mantener peso ⚡',
          eat_healthier: 'Comer más sano 🥗',
        };

        const weeklyProjection = data.goal === 'lose_weight'
          ? `−${data.weeklyGoalKg ?? 0.5} kg/semana`
          : data.goal === 'gain_muscle'
          ? '+0.25 kg de músculo/semana'
          : null;

        return (
          <div className="flex flex-col gap-5">
            <div className="flex flex-col gap-1">
              <div className="flex items-center gap-2">
                <span className="text-2xl">🎯</span>
                <h2 className="text-2xl font-extrabold text-white">Tu plan está listo,<br />{data.firstName}!</h2>
              </div>
              {data.goal && (
                <p className="text-sm text-gray-400">Objetivo: <span style={{ color: ACCENT }} className="font-semibold">{goalLabels[data.goal]}</span></p>
              )}
            </div>

            {/* Main calorie card */}
            <div className="rounded-2xl p-5 flex flex-col items-center gap-1" style={{ background: `linear-gradient(135deg, #1a1a1a, #0d0d0d)`, border: `2px solid ${ACCENT}33` }}>
              <p className="text-xs text-gray-400 uppercase tracking-widest font-medium">Calorías diarias</p>
              <p className="text-5xl font-black" style={{ color: ACCENT }}>{results.calories.toLocaleString()}</p>
              <p className="text-xs text-gray-500">kcal / día — TDEE base: {results.tdee.toLocaleString()} kcal</p>
            </div>

            {/* Macro breakdown */}
            <div className="grid grid-cols-3 gap-3">
              {[
                { label: 'Proteínas', value: results.protein, unit: 'g', color: '#ff6b35' },
                { label: 'Carbos', value: results.carbs, unit: 'g', color: '#4ade80' },
                { label: 'Grasas', value: results.fat, unit: 'g', color: '#facc15' },
              ].map(m => (
                <div key={m.label} className="rounded-2xl bg-gray-900 border border-gray-800 p-3 flex flex-col items-center gap-1">
                  <p className="text-2xl font-black" style={{ color: m.color }}>{m.value}</p>
                  <p className="text-xs text-gray-400">{m.unit} {m.label}</p>
                </div>
              ))}
            </div>

            {/* Weekly projection */}
            {weeklyProjection && (
              <div className="flex items-center gap-3 rounded-2xl bg-gray-900 border border-gray-700 p-4">
                <span className="text-2xl">📈</span>
                <div>
                  <p className="text-sm font-semibold text-white">Proyección semanal</p>
                  <p className="text-xs text-gray-400">{weeklyProjection} siguiendo el plan</p>
                </div>
              </div>
            )}

            {/* Struggles addressed */}
            {data.struggles.length > 0 && (
              <div className="rounded-2xl bg-gray-900 border border-gray-700 p-4">
                <p className="text-xs text-gray-400 font-medium mb-2">Tu plan aborda específicamente:</p>
                <div className="flex flex-wrap gap-2">
                  {data.struggles.slice(0, 3).map(s => (
                    <span key={s} className="rounded-full px-3 py-1 text-xs font-medium" style={{ backgroundColor: `${ACCENT}22`, color: ACCENT }}>
                      {{
                        consistency: '📅 Constancia',
                        portions: '⚖️ Porciones',
                        junk_food: '🍕 Antojos',
                        motivation: '😤 Motivación',
                        time: '⏱️ Tiempo',
                        knowledge: '🤔 Conocimiento',
                      }[s] ?? s}
                    </span>
                  ))}
                </div>
              </div>
            )}

            {/* Testimonial */}
            <div className="flex items-start gap-3 rounded-2xl bg-gray-900 border border-gray-800 p-4">
              <span className="text-2xl flex-shrink-0">💬</span>
              <div>
                <p className="text-xs font-semibold text-white leading-snug">"Seguí el plan y bajé 6 kg en 2 meses sin pasar hambre. Las calorías que me calculó fueron perfectas."</p>
                <p className="text-xs text-gray-500 mt-1">— Sofía M., Rosario ⭐⭐⭐⭐⭐</p>
              </div>
            </div>

            <PrimaryButton onClick={goNext}>
              Ver mi plan completo →
            </PrimaryButton>
          </div>
        );
      }

      // ── Paywall ────────────────────────────────────────────────────────────
      case 'paywall': {
        const plans: {
          id: Plan;
          label: string;
          price: string;
          monthly: string;
          detail: string;
          badge?: string;
          crossedOut?: string;
        }[] = [
          {
            id: 'free',
            label: 'Gratis',
            price: '$0',
            monthly: '$0/mes',
            detail: 'Funciones básicas, sin IA personalizada',
          },
          {
            id: 'monthly',
            label: 'Mensual',
            price: '$9.99',
            monthly: '$9.99/mes',
            detail: 'Plan completo con IA, cancelá cuando quieras',
          },
          {
            id: 'yearly',
            label: 'Anual',
            price: '$4.99/mes',
            monthly: '$59.88/año',
            detail: 'El plan más popular — ahorrás 50%',
            badge: 'MÁS POPULAR',
            crossedOut: '$9.99/mes',
          },
        ];

        return (
          <div className="flex flex-col gap-5">
            <div className="flex flex-col gap-1">
              <h2 className="text-2xl font-extrabold text-white">Elegí tu plan,<br />{data.firstName}</h2>
              <p className="text-sm text-gray-400">Empezá tu transformación hoy</p>
            </div>

            {/* 7-day trial badge with delayed animation */}
            <div
              className="flex items-center gap-3 rounded-2xl p-4 border transition-all duration-700"
              style={{
                borderColor: trialVisible ? `${ACCENT}66` : 'transparent',
                backgroundColor: trialVisible ? `${ACCENT}11` : 'transparent',
                opacity: trialVisible ? 1 : 0,
                transform: trialVisible ? 'translateY(0)' : 'translateY(8px)',
              }}
            >
              <span className="text-2xl">🎁</span>
              <div>
                <p className="text-sm font-bold text-white">7 días de prueba gratuita</p>
                <p className="text-xs text-gray-400">Sin cargos hasta que decidas continuar</p>
              </div>
            </div>

            {/* Plan cards */}
            <div className="flex flex-col gap-3">
              {plans.map(p => (
                <button
                  key={p.id}
                  onClick={() => setSelectedPlan(p.id)}
                  className="w-full text-left rounded-2xl border-2 p-4 transition-all duration-150 active:scale-[0.98]"
                  style={{
                    borderColor: selectedPlan === p.id ? ACCENT : '#374151',
                    backgroundColor: selectedPlan === p.id ? `${ACCENT}11` : '#111827',
                  }}
                >
                  <div className="flex items-start justify-between gap-3">
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 flex-wrap">
                        <span className="font-bold text-white">{p.label}</span>
                        {p.badge && (
                          <span className="rounded-full px-2 py-0.5 text-xs font-bold" style={{ backgroundColor: ACCENT, color: '#fff' }}>
                            {p.badge}
                          </span>
                        )}
                      </div>
                      <div className="flex items-center gap-2 mt-0.5">
                        <span className="text-xl font-black" style={{ color: selectedPlan === p.id ? ACCENT : '#fff' }}>
                          {p.price}
                        </span>
                        {p.crossedOut && (
                          <span className="text-sm text-gray-500 line-through">{p.crossedOut}</span>
                        )}
                      </div>
                      <p className="text-xs text-gray-400 mt-0.5">{p.detail}</p>
                    </div>
                    <div
                      className="mt-1 h-5 w-5 rounded-full border-2 flex items-center justify-center flex-shrink-0"
                      style={{
                        borderColor: selectedPlan === p.id ? ACCENT : '#4b5563',
                        backgroundColor: selectedPlan === p.id ? ACCENT : 'transparent',
                      }}
                    >
                      {selectedPlan === p.id && <span className="text-white text-xs font-bold">✓</span>}
                    </div>
                  </div>
                </button>
              ))}
            </div>

            {/* Social proof */}
            <div className="flex items-center gap-3 rounded-2xl bg-gray-900 border border-gray-800 p-4">
              <div className="flex -space-x-2">
                {['👩', '👨', '👩🏽'].map((e, i) => (
                  <span key={i} className="text-xl w-8 h-8 rounded-full bg-gray-700 flex items-center justify-center border-2 border-gray-900">{e}</span>
                ))}
              </div>
              <div>
                <p className="text-xs font-semibold text-white">"Bajé 8 kg en 3 meses sin pasar hambre"</p>
                <p className="text-xs text-gray-500">— Valentina, Buenos Aires ⭐⭐⭐⭐⭐</p>
              </div>
            </div>

            <PrimaryButton onClick={handleSubmit} loading={isSubmitting}>
              {selectedPlan === 'free'
                ? 'Empezar gratis →'
                : `Empezar con 7 días gratis →`}
            </PrimaryButton>

            {/* Trust signals */}
            <div className="flex justify-center gap-6 text-xs text-gray-600 pb-2">
              <span>🔒 Pago seguro</span>
              <span>❌ Cancelá cuando quieras</span>
              <span>🔄 Garantía 30 días</span>
            </div>
          </div>
        );
      }

      default:
        return null;
    }
  };

  // Don't show back button on welcome, analyzing, or results
  const showBack = !['welcome', 'analyzing', 'results'].includes(stepId);

  return (
    <div className="min-h-screen bg-[#0a0a0a] text-white">
      <div className="mx-auto max-w-md min-h-screen flex flex-col">
        {/* Header: back button + progress bar + step tag */}
        {stepId !== 'welcome' && (
          <div className="flex flex-col px-5 pt-6 pb-3 gap-2">
            <div className="flex items-center gap-3">
              {showBack && (
                <button
                  onClick={goBack}
                  className="flex-shrink-0 w-9 h-9 rounded-full bg-gray-900 border border-gray-700 flex items-center justify-center text-gray-400 hover:text-white transition-colors"
                  aria-label="Volver"
                >
                  ←
                </button>
              )}
              <div className="flex-1 h-2 bg-gray-800 rounded-full overflow-hidden">
                <div
                  className="h-full rounded-full transition-all duration-500 ease-out"
                  style={{ width: `${progress}%`, backgroundColor: ACCENT }}
                />
              </div>
              <span className="flex-shrink-0 text-xs text-gray-500 w-8 text-right">{progress}%</span>
            </div>
            {STEP_LABELS[stepId] && (
              <p className="text-xs font-medium" style={{ color: ACCENT }}>
                {STEP_LABELS[stepId]}
              </p>
            )}
          </div>
        )}

        {/* Step content */}
        <div className="flex-1 px-5 py-4 pb-8 overflow-y-auto">
          {renderStep()}
        </div>
      </div>
    </div>
  );
}
