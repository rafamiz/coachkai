import { NextRequest, NextResponse } from 'next/server';
import { getStripe } from '@/lib/stripe';
import { updateSubscription, getServiceClient } from '@nutricoach/core';
import Stripe from 'stripe';

export async function POST(req: NextRequest) {
  const body = await req.text();
  const sig = req.headers.get('stripe-signature')!;

  let event: Stripe.Event;
  try {
    event = getStripe().webhooks.constructEvent(body, sig, process.env.STRIPE_WEBHOOK_SECRET!);
  } catch {
    return NextResponse.json({ error: 'Invalid signature' }, { status: 400 });
  }

  switch (event.type) {
    case 'checkout.session.completed': {
      const session = event.data.object as Stripe.Checkout.Session;
      const userId = session.metadata?.user_id;
      if (userId) {
        const sub = await getStripe().subscriptions.retrieve(session.subscription as string);
        await updateSubscription(userId, {
          stripe_customer_id: session.customer as string,
          stripe_sub_id: sub.id,
          status: 'active',
          plan: sub.items.data[0]?.price.recurring?.interval === 'year' ? 'yearly' : 'monthly',
          current_period_end: new Date(sub.current_period_end * 1000).toISOString(),
        });
      }
      break;
    }

    case 'invoice.paid': {
      const invoice = event.data.object as Stripe.Invoice;
      if (invoice.subscription) {
        const sub = await getStripe().subscriptions.retrieve(invoice.subscription as string);
        const supabase = getServiceClient();
        const { data: subRecord } = await supabase
          .from('subscriptions')
          .select('user_id')
          .eq('stripe_sub_id', sub.id)
          .single();
        if (subRecord) {
          await updateSubscription(subRecord.user_id, {
            status: 'active',
            current_period_end: new Date(sub.current_period_end * 1000).toISOString(),
          });
        }
      }
      break;
    }

    case 'customer.subscription.deleted': {
      const sub = event.data.object as Stripe.Subscription;
      const supabase = getServiceClient();
      const { data: subRecord } = await supabase
        .from('subscriptions')
        .select('user_id')
        .eq('stripe_sub_id', sub.id)
        .single();
      if (subRecord) {
        await updateSubscription(subRecord.user_id, { status: 'canceled' });
      }
      break;
    }
  }

  return NextResponse.json({ received: true });
}
