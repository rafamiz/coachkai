import { NextRequest, NextResponse } from 'next/server';
import { getStripe, PLANS } from '@/lib/stripe';

export async function POST(req: NextRequest) {
  let body: { user_id: string; plan: 'monthly' | 'yearly' };
  try {
    body = await req.json();
  } catch {
    return NextResponse.json({ error: 'Invalid JSON' }, { status: 400 });
  }

  const { user_id, plan } = body;
  if (!user_id || !plan || !(plan in PLANS)) {
    return NextResponse.json({ error: 'Missing user_id or invalid plan' }, { status: 400 });
  }

  const priceId = PLANS[plan].priceId;
  if (!priceId) {
    return NextResponse.json({ error: 'Stripe price not configured' }, { status: 500 });
  }

  const appUrl = process.env.NEXT_PUBLIC_APP_URL || process.env.APP_URL || 'https://nutricoach.vercel.app';

  const session = await getStripe().checkout.sessions.create({
    mode: 'subscription',
    line_items: [{ price: priceId, quantity: 1 }],
    metadata: { user_id },
    subscription_data: {
      trial_period_days: 7,
      metadata: { user_id },
    },
    success_url: `${appUrl}/onboarding/checkout-success?session_id={CHECKOUT_SESSION_ID}`,
    cancel_url: `${appUrl}/onboarding`,
  });

  return NextResponse.json({ url: session.url });
}
