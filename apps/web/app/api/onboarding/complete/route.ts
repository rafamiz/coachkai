import { NextRequest, NextResponse } from 'next/server';
import {
  createUser,
  updateUser,
  getUserByPhone,
  createDefaultReminders,
  createSubscription,
  calculateAge,
  calculateTDEE,
  calculateDailyCalories,
  calculateMacros,
} from '@nutricoach/core';
import type { Goal, Gender, ActivityLevel, DietaryPreference } from '@nutricoach/core';

export async function POST(req: NextRequest) {
  const body = await req.json();

  const {
    phone,
    first_name,
    last_name,
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
    fasting_enabled,
    fasting_window,
  } = body as {
    phone: string;
    first_name: string;
    last_name?: string;
    gender: Gender;
    date_of_birth: string;
    height_cm: number;
    weight_kg: number;
    activity_level: ActivityLevel;
    goal: Goal;
    target_weight_kg?: number;
    weekly_goal_kg?: number;
    dietary_preference: DietaryPreference;
    allergies: string[];
    unit_system: string;
    timezone: string;
    fasting_enabled?: boolean;
    fasting_window?: { eating_start: string; eating_end: string };
  };

  if (!phone || !first_name || !gender || !date_of_birth || !height_cm || !weight_kg || !activity_level || !goal) {
    return NextResponse.json({ error: 'Missing required fields' }, { status: 400 });
  }

  // Calculate TDEE and macros
  const age = calculateAge(date_of_birth);
  const tdee = calculateTDEE(gender, weight_kg, height_cm, age, activity_level);
  const dailyCal = calculateDailyCalories(tdee, goal, weekly_goal_kg);
  const macros = calculateMacros(dailyCal, goal);

  // Check if user exists
  let user = await getUserByPhone(phone);

  const userData = {
    phone,
    phone_verified: true,
    first_name,
    last_name: last_name || null,
    gender,
    date_of_birth,
    height_cm,
    weight_kg,
    activity_level,
    goal,
    target_weight_kg: target_weight_kg || null,
    weekly_goal_kg: weekly_goal_kg || null,
    daily_calories: dailyCal,
    protein_g: macros.protein_g,
    carbs_g: macros.carbs_g,
    fat_g: macros.fat_g,
    dietary_preference: dietary_preference || 'none',
    allergies: allergies || [],
    unit_system: (unit_system || 'metric') as 'metric' | 'imperial',
    timezone: timezone || 'America/New_York',
    fasting_enabled: fasting_enabled || false,
    fasting_window: fasting_window || null,
    onboarding_completed: true,
    onboarding_step: 9,
  };

  if (user) {
    user = await updateUser(user.id, userData);
  } else {
    user = await createUser(userData);
  }

  if (!user) {
    return NextResponse.json({ error: 'Failed to save user' }, { status: 500 });
  }

  // Create default reminders
  await createDefaultReminders(user.id);

  // Create free trial subscription
  await createSubscription({
    user_id: user.id,
    plan: 'free',
    trial_ends_at: new Date(Date.now() + 7 * 24 * 60 * 60 * 1000).toISOString(),
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
