export type Goal = 'lose_weight' | 'gain_muscle' | 'maintain' | 'eat_healthier';
export type ActivityLevel = 'sedentary' | 'light' | 'moderate' | 'active' | 'very_active';
export type Gender = 'male' | 'female' | 'other';
export type DietaryPreference = 'none' | 'vegan' | 'vegetarian' | 'pescatarian' | 'keto' | 'paleo' | 'gluten_free' | 'mediterranean';
export type UnitSystem = 'metric' | 'imperial';
export type SubscriptionPlan = 'free' | 'monthly' | 'yearly';
export type SubscriptionStatus = 'trialing' | 'active' | 'past_due' | 'canceled' | 'expired';

export interface User {
  id: string;
  auth_id: string | null;
  phone: string;
  phone_verified: boolean;
  first_name: string | null;
  last_name: string | null;
  email: string | null;
  avatar_url: string | null;
  gender: Gender | null;
  date_of_birth: string | null;
  height_cm: number | null;
  weight_kg: number | null;
  activity_level: ActivityLevel | null;
  goal: Goal | null;
  target_weight_kg: number | null;
  weekly_goal_kg: number | null;
  daily_calories: number | null;
  protein_g: number | null;
  carbs_g: number | null;
  fat_g: number | null;
  dietary_preference: DietaryPreference;
  allergies: string[];
  unit_system: UnitSystem;
  timezone: string;
  language: string;
  fasting_enabled: boolean;
  fasting_window: { eating_start: string; eating_end: string } | null;
  onboarding_completed: boolean;
  onboarding_step: number;
  wa_provider: string | null;
  wa_id: string | null;
  created_at: string;
  updated_at: string;
}

export interface UserContext {
  first_name: string;
  goal: Goal;
  daily_calories: number;
  protein_g: number;
  carbs_g: number;
  fat_g: number;
  dietary_preference: DietaryPreference;
  allergies: string[];
  today_calories: number;
  today_protein: number;
  today_carbs: number;
  today_fat: number;
  today_water_ml: number;
  local_time: string;
  fasting_status: string;
  timezone: string;
}
