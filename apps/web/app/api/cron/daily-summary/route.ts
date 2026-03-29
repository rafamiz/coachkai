import { NextRequest, NextResponse } from 'next/server';
import {
  getServiceClient,
  getTodayTotals,
  getTodayWater,
  getTodayExercise,
  upsertDailySummary,
  getDailySummaries,
  markSummarySent,
  getWhatsAppProvider,
  getGoalEmoji,
} from '@nutricoach/core';
import type { User, Goal } from '@nutricoach/core';

export async function GET(req: NextRequest) {
  const authHeader = req.headers.get('authorization');
  if (authHeader !== `Bearer ${process.env.CRON_SECRET}`) {
    return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });
  }

  const supabase = getServiceClient();

  // Get all active users
  const { data: users } = await supabase
    .from('users')
    .select('*')
    .eq('onboarding_completed', true);

  if (!users?.length) {
    return NextResponse.json({ processed: 0 });
  }

  const provider = getWhatsAppProvider();
  const now = new Date();
  let processed = 0;

  for (const user of users as User[]) {
    // Check if it's ~9 PM in user's timezone
    const userTime = new Date(now.toLocaleString('en-US', { timeZone: user.timezone }));
    const hour = userTime.getHours();
    if (hour !== 21) continue; // Only send at 9 PM local

    const timezone = user.timezone || 'America/New_York';
    const formatter = new Intl.DateTimeFormat('en-CA', { timeZone: timezone });
    const today = formatter.format(now);

    // Gather data
    const totals = await getTodayTotals(user.id, timezone);
    const water = await getTodayWater(user.id, timezone);
    const exercises = await getTodayExercise(user.id, timezone);
    const exerciseMin = exercises.reduce((s, e) => s + (e.duration_min || 0), 0);
    const exerciseCal = exercises.reduce((s, e) => s + (e.calories_burned || 0), 0);

    // Calculate streak
    const recentSummaries = await getDailySummaries(user.id, 60);
    const datesWithMeals = recentSummaries
      .filter((s) => s.meal_count > 0)
      .map((s) => s.date);
    let streak = 0;
    const checkDate = new Date(today);
    // Today counts if they logged meals
    if (totals.meal_count > 0) {
      streak = 1;
      checkDate.setDate(checkDate.getDate() - 1);
      for (const d of datesWithMeals) {
        if (d === checkDate.toISOString().split('T')[0]) {
          streak++;
          checkDate.setDate(checkDate.getDate() - 1);
        } else {
          break;
        }
      }
    }

    // Compute average goal score
    const { data: todayMeals } = await supabase
      .from('meals')
      .select('goal_score')
      .eq('user_id', user.id)
      .gte('logged_at', `${today}T00:00:00`)
      .lt('logged_at', `${today}T23:59:59.999`);

    const scores = (todayMeals || []).map((m) => m.goal_score).filter(Boolean);
    const avgScore = scores.length > 0
      ? Math.round((scores.reduce((a, b) => a + b, 0) / scores.length) * 10) / 10
      : null;

    // Upsert summary
    await upsertDailySummary({
      user_id: user.id,
      date: today,
      total_calories: totals.calories,
      total_protein_g: totals.protein_g,
      total_carbs_g: totals.carbs_g,
      total_fat_g: totals.fat_g,
      total_water_ml: water,
      meal_count: totals.meal_count,
      exercise_min: exerciseMin,
      exercise_cal: exerciseCal,
      avg_goal_score: avgScore,
      calorie_target: user.daily_calories || 2000,
      streak_days: streak,
    });

    // Format and send summary
    const target = user.daily_calories || 2000;
    const adherence = target > 0 ? Math.round((totals.calories / target) * 100) : 0;
    const emoji = getGoalEmoji(user.goal || 'eat_healthier');

    let assessment = '';
    if (totals.meal_count === 0) {
      assessment = "Looks like you didn't log any meals today. No worries, tomorrow is a fresh start!";
    } else if (adherence >= 90 && adherence <= 110) {
      assessment = 'Great job staying on track today! \u{1F389}';
    } else if (adherence < 90) {
      assessment = "You're a bit under your target today. Make sure you're fueling enough!";
    } else {
      assessment = "You went a bit over today. Let's aim for balance tomorrow!";
    }

    const message = [
      `${emoji} *Daily Recap, ${user.first_name}!*`,
      '',
      `\u{1F37D}\u{FE0F} Meals: ${totals.meal_count} | Calories: ${totals.calories}/${target}`,
      `\u{1F4AA} P: ${totals.protein_g}g/${user.protein_g}g | C: ${totals.carbs_g}g/${user.carbs_g}g | F: ${totals.fat_g}g/${user.fat_g}g`,
      `\u{1F4A7} Water: ${water}ml`,
      exerciseMin > 0 ? `\u{1F3C3} Exercise: ${exerciseMin} min (${exerciseCal} kcal burned)` : '',
      '',
      assessment,
      streak > 1 ? `\n\u{1F525} ${streak}-day streak! Keep it going!` : '',
    ].filter(Boolean).join('\n');

    try {
      await provider.sendText(user.phone, message);
      await markSummarySent(user.id, today);
      processed++;
    } catch (err) {
      console.error(`Failed to send summary to ${user.id}:`, err);
    }
  }

  return NextResponse.json({ processed });
}
