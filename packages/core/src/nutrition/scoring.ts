import { Goal } from '../types/user';

export function calculateAdherence(actual: number, target: number): number {
  if (target <= 0) return 100;
  return Math.round((actual / target) * 100 * 10) / 10;
}

export function calculateStreak(dates: string[]): number {
  if (!dates.length) return 0;

  const sorted = [...dates].sort((a, b) => b.localeCompare(a));
  let streak = 1;
  const today = new Date().toISOString().split('T')[0];

  if (sorted[0] !== today) return 0;

  for (let i = 1; i < sorted.length; i++) {
    const prev = new Date(sorted[i - 1]);
    const curr = new Date(sorted[i]);
    const diffDays = (prev.getTime() - curr.getTime()) / (1000 * 60 * 60 * 24);
    if (diffDays === 1) {
      streak++;
    } else {
      break;
    }
  }

  return streak;
}

export function getGoalEmoji(goal: Goal): string {
  const emojis: Record<Goal, string> = {
    lose_weight: '\u{1F3AF}',
    gain_muscle: '\u{1F4AA}',
    maintain: '\u{2696}\u{FE0F}',
    eat_healthier: '\u{1F96C}',
  };
  return emojis[goal] || '\u{2B50}';
}
