import { Goal } from '../types/user';

export interface MacroSplit {
  protein_g: number;
  carbs_g: number;
  fat_g: number;
}

const MACRO_RATIOS: Record<Goal, { protein: number; carbs: number; fat: number }> = {
  lose_weight: { protein: 0.40, carbs: 0.30, fat: 0.30 },
  gain_muscle: { protein: 0.35, carbs: 0.40, fat: 0.25 },
  maintain: { protein: 0.30, carbs: 0.40, fat: 0.30 },
  eat_healthier: { protein: 0.30, carbs: 0.40, fat: 0.30 },
};

export function calculateMacros(dailyCalories: number, goal: Goal): MacroSplit {
  const ratios = MACRO_RATIOS[goal];
  return {
    protein_g: Math.round((dailyCalories * ratios.protein) / 4),
    carbs_g: Math.round((dailyCalories * ratios.carbs) / 4),
    fat_g: Math.round((dailyCalories * ratios.fat) / 9),
  };
}
