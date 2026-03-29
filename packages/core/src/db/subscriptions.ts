import { getServiceClient } from './client';

export interface Subscription {
  id: string;
  user_id: string;
  stripe_customer_id: string | null;
  stripe_sub_id: string | null;
  plan: 'free' | 'monthly' | 'yearly';
  status: 'trialing' | 'active' | 'past_due' | 'canceled' | 'expired';
  trial_ends_at: string | null;
  current_period_end: string | null;
}

export async function getSubscription(userId: string): Promise<Subscription | null> {
  const { data } = await getServiceClient()
    .from('subscriptions')
    .select('*')
    .eq('user_id', userId)
    .single();
  return data;
}

export async function isSubscriptionActive(userId: string): Promise<boolean> {
  const sub = await getSubscription(userId);
  if (!sub) return false;
  if (sub.status === 'active') return true;
  if (sub.status === 'trialing' && sub.trial_ends_at) {
    return new Date(sub.trial_ends_at) > new Date();
  }
  return false;
}

export async function createSubscription(params: {
  user_id: string;
  stripe_customer_id?: string;
  plan?: 'free' | 'monthly' | 'yearly';
  trial_ends_at?: string;
}) {
  const { data } = await getServiceClient()
    .from('subscriptions')
    .insert({
      user_id: params.user_id,
      stripe_customer_id: params.stripe_customer_id,
      plan: params.plan || 'free',
      status: 'trialing',
      trial_ends_at: params.trial_ends_at || new Date(Date.now() + 7 * 24 * 60 * 60 * 1000).toISOString(),
    })
    .select()
    .single();
  return data;
}

export async function updateSubscription(userId: string, updates: Partial<Subscription>) {
  const { data } = await getServiceClient()
    .from('subscriptions')
    .update({ ...updates, updated_at: new Date().toISOString() })
    .eq('user_id', userId)
    .select()
    .single();
  return data;
}
