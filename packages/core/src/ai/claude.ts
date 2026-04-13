import Anthropic from '@anthropic-ai/sdk';
import { buildSystemPrompt } from './prompts';
import { parseAIResponse } from './parser';
import { UserContext } from '../types/user';
import { AIResponse } from '../types/ai-response';

let client: Anthropic | null = null;

function getClient(): Anthropic {
  if (!client) {
    const apiKey = process.env.ANTHROPIC_API_KEY;
    if (!apiKey) throw new Error('ANTHROPIC_API_KEY is not set');
    client = new Anthropic({ apiKey });
  }
  return client;
}

export interface ChatMessage {
  role: 'user' | 'assistant';
  content: string;
}

export async function analyzeMessage(
  userMessage: string,
  userContext: UserContext,
  conversationHistory: ChatMessage[] = [],
  imageBase64?: string,
  imageMimeType?: string,
): Promise<AIResponse> {
  const anthropic = getClient();

  // Build messages array from history
  const messages: Anthropic.MessageParam[] = conversationHistory.map((msg) => ({
    role: msg.role,
    content: msg.content,
  }));

  // Build current user message content
  const userContent: Anthropic.ContentBlockParam[] = [];

  if (imageBase64 && imageMimeType) {
    userContent.push({
      type: 'image',
      source: {
        type: 'base64',
        media_type: imageMimeType as 'image/jpeg' | 'image/png' | 'image/gif' | 'image/webp',
        data: imageBase64,
      },
    });
    userContent.push({
      type: 'text',
      text: userMessage || 'Analizá esta comida',
    });
  } else {
    userContent.push({
      type: 'text',
      text: userMessage,
    });
  }

  messages.push({ role: 'user', content: userContent });

  // Use Sonnet for images (vision), Haiku for text-only (10x cheaper)
  const model = imageBase64
    ? 'claude-sonnet-4-20250514'
    : 'claude-haiku-4-5-20241022';

  const response = await anthropic.messages.create({
    model,
    max_tokens: 1024,
    temperature: 0.3,
    system: buildSystemPrompt(userContext),
    messages,
  });

  const text = response.content[0].type === 'text' ? response.content[0].text : '';
  return parseAIResponse(text);
}
