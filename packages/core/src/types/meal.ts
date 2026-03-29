export type MealType = 'breakfast' | 'lunch' | 'snack' | 'dinner';

export interface FoodItem {
  name: string;
  estimated_qty: string;
  calories: number;
  protein_g: number;
  carbs_g: number;
  fat_g: number;
}

export interface Meal {
  id: string;
  user_id: string;
  meal_type: MealType;
  description: string | null;
  foods: FoodItem[];
  calories: number;
  protein_g: number;
  carbs_g: number;
  fat_g: number;
  fiber_g: number | null;
  goal_score: number;
  ai_tip: string | null;
  ai_summary: string | null;
  photo_url: string | null;
  photo_storage_path: string | null;
  source: 'whatsapp' | 'web' | 'api';
  logged_at: string;
  created_at: string;
}

export interface DailySummary {
  id: string;
  user_id: string;
  date: string;
  total_calories: number;
  total_protein_g: number;
  total_carbs_g: number;
  total_fat_g: number;
  total_fiber_g: number;
  total_water_ml: number;
  meal_count: number;
  exercise_min: number;
  exercise_cal: number;
  avg_goal_score: number | null;
  calorie_target: number;
  adherence_pct: number | null;
  streak_days: number;
  fasting_compliant: boolean | null;
  summary_sent: boolean;
}
