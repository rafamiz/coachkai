import { getServiceClient } from './client';

export async function logWater(userId: string, amountMl: number) {
  const { data } = await getServiceClient()
    .from('water_intake')
    .insert({ user_id: userId, amount_ml: amountMl, logged_at: new Date().toISOString() })
    .select()
    .single();
  return data;
}

export async function getTodayWater(userId: string, timezone: string): Promise<number> {
  const now = new Date();
  const formatter = new Intl.DateTimeFormat('en-CA', { timeZone: timezone });
  const today = formatter.format(now);

  const { data } = await getServiceClient()
    .from('water_intake')
    .select('amount_ml')
    .eq('user_id', userId)
    .gte('logged_at', `${today}T00:00:00`)
    .lt('logged_at', `${today}T23:59:59.999`);

  return (data || []).reduce((sum, row) => sum + row.amount_ml, 0);
}
