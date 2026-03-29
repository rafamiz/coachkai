import { GoogleGenerativeAI } from '@google/generative-ai';
import { buildSystemPrompt } from './prompts';
import { parseAIResponse } from './parser';
import { UserContext } from '../types/user';
import { AIResponse } from '../types/ai-response';

let genAI: GoogleGenerativeAI | null = null;

function getClient(): GoogleGenerativeAI {
  if (!genAI) {
    const apiKey = process.env.GEMINI_API_KEY;
    if (!apiKey) throw new Error('GEMINI_API_KEY is not set');
    genAI = new GoogleGenerativeAI(apiKey);
  }
  return genAI;
}

export interface ChatMessage {
  role: 'user' | 'model';
  content: string;
}

export async function analyzeMessage(
  userMessage: string,
  userContext: UserContext,
  conversationHistory: ChatMessage[] = [],
  imageBase64?: string,
  imageMimeType?: string,
): Promise<AIResponse> {
  const client = getClient();
  const model = client.getGenerativeModel({
    model: 'gemini-2.0-flash',
    systemInstruction: buildSystemPrompt(userContext),
    generationConfig: {
      responseMimeType: 'application/json',
      temperature: 0.3,
      maxOutputTokens: 1024,
    },
  });

  const history = conversationHistory.map((msg) => ({
    role: msg.role,
    parts: [{ text: msg.content }],
  }));

  const chat = model.startChat({ history });

  const parts: Array<{ text: string } | { inlineData: { mimeType: string; data: string } }> = [];

  if (imageBase64 && imageMimeType) {
    parts.push({
      inlineData: { mimeType: imageMimeType, data: imageBase64 },
    });
    parts.push({ text: userMessage || 'Analyze this meal' });
  } else {
    parts.push({ text: userMessage });
  }

  const result = await chat.sendMessage(parts);
  const text = result.response.text();

  return parseAIResponse(text);
}
