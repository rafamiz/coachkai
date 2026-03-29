import { NextRequest, NextResponse } from 'next/server';
import {
  getServiceClient,
  getDailySummaries,
  getWeightHistory,
  getWhatsAppProvider,
  getGoalEmoji,
} from '@nutricoach/core';
import type { User } from '@nutricoach/core';

export async function GET(req: NextRequest) {
  const authHeader = req.headers.get('authorization');
  if (authHeader !== `Bearer ${process.env.CRON_SECRET}`) {
    return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });
  }

  const supabase = getServiceClient();
  const { data: users } = await supabase
    .from('users')
    .select('*')
    .eq('onboarding_completed', true);

  if (!users?.length) return NextResponse.json({ processed: 0 });

  const provider = getWhatsAppProvider();
  let processed = 0;

  for (const user of users as User[]) {
    const summaries = await getDailySummaries(user.id, 7);
    if (!summaries.length) continue;

    const daysTracked = summaries.filter((s) => s.meal_count > 0).length;
    const avgCal = Math.round(summaries.reduce((s, d) => s + d.total_calories, 0) / summaries.length);
    const avgProtein = Math.round(summaries.reduce((s, d) => s + d.total_protein_g, 0) / summaries.length);

    const weights = await getWeightHistory(user.id, 7);
    let weightLine = '';
    if (weights.length >= 2) {
      const latest = weights[0].weight_kg;
      const earliest = weights[weights.length - 1].weight_kg;
      const delta = (latest - earliest).toFixed(1);
      const sign = parseFloat(delta) >= 0 ? '+' : '';
      weightLine = `\u{2696}\u{FE0F} Weight: ${earliest}kg \u{2192} ${latest}kg (${sign}${delta}kg)`;
    }

    const currentStreak = summaries[0]?.streak_days || 0;
    const avgAdherence = Math.round(
      summaries.reduce((s, d) => s + (d.adherence_pct || 0), 0) / summaries.length,
    );

    const emoji = getGoalEmoji(user.goal || 'eat_healthier');

    const message = [
      `${emoji} *Weekly Report, ${user.first_name}!*`,
      '',
      `\u{1F4CA} Avg daily: ${avgCal} kcal (target: ${user.daily_calories})`,
      `\u{1F4AA} Avg protein: ${avgProtein}g/${user.protein_g}g`,
      `\u{1F4C5} Days tracked: ${daysTracked}/7`,
      `\u{1F3AF} Avg adherence: ${avgAdherence}%`,
      currentStreak > 0 ? `\u{1F525} Current streak: ${currentStreak} days` : '',
      weightLine,
      '',
      avgAdherence >= 90
        ? 'Amazing week! Keep this momentum going! \u{1F680}'
        : avgAdherence >= 70
          ? "Solid week! Let's push for even better consistency. \u{1F4AA}"
          : "Room for improvement! Remember, consistency is key. You've got this! \u{1F49A}",
    ].filter(Boolean).join('\n');

    try {
      await provider.sendText(user.phone, message);
      processed++;
    } catch (err) {
      console.error(`Failed to send weekly report to ${user.id}:`, err);
    }
  }

  return NextResponse.json({ processed });
}
