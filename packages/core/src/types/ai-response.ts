import { FoodItem, MealType } from './meal';

export type Intent =
  | 'log_meal'
  | 'log_water'
  | 'log_weight'
  | 'log_exercise'
  | 'ask_question'
  | 'get_recipe'
  | 'get_grocery_list'
  | 'get_progress'
  | 'start_fast'
  | 'end_fast'
  | 'greeting'
  | 'other';

export interface LogMealResponse {
  intent: 'log_meal';
  meal_type: MealType;
  foods: FoodItem[];
  total_calories: number;
  total_protein_g: number;
  total_carbs_g: number;
  total_fat_g: number;
  goal_score: number;
  tip: string;
  message: string;
}

export interface LogWaterResponse {
  intent: 'log_water';
  amount_ml: number;
  message: string;
}

export interface LogWeightResponse {
  intent: 'log_weight';
  weight_kg: number;
  message: string;
}

export interface LogExerciseResponse {
  intent: 'log_exercise';
  exercise_type: string;
  duration_min: number;
  estimated_calories_burned: number;
  message: string;
}

export interface AskQuestionResponse {
  intent: 'ask_question';
  message: string;
}

export interface GetRecipeResponse {
  intent: 'get_recipe';
  recipe_name: string;
  servings: number;
  prep_time_min: number;
  ingredients: string[];
  steps: string[];
  per_serving: {
    calories: number;
    protein_g: number;
    carbs_g: number;
    fat_g: number;
  };
  message: string;
}

export interface GetGroceryListResponse {
  intent: 'get_grocery_list';
  items: { category: string; items: string[] }[];
  message: string;
}

export interface GetProgressResponse {
  intent: 'get_progress';
  message: string;
}

export interface FastingResponse {
  intent: 'start_fast' | 'end_fast';
  message: string;
}

export interface GreetingResponse {
  intent: 'greeting';
  message: string;
}

export interface OtherResponse {
  intent: 'other';
  message: string;
}

export type AIResponse =
  | LogMealResponse
  | LogWaterResponse
  | LogWeightResponse
  | LogExerciseResponse
  | AskQuestionResponse
  | GetRecipeResponse
  | GetGroceryListResponse
  | GetProgressResponse
  | FastingResponse
  | GreetingResponse
  | OtherResponse;
