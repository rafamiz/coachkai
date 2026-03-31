import { NextRequest, NextResponse } from 'next/server';
import { createClient } from '@supabase/supabase-js';
import twilio from 'twilio';

const supabase = createClient(
  process.env.NEXT_PUBLIC_SUPABASE_URL!,
  process.env.SUPABASE_SERVICE_ROLE_KEY!
);

const TWILIO_AUTH_TOKEN = process.env.TWILIO_AUTH_TOKEN!;
const APP_URL = process.env.NEXT_PUBLIC_APP_URL || 'https://nutricoach-one.vercel.app';

function twiml(message: string): NextResponse {
  const xml = `<?xml version="1.0" encoding="UTF-8"?><Response><Message>${message}</Message></Response>`;
  return new NextResponse(xml, {
    status: 200,
    headers: { 'Content-Type': 'text/xml' },
  });
}

export async function POST(req: NextRequest) {
  try {
    // Parse form-encoded body from Twilio
    const text = await req.text();
    const params = new URLSearchParams(text);
    const body: Record<string, string> = {};
    params.forEach((v, k) => { body[k] = v; });

    // Validate Twilio signature
    const signature = req.headers.get('x-twilio-signature') || '';
    const url = req.url;
    const isValid = twilio.validateRequest(TWILIO_AUTH_TOKEN, signature, url, body);

    if (!isValid && process.env.NODE_ENV === 'production') {
      return new NextResponse('Forbidden', { status: 403 });
    }

    // Extract phone number (strip "whatsapp:" prefix)
    const rawFrom = body.From || '';
    const phone = rawFrom.replace('whatsapp:', '').trim();
    const messageBody = body.Body || '';

    if (!phone) {
      return twiml('No se pudo identificar tu número.');
    }

    // Look up user by phone
    const { data: user } = await supabase
      .from('users')
      .select('id, onboarding_completed')
      .eq('phone', phone)
      .single();

    if (!user || !user.onboarding_completed) {
      // No user or onboarding not completed → send onboarding link
      const onboardingUrl = `${APP_URL}/onboarding?phone=${encodeURIComponent(phone)}`;
      return twiml(
        `👋 ¡Hola! Soy tu coach nutricional con IA.\n\n` +
        `Para empezar, necesito conocerte un poco. Completá tu perfil acá (2 minutos):\n\n` +
        `${onboardingUrl}\n\n` +
        `Después de eso, mandame una foto de tu comida y te digo los macros al toque 💪`
      );
    }

    // Check active subscription
    const { data: sub } = await supabase
      .from('subscriptions')
      .select('status, plan')
      .eq('user_id', user.id)
      .in('status', ['active', 'trialing'])
      .single();

    if (!sub && true) {
      // Has account but check if free plan is allowed
      // For now, allow free users with limited responses
    }

    // Active user → placeholder AI response
    return twiml(
      `¡Recibí tu mensaje! 🤖\n\n` +
      `Dijiste: "${messageBody.substring(0, 100)}"\n\n` +
      `La función de coach por IA viene pronto. Mientras tanto, podés ver tu progreso en:\n` +
      `${APP_URL}/dashboard`
    );
  } catch (error) {
    console.error('WhatsApp webhook error:', error);
    return twiml('Hubo un error procesando tu mensaje. Intentá de nuevo en unos minutos.');
  }
}
