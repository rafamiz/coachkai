import { AIResponse, Intent } from '../types/ai-response';

const VALID_INTENTS: Intent[] = [
  'log_meal', 'log_water', 'log_weight', 'log_exercise',
  'ask_question', 'get_recipe', 'get_grocery_list', 'get_progress',
  'start_fast', 'end_fast', 'greeting', 'other',
];

export function parseAIResponse(raw: string): AIResponse {
  let text = raw.trim();

  // Strip markdown fences if present (shouldn't happen with Gemini JSON mode)
  if (text.startsWith('```')) {
    text = text.replace(/^```(?:json)?\n?/, '').replace(/\n?```$/, '');
  }

  const parsed = JSON.parse(text);

  if (!parsed.intent || !VALID_INTENTS.includes(parsed.intent)) {
    return {
      intent: 'other',
      message: parsed.message || "I didn't quite catch that. Could you try again?",
    };
  }

  // Ensure message field exists
  if (!parsed.message) {
    parsed.message = 'Got it!';
  }

  return parsed as AIResponse;
}
