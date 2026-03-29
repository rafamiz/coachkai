import Stripe from 'stripe';

let _stripe: Stripe | null = null;

export function getStripe(): Stripe {
  if (!_stripe) {
    _stripe = new Stripe(process.env.STRIPE_SECRET_KEY || '', {
      apiVersion: '2025-02-24.acacia',
    });
  }
  return _stripe;
}

export const PLANS = {
  monthly: {
    name: 'Monthly',
    price: 999, // $9.99
    priceId: process.env.STRIPE_MONTHLY_PRICE_ID || '',
  },
  yearly: {
    name: 'Yearly',
    price: 7999, // $79.99
    priceId: process.env.STRIPE_YEARLY_PRICE_ID || '',
  },
} as const;
