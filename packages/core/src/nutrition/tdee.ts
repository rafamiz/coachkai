import { ActivityLevel, Gender, Goal } from '../types/user';

const ACTIVITY_MULTIPLIERS: Record<ActivityLevel, number> = {
  sedentary: 1.2,
  light: 1.375,
  moderate: 1.55,
  active: 1.725,
  very_active: 1.9,
};

export function calculateAge(dateOfBirth: string): number {
  const dob = new Date(dateOfBirth);
  const today = new Date();
  let age = today.getFullYear() - dob.getFullYear();
  const monthDiff = today.getMonth() - dob.getMonth();
  if (monthDiff < 0 || (monthDiff === 0 && today.getDate() < dob.getDate())) {
    age--;
  }
  return age;
}

export function calculateBMR(
  gender: Gender,
  weightKg: number,
  heightCm: number,
  age: number,
): number {
  // Mifflin-St Jeor equation
  const base = 10 * weightKg + 6.25 * heightCm - 5 * age;
  return gender === 'female' ? base - 161 : base + 5;
}

export function calculateTDEE(
  gender: Gender,
  weightKg: number,
  heightCm: number,
  age: number,
  activityLevel: ActivityLevel,
): number {
  const bmr = calculateBMR(gender, weightKg, heightCm, age);
  return Math.round(bmr * ACTIVITY_MULTIPLIERS[activityLevel]);
}

export function calculateDailyCalories(
  tdee: number,
  goal: Goal,
  weeklyGoalKg?: number,
): number {
  switch (goal) {
    case 'lose_weight': {
      // Default 0.5kg/week = ~550 cal deficit
      const deficit = (weeklyGoalKg || 0.5) * 1100;
      return Math.max(1200, Math.round(tdee - deficit));
    }
    case 'gain_muscle':
      return Math.round(tdee + 300);
    case 'maintain':
    case 'eat_healthier':
    default:
      return Math.round(tdee);
  }
}
