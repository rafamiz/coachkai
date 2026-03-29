import { getServiceClient } from './client';
import { DailySummary } from '../types/meal';

export async function upsertDailySummary(params: {
  user_id: string;
  date: string;
  total_calories: number;
  total_protein_g: number;
  total_carbs_g: number;
  total_fat_g: number;
  total_water_ml: number;
  meal_count: number;
  exercise_min: number;
  exercise_cal: number;
  avg_goal_score: number | null;
  calorie_target: number;
  streak_days: number;
}): Promise<DailySummary | null> {
  const adherence = params.calorie_target > 0
    ? Math.round((params.total_calories / params.calorie_target) * 100 * 10) / 10
    : null;

  const { data } = await getServiceClient()
    .from('daily_summaries')
    .upsert(
      {
        ...params,
        adherence_pct: adherence,
        total_fiber_g: 0,
        fasting_compliant: null,
        summary_sent: false,
      },
      { onConflict: 'user_id,date' },
    )
    .select()
    .single();
  return data;
}

export async function getDailySummaries(
  userId: string,
  days = 30,
): Promise<DailySummary[]> {
  const startDate = new Date();
  startDate.setDate(startDate.getDate() - days);

  const { data } = await getServiceClient()
    .from('daily_summaries')
    .select('*')
    .eq('user_id', userId)
    .gte('date', startDate.toISOString().split('T')[0])
    .order('date', { ascending: false });

  return data || [];
}

export async function markSummarySent(userId: string, date: string) {
  await getServiceClient()
    .from('daily_summaries')
    .update({ summary_sent: true })
    .eq('user_id', userId)
    .eq('date', date);
}
