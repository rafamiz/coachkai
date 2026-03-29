import { AIResponse, LogMealResponse, GetRecipeResponse, GetGroceryListResponse } from '../types/ai-response';

export function formatWhatsAppReply(
  response: AIResponse,
  todayTotalCal?: number,
  targetCal?: number,
): string {
  switch (response.intent) {
    case 'log_meal':
      return formatMealReply(response, todayTotalCal, targetCal);
    case 'get_recipe':
      return formatRecipeReply(response);
    case 'get_grocery_list':
      return formatGroceryReply(response);
    case 'log_water':
    case 'log_weight':
    case 'log_exercise':
    case 'ask_question':
    case 'get_progress':
    case 'start_fast':
    case 'end_fast':
    case 'greeting':
    case 'other':
      return response.message;
    default:
      return (response as { message: string }).message;
  }
}

function formatMealReply(
  meal: LogMealResponse,
  todayTotalCal?: number,
  targetCal?: number,
): string {
  const lines: string[] = [meal.message, ''];

  const macroLine = `${meal.total_calories} kcal | P: ${meal.total_protein_g}g | C: ${meal.total_carbs_g}g | F: ${meal.total_fat_g}g`;
  lines.push(macroLine);

  if (meal.tip) {
    lines.push('', `\u{1F4A1} ${meal.tip}`);
  }

  if (todayTotalCal !== undefined && targetCal) {
    const newTotal = todayTotalCal + meal.total_calories;
    const remaining = targetCal - newTotal;
    lines.push('', `Today: ${newTotal}/${targetCal} kcal${remaining > 0 ? ` (${remaining} remaining)` : ''}`);
  }

  return lines.join('\n');
}

function formatRecipeReply(recipe: GetRecipeResponse): string {
  const lines: string[] = [
    recipe.message,
    '',
    `*${recipe.recipe_name}* (${recipe.prep_time_min} min, ${recipe.servings} servings)`,
    '',
    '*Ingredients:*',
    ...recipe.ingredients.map((i) => `- ${i}`),
    '',
    '*Steps:*',
    ...recipe.steps.map((s, idx) => `${idx + 1}. ${s}`),
    '',
    `Per serving: ${recipe.per_serving.calories} kcal | P: ${recipe.per_serving.protein_g}g | C: ${recipe.per_serving.carbs_g}g | F: ${recipe.per_serving.fat_g}g`,
  ];
  return lines.join('\n');
}

function formatGroceryReply(grocery: GetGroceryListResponse): string {
  const lines: string[] = [grocery.message, ''];
  for (const cat of grocery.items) {
    lines.push(`*${cat.category}:*`);
    for (const item of cat.items) {
      lines.push(`- ${item}`);
    }
    lines.push('');
  }
  return lines.join('\n').trim();
}
