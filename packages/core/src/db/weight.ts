import { getServiceClient } from './client';

export async function logWeight(userId: string, weightKg: number, note?: string) {
  const { data } = await getServiceClient()
    .from('weight_log')
    .insert({ user_id: userId, weight_kg: weightKg, note, logged_at: new Date().toISOString() })
    .select()
    .single();

  // Also update current weight on user profile
  await getServiceClient()
    .from('users')
    .update({ weight_kg: weightKg, updated_at: new Date().toISOString() })
    .eq('id', userId);

  return data;
}

export async function getWeightHistory(userId: string, limit = 30) {
  const { data } = await getServiceClient()
    .from('weight_log')
    .select('*')
    .eq('user_id', userId)
    .order('logged_at', { ascending: false })
    .limit(limit);
  return data || [];
}
