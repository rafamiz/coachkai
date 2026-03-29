import { getServiceClient } from './client';
import { Meal, FoodItem, MealType } from '../types/meal';

export async function logMeal(params: {
  user_id: string;
  meal_type: MealType;
  description?: string;
  foods: FoodItem[];
  calories: number;
  protein_g: number;
  carbs_g: number;
  fat_g: number;
  goal_score: number;
  ai_tip?: string;
  ai_summary?: string;
  photo_url?: string;
  photo_storage_path?: string;
  source?: 'whatsapp' | 'web' | 'api';
}): Promise<Meal | null> {
  const { data } = await getServiceClient()
    .from('meals')
    .insert({
      ...params,
      foods: params.foods,
      source: params.source || 'whatsapp',
      logged_at: new Date().toISOString(),
    })
    .select()
    .single();
  return data;
}

export async function getTodayMeals(userId: string, timezone: string): Promise<Meal[]> {
  const now = new Date();
  const formatter = new Intl.DateTimeFormat('en-CA', { timeZone: timezone }); // YYYY-MM-DD
  const today = formatter.format(now);

  const { data } = await getServiceClient()
    .from('meals')
    .select('*')
    .eq('user_id', userId)
    .gte('logged_at', `${today}T00:00:00`)
    .lt('logged_at', `${today}T23:59:59.999`)
    .order('logged_at', { ascending: true });

  return data || [];
}

export async function getTodayTotals(userId: string, timezone: string) {
  const meals = await getTodayMeals(userId, timezone);
  return {
    calories: meals.reduce((sum, m) => sum + (m.calories || 0), 0),
    protein_g: meals.reduce((sum, m) => sum + (m.protein_g || 0), 0),
    carbs_g: meals.reduce((sum, m) => sum + (m.carbs_g || 0), 0),
    fat_g: meals.reduce((sum, m) => sum + (m.fat_g || 0), 0),
    meal_count: meals.length,
  };
}

export async function getMealsByDateRange(
  userId: string,
  startDate: string,
  endDate: string,
): Promise<Meal[]> {
  const { data } = await getServiceClient()
    .from('meals')
    .select('*')
    .eq('user_id', userId)
    .gte('logged_at', startDate)
    .lte('logged_at', endDate)
    .order('logged_at', { ascending: false });
  return data || [];
}
