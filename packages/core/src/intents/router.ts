import { AIResponse, LogMealResponse, LogWaterResponse, LogWeightResponse, LogExerciseResponse } from '../types/ai-response';
import { User, UserContext } from '../types/user';
import { analyzeMessage, ChatMessage } from '../ai/gemini';
import { formatWhatsAppReply } from '../whatsapp/formatter';
import { logMeal, getTodayTotals } from '../db/meals';
import { logWater, getTodayWater } from '../db/water';
import { logWeight } from '../db/weight';
import { logExercise } from '../db/exercise';
import { saveMessage, getRecentMessages } from '../db/conversations';
import { getWhatsAppProvider } from '../whatsapp/provider';

export interface ProcessResult {
  response: AIResponse;
  formattedReply: string;
}

export async function processWhatsAppMessage(
  user: User,
  text: string,
  imageBase64?: string,
  imageMimeType?: string,
  photoUrl?: string,
  photoStoragePath?: string,
): Promise<ProcessResult> {
  const timezone = user.timezone || 'America/New_York';

  // Build user context
  const todayTotals = await getTodayTotals(user.id, timezone);
  const todayWater = await getTodayWater(user.id, timezone);

  const now = new Date();
  const localTime = now.toLocaleString('en-US', { timeZone: timezone });

  const userContext: UserContext = {
    first_name: user.first_name || 'there',
    goal: user.goal || 'eat_healthier',
    daily_calories: user.daily_calories || 2000,
    protein_g: user.protein_g || 150,
    carbs_g: user.carbs_g || 200,
    fat_g: user.fat_g || 65,
    dietary_preference: user.dietary_preference || 'none',
    allergies: user.allergies || [],
    today_calories: todayTotals.calories,
    today_protein: todayTotals.protein_g,
    today_carbs: todayTotals.carbs_g,
    today_fat: todayTotals.fat_g,
    today_water_ml: todayWater,
    local_time: localTime,
    fasting_status: user.fasting_enabled && user.fasting_window
      ? `Eating window: ${user.fasting_window.eating_start} - ${user.fasting_window.eating_end}`
      : 'not tracking',
    timezone,
  };

  // Get conversation history
  const history = await getRecentMessages(user.id, 10);

  // Save user message
  await saveMessage(user.id, 'user', text || '[photo]');

  // Call AI
  const response = await analyzeMessage(text, userContext, history, imageBase64, imageMimeType);

  // Handle intent-specific side effects
  await handleIntentSideEffects(user, response, photoUrl, photoStoragePath, text);

  // Save assistant response
  await saveMessage(user.id, 'assistant', JSON.stringify(response), response.intent);

  // Format reply
  const newTotalCal = response.intent === 'log_meal'
    ? todayTotals.calories + (response as LogMealResponse).total_calories
    : todayTotals.calories;

  const formattedReply = formatWhatsAppReply(
    response,
    response.intent === 'log_meal' ? todayTotals.calories : undefined,
    user.daily_calories || undefined,
  );

  return { response, formattedReply };
}

async function handleIntentSideEffects(
  user: User,
  response: AIResponse,
  photoUrl?: string,
  photoStoragePath?: string,
  description?: string,
) {
  switch (response.intent) {
    case 'log_meal': {
      const meal = response as LogMealResponse;
      await logMeal({
        user_id: user.id,
        meal_type: meal.meal_type,
        description,
        foods: meal.foods,
        calories: meal.total_calories,
        protein_g: meal.total_protein_g,
        carbs_g: meal.total_carbs_g,
        fat_g: meal.total_fat_g,
        goal_score: meal.goal_score,
        ai_tip: meal.tip,
        ai_summary: meal.message,
        photo_url: photoUrl,
        photo_storage_path: photoStoragePath,
        source: 'whatsapp',
      });
      break;
    }
    case 'log_water': {
      const water = response as LogWaterResponse;
      await logWater(user.id, water.amount_ml);
      break;
    }
    case 'log_weight': {
      const weight = response as LogWeightResponse;
      await logWeight(user.id, weight.weight_kg);
      break;
    }
    case 'log_exercise': {
      const exercise = response as LogExerciseResponse;
      await logExercise({
        user_id: user.id,
        exercise_type: exercise.exercise_type,
        duration_min: exercise.duration_min,
        calories_burned: exercise.estimated_calories_burned,
      });
      break;
    }
  }
}

export async function sendWhatsAppReply(phone: string, message: string) {
  const provider = getWhatsAppProvider();
  await provider.sendText(phone, message);
}
