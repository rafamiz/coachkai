import { getServiceClient } from './client';

export async function logExercise(params: {
  user_id: string;
  exercise_type: string;
  duration_min: number;
  calories_burned: number;
  description?: string;
}) {
  const { data } = await getServiceClient()
    .from('exercise_log')
    .insert({ ...params, logged_at: new Date().toISOString() })
    .select()
    .single();
  return data;
}

export async function getTodayExercise(userId: string, timezone: string) {
  const now = new Date();
  const formatter = new Intl.DateTimeFormat('en-CA', { timeZone: timezone });
  const today = formatter.format(now);

  const { data } = await getServiceClient()
    .from('exercise_log')
    .select('*')
    .eq('user_id', userId)
    .gte('logged_at', `${today}T00:00:00`)
    .lt('logged_at', `${today}T23:59:59.999`);

  return data || [];
}
