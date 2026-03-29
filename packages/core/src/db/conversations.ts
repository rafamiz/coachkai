import { getServiceClient } from './client';
import { ChatMessage } from '../ai/gemini';

export async function saveMessage(
  userId: string,
  role: 'user' | 'assistant',
  content: string,
  intent?: string,
  metadata?: Record<string, unknown>,
) {
  await getServiceClient()
    .from('conversations')
    .insert({
      user_id: userId,
      role,
      content,
      intent,
      metadata: metadata || {},
      created_at: new Date().toISOString(),
    });
}

export async function getRecentMessages(userId: string, limit = 10): Promise<ChatMessage[]> {
  const { data } = await getServiceClient()
    .from('conversations')
    .select('role, content')
    .eq('user_id', userId)
    .order('created_at', { ascending: false })
    .limit(limit);

  if (!data) return [];

  return data.reverse().map((msg) => ({
    role: msg.role === 'user' ? 'user' as const : 'model' as const,
    content: msg.content,
  }));
}
