import { getServiceClient } from './client';

export interface Reminder {
  id: string;
  user_id: string;
  type: 'meal' | 'water' | 'weigh_in' | 'custom';
  label: string | null;
  time_utc: string;
  days: number[];
  enabled: boolean;
  last_sent: string | null;
}

export async function getDueReminders(): Promise<(Reminder & { phone: string; first_name: string })[]> {
  const now = new Date();
  const currentTime = now.toISOString().slice(11, 16); // HH:MM
  const currentDay = now.getUTCDay() || 7; // 1=Mon, 7=Sun

  // Get reminders within 5-minute window
  const startMin = new Date(now.getTime() - 5 * 60 * 1000).toISOString().slice(11, 16);

  const { data } = await getServiceClient()
    .from('reminders')
    .select('*, users!inner(phone, first_name)')
    .eq('enabled', true)
    .gte('time_utc', startMin)
    .lte('time_utc', currentTime)
    .contains('days', [currentDay]);

  if (!data) return [];

  return data.map((r: Record<string, unknown>) => {
    const users = r.users as { phone: string; first_name: string };
    return {
      ...r,
      phone: users.phone,
      first_name: users.first_name,
    } as Reminder & { phone: string; first_name: string };
  });
}

export async function createDefaultReminders(userId: string) {
  const defaults = [
    { type: 'meal', label: 'Breakfast reminder', time_utc: '12:00', days: [1, 2, 3, 4, 5, 6, 7] },
    { type: 'meal', label: 'Lunch reminder', time_utc: '17:00', days: [1, 2, 3, 4, 5, 6, 7] },
    { type: 'meal', label: 'Dinner reminder', time_utc: '23:00', days: [1, 2, 3, 4, 5, 6, 7] },
    { type: 'water', label: 'Water reminder', time_utc: '15:00', days: [1, 2, 3, 4, 5, 6, 7] },
    { type: 'weigh_in', label: 'Weekly weigh-in', time_utc: '13:00', days: [1] },
  ];

  await getServiceClient()
    .from('reminders')
    .insert(defaults.map((r) => ({ ...r, user_id: userId, enabled: true })));
}

export async function markReminderSent(reminderId: string) {
  await getServiceClient()
    .from('reminders')
    .update({ last_sent: new Date().toISOString() })
    .eq('id', reminderId);
}
