import { NextRequest, NextResponse } from 'next/server';
import { createUser, getServiceClient } from '@nutricoach/core';
import type { Goal, Gender, ActivityLevel, DietaryPreference } from '@nutricoach/core';

// ─── Nutrition helpers (inlined to avoid server-only imports client-side) ─────

function calcAge(dateOfBirth: string): number {
  const d = new Date(dateOfBirth);
  const today = new Date();
  let age = today.getFullYear() - d.getFullYear();
  const m = today.getMonth() - d.getMonth();
  if (m < 0 || (m === 0 && today.getDate() < d.getDate())) age--;
  return age;
}

const ACTIVITY_MULT: Record<ActivityLevel, number> = {
  sedentary: 1.2,
  light: 1.375,
  moderate: 1.55,
  active: 1.725,
  very_active: 1.9,
};

function calcTDEE(gender: Gender, kg: number, cm: number, age: number, level: ActivityLevel): number {
  const base = 10 * kg + 6.25 * cm - 5 * age;
  const bmr = gender === 'female' ? base - 161 : base + 5;
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
  return Math.min(calories, 4500);
}

function calcMacros(cal: number, goal: Goal, weightKg: number) {
  // Protein based on g/kg body weight (not % of calories)
  const proteinPerKg: Record<Goal, number> = {
    lose_weight: 2.0,
    gain_muscle: 2.2,
    maintain: 1.6,
    eat_healthier: 1.6,
  };
  const protein_g = Math.round(weightKg * proteinPerKg[goal]);
  const proteinCals = protein_g * 4;
  const remaining = Math.max(0, cal - proteinCals);
  // Split remaining between carbs and fat
  const carbRatio: Record<Goal, number> = {
    lose_weight: 0.55, gain_muscle: 0.65, maintain: 0.6, eat_healthier: 0.6,
  };
  const cr = carbRatio[goal];
  return {
    protein_g,
    carbs_g: Math.round((remaining * cr) / 4),
    fat_g: Math.round((remaining * (1 - cr)) / 9),
  };
}

// ─── POST /api/onboarding ─────────────────────────────────────────────────────

export async function POST(req: NextRequest) {
  let body: Record<string, unknown>;
  try {
    body = await req.json();
  } catch {
    return NextResponse.json({ error: 'Invalid JSON' }, { status: 400 });
  }

  const {
    first_name,
    gender,
    date_of_birth,
    height_cm,
    weight_kg,
    activity_level,
    goal,
    target_weight_kg,
    weekly_goal_kg,
    dietary_preference,
    allergies,
    unit_system,
    timezone,
    plan,
  } = body as {
    first_name: string;
    gender: Gender;
    date_of_birth: string;
    height_cm: number;
    weight_kg: number;
    activity_level: ActivityLevel;
    goal: Goal;
    target_weight_kg?: number;
    weekly_goal_kg?: number;
    dietary_preference?: DietaryPreference;
    allergies?: string[];
    unit_system?: string;
    timezone?: string;
    plan?: 'free' | 'monthly' | 'yearly';
    phone?: string;
  };

  if (!first_name || !gender || !date_of_birth || !height_cm || !weight_kg || !activity_level || !goal) {
    return NextResponse.json({ error: 'Missing required fields' }, { status: 400 });
  }

  // Calculate nutrition targets
  const age = calcAge(date_of_birth);
  const tdee = calcTDEE(gender, weight_kg, height_cm, age, activity_level);
  const dailyCal = calcDailyCal(tdee, goal, weekly_goal_kg);
  const macros = calcMacros(dailyCal, goal, weight_kg);

  const userData = {
    phone: (body.phone as string) || `web_${Date.now()}`,
    phone_verified: !!(body.phone),
    first_name,
    gender,
    date_of_birth,
    height_cm,
    weight_kg,
    activity_level,
    goal,
    target_weight_kg: target_weight_kg ?? null,
    weekly_goal_kg: weekly_goal_kg ?? 0.5,
    daily_calories: dailyCal,
    protein_g: macros.protein_g,
    carbs_g: macros.carbs_g,
    fat_g: macros.fat_g,
    dietary_preference: (dietary_preference ?? 'none') as DietaryPreference,
    allergies: allergies ?? [],
    unit_system: ((unit_system ?? 'metric') as 'metric' | 'imperial'),
    timezone: timezone ?? 'America/Argentina/Buenos_Aires',
    onboarding_completed: true,
    onboarding_step: 11,
  };

  const user = await createUser(userData);
  if (!user) {
    return NextResponse.json({ error: 'Failed to save user' }, { status: 500 });
  }

  const trialEndsAt = new Date(Date.now() + 7 * 24 * 60 * 60 * 1000).toISOString();
  await getServiceClient()
    .from('subscriptions')
    .insert({
      user_id: user.id,
      plan: plan ?? 'free',
      status: plan && plan !== 'free' ? 'trialing' : 'active',
      trial_ends_at: plan && plan !== 'free' ? trialEndsAt : null,
    });

  return NextResponse.json({
    user_id: user.id,
    daily_calories: dailyCal,
    protein_g: macros.protein_g,
    carbs_g: macros.carbs_g,
    fat_g: macros.fat_g,
    tdee,
  });
}
